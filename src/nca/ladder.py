"""Calibrated ladders of interchangeable experts and budgeted refinement.

Generic over experts: a *ladder* for a contract is every installed module with
that contract whose output is a probability distribution, ordered by declared
cost. Each rung carries temperatures fitted on held-out labeled inputs, one for its
full output and one per restricted decision it serves (fitted on the held-out
inputs whose label is among the decision's classes), so its risk estimates
the error probability of the decision actually made. ``SecondLook`` wraps any such
expert into a costlier one with the same contract that averages its readings
of several views of the input; it joins ladders like any other expert.

``refine`` reads every item at the bottom of its ladder and, while the sum of
risks (the union bound) exceeds the target ``δ``, moves the riskiest item one
rung up, using its latest reading. An item's risk is measured against the
decision it serves: among the classes ``C`` it ranges over, possibly grouped,
the decision picks the group holding the most probable class, with risk
``1 - p(group) / p(C)``. This never exceeds ``1 - max p`` when the most
probable class is in ``C`` (``NCA.restricted_risk_le``,
``NCA.grouped_risk_le``). What each item is charged may depend on the
readings: a consumer's *certificate* returns a risk account, each item's
charge, summing to a bound on the answer's error probability (for example
the risks of the decisions it serves, ``NCA.certificate_error_le``); by
default every item is charged the risk of a fixed decision. It abstains when
no rung remains. For
calibrated risks the error among answered inputs is at most ``δ``
(``NCA.selective_risk_le``). For known independent reductions,
``NCA.threshold_optimal`` characterizes a different objective: bound plus
priced compute. The current largest-charge rule need not minimize compute;
with a floor ``ρ`` per item, ``n`` items need ``n · ρ ≤ δ``
(``NCA.length_limit``).

``refine`` may also abstain early (§22). A *floor* is a lower bound on every
bound refinement can still reach, computed from the readings of *fixed*
items, those at the top of their ladder. Once it exceeds ``δ`` refinement
would end in abstention anyway, so abstaining at once changes no answer. A
consumer declares its floor next to its certificate; for the default
account, a sum of charges where fixed items' charges never change, the sum
over fixed items is a floor (``additive_floor``). A *stopping rule* may
abstain earlier still, from the state of refinement; it trades coverage for
compute and never affects the answers given.
"""

from __future__ import annotations

import math
import sys
from collections import Counter
from numbers import Integral
from collections.abc import Callable, Sequence
from dataclasses import dataclass, field, replace
from functools import lru_cache
from typing import Any, Literal, overload
from weakref import ReferenceType, ref

import numpy as np
import torch
from torch import nn

from nca.abi import Contract, Module
from nca.native import load

_NATIVE = load("decoding")
_FLOAT32_TINY = torch.finfo(torch.float32).tiny
_FLOAT32_MAX = torch.finfo(torch.float32).max


class MissingCalibrationError(ValueError):
    """A decision lacks the held-out labels needed to fit its temperature."""


class _UnavailableCalibration(Exception):
    def __init__(self, index: int) -> None:
        self.index = index


class _MissingCalibration:
    """Cache marker for a decision with no matching held-out labels."""


_MISSING_CALIBRATION = _MissingCalibration()


Decision = Sequence[int | Sequence[int]] | None
"""What a decision chooses among: ``None`` for all classes; otherwise entries,
each a class or a group of classes. The decision picks the entry holding the
most probable of the classes listed."""

DecisionKey = tuple[int | tuple[int, ...], ...] | None


@lru_cache(maxsize=128)
def _immutable_decision_key(identity: int, decision: tuple) -> DecisionKey:
    """Cache only tuples composed exclusively of immutable built-in integers."""
    if all(type(entry) is int or
           (type(entry) is tuple and all(type(c) is int for c in entry))
           for entry in decision):
        return decision
    return None


def decision_key(decision: Decision) -> DecisionKey:
    if decision is None:
        return None
    if type(decision) is tuple:
        try:
            key = _immutable_decision_key(id(decision), decision)
            if key is not None:
                return key
        except TypeError:
            pass  # A tuple may contain mutable, unhashable groups.

    def index(value: object) -> int:
        if isinstance(value, bool) or not isinstance(value, Integral):
            raise ValueError("decision groups must form a nonempty partition of nonnegative class indices")
        return int(value)

    try:
        return tuple(index(e) if isinstance(e, Integral) else tuple(index(c) for c in e)
                     for e in decision)
    except TypeError as exc:
        raise ValueError("decision groups must form a nonempty partition of nonnegative class indices") from exc



def _fixed_decision(decision: Decision) -> bool:
    """Whether a decision cannot change while refinement is running."""
    if decision is None or type(decision) is range:
        return True
    if type(decision) is not tuple:
        return False
    try:
        return _immutable_decision_key(id(decision), decision) is decision
    except TypeError:
        return False


@lru_cache(maxsize=128)
def _layout(key: tuple[int | tuple[int, ...], ...]) -> tuple[list[int], list[list[int]]]:
    """The classes a decision ranges over, and each entry's positions among them."""
    parts = [[e] if isinstance(e, int) else list(e) for e in key]
    union = [c for part in parts for c in part]
    if (not parts or any(not part for part in parts)
            or any(isinstance(c, bool) or not isinstance(c, int) or c < 0 for c in union)
            or len(set(union)) != len(union)):
        raise ValueError("decision groups must form a nonempty partition of nonnegative class indices")
    positions = []
    offset = 0
    for part in parts:
        positions.append(list(range(offset, offset + len(part))))
        offset += len(part)
    return union, positions


@lru_cache(maxsize=128)
def _group_ids(key: tuple[int | tuple[int, ...], ...]) -> np.ndarray:
    """Read-only native group metadata for a partitioned decision."""
    union, positions = _layout(key)
    native = getattr(_NATIVE, "partition_group_ids", None)
    if native is not None:
        lengths = np.fromiter((len(part) for part in positions), dtype=np.int64,
                              count=len(positions))
        groups = np.asarray(native(lengths, len(union)), dtype=np.int64)
    else:
        groups = np.empty(len(union), dtype=np.int64)
        for entry, part in enumerate(positions):
            groups[part] = entry
    groups.setflags(write=False)
    return groups


@lru_cache(maxsize=128)
def _native_indices(key: tuple[int | tuple[int, ...], ...]) -> np.ndarray:
    """Read-only class indices for native restricted decisions."""
    indices = np.asarray(_layout(key)[0], dtype=np.int64)
    indices.setflags(write=False)
    return indices


class SecondLook:
    """An expert reading its input and ``views`` of it, averaging the readings."""

    def __init__(self, module: Module, views: Callable[[Any], list[Any]], count: int) -> None:
        self.module = module
        self.views = views
        self.manifest = replace(module.manifest,
                                module_id=f"{module.manifest.module_id}.second-look",
                                cost=module.manifest.cost * (count + 1))

    def invoke(self, value: Any) -> tuple[float, ...]:
        readings = [self.module.invoke(v) for v in (value, *self.views(value))]
        return tuple(np.mean(readings, axis=0).tolist())


@dataclass(frozen=True)
class RankedObservation:
    """An observation's log weights and the original binary64 ordering data.

    The logits are a tensor; callers must treat it as read-only. The weights
    are an immutable snapshot and retain distinctions lost by logarithms.
    """

    logits: torch.Tensor
    weights: tuple[float, ...]

    def top(self, classes: Sequence[int] | None = None) -> int:
        """Return the first highest-weight class among the supplied indices."""
        return _ranked_top(self.weights, classes)


def _ranked_index_array(indices: tuple) -> np.ndarray | None:
    if any(type(index) is not int for index in indices):
        return None
    try:
        result = np.asarray(indices, dtype=np.int64)
    except OverflowError as exc:
        raise ValueError("classes must contain valid class indices") from exc
    result.setflags(write=False)
    return result


@lru_cache(maxsize=128)
def _immutable_ranked_indices(identity: int, indices: tuple) -> np.ndarray | None:
    """Cache integer tuples without aliasing equal non-integer tuples."""
    return _ranked_index_array(indices)


def _ranked_top(weights: tuple[float, ...], classes: Sequence[int] | None) -> int:
    indices = None if classes is None else tuple(classes)
    indexed_native = getattr(_NATIVE, "ranked_argmax_indices_checked", None)
    if (indexed_native is not None and indices is not None and len(indices) >= 16
            and len(indices) * 4 >= len(weights)):
        if type(classes) is tuple:
            try:
                native_indices = _immutable_ranked_indices(id(classes), classes)
            except TypeError:
                native_indices = None
        else:
            native_indices = _ranked_index_array(indices)
        if native_indices is not None:
            try:
                native_weights = np.ascontiguousarray(weights, dtype=np.float64)
            except (TypeError, ValueError, OverflowError):
                # Unselected weights need not be convertible to binary64.
                native_weights = None
            if native_weights is not None:
                top = int(indexed_native(native_weights, native_indices))
                if top == -1:
                    raise ValueError("classes must contain valid class indices")
                if top == -2:
                    raise ValueError("ranked weights must be finite and nonnegative")
                return top
    if (len(weights) == 0 or (indices is not None and
            (not indices or any(isinstance(i, bool) or not isinstance(i, Integral)
                                or not 0 <= i < len(weights) for i in indices)))):
        raise ValueError("classes must contain valid class indices")
    native = getattr(_NATIVE, "ranked_argmax_checked", None)
    if native is not None:
        values = (np.ascontiguousarray(weights, dtype=np.float64) if indices is None else
                  np.fromiter((weights[i] for i in indices), dtype=np.float64,
                              count=len(indices)))
        top = int(native(values))
        if top < 0:
            raise ValueError("ranked weights must be finite and nonnegative")
        return top if indices is None else int(indices[top])
    if indices is None:
        indices = tuple(range(len(weights)))
    if any(not math.isfinite(weights[i]) or weights[i] < 0 for i in indices):
        raise ValueError("ranked weights must be finite and nonnegative")
    return int(max(indices, key=weights.__getitem__))


@dataclass(frozen=True)
class RankedReading(Sequence[float]):
    """Calibrated probabilities with the expert's original class ordering."""

    probabilities: tuple[float, ...]
    weights: tuple[float, ...]

    def __len__(self) -> int:
        return len(self.probabilities)

    def __getitem__(self, index: int | slice) -> float | tuple[float, ...]:
        return self.probabilities[index]

    def top(self, classes: Sequence[int] | None = None) -> int:
        return _ranked_top(self.weights, classes)

    def tolist(self) -> list[float]:
        return list(self.probabilities)


def _temperature_scores(log: torch.Tensor, temperature: float) -> torch.Tensor:
    if ((temperature < _FLOAT32_TINY or temperature > _FLOAT32_MAX)
            and log.device.type == "mps"):
        return _temperature_scores(log.cpu(), temperature).to(device=log.device, dtype=torch.float32)
    if not log.is_floating_point():
        if log.is_complex() or log.is_quantized:
            raise ValueError("log weights must be real numeric values")
        rows = log.ndim > 1 and log.numel() != log.shape[-1]
        native = getattr(_NATIVE, "shifted_integer_rows_into" if rows else "shifted_integer_logits_into", None)
        if native is not None and log.device.type == "cpu" and log.numel():
            unsigned = log.dtype == torch.uint64
            values = (log.contiguous().numpy().view(np.int64) if unsigned else
                      log.to(torch.int64).contiguous().numpy())
            shifted = np.empty(values.size, dtype=np.float64)
            status = (native(values.reshape(-1), shifted, log.shape[-1], unsigned) if rows else
                      native(values.reshape(-1), shifted, unsigned))
            if status == 0:
                return torch.from_numpy(shifted).reshape(log.shape) / temperature
        if log.dtype == torch.uint64:
            values = log.detach().cpu().numpy()
            maximum = np.max(values, axis=-1, keepdims=True) if rows else np.max(values)
            offsets = maximum - values
            differences = torch.from_numpy(offsets.astype(np.float64)).to(
                device=log.device, dtype=torch.float32 if log.device.type == "mps" else torch.float64)
            return -differences / temperature
        values = log.to(torch.int64)
        maximum = values.max(dim=-1, keepdim=True).values if rows else values.max()
        difference = values - maximum
        floating = difference.to(torch.float64 if log.device.type != "mps" else torch.float32)
        # A positive difference indicates signed subtraction wrapped below i64 minimum.
        if bool((difference > 0).any()):
            wide = values.to(floating.dtype) - maximum.to(floating.dtype)
            floating = torch.where(difference > 0, wide, floating)
        return floating / temperature
    # Keep a positive binary64 temperature representable for lower-precision inputs.
    if (log.dtype != torch.float64
            and (0 < temperature < torch.finfo(log.dtype).tiny
                 or temperature > torch.finfo(log.dtype).max)):
        log = log.float() if log.device.type == "mps" else log.double()
    if log.ndim > 1 and log.numel() != log.shape[-1]:
        native = getattr(_NATIVE, "scaled_logit_rows_into", None)
        if (native is not None and log.device.type == "cpu" and log.dtype == torch.float64
                and not log.requires_grad and 0 < log.numel() <= 512):
            values = log.contiguous().numpy()
            scaled = np.empty(values.size, dtype=np.float64)
            if native(values.reshape(-1), scaled, log.shape[-1], temperature) != 0:
                raise ValueError("calibrated decision requires finite log weights with positive mass")
            return torch.from_numpy(scaled).reshape(log.shape)
        maximum = log.amax(dim=-1, keepdim=True)
        if not bool(torch.isfinite(maximum).all()):
            raise ValueError("calibrated decision requires finite log weights with positive mass")
        difference = log - maximum
        if temperature > 1:
            return torch.where(torch.isneginf(difference) & torch.isfinite(log),
                               log / temperature - maximum / temperature,
                               difference / temperature)
        return difference / temperature
    maximum = log.max()
    maximum_value = maximum.item()
    if not math.isfinite(maximum_value):
        raise ValueError("calibrated decision requires finite log weights with positive mass")
    difference = log - maximum
    # Below half an ulp at the finite limit, adding the maximum to even the
    # most negative finite value cannot round the difference to infinity.
    if (temperature > 1 and maximum_value > 0 and
            (not log.is_floating_point() or maximum_value >
             torch.finfo(log.dtype).max * torch.finfo(log.dtype).eps / 4)):
        # A finite difference can overflow before a large divisor rescales it.
        return torch.where(torch.isneginf(difference) & torch.isfinite(log),
                           log / temperature - maximum / temperature,
                           difference / temperature)
    return difference / temperature


def _selected_logits(log: torch.Tensor, indices: Sequence[int] | None) -> torch.Tensor:
    """Select before shifting integers, retaining differences inside the decision."""
    if log.is_floating_point():
        return log if indices is None else log[..., list(indices)]
    if log.is_complex() or log.is_quantized:
        raise ValueError("log weights must be real numeric values")
    if indices is not None:
        if log.dtype == torch.uint64:
            values = log.detach().cpu().numpy()[..., list(indices)]
            log = torch.from_numpy(np.ascontiguousarray(values)).to(log.device)
        else:
            log = log[..., list(indices)]
    return _temperature_scores(log, 1.0)


def _binary64_logits(log: torch.Tensor) -> torch.Tensor:
    return log.cpu().double() if log.device.type == "mps" else log.double()


def _grouped_batch(log: torch.Tensor, key: DecisionKey, temperature: float, *, logarithmic: bool) -> torch.Tensor:
    union, positions = _layout(key)
    selected = (_selected_logits(log[..., union].cpu(), None)
                if logarithmic and log.device.type == "mps" else _selected_logits(log, union))
    output_dtype = torch.float64 if logarithmic else (
        log.dtype if log.is_floating_point() else torch.get_default_dtype())
    shape = (*log.shape[:-1], len(positions))
    native = getattr(_NATIVE, "calibrated_group_rows_into", None)
    if (native is not None and selected.device.type == "cpu" and not selected.requires_grad
            and selected.numel() <= (16384 if logarithmic else 8192)):
        values = selected.double().contiguous().numpy()
        output = np.empty(math.prod(shape), dtype=np.float64)
        status = native(values.reshape(-1), _group_ids(key), output,
                        len(positions), temperature, logarithmic)
        if status != 0:
            raise ValueError("calibrated decision requires finite log weights with positive mass")
        return torch.from_numpy(output.reshape(shape)).to(output_dtype)
    if logarithmic:
        scores = _temperature_scores(_binary64_logits(selected), temperature)
        normalizer = torch.logsumexp(scores, dim=-1)
        return torch.stack([torch.logsumexp(scores[..., part], dim=-1) - normalizer
                            for part in positions], dim=-1)
    reading = torch.softmax(_temperature_scores(selected, temperature), dim=-1).to(output_dtype)
    return torch.stack([reading[..., part].sum(dim=-1) for part in positions], dim=-1)


def _checked_calibrated_risk(value: float) -> float:
    if not math.isfinite(value):
        raise ValueError("calibrated decision requires finite log weights with positive mass "
                         "and a finite nonnegative reading")
    return value


@dataclass
class Rung:
    """An expert read through temperatures fitted on held-out labeled inputs:
    one for its full output and one for each restricted decision it serves."""

    module: Module
    temperatures: dict[DecisionKey, float] = field(default_factory=dict)
    held_out: tuple[torch.Tensor, torch.Tensor] | None = None
    _missing_temperatures: set[DecisionKey] = field(default_factory=set, init=False, repr=False, compare=False)
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

    def observe_ranked(self, value: Any) -> RankedObservation:
        """Observe once while retaining exact binary64 weight ordering."""
        return self._observe(value, ranked=True)

    @overload
    def _observe(self, value: Any, *, ranked: Literal[False]) -> torch.Tensor: ...

    @overload
    def _observe(self, value: Any, *, ranked: Literal[True]) -> RankedObservation: ...

    def _observe(self, value: Any, *, ranked: bool) -> torch.Tensor | RankedObservation:
        output = self.module.invoke(value)
        if isinstance(output, np.ma.MaskedArray) and np.ma.is_masked(output):
            raise ValueError("expert output must not contain masked weights")
        if isinstance(output, torch.Tensor) and output.is_complex():
            raise ValueError("expert output must contain real-valued weights")
        native = getattr(_NATIVE, "observation_logs", None)
        native_into = getattr(_NATIVE, "observation_logs_into", None)
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
                return RankedObservation(logits, tuple(array.tolist())) if ranked else logits
            if native is not None:
                logs = native(array)
                if not logs:
                    raise ValueError("expert output must contain finite nonnegative weights with positive mass")
                logits = torch.tensor(logs, dtype=torch.float64)
                return RankedObservation(logits, tuple(array.tolist())) if ranked else logits
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
            return RankedObservation(logits, tuple(array.tolist())) if ranked else logits
        assert probabilities is not None
        valid = (bool(torch.isfinite(probabilities).all()) and
                 not bool((probabilities < 0).any()) and
                 bool((probabilities > 0).any()))
        if not valid:
            raise ValueError("expert output must contain finite nonnegative weights with positive mass")
        logits = probabilities.clamp_min(math.nextafter(0.0, 1.0)).log()
        return RankedObservation(logits, tuple(probabilities.tolist())) if ranked else logits

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

    def temperature(self, classes: Decision = None) -> float:
        """Temperature of the decision over ``classes``, fitted on first use on
        the held-out inputs whose label is among them, by the likelihood of
        the label's entry."""
        key = decision_key(classes)
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
                raise MissingCalibrationError("cannot fit decision temperature without matching held-out labels")
            log, labels = self.held_out
            union, positions = _layout(key)
            subset = getattr(_NATIVE, "calibration_subset", None)
            packed = None
            if (subset is not None and log.device.type == "cpu" and log.ndim == 2
                    and labels.device.type == "cpu" and labels.dtype == torch.int64
                    and labels.ndim == 1):
                try:
                    packed = subset(labels.contiguous().numpy(), _native_indices(key),
                                    _group_ids(key), log.shape[1], len(positions))
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
                raise MissingCalibrationError("cannot fit decision temperature without matching held-out labels")
            columns = torch.as_tensor(union, dtype=torch.long, device=log.device)
            selected_log = log[rows[:, None], columns]
            self.temperatures[key] = self._fit(selected_log, targets, positions)
        return self.temperatures[key]

    def reading(self, log: torch.Tensor | RankedObservation) -> torch.Tensor:
        """Numerical probabilities; ranked ordering remains on the observation."""
        temperature = self.temperature()
        if not math.isfinite(temperature) or temperature <= 0:
            name = "ranked reading" if isinstance(log, RankedObservation) else "reading"
            raise ValueError(f"{name} requires a positive finite temperature")
        if isinstance(log, RankedObservation):
            log = log.logits
        result = torch.softmax(_temperature_scores(log, temperature), dim=-1)
        return result.to(log.dtype if log.is_floating_point() else torch.get_default_dtype())

    def risk(self, log: torch.Tensor | RankedObservation, classes: Decision = None, *,
             reading: torch.Tensor | None = None) -> float:
        """Calibrated error probability for one observation over ``classes``.

        A ranked observation chooses the winning class by its original weights;
        a tensor chooses from its numerical reading. Consumers must use the
        same choice: the numerical reading can contain ties. The optional
        ``reading`` reuses the numerical reading of this observation; callers
        must supply the reading for this observation and calibration.
        """
        key = decision_key(classes)
        temperature = self.temperature(key)
        ranked = log if isinstance(log, RankedObservation) else None
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
        union = list(range(len(log))) if key is None else _layout(key)[0]
        probabilities = (self.reading(log) if reading is None else reading) if ranked is None else None
        integral_reading = ranked is None and not probabilities.is_floating_point()
        if integral_reading and (probabilities.is_complex() or probabilities.is_quantized):
            raise ValueError("reused reading must be finite and nonnegative")
        native_reading = getattr(_NATIVE, "calibrated_risk_for_reading_checked", None)
        if native_reading is None and reading is None and ranked is None:
            native_reading = getattr(_NATIVE, "calibrated_risk_for_reading", None)
        if (native_reading is not None and not integral_reading
                and log.device.type == "cpu" and not log.requires_grad
                and (ranked is not None or (probabilities.device.type == "cpu"
                                            and not probabilities.requires_grad))):
            native_key = key if key is not None else tuple(range(len(log)))
            _, positions = _layout(native_key)
            groups = _group_ids(native_key)
            ordering = (np.asarray(ranked.weights, dtype=np.float64) if ranked is not None else
                        probabilities.double().numpy())
            logits = (log.double().numpy() if log.is_floating_point() else
                      _selected_logits(log, None if classes is None else union).double().numpy())
            if classes is None:
                logits = np.ascontiguousarray(logits)
                ordering = np.ascontiguousarray(ordering)
            else:
                indices = _native_indices(key)
                if log.is_floating_point():
                    logits = logits[indices]
                ordering = ordering[indices]
            return _checked_calibrated_risk(float(native_reading(
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
        native = getattr(_NATIVE, "calibrated_risk_at", None)
        if native is not None and log.device.type == "cpu" and not log.requires_grad:
            native_key = key if key is not None else tuple(range(len(log)))
            union, positions = _layout(native_key)
            groups = _group_ids(native_key)
            return _checked_calibrated_risk(float(native(
                _selected_logits(log, None if key is None else union).double().numpy(),
                groups, len(positions), temperature, selected)))
        if classes is None:
            values, positions = _selected_logits(log, None), None
        else:
            union, positions = _layout(key)
            values = _selected_logits(log, union)
        result = _checked_calibrated_risk(risk(
            torch.softmax(_temperature_scores(values, temperature), dim=-1), positions, _top=selected))
        if result != 0.0:
            return result
        # A float32 softmax can erase probabilities that fit in binary64.
        scores = _binary64_logits(values)
        scores = _temperature_scores(scores, temperature)
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

    def risk_batch(self, log: torch.Tensor, classes: Decision = None, *,
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
        key = decision_key(classes)
        temperature = self.temperature(key)
        if not math.isfinite(temperature) or temperature <= 0:
            raise ValueError("batched risk requires a positive finite temperature")
        selection_weights = self.reading(log) if supplied is None else supplied
        if key is None:
            union = None
            group_count = log.shape[-1]
            group_ids = np.empty(0, dtype=np.int64)
        else:
            union, positions = _layout(key)
            group_count = len(positions)
            group_ids = _group_ids(key)
        if key is None:
            order = selection_weights
        elif selection_weights.dtype == torch.uint64:
            order_values = selection_weights.detach().cpu().numpy()[..., union]
            order = torch.from_numpy(np.ascontiguousarray(order_values))
        else:
            order = selection_weights[..., union]
        if log.device.type == "mps":
            raw = log if key is None else log[..., union]
            selected = _selected_logits(raw.cpu(), None)
        else:
            selected = _selected_logits(log, None if key is None else union)
        if order.device.type == "mps" and selected.device.type == "cpu":
            order = order.cpu()
        order = order.to(device=selected.device, dtype=torch.float64)
        shape = log.shape[:-1]
        native = getattr(_NATIVE, "calibrated_risk_rows_into", None)
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
        scores = _temperature_scores(_binary64_logits(selected), temperature)
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

    def distribution(self, log: torch.Tensor | RankedObservation, classes: Decision = None) -> torch.Tensor:
        """Calibrated probabilities of the decision's entries: each entry's
        share of the classes it ranges over, under the decision's temperature.
        Leading batch dimensions are preserved.
        """
        temperature = self.temperature(classes)
        if not math.isfinite(temperature) or temperature <= 0:
            name = "ranked distribution" if isinstance(log, RankedObservation) else "distribution"
            raise ValueError(f"{name} requires a positive finite temperature")
        if isinstance(log, RankedObservation):
            log = log.logits
        if classes is None:
            return self.reading(log)
        if log.ndim == 0:
            raise ValueError("grouped distribution requires a one-dimensional logit vector")
        if log.ndim > 1:
            return _grouped_batch(log, decision_key(classes), temperature, logarithmic=False)
        output_dtype = log.dtype if log.is_floating_point() else torch.get_default_dtype()
        union, positions = _layout(decision_key(classes))
        values = _selected_logits(log, union)
        native = getattr(_NATIVE, "calibrated_groups", None)
        groups = _group_ids(decision_key(classes))
        if native is not None and log.device.type == "cpu" and not log.requires_grad:
            grouped = native(values.double().numpy(), groups, len(positions), temperature)
            if not grouped or not all(math.isfinite(value) for value in grouped):
                raise ValueError("calibrated decision requires finite log weights with positive mass")
            return torch.tensor(grouped, dtype=output_dtype)
        reading = torch.softmax(_temperature_scores(values, temperature), dim=-1)
        reading = reading.to(output_dtype)
        return torch.stack([reading[part].sum() for part in positions])

    def log_distribution(self, log: torch.Tensor | RankedObservation,
                         classes: Decision = None) -> torch.Tensor:
        """Log probabilities retaining underflowed mass, with optional batch dimensions."""
        temperature = self.temperature(classes)
        if not math.isfinite(temperature) or temperature <= 0:
            name = "ranked distribution" if isinstance(log, RankedObservation) else "distribution"
            raise ValueError(f"{name} requires a positive finite temperature")
        if isinstance(log, RankedObservation):
            log = log.logits
        if classes is None:
            if log.device.type == "mps":
                # MPS lacks binary64, which this interface uses for log probabilities.
                log = log.cpu()
            return torch.log_softmax(_temperature_scores(_binary64_logits(_selected_logits(log, None)), temperature), dim=-1)
        if log.ndim == 0:
            raise ValueError("grouped log distribution requires a one-dimensional logit vector")
        if log.ndim > 1:
            return _grouped_batch(log, decision_key(classes), temperature, logarithmic=True)
        key = decision_key(classes)
        union, positions = _layout(key)
        if log.device.type == "mps":
            if log.numel() * log.element_size() >= 16_000_000 and len(union) * 4 < log.numel():
                selected = _selected_logits(log[union].cpu(), None)
            else:
                selected = _selected_logits(log.cpu(), union)
        else:
            selected = _selected_logits(log, union)
        native = getattr(_NATIVE, "calibrated_log_groups", None)
        if native is not None and selected.device.type == "cpu" and not selected.requires_grad:
            values = native(selected.double().numpy(), _group_ids(key), len(positions), temperature)
            if (values and all(not math.isnan(value) and value != math.inf for value in values)
                    and any(math.isfinite(value) for value in values)):
                return torch.tensor(values, dtype=torch.float64)
            raise ValueError("calibrated decision requires finite log weights with positive mass")
        scores = _temperature_scores(_binary64_logits(selected), temperature)
        normalizer = torch.logsumexp(scores, dim=-1)
        return torch.stack([torch.logsumexp(scores[part], dim=-1) - normalizer
                            for part in positions])

    @staticmethod
    def _fit(log: torch.Tensor, labels: torch.Tensor,
             entries: Sequence[Sequence[int]] | None = None) -> float:
        """Minimize label negative log-likelihood over a fixed temperature grid.

        Each label names an entry (a group of columns) when ``entries`` is given.
        """
        grouped = entries is not None and any(len(e) > 1 for e in entries)
        temperatures = np.geomspace(0.1, 8.0, 120)
        native = getattr(_NATIVE, "calibration_loss_grid", None)
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
                if len(losses) == len(temperatures) and not any(math.isnan(loss) for loss in losses):
                    return float(temperatures[min(range(len(losses)), key=losses.__getitem__)])

        def nll(t: float) -> float:
            scaled = torch.log_softmax(log / t, dim=-1)
            if grouped:
                scaled = torch.stack([scaled[:, list(e)].logsumexp(dim=-1) for e in entries],
                                     dim=-1)
            return nn.functional.nll_loss(scaled, labels).item()

        return float(min(temperatures, key=nll))


def ladder(modules: Sequence[Module], contract: Contract) -> list[Rung]:
    """Rungs for every module with ``contract``, cheapest first."""
    found = [m for m in modules if m.manifest.contract == contract]
    return [Rung(m) for m in sorted(found, key=lambda m: m.manifest.cost)]


@dataclass
class Refinement:
    readings: list[torch.Tensor | RankedReading]
    cost: float
    bound: float
    abstained: bool
    available: bool = True


def _upper_sum(values: Sequence[float]) -> float:
    """Bound the exact sum of nonnegative binary64 inputs from above."""
    native = getattr(_NATIVE, "upper_sum", None)
    if native is not None:
        return float(native(np.asarray(values, dtype=np.float64)))
    total = 0.0
    for x in values:
        rounded = total + float(x)
        if math.isinf(rounded):
            return rounded
        part = rounded - total
        residual = (total - (rounded - part)) + (float(x) - part)
        total = math.nextafter(rounded, math.inf) if residual > 0.0 else rounded
    return total


def _lower_values(values: Sequence[float]) -> list[float]:
    rounded_values = []
    for value in values:
        rounded = float(value)
        rounded_values.append(math.nextafter(rounded, 0.0) if rounded > value else rounded)
    return rounded_values


def _lower_sum(values: Sequence[float]) -> float:
    """Bound the exact sum of nonnegative inputs from below."""
    rounded_values = _lower_values(values)
    native = getattr(_NATIVE, "lower_sum", None)
    if native is not None:
        return float(native(np.asarray(rounded_values, dtype=np.float64)))
    total = 0.0
    for x in rounded_values:
        rounded = total + x
        if math.isinf(rounded):
            total = math.nextafter(rounded, 0.0)
            continue
        part = rounded - total
        residual = (total - (rounded - part)) + (x - part)
        total = math.nextafter(rounded, 0.0) if residual < 0.0 else rounded
    return total


def risk(reading: torch.Tensor, classes: Decision = None, *, _top: int | None = None) -> float:
    """Error probability of the decision over ``classes`` (all if ``None``):
    the share outside the entry holding the most probable class listed."""
    if reading.ndim != 1 or not len(reading):
        raise ValueError("decision weights must be a nonempty vector")
    if reading.is_complex() or reading.is_quantized:
        raise ValueError("decision weights must be real numeric values")
    key = decision_key(classes)
    native_key = key if key is not None else tuple(range(len(reading)))
    union, positions = _layout(native_key)
    mass = reading if key is None else reading[union]
    top = None if _top is None else union.index(_top)
    if top is None and not mass.is_floating_point():
        # Choose before conversion: adjacent large integers can tie in binary64.
        top = (int(mass.detach().cpu().numpy().argmax()) if mass.dtype == torch.uint64 else
               int(mass.to(torch.int64).argmax()))
    native = getattr(_NATIVE, "weighted_decision_risk", None)
    if native is not None and mass.device.type == "cpu" and not mass.requires_grad:
        value = float(native(mass.double().contiguous().numpy(), _group_ids(native_key),
                             len(positions), -1 if top is None else top))
        if value < 0:
            raise ValueError("decision weights must be finite, nonnegative and have positive mass")
        return value
    mass = mass.to(torch.float32 if mass.device.type == "mps" else torch.float64)
    if not bool(torch.isfinite(mass).all()) or bool((mass < 0).any()):
        raise ValueError("decision weights must be finite, nonnegative and have positive mass")
    largest = mass.max()
    if not bool(largest > 0):
        raise ValueError("decision weights must be finite, nonnegative and have positive mass")
    top = int(mass.argmax()) if top is None else top
    chosen = next(part for part in positions if top in part)
    selected = set(chosen)
    outside = [i for i in range(len(union)) if i not in selected]
    outside_mass, total = mass[outside].sum(), mass.sum()
    outside_value, total_value = outside_mass.item(), total.item()
    if math.isfinite(total_value):
        value = outside_value / total_value
    else:
        scaled = mass / largest
        scaled_total = scaled.sum().item()
        value = ((outside_value / largest.item()) / scaled_total if math.isfinite(outside_value)
                 else scaled[outside].sum().item() / scaled_total)
    return math.nextafter(0.0, 1.0) if value == 0.0 and outside_value > 0.0 else value


@dataclass(frozen=True)
class Distribution:
    """Calibrated probabilities with optional per-item revision identities.

    A revision identifies the observation and calibration within its source.
    Adapters may share a source token when they preserve that identity.
    Consumers without revision support may call this like any other function.
    ``log_lookup`` may preserve mass lost in numerical probabilities; without
    it, ``log`` operates on the returned probabilities and cannot recover it.
    """

    lookup: Callable[[int, Decision], torch.Tensor]
    revision: Callable[[int], int] | None
    source: object = field(default_factory=object, compare=False, repr=False)
    log_lookup: Callable[[int, Decision], torch.Tensor] | None = None

    def __call__(self, i: int, decision: Decision) -> torch.Tensor:
        return self.lookup(i, decision)

    def log(self, i: int, decision: Decision) -> torch.Tensor:
        if self.log_lookup is not None:
            return self.log_lookup(i, decision)
        return torch.as_tensor(self.lookup(i, decision)).double().log()


Reading = torch.Tensor | RankedReading


Certificate = Callable[[Sequence[Reading], Callable[[int, Decision], float],
                        Callable[[int, Decision], torch.Tensor]], dict[int, float] | None]
"""``certificate(readings, risk, distribution)``: a risk account for the
current readings, each charged item's finite nonnegative charge, computed with
``risk(i, decision)`` and the calibrated entry probabilities
``distribution(i, decision)``; the charges sum to a bound on the answer's
error probability. Keys identify refined items. ``None`` if the readings
determine no answer."""


Floor = Callable[[Sequence[Reading], Callable[[int, Decision], float], frozenset[int]],
                 float]
"""``floor(readings, risk, fixed)``: a lower bound on every bound refinement
can reach while the readings of the items in ``fixed`` stay as they are."""


@dataclass(frozen=True)
class State:
    """Refinement after a step: the bound, the summed charges of items that
    can still climb, and the cost spent so far."""

    bound: float
    open_charge: float
    cost: float


Stop = Callable[[State], bool]
"""A stopping rule: abstain now, given the state of refinement."""


ClimbPriority = Callable[[int, float, float], float]
"""Priority of an open item given its index, current charge and next cost."""


def charge_per_cost(index: int, charge: float, cost: float) -> float:
    """Rank a current charge by the declared cost of its next invocation.

    This is a heuristic, not a guarantee that the charge will fall. A free
    invocation takes priority. ``refine`` resolves rounded-score ties by
    comparing the exact binary64 ratios, then preserves item order on equality.
    """
    if not math.isfinite(cost) or cost < 0:
        raise ValueError("next invocation cost must be finite and nonnegative")
    return math.inf if cost == 0 else charge / cost


def _ratio_greater(a: float, b: float, c: float, d: float) -> bool:
    """Compare a/b > c/d exactly for finite nonnegative a,c and positive b,d."""
    if b == d:
        return a > c
    an, ad = a.as_integer_ratio()
    bn, bd = b.as_integer_ratio()
    cn, cd = c.as_integer_ratio()
    dn, dd = d.as_integer_ratio()
    return an * bd * cd * dn > cn * dd * ad * bn


def _cost_aware_choice(open_: Sequence[int], charges: dict[int, float],
                       ladders: Sequence[Sequence[Rung]], levels: Sequence[int]) -> int:
    """First maximum ratio; only rounded ties need exact integer arithmetic."""
    chosen = open_[0]
    best_charge = best_cost = best_score = 0.0
    have_best = False
    for i in open_:
        charge = float(charges[i])
        cost = float(ladders[i][levels[i] + 1].cost)
        score = charge_per_cost(i, charge, cost)
        better = not have_best
        if have_best:
            if cost == 0:
                better = best_cost != 0
            elif best_cost != 0:
                better = (score > best_score or
                          (score == best_score and
                           _ratio_greater(charge, cost, best_charge, best_cost)))
        if better:
            chosen, best_charge, best_cost, best_score = i, charge, cost, score
            have_best = True
    return chosen


def allocate_risk(bound: float, priorities: Sequence[float]) -> list[float]:
    """Allocate a current bound using possibly stale, nonnegative priorities.

    Priorities may be a Python sequence or a one-dimensional NumPy array.
    They guide refinement only; their age does not affect the total
    charge in exact arithmetic (THEORY 23.11). Zero priorities receive a
    uniform allocation. If every share underflows, one retains the bound;
    positive allocations are adjusted to cover the bound under binary64 arithmetic.
    """
    if not math.isfinite(bound) or bound < 0:
        raise ValueError("bound must be finite and nonnegative")
    if len(priorities) == 0:
        raise ValueError("risk allocation requires at least one item")
    checked = getattr(_NATIVE, "risk_shares_covering", None)
    if checked is not None:
        values = np.asarray(priorities)
        if values.ndim == 1 and values.dtype.kind in "biuf" and values.dtype.itemsize <= 8:
            shares = checked(bound, np.asarray(values, dtype=np.float64))
            if not shares:
                raise ValueError("priorities must be finite and nonnegative")
            return shares
    if any(not math.isfinite(p) or p < 0 for p in priorities):
        raise ValueError("priorities must be finite and nonnegative")
    native = getattr(_NATIVE, "risk_shares", None)
    if native is not None:
        shares = native(bound, np.asarray(priorities, dtype=np.float64))
    else:
        scale = max(priorities)
        weights = [p / scale for p in priorities] if scale > 0 else [1.0] * len(priorities)
        total = math.fsum(weights)
        shares = [bound * (w / total) for w in weights]
    if bound > 0 and not any(shares):
        shares[max(range(len(priorities)), key=priorities.__getitem__)] = bound
    if bound > 0:
        top = max(range(len(shares)), key=shares.__getitem__)
        total, correction = 0.0, 0.0
        for share in shares:
            if share > 0:
                updated = total + share
                if updated == math.inf:
                    return shares
                virtual = updated - total
                residual = (total - (updated - virtual)) + (share - virtual)
                if residual:
                    correction = math.nextafter(correction + residual, -math.inf)
                total = updated
        estimate = total + correction
        lower = math.nextafter(estimate, 0.0) if estimate > 0 else 0.0
        if shares[top] < bound and lower < bound:
            deficit = math.nextafter(bound - lower, math.inf)
            increased = shares[top] + deficit
            shares[top] = bound if increased >= bound else math.nextafter(increased, math.inf)
    return shares


def refine(values: Sequence[Any], ladders: Sequence[Sequence[Rung]], delta: float,
           start: int = 0, classes: Sequence[Decision] | None = None,
           certificate: Certificate | None = None, floor: Floor | None = None,
           additive_floor: bool = False, stop: Stop | None = None,
           trace: list[State] | None = None,
           observe: Callable[[Refinement], None] | None = None, *,
           priority: ClimbPriority | None = None, ranked: bool = False) -> Refinement:
    """Read ``values[i]`` with ``ladders[i]``, refining until the bound meets ``delta``.

    Each value requires one nonempty ladder and, when supplied, one decision.
    Every item starts at rung ``min(start, top)``, reading each rung below it.
    The bound sums the charges of ``certificate``'s account; by default every
    item ``i`` is charged the risk of decision ``classes[i]``. While it exceeds
    ``delta`` the open item with the largest charge climbs a rung; if the
    readings determine no answer, the riskiest item. A supplied ``priority``
    instead ranks open items using their index, charge and next invocation
    cost; it must not mutate the refinement state. ``observe`` receives each
    state, including the initial and terminal states, with an independent
    outer reading list. Observers must not mutate the reading tensors. Experts,
    ladders and calibration parameters must remain fixed during a run. When
    ``ranked`` is enabled, readings preserve the original weight ordering;
    the certificate and downstream consumer must use that ordering to choose.
    Missing restricted calibration makes the account unavailable; refinement
    may climb another rung and abstains if no usable account is found.
    """
    if math.isnan(delta) or delta < 0:
        raise ValueError("target must be nonnegative and not NaN")
    decisions = list(classes) if classes is not None else [None] * len(values)
    if len(decisions) != len(values):
        raise ValueError("classes must contain exactly one decision per value")
    if len(ladders) != len(values) or any(not ladder for ladder in ladders):
        raise ValueError("ladders must contain one nonempty ladder per value")
    levels = [0] * len(values)
    logs: list[torch.Tensor | RankedObservation] = [torch.empty(0)] * len(values)
    readings: list[Reading] = [torch.empty(0)] * len(values)
    risks: list[tuple[DecisionKey, float | _MissingCalibration] |
                dict[DecisionKey, float | _MissingCalibration] | None] = [None] * len(values)
    distributions: list[tuple[DecisionKey, torch.Tensor | _MissingCalibration] |
                        dict[DecisionKey, torch.Tensor | _MissingCalibration] | None] = [None] * len(values)
    log_distributions: list[dict[DecisionKey, torch.Tensor | _MissingCalibration] | None] = [None] * len(values)
    cost = 0.0

    def climb(i: int) -> None:
        nonlocal cost
        rung = ladders[i][levels[i]]
        risks[i] = None
        distributions[i] = None
        log_distributions[i] = None
        observation = rung.observe_ranked(values[i]) if ranked else rung.observe(values[i])
        logs[i] = observation
        numeric = rung.reading(observation)
        readings[i] = (RankedReading(tuple(numeric.tolist()), observation.weights)
                       if isinstance(observation, RankedObservation) else numeric)
        cost += rung.cost

    def item_risk(i: int, decision: Decision) -> float:
        key = decision_key(decision)
        cache = risks[i]
        if isinstance(cache, tuple) and cache[0] == key:
            result = cache[1]
        elif isinstance(cache, dict) and key in cache:
            result = cache[key]
        else:
            try:
                result = ladders[i][levels[i]].risk(
                    logs[i], decision, reading=readings[i] if isinstance(readings[i], torch.Tensor) else None)
            except MissingCalibrationError:
                result = _MISSING_CALIBRATION
            if cache is None:
                risks[i] = (key, result)
            elif isinstance(cache, tuple):
                risks[i] = {cache[0]: cache[1], key: result}
            else:
                cache[key] = result
        if result is _MISSING_CALIBRATION:
            raise _UnavailableCalibration(i)
        return result

    def item_distribution(i: int, decision: Decision) -> torch.Tensor:
        key = decision_key(decision)
        cache = distributions[i]
        if isinstance(cache, tuple) and cache[0] == key:
            result = cache[1]
        elif isinstance(cache, dict) and key in cache:
            result = cache[key]
        else:
            try:
                result = ladders[i][levels[i]].distribution(logs[i], decision)
            except MissingCalibrationError:
                result = _MISSING_CALIBRATION
            if cache is None:
                distributions[i] = (key, result)
            elif isinstance(cache, tuple):
                distributions[i] = {cache[0]: cache[1], key: result}
            else:
                cache[key] = result
        if result is _MISSING_CALIBRATION:
            raise _UnavailableCalibration(i)
        return result

    def item_log_distribution(i: int, decision: Decision) -> torch.Tensor:
        key = decision_key(decision)
        cache = log_distributions[i]
        if cache is None:
            cache = log_distributions[i] = {}
        if key not in cache:
            rung = ladders[i][levels[i]]
            log_method = getattr(rung, "log_distribution", None)
            base_log = getattr(log_method, "__func__", None) is Rung.log_distribution
            base_distribution = getattr(rung.distribution, "__func__", None) is Rung.distribution
            try:
                if log_method is None or (base_log and not base_distribution):
                    cache[key] = item_distribution(i, decision).double().log()
                else:
                    cache[key] = log_method(logs[i], decision)
            except MissingCalibrationError:
                cache[key] = _MISSING_CALIBRATION
        result = cache[key]
        if result is _MISSING_CALIBRATION:
            raise _UnavailableCalibration(i)
        return result

    current_distribution = Distribution(item_distribution, levels.__getitem__,
                                        log_lookup=item_log_distribution)

    for i in range(len(values)):
        climb(i)
        while levels[i] < min(start, len(ladders[i]) - 1):
            levels[i] += 1
            climb(i)
    fixed_account = certificate is None and all(map(_fixed_decision, decisions))
    # Seed the default account in native batches when this preserves the exact
    # per-item kernel and does not bypass lazy calibration or custom rungs.
    if (fixed_account and len(values) >= 16
            and getattr(_NATIVE, "calibrated_risk_rows_into", None) is not None
            and getattr(_NATIVE, "calibrated_risk_for_reading_checked", None) is not None):
        # A batch cannot span rungs, so skip detailed checks for rungs that
        # cannot possibly fill one. This matters for heterogeneous ladders.
        rung_counts = Counter(id(ladders[i][levels[i]]) for i in range(len(values)))
        batches: dict[tuple[int, DecisionKey, int], list[int]] = {}
        for i, decision in enumerate(decisions):
            rung = ladders[i][levels[i]]
            if rung_counts[id(rung)] < 16:
                continue
            observation = logs[i]
            if ranked != isinstance(observation, RankedObservation):
                continue
            log = observation.logits if isinstance(observation, RankedObservation) else observation
            if (type(rung) is not Rung or type(rung.temperatures) is not dict
                    or getattr(rung.risk, "__func__", None) is not Rung.risk
                    or getattr(rung.risk_batch, "__func__", None) is not Rung.risk_batch
                    or getattr(rung.temperature, "__func__", None) is not Rung.temperature
                    or log.ndim != 1 or log.device.type != "cpu"
                    or log.dtype != torch.float64 or log.requires_grad):
                continue
            if not ranked:
                reading = readings[i]
                if (not isinstance(reading, torch.Tensor) or reading.shape != log.shape
                        or reading.device.type != "cpu" or reading.dtype != torch.float64
                        or reading.requires_grad):
                    continue
            elif len(observation.weights) != log.numel():
                continue
            key = decision_key(decision)
            if key not in rung.temperatures and key is not None and rung.held_out is not None:
                continue
            try:
                union = None if key is None else _layout(key)[0]
                if log.numel() == 0 or (union is not None and max(union) >= log.numel()):
                    continue
            except ValueError:
                continue
            batches.setdefault((id(rung), key, log.numel()), []).append(i)
        for (_, key, width), indices in batches.items():
            selected_width = width if key is None else len(_layout(key)[0])
            chunk_size = 65536 // selected_width
            if chunk_size < 16:
                continue
            for offset in range(0, len(indices), chunk_size):
                chunk = indices[offset:offset + chunk_size]
                if len(chunk) < 16:
                    continue
                rung = ladders[chunk[0]][levels[chunk[0]]]
                try:
                    if ranked:
                        observations = [logs[i] for i in chunk]
                        batch = torch.stack([o.logits for o in observations])
                        ordering = torch.tensor([o.weights for o in observations], dtype=torch.float64)
                        result = rung.risk_batch(batch, key, ordering=ordering)
                    else:
                        batch = torch.stack([logs[i] for i in chunk])
                        reading = torch.stack([readings[i] for i in chunk])
                        result = rung.risk_batch(batch, key, reading=reading)
                except (ValueError, IndexError):
                    # Preserve the ordinary path's error and calibration order.
                    continue
                for i, value in zip(chunk, result.tolist()):
                    risks[i] = (key, value)
    default_account: dict[int, float] | None = None
    while True:
        unavailable: set[int] = set()
        try:
            if certificate is not None:
                account = certificate(readings, item_risk, current_distribution)
            elif default_account is not None:
                account = default_account
            else:
                account = {i: item_risk(i, d) for i, d in enumerate(decisions)}
                if fixed_account:
                    default_account = account
        except _UnavailableCalibration as exc:
            unavailable.add(exc.index)
            account = None
        if account is None:
            charges = {}
            for i, decision in enumerate(decisions):
                try:
                    charges[i] = item_risk(i, decision)
                except _UnavailableCalibration:
                    unavailable.add(i)
                    charges[i] = 1.0
            for i in unavailable:
                charges[i] = 1.0
        else:
            charges = account
        binary_charges = []
        for i, charge in charges.items():
            if (isinstance(i, bool) or (not isinstance(i, int) and not isinstance(i, Integral))
                    or not 0 <= i < len(values) or not math.isfinite(charge) or charge < 0):
                raise ValueError("certificate charges must have valid item indices and finite nonnegative values")
            rounded = float(charge)
            if charge > rounded:
                rounded = math.nextafter(rounded, math.inf)
            binary_charges.append(rounded)
        bound = math.inf if account is None else _upper_sum(binary_charges)
        if account is not None and not math.isfinite(bound):
            raise ValueError("certificate charges must have a finite total")
        available = account is not None
        if observe is not None:
            observe(Refinement(list(readings), cost, bound,
                               not available or bound > delta, available))
        if available and bound <= delta:
            break
        if not unavailable and (floor is not None or (certificate is None and additive_floor)):
            fixed = frozenset(i for i in range(len(values)) if levels[i] + 1 >= len(ladders[i]))
            if floor is not None:
                try:
                    if floor(readings, item_risk, fixed) > delta:
                        break
                except _UnavailableCalibration:
                    pass  # An unavailable floor cannot justify early abstention.
            elif _lower_sum([charges[i] for i in fixed]) > delta:
                break
        open_ = [i for i in charges if levels[i] + 1 < len(ladders[i])]
        if not open_:
            break
        if trace is not None or stop is not None:
            state = State(bound, sum(charges[i] for i in open_), cost)
            if trace is not None:
                trace.append(state)
            if stop is not None and stop(state):
                break
        if priority is None:
            i = max(open_, key=charges.__getitem__)
        elif priority is charge_per_cost:
            i = _cost_aware_choice(open_, charges, ladders, levels)
        else:
            def score(i: int) -> float:
                value = priority(i, float(charges[i]), float(ladders[i][levels[i] + 1].cost))
                if math.isnan(value):
                    raise ValueError("climb priority must not be NaN")
                return value
            i = max(open_, key=score)
        levels[i] += 1
        climb(i)
        if default_account is not None:
            try:
                default_account[i] = item_risk(i, decisions[i])
            except _UnavailableCalibration:
                default_account = None
    return Refinement(readings, cost, bound, not available or bound > delta, available)


def stopping_rule(runs: Sequence[tuple[Sequence[State], bool, float]], delta: float,
                  lam: float, width: float = 0.25, *, open_charge: bool = False) -> Stop:
    """A predictive stopping rule (§22.4), fitted on refinement runs of held-out
    inputs, each its trace, whether it answered, and its final cost.

    States are binned by ``log10(bound / delta)`` (unbounded states share a
    bin). The rule abstains in a bin where the fraction of states that went on
    to answer is below ``lam`` times their mean remaining cost: refinement
    there buys less than ``lam`` coverage per unit of compute. Unseen bins
    continue. At a zero target, all unfinished states share the unbounded
    bound bin.
    When ``open_charge`` is set, split finite-bound bins by the fraction of
    the bound charged to open items. With an unbounded account, use the open
    charge relative to the target instead. A zero bound has its own bin.
    """
    if math.isnan(delta) or delta < 0:
        raise ValueError("target must be nonnegative and not NaN")
    if not math.isfinite(width) or width <= 0:
        raise ValueError("bin width must be positive and finite")
    if not math.isfinite(lam) or lam < 0:
        raise ValueError("cost weight must be nonnegative and finite")

    def bound_bin(value: float) -> float:
        if not math.isfinite(value):
            return math.inf
        if delta == 0:
            return math.inf
        if value <= 0:
            return -math.inf
        ratio = value / delta
        if ratio < sys.float_info.min or math.isinf(ratio):
            # Avoid overflow and loss of subnormal precision in the quotient.
            scaled = (math.log10(value) - math.log10(delta)) / width
        else:
            scaled = math.log10(ratio) / width
        return round(scaled) if math.isfinite(scaled) else scaled

    def key(state: State) -> tuple[float, ...]:
        bound = bound_bin(state.bound)
        if not open_charge:
            return (bound,)
        if not math.isfinite(state.bound):
            return (bound, bound_bin(state.open_charge))
        if state.bound <= 0:
            return (bound, -math.inf)
        share = min(1.0, max(0.0, state.open_charge / state.bound))
        scaled = share / width
        return (bound, round(scaled) if math.isfinite(scaled) else scaled)

    stats: dict[tuple[float, ...], list[float]] = {}
    for trace, answered, cost in runs:
        for state in trace:
            entry = stats.setdefault(key(state), [0.0, 0.0, 0.0])
            entry[0] += answered
            entry[1] += 1
            entry[2] += cost - state.cost

    def stop(state: State) -> bool:
        entry = stats.get(key(state))
        return entry is not None and entry[0] < lam * entry[2]

    return stop


def recalibrated(rungs: Sequence[Rung], values: Sequence[Any], labels: torch.Tensor,
                 ) -> list[Rung]:
    """Copies of ``rungs`` calibrated on other held-out data, such as a
    teacher-labeled audit from the deployment distribution."""
    copies = [Rung(r.module) for r in rungs]
    for rung in copies:
        rung.calibrate(values, labels)
    return copies


def certification_possible(budget: int, delta: float, alpha: float) -> bool:
    """Whether a zero-error, full-coverage checking sample could pass (§17.6)."""
    from nca.stats import clopper_pearson_within

    if budget < 0 or not 0 < delta < 1 or not 0 < alpha < 1:
        raise ValueError("requires a nonnegative budget and delta, alpha strictly between 0 and 1")
    return clopper_pearson_within(0, budget, alpha, delta)


def certify(candidates: Sequence[tuple[int, int]], delta: float, alpha: float,
            order: Sequence[int] | None = None) -> list[int]:
    """Fixed-sequence risk control (``NCA.fixed_sequence_le``).

    ``candidates[i]`` gives the number of audit inputs policy ``i`` answered
    and how many of those it got wrong. Policies are tested in ``order``
    (default: as listed), which must be fixed without looking at these
    audit inputs, for example from a separate audit part. Each is declared
    safe when the Clopper–Pearson upper bound on its error rate among
    answered inputs is at most ``delta``; testing stops at the first policy
    not declared safe. Returns the policies declared safe. With probability
    at least ``1 - alpha`` over the audit, *every* returned policy's error
    rate among answered inputs is at most ``delta``, so any of them may be
    deployed, such as the one answering most.
    """
    from nca.stats import clopper_pearson_within

    accepted = []
    for index in order if order is not None else range(len(candidates)):
        answered, wrong = candidates[index]
        if not clopper_pearson_within(wrong, answered, alpha, delta):
            break
        accepted.append(index)
    return accepted


def certification_order(candidates: Sequence[tuple[int, int]], alpha: float) -> list[int]:
    """Policies ordered from most to least likely to be certified, judged on a
    separate audit part: by Clopper–Pearson upper bound, then by inputs
    answered."""
    from nca.stats import clopper_pearson_upper

    return sorted(range(len(candidates)),
                  key=lambda i: (clopper_pearson_upper(candidates[i][1], candidates[i][0], alpha),
                                 -candidates[i][0]))
