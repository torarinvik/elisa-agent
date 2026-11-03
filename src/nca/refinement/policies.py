"""Scheduling, stopping and certification policies for budgeted refinement.

The nca.ladder API re-exports these policies. Their implementation depends on
refinement state and declared costs, independently of numerical reader backends.
"""
from __future__ import annotations

import math
import sys
from collections.abc import Callable, Sequence
from dataclasses import dataclass
from typing import TYPE_CHECKING

if TYPE_CHECKING:
    from nca.ladder import Rung


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


def certification_possible(budget: int, delta: float, alpha: float) -> bool:
    """Whether a zero-error, full-coverage checking sample could pass (§17.6)."""
    from nca.stats import clopper_pearson_within

    if budget < 0 or not 0 < delta < 1 or not 0 < alpha < 1:
        raise ValueError("requires a nonnegative budget and delta, alpha strictly between 0 and 1")
    return clopper_pearson_within(0, budget, alpha, delta)


INFLATIONS = (4.0, 2.0, 1.5, 1.25, 1.0, 0.75, 0.5)
"""Candidate policies for ``certify``: refinement targets ``δ / λ`` for these
inflation factors ``λ``; below 1 a policy answers above its bound."""


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
