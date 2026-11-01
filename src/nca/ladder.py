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
from functools import cache
from typing import Any

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


def decision_key(decision: Decision) -> DecisionKey:
    if decision is None:
        return None
    if (type(decision) is tuple and
            all(type(entry) is int or type(entry) is tuple for entry in decision)):
        return decision
    return tuple(e if isinstance(e, int) else tuple(e) for e in decision)


@cache
def _layout(key: tuple[int | tuple[int, ...], ...]) -> tuple[list[int], list[list[int]]]:
    """The classes a decision ranges over, and each entry's positions among them."""
    parts = [[e] if isinstance(e, int) else list(e) for e in key]
    union = [c for part in parts for c in part]
    return union, [[union.index(c) for c in part] for part in parts]


@cache
def _group_ids(key: tuple[int | tuple[int, ...], ...]) -> np.ndarray | None:
    """Read-only native group metadata for a partitioned decision."""
    union, positions = _layout(key)
    if sorted(k for part in positions for k in part) != list(range(len(union))):
        return None
    groups = np.empty(len(union), dtype=np.int64)
    for entry, part in enumerate(positions):
        groups[part] = entry
    groups.setflags(write=False)
    return groups


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
        output = self.module.invoke(value)
        native = getattr(_NATIVE, "observation_logs", None)
        array = None
        if isinstance(output, (tuple, list, np.ndarray)):
            try:
                array = np.asarray(output, dtype=np.float64)
            except (TypeError, ValueError, RuntimeError):
                pass  # Some valid tensor-containing sequences require PyTorch conversion.
        if array is not None:
            if array.ndim != 1:
                raise ValueError("expert output must be a one-dimensional weight vector")
            array = np.ascontiguousarray(array)
            if native is not None:
                logs = native(array)
                if not logs:
                    raise ValueError("expert output must contain finite nonnegative weights with positive mass")
                return torch.tensor(logs, dtype=torch.float64)
        probabilities = torch.tensor(array if array is not None else output, dtype=torch.float64)
        if probabilities.ndim != 1:
            raise ValueError("expert output must be a one-dimensional weight vector")
        valid = (bool(torch.isfinite(probabilities).all()) and
                 not bool((probabilities < 0).any()) and
                 bool((probabilities > 0).any()))
        if not valid:
            raise ValueError("expert output must contain finite nonnegative weights with positive mass")
        return probabilities.clamp_min(math.nextafter(0.0, 1.0)).log()

    def calibrate(self, values: Sequence[Any], labels: torch.Tensor) -> None:
        """Keep held-out observations and fit the full output's temperature."""
        self.held_out = (torch.stack([self.observe(v) for v in values]), labels)
        self.temperatures = {None: self._fit(*self.held_out)}

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
            inside = torch.isin(labels, torch.tensor(union))
            targets = torch.tensor([entry[int(y)] for y in labels[inside]])
            self.temperatures[key] = self._fit(log[inside][:, union], targets, positions)
        return self.temperatures[key]

    def reading(self, log: torch.Tensor) -> torch.Tensor:
        return torch.softmax(log / self.temperature(), dim=-1)

    def risk(self, log: torch.Tensor, classes: Decision = None) -> float:
        """Calibrated error probability of the decision over ``classes``."""
        native = getattr(_NATIVE, "calibrated_risk", None)
        if native is not None and log.device.type == "cpu" and not log.requires_grad:
            key = decision_key(classes) if classes is not None else tuple(range(len(log)))
            union, positions = _layout(key)
            groups = _group_ids(key)
            if groups is not None:
                return float(native(log[union].double().numpy(), groups, len(positions),
                                    self.temperature(classes)))
        if classes is None:
            values, positions = log, None
        else:
            key = decision_key(classes)
            union, positions = _layout(key)
            values = log[union]
        temperature = self.temperature(classes)
        result = risk(torch.softmax(values / temperature, dim=-1), positions)
        if result != 0.0 or (classes is not None and _group_ids(key) is None):
            return result
        # A float32 softmax can erase probabilities that fit in binary64.
        scores = values.double() / temperature
        top = int(scores.argmax())
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

    def distribution(self, log: torch.Tensor, classes: Decision = None) -> torch.Tensor:
        """Calibrated probabilities of the decision's entries: each entry's
        share of the classes it ranges over, under the decision's temperature."""
        if classes is None:
            return self.reading(log)
        union, positions = _layout(decision_key(classes))
        native = getattr(_NATIVE, "calibrated_groups", None)
        groups = _group_ids(decision_key(classes))
        if (native is not None and log.device.type == "cpu" and not log.requires_grad
                and groups is not None):
            values = native(log[union].double().numpy(), groups,
                            len(positions), self.temperature(classes))
            return torch.tensor(values, dtype=log.dtype)
        reading = torch.softmax(log[union] / self.temperature(classes), dim=-1)
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
    readings: list[torch.Tensor]
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


def risk(reading: torch.Tensor, classes: Decision = None) -> float:
    """Error probability of the decision over ``classes`` (all if ``None``):
    the share outside the entry holding the most probable class listed."""
    if classes is None:
        top = int(reading.argmax())
        outside = torch.cat((reading[:top], reading[top + 1:]))
        return (outside.sum() / reading.sum()).item()
    key = decision_key(classes)
    union, positions = _layout(key)
    mass = reading[union]
    top = int(mass.argmax())
    chosen = next(part for part in positions if top in part)
    if _group_ids(key) is None:
        return 1.0 - (mass[chosen].sum() / mass.sum()).item()
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


Certificate = Callable[[Sequence[torch.Tensor], Callable[[int, Decision], float],
                        Callable[[int, Decision], torch.Tensor]], dict[int, float] | None]
"""``certificate(readings, risk, distribution)``: a risk account for the
current readings, each charged item's finite nonnegative charge, computed with
``risk(i, decision)`` and the calibrated entry probabilities
``distribution(i, decision)``; the charges sum to a bound on the answer's
error probability. Keys identify refined items. ``None`` if the readings
determine no answer."""


Floor = Callable[[Sequence[torch.Tensor], Callable[[int, Decision], float], frozenset[int]],
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
           priority: ClimbPriority | None = None) -> Refinement:
    """Read ``values[i]`` with ``ladders[i]``, refining until the bound meets ``delta``.

    Every item starts at rung ``min(start, top)``, reading each rung below it.
    The bound sums the charges of ``certificate``'s account; by default every
    item ``i`` is charged the risk of decision ``classes[i]``. While it exceeds
    ``delta`` the open item with the largest charge climbs a rung; if the
    readings determine no answer, the riskiest item. A supplied ``priority``
    instead ranks open items using their index, charge and next invocation
    cost; it must not mutate the refinement state. ``observe`` receives each
    state, including the initial and terminal states, with an independent
    outer reading list. Observers must not mutate the reading tensors.
    """
    if math.isnan(delta) or delta < 0:
        raise ValueError("target must be nonnegative and not NaN")
    decisions = list(classes) if classes is not None else [None] * len(values)
    levels = [0] * len(values)
    logs: list[torch.Tensor] = [torch.empty(0)] * len(values)
    readings: list[torch.Tensor] = [torch.empty(0)] * len(values)
    risks: dict[tuple[int, int, DecisionKey], float] = {}
    distributions: dict[tuple[int, int, DecisionKey], torch.Tensor] = {}
    cost = 0.0

    def climb(i: int) -> None:
        nonlocal cost
        rung = ladders[i][levels[i]]
        logs[i] = rung.observe(values[i])
        readings[i] = rung.reading(logs[i])
        cost += rung.cost

    def item_risk(i: int, decision: Decision) -> float:
        key = (i, levels[i], decision_key(decision))
        if key not in risks:
            risks[key] = ladders[i][levels[i]].risk(logs[i], decision)
        return risks[key]

    def item_distribution(i: int, decision: Decision) -> torch.Tensor:
        key = (i, levels[i], decision_key(decision))
        if key not in distributions:
            distributions[key] = ladders[i][levels[i]].distribution(logs[i], decision)
        return distributions[key]

    current_distribution = Distribution(item_distribution, levels.__getitem__)

    for i in range(len(values)):
        climb(i)
        while levels[i] < min(start, len(ladders[i]) - 1):
            levels[i] += 1
            climb(i)
    while True:
        account = (certificate(readings, item_risk, current_distribution) if certificate is not None
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
        fixed = frozenset(i for i in range(len(values)) if levels[i] + 1 >= len(ladders[i]))
        if floor is not None and floor(readings, item_risk, fixed) > delta:
            break
        if floor is None and certificate is None and additive_floor:
            if _lower_sum([charges[i] for i in fixed]) > delta:
                break
        open_ = [i for i in charges if levels[i] + 1 < len(ladders[i])]
        if not open_:
            break
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
