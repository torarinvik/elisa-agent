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

``Calibrated`` installs a rung as an expert that outputs its calibrated
distribution and reports the risk of deciding by it, so any route can
charge it per input (§33).

A rung's temperatures are evidence about its expert, not part of it:
``calibration`` states them as an attestation about the expert's reference,
and ``attested`` reads one back into a rung (§28.4).
"""

from __future__ import annotations

import math
from numbers import Integral
from collections.abc import Callable, Sequence
from dataclasses import dataclass, field, replace
from functools import lru_cache
from typing import Any

import numpy as np
import torch

from nca.abi import Contract, Module
from nca.effects import invoke_scoped
from nca.refinement.policies import (
    INFLATIONS as INFLATIONS,
    ClimbPriority as ClimbPriority,
    State as State,
    Stop as Stop,
    _cost_aware_choice as _cost_aware_choice,
    _ratio_greater as _ratio_greater,
    certification_order as certification_order,
    certification_possible as certification_possible,
    certify as certify,
    charge_per_cost as charge_per_cost,
    stopping_rule as stopping_rule,
)
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
        readings = [invoke_scoped(self.module, v) for v in (value, *self.views(value))]
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


def ladder(modules: Sequence[Module], contract: Contract) -> list[Rung]:
    """Rungs for every module with ``contract``, cheapest first."""
    found = [m for m in modules if m.manifest.contract == contract]
    return [Rung(m) for m in sorted(found, key=lambda m: m.manifest.cost)]


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


CALIBRATION = "calibration"


from nca.ladder.rungs import (
    Rung as Rung,
)

from nca.ladder.engine import (
    Refinement as Refinement,
    refine as refine,
)

from nca.ladder.budgets import (
    _upper_sum as _upper_sum,
    _lower_values as _lower_values,
    _lower_sum as _lower_sum,
    allocate_risk as allocate_risk,
)

from nca.ladder.attestations import (
    recalibrated as recalibrated,
    Calibrated as Calibrated,
    calibration as calibration,
    attested as attested,
)
