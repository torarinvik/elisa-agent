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
(``NCA.selective_risk_le``), and refining where the bound falls most per unit
of compute is the ``NCA.threshold_optimal`` rule; with a floor ``ρ`` per item,
``n`` items need ``n · ρ ≤ δ`` (``NCA.length_limit``).

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
from collections.abc import Callable, Sequence
from dataclasses import dataclass, field, replace
from functools import cache
from typing import Any

import numpy as np
import torch
from torch import nn

from nca.abi import Contract
from nca.registry import Module


Decision = Sequence[int | Sequence[int]] | None
"""What a decision chooses among: ``None`` for all classes; otherwise entries,
each a class or a group of classes. The decision picks the entry holding the
most probable of the classes listed."""

DecisionKey = tuple[int | tuple[int, ...], ...] | None


def decision_key(decision: Decision) -> DecisionKey:
    if decision is None:
        return None
    return tuple(e if isinstance(e, int) else tuple(e) for e in decision)


@cache
def _layout(key: tuple[int | tuple[int, ...], ...]) -> tuple[list[int], list[list[int]]]:
    """The classes a decision ranges over, and each entry's positions among them."""
    parts = [[e] if isinstance(e, int) else list(e) for e in key]
    union = [c for part in parts for c in part]
    return union, [[union.index(c) for c in part] for part in parts]


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
        """Log-probabilities of the expert's output."""
        return torch.tensor(self.module.invoke(value)).clamp_min(1e-12).log()

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
        if classes is None:
            return risk(self.reading(log))
        union, positions = _layout(decision_key(classes))
        return risk(torch.softmax(log[union] / self.temperature(classes), dim=-1), positions)

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


def risk(reading: torch.Tensor, classes: Decision = None) -> float:
    """Error probability of the decision over ``classes`` (all if ``None``):
    one minus the share of the chosen entry, the one holding the most
    probable class listed."""
    if classes is None:
        return 1.0 - (reading.max() / reading.sum()).item()
    union, positions = _layout(decision_key(classes))
    mass = reading[union]
    top = int(mass.argmax())
    chosen = next(part for part in positions if top in part)
    return 1.0 - (mass[chosen].sum() / mass.sum()).item()


Certificate = Callable[[Sequence[torch.Tensor], Callable[[int, Decision], float]],
                       dict[int, float] | None]
"""``certificate(readings, risk)``: a risk account for the current readings,
each charged item's charge, computed with ``risk(i, decision)``; the charges
sum to a bound on the answer's error probability. ``None`` if the readings
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


def refine(values: Sequence[Any], ladders: Sequence[Sequence[Rung]], delta: float,
           start: int = 0, classes: Sequence[Decision] | None = None,
           certificate: Certificate | None = None, floor: Floor | None = None,
           additive_floor: bool = False, stop: Stop | None = None,
           trace: list[State] | None = None) -> Refinement:
    """Read ``values[i]`` with ``ladders[i]``, refining until the bound meets ``delta``.

    Every item starts at rung ``min(start, top)``, reading each rung below it.
    The bound sums the charges of ``certificate``'s account; by default every
    item ``i`` is charged the risk of decision ``classes[i]``. While it exceeds
    ``delta`` the open item with the largest charge climbs a rung; if the
    readings determine no answer, the riskiest item.
    """
    decisions = list(classes) if classes is not None else [None] * len(values)
    levels = [0] * len(values)
    logs: list[torch.Tensor] = [torch.empty(0)] * len(values)
    readings: list[torch.Tensor] = [torch.empty(0)] * len(values)
    risks: dict[tuple[int, int, DecisionKey], float] = {}
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

    for i in range(len(values)):
        climb(i)
        while levels[i] < min(start, len(ladders[i]) - 1):
            levels[i] += 1
            climb(i)
    while True:
        account = (certificate(readings, item_risk) if certificate is not None
                   else {i: item_risk(i, d) for i, d in enumerate(decisions)})
        if account is None:
            charges, bound = {i: item_risk(i, d) for i, d in enumerate(decisions)}, math.inf
        else:
            charges, bound = account, sum(account.values())
        if bound <= delta:
            break
        fixed = frozenset(i for i in range(len(values)) if levels[i] + 1 >= len(ladders[i]))
        if floor is not None and floor(readings, item_risk, fixed) > delta:
            break
        if (floor is None and certificate is None and additive_floor
                and sum(charges[i] for i in fixed) > delta):
            break
        open_ = [i for i in charges if levels[i] + 1 < len(ladders[i])]
        if not open_:
            break
        state = State(bound, sum(charges[i] for i in open_), cost)
        if trace is not None:
            trace.append(state)
        if stop is not None and stop(state):
            break
        i = max(open_, key=charges.__getitem__)
        levels[i] += 1
        climb(i)
    return Refinement(readings, cost, bound, bound > delta)


def stopping_rule(runs: Sequence[tuple[Sequence[State], bool, float]], delta: float,
                  lam: float, width: float = 0.25) -> Stop:
    """A predictive stopping rule (§22.4), fitted on refinement runs of held-out
    inputs, each its trace, whether it answered, and its final cost.

    States are binned by ``log10(bound / delta)`` (unbounded states share a
    bin). The rule abstains in a bin where the fraction of states that went on
    to answer is below ``lam`` times their mean remaining cost: refinement
    there buys less than ``lam`` coverage per unit of compute. Unseen bins
    continue.
    """
    def key(state: State) -> float:
        if not math.isfinite(state.bound):
            return math.inf
        return round(math.log10(max(state.bound, 1e-12) / delta) / width)

    stats: dict[float, list[float]] = {}
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
    from nca.stats import clopper_pearson_upper

    accepted = []
    for index in order if order is not None else range(len(candidates)):
        answered, wrong = candidates[index]
        if clopper_pearson_upper(wrong, answered, alpha) > delta:
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
