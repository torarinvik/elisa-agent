"""Calibrated expert rungs and held-out temperature fitting."""

from __future__ import annotations

from collections.abc import Sequence
from dataclasses import dataclass, field
import math
from typing import Any, Literal, overload
from weakref import ReferenceType, ref
import numpy as np
import torch
from torch import nn
from nca.abi import Module
from nca import ladder as _ladder


@dataclass
class Rung:
    """An expert read through temperatures fitted on held-out labeled inputs:
    one for its full output and one for each restricted decision it serves."""

    module: Module
    temperatures: dict[_ladder.DecisionKey, float] = field(default_factory=dict)
    held_out: tuple[torch.Tensor, torch.Tensor] | None = None
    _missing_temperatures: set[_ladder.DecisionKey] = field(default_factory=set, init=False, repr=False, compare=False)
    _missing_labels: ReferenceType[torch.Tensor] | None = field(default=None, init=False, repr=False, compare=False)

    def __getstate__(self) -> dict[str, Any]:
        state = self.__dict__.copy()
        # The cache is derived and weak references are not serializable.
        state["_missing_temperatures"] = set()
        state["_missing_labels"] = None
        return state

    def __setstate__(self, state: dict[str, Any]) -> None:
        self.__dict__.update(state)
        # Older serialized rungs have neither cache field.
        self._missing_temperatures = set()
        self._missing_labels = None

    @property
    def cost(self) -> float:
        return self.module.manifest.cost

    def observe(self, value: Any) -> torch.Tensor:
        """Binary64 log-probabilities with a smallest-positive numerical floor."""
        return self._observe(value, ranked=False)

    def observe_ranked(self, value: Any) -> _ladder.RankedObservation:
        """Observe once while retaining exact binary64 weight ordering."""
        return self._observe(value, ranked=True)

    @overload
    def _observe(self, value: Any, *, ranked: Literal[False]) -> torch.Tensor: ...

    @overload
    def _observe(self, value: Any, *, ranked: Literal[True]) -> _ladder.RankedObservation: ...

    def _observe(self, value: Any, *, ranked: bool) -> torch.Tensor | _ladder.RankedObservation:
        output = self.module.invoke(value)
        if isinstance(output, np.ma.MaskedArray) and np.ma.is_masked(output):
            raise ValueError("expert output must not contain masked weights")
        if isinstance(output, torch.Tensor) and output.is_complex():
            raise ValueError("expert output must contain real-valued weights")
        native = getattr(_ladder._NATIVE, "observation_logs", None)
        native_into = getattr(_ladder._NATIVE, "observation_logs_into", None)
        array = None
        if isinstance(output, (tuple, list, np.ndarray)):
            try:
                raw = np.asarray(output)
            except (TypeError, ValueError, RuntimeError):
                raw = None
            if raw is not None:
                if (raw.dtype.kind not in "biufO" or
                        (raw.dtype.kind == "O" and any(
                            isinstance(x, (str, bytes, complex, np.complexfloating)) or
                            (isinstance(x, torch.Tensor) and x.is_complex()) for x in raw.flat))):
                    raise ValueError("expert output must contain real-valued weights")
                try:
                    array = np.asarray(raw, dtype=np.float64)
                except (TypeError, ValueError, RuntimeError):
                    pass  # Some valid tensor-containing sequences require PyTorch conversion.
        probabilities = None
        if array is None:
            if isinstance(output, torch.Tensor) and output.device.type == "mps":
                # MPS does not support binary64; retain its represented values on CPU.
                probabilities = output.detach().cpu().to(dtype=torch.float64)
            else:
                probabilities = torch.tensor(output, dtype=torch.float64)
            if probabilities.ndim != 1:
                raise ValueError("expert output must be a one-dimensional weight vector")
            if probabilities.device.type == "cpu":
                array = probabilities.numpy()
        if array is not None:
            if array.ndim != 1:
                raise ValueError("expert output must be a one-dimensional weight vector")
            array = np.ascontiguousarray(array)
            if native_into is not None:
                logs = np.empty_like(array)
                if native_into(array, logs) != 0:
                    raise ValueError("expert output must contain finite nonnegative weights with positive mass")
                logits = torch.from_numpy(logs)
                return _ladder.RankedObservation(logits, tuple(array.tolist())) if ranked else logits
            if native is not None:
                logs = native(array)
                if not logs:
                    raise ValueError("expert output must contain finite nonnegative weights with positive mass")
                logits = torch.tensor(logs, dtype=torch.float64)
                return _ladder.RankedObservation(logits, tuple(array.tolist())) if ranked else logits
            logs = []
            positive = False
            for weight in array:
                weight = float(weight)
                if not math.isfinite(weight) or weight < 0:
                    raise ValueError("expert output must contain finite nonnegative weights with positive mass")
                positive = positive or weight > 0
                logs.append(math.log(weight if weight > 0 else math.nextafter(0.0, 1.0)))
            if not positive:
                raise ValueError("expert output must contain finite nonnegative weights with positive mass")
            logits = torch.tensor(logs, dtype=torch.float64)
            return _ladder.RankedObservation(logits, tuple(array.tolist())) if ranked else logits
        assert probabilities is not None
        valid = (bool(torch.isfinite(probabilities).all()) and
                 not bool((probabilities < 0).any()) and
                 bool((probabilities > 0).any()))
        if not valid:
            raise ValueError("expert output must contain finite nonnegative weights with positive mass")
        logits = probabilities.clamp_min(math.nextafter(0.0, 1.0)).log()
        return _ladder.RankedObservation(logits, tuple(probabilities.tolist())) if ranked else logits

    def calibrate(self, values: Sequence[Any], labels: torch.Tensor) -> None:
        """Replace held-out observations and temperature only after fitting succeeds."""
        if (not isinstance(labels, torch.Tensor) or labels.ndim != 1 or labels.is_quantized
                or len(values) == 0 or labels.numel() != len(values)):
            raise ValueError("calibration needs nonempty values and one integer label per value")
        try:
            torch.iinfo(labels.dtype)
        except TypeError as exc:
            raise ValueError("calibration needs nonempty values and one integer label per value") from exc
        value_snapshot = tuple(values)
        label_snapshot = labels.detach().clone()
        observations = torch.stack([self.observe(v) for v in value_snapshot])
        targets = label_snapshot.to(device=observations.device, dtype=torch.long)
        if bool(((targets < 0) | (targets >= observations.shape[1])).any()):
            raise ValueError("calibration labels must be valid class indices")
        temperature = self._fit(observations, targets)
        self.held_out = (observations, targets)
        self.temperatures = {None: temperature}
        self._missing_temperatures.clear()
        self._missing_labels = None

    def temperature(self, classes: _ladder.Decision = None) -> float:
        """Temperature of the decision over ``classes``, fitted on first use on
        the held-out inputs whose label is among them, by the likelihood of
        the label's entry."""
        key = _ladder.decision_key(classes)
        if key not in self.temperatures:
            if self.held_out is None or key is None:
                return 1.0
            labels_snapshot = self.held_out[1]
            if self._missing_labels is None or self._missing_labels() is not labels_snapshot:
                self._missing_temperatures.clear()
                self._missing_labels = ref(labels_snapshot)
            if key in self._missing_temperatures:
                if len(key) == 1:
                    return 1.0
                raise _ladder.MissingCalibrationError("cannot fit decision temperature without matching held-out labels")
            log, labels = self.held_out
            union, positions = _ladder._layout(key)
            subset = getattr(_ladder._NATIVE, "calibration_subset", None)
            packed = None
            if (subset is not None and log.device.type == "cpu" and log.ndim == 2
                    and labels.device.type == "cpu" and labels.dtype == torch.int64
                    and labels.ndim == 1):
                try:
                    packed = subset(labels.contiguous().numpy(), _ladder._native_indices(key),
                                    _ladder._group_ids(key), log.shape[1], len(positions))
                except OverflowError:
                    pass  # The reference path handles out-of-range class indices.
            if packed is not None and len(packed) % 2 == 0:
                count = len(packed) // 2
                if count:
                    mapped = np.asarray(packed, dtype=np.int64)
                    rows = torch.from_numpy(mapped[:count])
                    targets = torch.from_numpy(mapped[count:])
            else:
                entry = {union[i]: k for k, part in enumerate(positions) for i in part}
                inside = torch.isin(labels, torch.tensor(union, device=labels.device))
                count = int(inside.sum())
                if count:
                    rows = inside.nonzero(as_tuple=True)[0]
                    targets = torch.tensor([entry[int(y)] for y in labels[inside]], dtype=torch.long,
                                           device=labels.device)
            if not count:
                if len(self._missing_temperatures) >= 128:
                    self._missing_temperatures.pop()
                self._missing_temperatures.add(key)
                if len(positions) == 1:
                    return 1.0  # A single entry has no decision ambiguity.
                raise _ladder.MissingCalibrationError("cannot fit decision temperature without matching held-out labels")
            columns = torch.as_tensor(union, dtype=torch.long, device=log.device)
            selected_log = log[rows[:, None], columns]
            self.temperatures[key] = self._fit(selected_log, targets, positions)
        return self.temperatures[key]

    def reading(self, log: torch.Tensor | _ladder.RankedObservation) -> torch.Tensor:
        """Numerical probabilities; ranked ordering remains on the observation."""
        temperature = self.temperature()
        if not math.isfinite(temperature) or temperature <= 0:
            name = "ranked reading" if isinstance(log, _ladder.RankedObservation) else "reading"
            raise ValueError(f"{name} requires a positive finite temperature")
        if isinstance(log, _ladder.RankedObservation):
            log = log.logits
        result = torch.softmax(_ladder._temperature_scores(log, temperature), dim=-1)
        return result.to(log.dtype if log.is_floating_point() else torch.get_default_dtype())

    def risk(self, log: torch.Tensor | _ladder.RankedObservation, classes: _ladder.Decision = None, *,
             reading: torch.Tensor | None = None) -> float:
        """Calibrated error probability for one observation over ``classes``.

        A ranked observation chooses the winning class by its original weights;
        a tensor chooses from its numerical reading. Consumers must use the
        same choice: the numerical reading can contain ties. The optional
        ``reading`` reuses the numerical reading of this observation; callers
        must supply the reading for this observation and calibration.
        """
        key = _ladder.decision_key(classes)
        temperature = self.temperature(key)
        ranked = log if isinstance(log, _ladder.RankedObservation) else None
        if not math.isfinite(temperature) or temperature <= 0:
            name = "ranked risk" if ranked is not None else "risk"
            raise ValueError(f"{name} requires a positive finite temperature")
        if ranked is not None:
            log = ranked.logits
        elif reading is not None and (not isinstance(reading, torch.Tensor)
                                      or reading.shape != log.shape):
            raise ValueError("reused reading must match the observation's shape")
        elif reading is not None and (reading.is_complex() or reading.is_quantized):
            raise ValueError("reused reading must be finite and nonnegative")
        if log.ndim != 1:
            raise ValueError("decision risk requires a one-dimensional logit vector")
        union = list(range(len(log))) if key is None else _ladder._layout(key)[0]
        probabilities = (self.reading(log) if reading is None else reading) if ranked is None else None
        integral_reading = ranked is None and not probabilities.is_floating_point()
        if integral_reading and (probabilities.is_complex() or probabilities.is_quantized):
            raise ValueError("reused reading must be finite and nonnegative")
        native_reading = getattr(_ladder._NATIVE, "calibrated_risk_for_reading_checked", None)
        if native_reading is None and reading is None and ranked is None:
            native_reading = getattr(_ladder._NATIVE, "calibrated_risk_for_reading", None)
        if (native_reading is not None and not integral_reading
                and log.device.type == "cpu" and not log.requires_grad
                and (ranked is not None or (probabilities.device.type == "cpu"
                                            and not probabilities.requires_grad))):
            native_key = key if key is not None else tuple(range(len(log)))
            _, positions = _ladder._layout(native_key)
            groups = _ladder._group_ids(native_key)
            ordering = (np.asarray(ranked.weights, dtype=np.float64) if ranked is not None else
                        probabilities.double().numpy())
            logits = (log.double().numpy() if log.is_floating_point() else
                      _ladder._selected_logits(log, None if classes is None else union).double().numpy())
            if classes is None:
                logits = np.ascontiguousarray(logits)
                ordering = np.ascontiguousarray(ordering)
            else:
                indices = _ladder._native_indices(key)
                if log.is_floating_point():
                    logits = logits[indices]
                ordering = ordering[indices]
            return _ladder._checked_calibrated_risk(float(native_reading(
                logits, ordering, groups, len(positions), temperature)))
        if ranked is not None:
            selected = union.index(ranked.top(union))
        else:
            if reading is not None or integral_reading:
                selected_reading = probabilities[union]
                checked = selected_reading.double() if integral_reading else selected_reading
                if not bool(torch.isfinite(checked).all()) or bool((checked < 0).any()):
                    raise ValueError("reused reading must be finite and nonnegative")
            if integral_reading:
                selected = (int(selected_reading.detach().cpu().numpy().argmax())
                            if selected_reading.dtype == torch.uint64 else
                            int(selected_reading.to(torch.int64).argmax()))
            else:
                selected = int(probabilities[union].argmax())
        native = getattr(_ladder._NATIVE, "calibrated_risk_at", None)
        if native is not None and log.device.type == "cpu" and not log.requires_grad:
            native_key = key if key is not None else tuple(range(len(log)))
            union, positions = _ladder._layout(native_key)
            groups = _ladder._group_ids(native_key)
            return _ladder._checked_calibrated_risk(float(native(
                _ladder._selected_logits(log, None if key is None else union).double().numpy(),
                groups, len(positions), temperature, selected)))
        if classes is None:
            values, positions = _ladder._selected_logits(log, None), None
        else:
            union, positions = _ladder._layout(key)
            values = _ladder._selected_logits(log, union)
        result = _ladder._checked_calibrated_risk(_ladder.risk(
            torch.softmax(_ladder._temperature_scores(values, temperature), dim=-1), positions, _top=selected))
        if result != 0.0:
            return result
        # A float32 softmax can erase probabilities that fit in binary64.
        scores = _ladder._binary64_logits(values)
        scores = _ladder._temperature_scores(scores, temperature)
        top = int(scores.argmax()) if selected is None else selected
        chosen = (next(part for part in positions if top in part)
                  if positions is not None else [top])
        outside = [i for i in range(len(scores)) if i not in chosen]
        if not outside:
            return 0.0
        log_outside = torch.logsumexp(scores[outside], dim=0)
        if not bool(torch.isfinite(log_outside)):
            # Temperature scaling can itself overflow a finite negative logit.
            return (math.nextafter(0.0, 1.0)
                    if bool(torch.isneginf(log_outside)) and
                    bool(torch.isfinite(values[outside]).any()) else 0.0)
        recovered = math.exp(float(log_outside - torch.logsumexp(scores, dim=0)))
        return math.nextafter(0.0, 1.0) if recovered == 0.0 else recovered

    def risk_batch(self, log: torch.Tensor, classes: _ladder.Decision = None, *,
                   reading: torch.Tensor | None = None,
                   ordering: torch.Tensor | None = None) -> torch.Tensor:
        """Calibrated decision risks for logits with leading batch dimensions.

        Selection follows the numerical reading unless original ordering weights
        are supplied. A supplied reading must belong to the same observation and
        calibration; ordering weights must belong to the same observation and
        be floating-point values used by the consumer for its selection. Supply
        at most one of them.
        MPS inputs return binary64 risks on CPU.
        """
        if not isinstance(log, torch.Tensor) or log.ndim < 2 or log.shape[-1] == 0:
            raise ValueError("batched risk requires logits with a nonempty final dimension")
        if reading is not None and ordering is not None:
            raise ValueError("supply either a reused reading or ordering weights")
        supplied = ordering if ordering is not None else reading
        if supplied is not None and (not isinstance(supplied, torch.Tensor) or supplied.shape != log.shape):
            raise ValueError("reused reading or ordering must match the observation's shape")
        if supplied is not None and (supplied.is_complex() or supplied.is_quantized):
            raise ValueError("reused reading or ordering must be finite and nonnegative")
        if ordering is not None and not ordering.is_floating_point():
            raise ValueError("ordering weights must use a floating-point dtype")
        key = _ladder.decision_key(classes)
        temperature = self.temperature(key)
        if not math.isfinite(temperature) or temperature <= 0:
            raise ValueError("batched risk requires a positive finite temperature")
        selection_weights = self.reading(log) if supplied is None else supplied
        if supplied is None and (selection_weights.is_complex() or selection_weights.is_quantized):
            raise ValueError("reused reading or ordering must be finite and nonnegative")
        if key is None:
            union = None
            group_count = log.shape[-1]
            group_ids = np.empty(0, dtype=np.int64)
        else:
            union, positions = _ladder._layout(key)
            group_count = len(positions)
            group_ids = _ladder._group_ids(key)
        if key is None:
            order = selection_weights
        elif selection_weights.dtype == torch.uint64:
            order_values = selection_weights.detach().cpu().numpy()[..., union]
            order = torch.from_numpy(np.ascontiguousarray(order_values))
        else:
            order = selection_weights[..., union]
        if log.device.type == "mps":
            raw = log if key is None else log[..., union]
            selected = _ladder._selected_logits(raw.cpu(), None)
        else:
            selected = _ladder._selected_logits(log, None if key is None else union)
        if order.device.type == "mps" and selected.device.type == "cpu":
            order = order.cpu()
        shape = log.shape[:-1]
        integer_native = getattr(_ladder._NATIVE, "calibrated_integer_risk_rows_into", None)
        if (order.dtype in (torch.int64, torch.uint64) and integer_native is not None
                and selected.device.type == "cpu" and not selected.requires_grad
                and selected.numel() <= 65536):
            values = selected.double().contiguous().numpy()
            unsigned = order.dtype == torch.uint64
            orders = order.detach().cpu().contiguous().numpy()
            if unsigned:
                orders = orders.view(np.int64)
            output = np.empty(math.prod(shape), dtype=np.float64)
            status = integer_native(values.reshape(-1), orders.reshape(-1), group_ids,
                                    output, selected.shape[-1], group_count, temperature, unsigned)
            if status != 0:
                raise ValueError("calibrated decision requires finite log weights with positive mass "
                                 "and finite nonnegative selection weights")
            return torch.from_numpy(output.reshape(shape))
        if order.dtype in (torch.int64, torch.uint64):
            # Preserve the first maximum before integer-to-binary64 rounding.
            if order.dtype == torch.uint64:
                indices = np.argmax(order.detach().cpu().numpy(), axis=-1)
                top = torch.from_numpy(np.asarray(indices, dtype=np.int64)).to(selected.device)
            else:
                integer_order = order.to(device=selected.device, dtype=torch.int64)
                if bool((integer_order < 0).any()):
                    raise ValueError("reused reading or ordering must be finite and nonnegative")
                top = integer_order.argmax(dim=-1)
            order = torch.nn.functional.one_hot(top, num_classes=selected.shape[-1]).double()
        else:
            order = order.to(device=selected.device, dtype=torch.float64)
        native = getattr(_ladder._NATIVE, "calibrated_risk_rows_into", None)
        if (native is not None and selected.device.type == "cpu"
                and not selected.requires_grad and not order.requires_grad
                and selected.numel() <= 65536):
            values = selected.double().contiguous().numpy()
            orders = order.contiguous().numpy()
            output = np.empty(math.prod(shape), dtype=np.float64)
            status = native(values.reshape(-1), orders.reshape(-1), group_ids,
                            output, selected.shape[-1], group_count, temperature)
            if status != 0:
                raise ValueError("calibrated decision requires finite log weights with positive mass "
                                 "and finite nonnegative selection weights")
            return torch.from_numpy(output.reshape(shape))
        if not bool(torch.isfinite(order).all()) or bool((order < 0).any()):
            raise ValueError("reused reading or ordering must be finite and nonnegative")
        scores = _ladder._temperature_scores(_ladder._binary64_logits(selected), temperature)
        groups = (torch.arange(scores.shape[-1], device=scores.device) if key is None else
                  torch.as_tensor(group_ids.copy(), device=scores.device))
        chosen = groups[order.to(scores.device).argmax(dim=-1)]
        outside = groups != chosen.unsqueeze(-1)
        weights = scores.exp()
        total = weights.sum(dim=-1)
        result = torch.where(outside, weights, 0.0).sum(dim=-1) / total
        if bool((result == 0).any()):
            outside_scores = scores.masked_fill(~outside, -math.inf)
            finite_scores = torch.isfinite(outside_scores).any(dim=-1)
            safe_scores = torch.where(finite_scores.unsqueeze(-1), outside_scores, 0.0)
            recovered = (torch.logsumexp(safe_scores, dim=-1) - torch.logsumexp(scores, dim=-1)).exp()
            finite_alternative = (torch.isfinite(selected.to(scores.device)) & outside).any(dim=-1)
            recovered = torch.where(finite_scores, recovered, 0.0)
            recovered = torch.where((recovered == 0) & finite_alternative, math.nextafter(0.0, 1.0), recovered)
            result = torch.where(result == 0, recovered, result)
        return result

    def distribution(self, log: torch.Tensor | _ladder.RankedObservation, classes: _ladder.Decision = None) -> torch.Tensor:
        """Calibrated probabilities of the decision's entries: each entry's
        share of the classes it ranges over, under the decision's temperature.
        Leading batch dimensions are preserved.
        """
        temperature = self.temperature(classes)
        if not math.isfinite(temperature) or temperature <= 0:
            name = "ranked distribution" if isinstance(log, _ladder.RankedObservation) else "distribution"
            raise ValueError(f"{name} requires a positive finite temperature")
        if isinstance(log, _ladder.RankedObservation):
            log = log.logits
        if classes is None:
            return self.reading(log)
        if log.ndim == 0:
            raise ValueError("grouped distribution requires a one-dimensional logit vector")
        if log.ndim > 1:
            return _ladder._grouped_batch(log, _ladder.decision_key(classes), temperature, logarithmic=False)
        output_dtype = log.dtype if log.is_floating_point() else torch.get_default_dtype()
        union, positions = _ladder._layout(_ladder.decision_key(classes))
        values = _ladder._selected_logits(log, union)
        native = getattr(_ladder._NATIVE, "calibrated_groups", None)
        groups = _ladder._group_ids(_ladder.decision_key(classes))
        if native is not None and log.device.type == "cpu" and not log.requires_grad:
            grouped = native(values.double().numpy(), groups, len(positions), temperature)
            if not grouped or not all(math.isfinite(value) for value in grouped):
                raise ValueError("calibrated decision requires finite log weights with positive mass")
            return torch.tensor(grouped, dtype=output_dtype)
        reading = torch.softmax(_ladder._temperature_scores(values, temperature), dim=-1)
        reading = reading.to(output_dtype)
        return torch.stack([reading[part].sum() for part in positions])

    def log_distribution(self, log: torch.Tensor | _ladder.RankedObservation,
                         classes: _ladder.Decision = None) -> torch.Tensor:
        """Log probabilities retaining underflowed mass, with optional batch dimensions."""
        temperature = self.temperature(classes)
        if not math.isfinite(temperature) or temperature <= 0:
            name = "ranked distribution" if isinstance(log, _ladder.RankedObservation) else "distribution"
            raise ValueError(f"{name} requires a positive finite temperature")
        if isinstance(log, _ladder.RankedObservation):
            log = log.logits
        if classes is None:
            if log.device.type == "mps":
                # MPS lacks binary64, which this interface uses for log probabilities.
                log = log.cpu()
            return torch.log_softmax(_ladder._temperature_scores(_ladder._binary64_logits(_ladder._selected_logits(log, None)), temperature), dim=-1)
        if log.ndim == 0:
            raise ValueError("grouped log distribution requires a one-dimensional logit vector")
        if log.ndim > 1:
            return _ladder._grouped_batch(log, _ladder.decision_key(classes), temperature, logarithmic=True)
        key = _ladder.decision_key(classes)
        union, positions = _ladder._layout(key)
        if log.device.type == "mps":
            if log.numel() * log.element_size() >= 16_000_000 and len(union) * 4 < log.numel():
                selected = _ladder._selected_logits(log[union].cpu(), None)
            else:
                selected = _ladder._selected_logits(log.cpu(), union)
        else:
            selected = _ladder._selected_logits(log, union)
        native = getattr(_ladder._NATIVE, "calibrated_log_groups", None)
        if native is not None and selected.device.type == "cpu" and not selected.requires_grad:
            values = native(selected.double().numpy(), _ladder._group_ids(key), len(positions), temperature)
            if (values and all(not math.isnan(value) and value != math.inf for value in values)
                    and any(math.isfinite(value) for value in values)):
                return torch.tensor(values, dtype=torch.float64)
            raise ValueError("calibrated decision requires finite log weights with positive mass")
        scores = _ladder._temperature_scores(_ladder._binary64_logits(selected), temperature)
        normalizer = torch.logsumexp(scores, dim=-1)
        return torch.stack([torch.logsumexp(scores[part], dim=-1) - normalizer
                            for part in positions])

    @staticmethod
    def _fit(log: torch.Tensor, labels: torch.Tensor,
             entries: Sequence[Sequence[int]] | None = None) -> float:
        """Minimize label negative log-likelihood over a fixed temperature grid.

        Each label names an entry (a group of columns) when ``entries`` is given.
        An entry may be empty only when no label names it.
        """
        target_count = len(entries) if entries is not None else log.shape[-1]
        target_indices = labels.to(torch.int64)
        if bool(((target_indices < 0) | (target_indices >= target_count)).any()):
            raise ValueError("calibration labels must name target entries")
        if entries is not None:
            for index, entry in enumerate(entries):
                if len(entry) == 0 and bool((labels == index).any()):
                    raise ValueError("calibration target entry must contain at least one column")
        grouped = (entries is not None and
                   (len(entries) != log.shape[-1] or
                    any(len(entry) != 1 or entry[0] != index
                        for index, entry in enumerate(entries))))
        temperatures = np.geomspace(0.1, 8.0, 120)
        stable_native = getattr(_ladder._NATIVE, "calibration_loss_grid_stable", None)
        native = stable_native or getattr(_ladder._NATIVE, "calibration_loss_grid", None)
        if (native is not None and log.device.type == "cpu" and labels.device.type == "cpu"
                and log.dtype == torch.float64 and labels.dtype == torch.int64
                and log.ndim == 2 and labels.ndim == 1 and not log.requires_grad
                and log.numel() <= (16384 if grouped else 2048)):
            width = log.shape[1]
            groups = np.arange(width, dtype=np.int64)
            if grouped:
                columns = [column for entry in entries for column in entry]
                if (all(type(column) is int for column in columns)
                        and sorted(columns) == list(range(width))):
                    for index, entry in enumerate(entries):
                        groups[list(entry)] = index
                else:
                    native = None
            if native is not None:
                losses = native(log.contiguous().numpy().reshape(-1), labels.contiguous().numpy(),
                                groups, len(entries) if grouped else width, temperatures)
                usable = (len(losses) == len(temperatures) and
                          (all(math.isfinite(loss) for loss in losses) or
                           (native is stable_native and any(math.isfinite(loss) for loss in losses)
                            and all(not math.isnan(loss) and loss != -math.inf for loss in losses))))
                if usable:
                    return float(temperatures[min(range(len(losses)), key=losses.__getitem__)])

        shifted = _ladder._temperature_scores(log, 1.0)
        overflowed = (log.is_floating_point() and
                      bool((torch.isneginf(shifted) & torch.isfinite(log)).any()))

        def nll(t: float) -> float:
            scores = _ladder._temperature_scores(log, t) if overflowed and t > 1 else shifted / t
            scaled = torch.log_softmax(scores, dim=-1)
            if grouped:
                scaled = torch.stack([scaled[:, list(e)].logsumexp(dim=-1) for e in entries],
                                     dim=-1)
            loss = nn.functional.nll_loss(scaled, labels).item()
            if math.isfinite(loss):
                return loss
            # Compute the average without first forming an overflowing row loss
            # or sum. Normalize each target group relative to its own maximum.
            if grouped:
                target_max = torch.empty_like(log[:, 0])
                target_norm = torch.empty_like(scores[:, 0])
                for index, entry in enumerate(entries):
                    selected_rows = labels == index
                    if bool(selected_rows.any()):
                        target_log = log[selected_rows][:, list(entry)]
                        selected_max = target_log.amax(dim=-1)
                        if not bool(torch.isfinite(selected_max).all()):
                            return math.inf
                        target_max[selected_rows] = selected_max
                        target_norm[selected_rows] = torch.logsumexp(
                            _ladder._temperature_scores(target_log, t), dim=-1)
            else:
                target_max = log.gather(1, labels[:, None]).squeeze(1)
                if not bool(torch.isfinite(target_max).all()):
                    return math.inf
                target_norm = torch.zeros_like(target_max)
            maxima = log.amax(dim=-1)
            count = labels.numel()
            pairs = torch.stack((maxima, target_max), dim=-1)
            gap = -_ladder._temperature_scores(pairs, t * count)[:, 1]
            normalizer = torch.logsumexp(scores, dim=-1)
            return (gap + (normalizer - target_norm) / count).sum().item()

        return float(min(temperatures, key=nll))
