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
from numbers import Integral
from collections.abc import Callable, Sequence
from dataclasses import dataclass, field, replace
from functools import lru_cache
from typing import Any, Literal, overload

import numpy as np
import torch
from torch import nn

from nca.abi import Contract, Module
from nca.native import load

_NATIVE = load("decoding")


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


def _ranked_top(weights: tuple[float, ...], classes: Sequence[int] | None) -> int:
    indices = tuple(range(len(weights))) if classes is None else tuple(classes)
    if (not indices or any(isinstance(i, bool) or not isinstance(i, Integral)
                           or not 0 <= i < len(weights) for i in indices)):
        raise ValueError("classes must contain valid class indices")
    native = getattr(_NATIVE, "row_argmax", None)
    if native is not None:
        values = np.fromiter((weights[i] for i in indices), dtype=np.float64,
                             count=len(indices))
        return int(indices[int(native(values, len(indices))[0])])
    return int(max(indices, key=weights.__getitem__))


@dataclass(frozen=True)
class RankedReading(Sequence[float]):
    """Calibrated probabilities with the expert's original class ordering."""

    probabilities: tuple[float, ...]
    weights: tuple[float, ...]

    def __len__(self) -> int:
        return len(self.probabilities)

    def __getitem__(self, index):
        return self.probabilities[index]

    def top(self, classes: Sequence[int] | None = None) -> int:
        return _ranked_top(self.weights, classes)

    def tolist(self) -> list[float]:
        return list(self.probabilities)


def _temperature_scores(log: torch.Tensor, temperature: float) -> torch.Tensor:
    # Keep a positive binary64 temperature representable for lower-precision inputs.
    if (log.is_floating_point() and log.dtype != torch.float64
            and 0 < temperature < torch.finfo(log.dtype).tiny):
        log = log.double()
    return (log - log.max()) / temperature


@dataclass
class Rung:
    """An expert read through temperatures fitted on held-out labeled inputs:
    one for its full output and one for each restricted decision it serves."""

    module: Module
    temperatures: dict[tuple[int, ...] | None, float] = field(default_factory=dict)
    held_out: tuple[torch.Tensor, torch.Tensor] | None = None

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
        integer_types = (torch.uint8, torch.int8, torch.int16, torch.int32, torch.int64)
        if (not isinstance(labels, torch.Tensor) or labels.ndim != 1
                or labels.dtype not in integer_types or len(values) == 0
                or labels.numel() != len(values)):
            raise ValueError("calibration needs nonempty values and one integer label per value")
        value_snapshot = tuple(values)
        label_snapshot = labels.detach().clone()
        observations = torch.stack([self.observe(v) for v in value_snapshot])
        targets = label_snapshot.to(device=observations.device, dtype=torch.long)
        if bool(((targets < 0) | (targets >= observations.shape[1])).any()):
            raise ValueError("calibration labels must be valid class indices")
        temperature = self._fit(observations, targets)
        self.held_out = (observations, targets)
        self.temperatures = {None: temperature}

    def temperature(self, classes: Decision = None) -> float:
        """Temperature of the decision over ``classes``, fitted on first use on
        the held-out inputs whose label is among them, by the likelihood of
        the label's entry."""
        key = decision_key(classes)
        if key not in self.temperatures:
            if self.held_out is None or key is None:
                return 1.0
            log, labels = self.held_out
            union, positions = _layout(key)
            entry = {union[i]: k for k, part in enumerate(positions) for i in part}
            inside = torch.isin(labels, torch.tensor(union, device=labels.device))
            if not bool(inside.any()):
                if len(positions) == 1:
                    return 1.0  # A single entry has no decision ambiguity.
                raise ValueError("cannot fit decision temperature without matching held-out labels")
            targets = torch.tensor([entry[int(y)] for y in labels[inside]], dtype=torch.long,
                                   device=labels.device)
            self.temperatures[key] = self._fit(log[inside][:, union], targets, positions)
        return self.temperatures[key]

    def reading(self, log: torch.Tensor | RankedObservation) -> torch.Tensor:
        """Numerical probabilities; ranked ordering remains on the observation."""
        temperature = self.temperature()
        if isinstance(log, RankedObservation):
            if not math.isfinite(temperature) or temperature <= 0:
                raise ValueError("ranked reading requires a positive finite temperature")
            log = log.logits
        result = torch.softmax(_temperature_scores(log, temperature), dim=-1)
        return result.to(log.dtype) if log.is_floating_point() else result

    def risk(self, log: torch.Tensor | RankedObservation, classes: Decision = None, *,
             reading: torch.Tensor | None = None) -> float:
        """Calibrated error probability of the decision over ``classes``.

        A ranked observation chooses the winning class by its original weights;
        a tensor chooses from its numerical reading. Consumers must use the
        same choice: the numerical reading can contain ties. The optional
        ``reading`` reuses the numerical reading of this observation.
        """
        key = decision_key(classes)
        temperature = self.temperature(key)
        ranked = log if isinstance(log, RankedObservation) else None
        if ranked is not None:
            log = ranked.logits
            if not math.isfinite(temperature) or temperature <= 0:
                raise ValueError("ranked risk requires a positive finite temperature")
        union = list(range(len(log))) if key is None else _layout(key)[0]
        probabilities = (self.reading(log) if reading is None else reading) if ranked is None else None
        native_reading = getattr(_NATIVE, "calibrated_risk_for_reading", None)
        if (native_reading is not None and log.device.type == "cpu" and not log.requires_grad
                and (ranked is not None or (probabilities.device.type == "cpu"
                                            and not probabilities.requires_grad))):
            native_key = key if key is not None else tuple(range(len(log)))
            _, positions = _layout(native_key)
            groups = _group_ids(native_key)
            ordering = (np.asarray(ranked.weights, dtype=np.float64) if ranked is not None else
                        probabilities.double().numpy())
            logits = log.double().numpy()
            if classes is None:
                logits = np.ascontiguousarray(logits)
                ordering = np.ascontiguousarray(ordering)
            else:
                indices = _native_indices(key)
                logits, ordering = logits[indices], ordering[indices]
            return float(native_reading(logits, ordering, groups, len(positions),
                                        temperature))
        if ranked is not None:
            selected = union.index(ranked.top(union))
        else:
            selected = int(probabilities[union].argmax())
        native = getattr(_NATIVE, "calibrated_risk_at", None)
        if native is not None and log.device.type == "cpu" and not log.requires_grad:
            native_key = key if key is not None else tuple(range(len(log)))
            union, positions = _layout(native_key)
            groups = _group_ids(native_key)
            return float(native(log[union].double().numpy(), groups, len(positions),
                                temperature, selected))
        if classes is None:
            values, positions = log, None
        else:
            union, positions = _layout(key)
            values = log[union]
        result = risk(torch.softmax(_temperature_scores(values, temperature), dim=-1),
                      positions, _top=selected)
        if result != 0.0:
            return result
        # A float32 softmax can erase probabilities that fit in binary64.
        scores = values.double()
        scores = (scores - scores.max()) / temperature
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

    def distribution(self, log: torch.Tensor | RankedObservation, classes: Decision = None) -> torch.Tensor:
        """Calibrated probabilities of the decision's entries: each entry's
        share of the classes it ranges over, under the decision's temperature."""
        if isinstance(log, RankedObservation):
            temperature = self.temperature(classes)
            if not math.isfinite(temperature) or temperature <= 0:
                raise ValueError("ranked distribution requires a positive finite temperature")
            log = log.logits
        if classes is None:
            return self.reading(log)
        union, positions = _layout(decision_key(classes))
        native = getattr(_NATIVE, "calibrated_groups", None)
        groups = _group_ids(decision_key(classes))
        if native is not None and log.device.type == "cpu" and not log.requires_grad:
            values = native(log[union].double().numpy(), groups,
                            len(positions), self.temperature(classes))
            return torch.tensor(values, dtype=log.dtype)
        values = log[union]
        reading = torch.softmax(_temperature_scores(values, self.temperature(classes)), dim=-1)
        if log.is_floating_point():
            reading = reading.to(log.dtype)
        return torch.stack([reading[part].sum() for part in positions])

    @staticmethod
    def _fit(log: torch.Tensor, labels: torch.Tensor,
             entries: Sequence[Sequence[int]] | None = None) -> float:
        """The temperature minimizing negative log-likelihood of the labels,
        each label naming an entry (a group of columns) when ``entries`` is given."""
        grouped = entries is not None and any(len(e) > 1 for e in entries)

        def nll(t: float) -> float:
            scaled = torch.log_softmax(log / t, dim=-1)
            if grouped:
                scaled = torch.stack([scaled[:, list(e)].logsumexp(dim=-1) for e in entries],
                                     dim=-1)
            return nn.functional.nll_loss(scaled, labels).item()

        return float(min(np.geomspace(0.1, 8.0, 120), key=nll))


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
    if classes is None:
        top = int(reading.argmax()) if _top is None else _top
        outside = torch.cat((reading[:top], reading[top + 1:]))
        return (outside.sum() / reading.sum()).item()
    key = decision_key(classes)
    union, positions = _layout(key)
    mass = reading[union]
    top = int(mass.argmax()) if _top is None else union.index(_top)
    chosen = next(part for part in positions if top in part)
    selected = set(chosen)
    outside = [i for i in range(len(union)) if i not in selected]
    return (mass[outside].sum() / mass.sum()).item()


@dataclass(frozen=True)
class Distribution:
    """Calibrated probabilities with optional per-item revision identities.

    A revision identifies the observation and calibration within its source.
    Adapters may share a source token when they preserve that identity.
    Consumers without revision support may call this like any other function.
    """

    lookup: Callable[[int, Decision], torch.Tensor]
    revision: Callable[[int], int]
    source: object = field(default_factory=object, compare=False, repr=False)

    def __call__(self, i: int, decision: Decision) -> torch.Tensor:
        return self.lookup(i, decision)


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

    Priorities guide refinement only; their age does not affect the total
    charge (THEORY 23.11). Zero priorities receive a uniform allocation.
    """
    if not math.isfinite(bound) or bound < 0:
        raise ValueError("bound must be finite and nonnegative")
    if not priorities:
        raise ValueError("risk allocation requires at least one item")
    if any(not math.isfinite(p) or p < 0 for p in priorities):
        raise ValueError("priorities must be finite and nonnegative")
    native = getattr(_NATIVE, "risk_shares", None)
    if native is not None:
        return native(bound, np.asarray(priorities, dtype=np.float64))
    scale = max(priorities)
    weights = [p / scale for p in priorities] if scale > 0 else [1.0] * len(priorities)
    total = math.fsum(weights)
    return [bound * (w / total) for w in weights]


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
    risks: list[tuple[DecisionKey, float] | dict[DecisionKey, float] | None] = [None] * len(values)
    distributions: list[tuple[DecisionKey, torch.Tensor] | dict[DecisionKey, torch.Tensor] | None] = [None] * len(values)
    cost = 0.0

    def climb(i: int) -> None:
        nonlocal cost
        rung = ladders[i][levels[i]]
        risks[i] = None
        distributions[i] = None
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
            return cache[1]
        if isinstance(cache, dict) and key in cache:
            return cache[key]
        result = ladders[i][levels[i]].risk(
            logs[i], decision, reading=readings[i] if isinstance(readings[i], torch.Tensor) else None)
        if cache is None:
            risks[i] = (key, result)
        elif isinstance(cache, tuple):
            risks[i] = {cache[0]: cache[1], key: result}
        else:
            cache[key] = result
        return result

    def item_distribution(i: int, decision: Decision) -> torch.Tensor:
        key = decision_key(decision)
        cache = distributions[i]
        if isinstance(cache, tuple) and cache[0] == key:
            return cache[1]
        if isinstance(cache, dict) and key in cache:
            return cache[key]
        result = ladders[i][levels[i]].distribution(logs[i], decision)
        if cache is None:
            distributions[i] = (key, result)
        elif isinstance(cache, tuple):
            distributions[i] = {cache[0]: cache[1], key: result}
        else:
            cache[key] = result
        return result

    current_distribution = Distribution(item_distribution, levels.__getitem__)

    for i in range(len(values)):
        climb(i)
        while levels[i] < min(start, len(ladders[i]) - 1):
            levels[i] += 1
            climb(i)
    default_account = ({i: item_risk(i, decision) for i, decision in enumerate(decisions)}
                       if certificate is None and all(map(_fixed_decision, decisions)) else None)
    while True:
        account = (certificate(readings, item_risk, current_distribution) if certificate is not None
                   else default_account if default_account is not None
                   else {i: item_risk(i, d) for i, d in enumerate(decisions)})
        if account is None:
            charges = {i: item_risk(i, d) for i, d in enumerate(decisions)}
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
        if floor is not None or (certificate is None and additive_floor):
            fixed = frozenset(i for i in range(len(values)) if levels[i] + 1 >= len(ladders[i]))
            if floor is not None and floor(readings, item_risk, fixed) > delta:
                break
            if floor is None and _lower_sum([charges[i] for i in fixed]) > delta:
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
            default_account[i] = item_risk(i, decisions[i])
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
