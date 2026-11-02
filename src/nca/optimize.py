"""Cost-optimal planning.

``plan_min`` mirrors ``NCA.planMin`` (``lean/NCA/Planning/MinCost.lean``): at every type
it keeps the cheapest candidate plan, where a plan's cost is the sum of its
invocations' declared costs and a ``map`` body is charged once per element of
a sequence of assumed length ``length``. It is proved sound (well-typed, with
the reported cost) and optimal against every searchable plan within the depth
bound (``NCA.planMin_sound``, ``NCA.planMin_optimal``).

``plan_pareto`` extends the recursion to two additive objectives, cost and an
error bound (the union bound of ``NCA.composition_error_le_sum``: a plan's
error is at most the sum of its invocations' failure rates). It keeps every
non-dominated (cost, error) pair at each type, so the cheapest plan meeting an
error target can be selected exactly. It mirrors ``NCA.planPareto``
(``lean/NCA/Planning/Pareto.lean``): every option is a well-typed plan with its reported
cost and error bound, every searchable plan within the depth bound is
dominated by an option, and so ``cheapest_within`` is exact
(``NCA.planPareto_sound``, ``NCA.planPareto_cover``, ``NCA.planPareto_within``).

Higher-order experts (§20) fill their slots with plans for sub-goals from the
slots' inputs. A filling is charged once per call: ``κ + Σ νᵢ · cost(fᵢ) +
Σ cost(argⱼ)``, with ``νᵢ`` the declared worst-case calls, or the expected
calls with ``expected=True``. Cost is monotone in every filling's cost
(``NCA.HPlan.cost_mono``), so cheapest fillings make cheapest plans, and a
filling's frontier scaled by ``νᵢ`` is the frontier of its contribution.
Polymorphic contracts are costed at every instance the planner can apply:
the one a ground goal selects and, for free variables, each instance pattern
search determines, so both planners are exact over those instances, and
``map`` sources include the sequences polymorphic producers make.

An expert whose error depends on its fillings jointly (a cascade) may declare
``assess(fillings) -> (cost, error)``, giving their contribution from audit
data; the Pareto planner then combines frontier fillings with it. That is
exact when the assessment is monotone in each filling's cost and error.
"""

from __future__ import annotations

from collections.abc import Callable, Iterator, Mapping, Sequence
from dataclasses import dataclass
from itertools import product

from nca.abi import Binding, Manifest, Module, TypeId, elem_type, seq_type
from nca.index import ProducerIndex
from nca.planner import (Apply, Given, Map, Plan, _ground_slots_possible, assignments,
                         free_bindings, map_candidates, slot_goals)


def slot_calls(manifest: Manifest, length: int, expected: bool = False) -> list[float]:
    """Calls per invocation to each slot: declared worst case, or expected."""
    calls = manifest.calls
    if expected and manifest.expected_calls is not None:
        calls = manifest.expected_calls
    return [c.at(length) for c in calls]


def _instances(index: ProducerIndex, available: Sequence[TypeId], goal: TypeId,
               fuel: int) -> Iterator[tuple[Module, Binding]]:
    """Each module producing ``goal`` with each binding it may be applied at:
    the one the goal selects (THEORY §2.1), extended, for a contract with
    free variables, by every instance pattern search determines (§2.2)."""
    for _, module, binding in index.candidates(goal, index.size):
        if module.manifest.contract.free:
            if not _ground_slots_possible(index, index.size, module, binding, fuel,
                                          index.memo(index.size)):
                continue
            for full in free_bindings(index, available, module, binding, fuel):
                yield module, full
        else:
            yield module, binding


def _given(available: Sequence[TypeId], goal: TypeId, required: frozenset[int]) -> Given | None:
    """The available input of type ``goal`` meeting ``required``, if any."""
    positions = [k for k, t in enumerate(available) if t == goal]
    return next((Given(goal) if k == positions[0] else Given(goal, k)
                 for k in positions if required <= {k}), None)


def plan_min(modules: Sequence[Module], available: Sequence[TypeId], goal: TypeId,
             length: int, fuel: int = 8, expected: bool = False,
             required: frozenset[int] = frozenset()) -> tuple[Plan, float] | None:
    """The cheapest plan for ``goal`` and its cost (the first among equal costs)
    that uses every available input whose position is in ``required``."""
    index = ProducerIndex(modules)
    memo: dict[tuple[tuple[TypeId, ...], TypeId, int, frozenset[int]],
               tuple[Plan, float] | None] = {}

    def search(avail: tuple[TypeId, ...], t: TypeId, n: int,
               required: frozenset[int] = frozenset()) -> tuple[Plan, float] | None:
        key = (avail, t, n, required)
        if key in memo:
            return memo[key]
        memo[key] = None
        result: tuple[Plan, float] | None = None
        given = _given(avail, t, required) if n > 0 else None
        if given is not None:
            result = (given, 0.0)
        elif n > 0:
            candidates: list[tuple[Plan, float]] = []
            for module, binding in _instances(index, avail, t, n):
                contract = module.manifest.contract.instance(binding)
                fills = [search(inputs, out, n - 1, r) for inputs, out, r in slot_goals(contract)]
                if any(f is None for f in fills):
                    continue
                calls = slot_calls(module.manifest, length, expected)
                slot_cost = sum(c * f[1] for c, f in zip(calls, fills) if f is not None)
                for shares in assignments(required, len(contract.inputs)):
                    subs = [search(avail, i, n - 1, r) for i, r in zip(contract.inputs, shares)]
                    if all(s is not None for s in subs):
                        candidates.append((
                            Apply(module, tuple(s[0] for s in subs if s is not None),
                                  tuple(f[0] for f in fills if f is not None), binding),
                            module.manifest.cost + slot_cost
                            + sum(s[1] for s in subs if s is not None)))
            element_goal = elem_type(t)
            if element_goal is not None:
                for a in map_candidates(index, avail, n):
                    body = search((a,), element_goal, n - 1)
                    source = search(avail, seq_type(a), n - 1, required)
                    if body is not None and source is not None:
                        candidates.append((Map(a, body[0], source[0]),
                                           length * body[1] + source[1]))
            result = min(candidates, key=lambda c: c[1], default=None)
        memo[key] = result
        return result

    return search(tuple(available), goal, fuel, required)


@dataclass(frozen=True)
class Option:
    plan: Plan
    cost: float
    error: float


def _frontier(options: list[Option]) -> list[Option]:
    """Non-dominated options, cheapest first."""
    kept: list[Option] = []
    for option in sorted(options, key=lambda o: (o.cost, o.error)):
        if not kept or option.error < kept[-1].error:
            kept.append(option)
    return kept


def plan_pareto(modules: Sequence[Module], available: Sequence[TypeId], goal: TypeId,
                length: int, errors: Mapping[str, float] | Callable[[Module], float | None],
                fuel: int = 8, expected: bool = False,
                required: frozenset[int] = frozenset()) -> list[Option]:
    """All non-dominated (cost, error bound) plans for ``goal``.

    ``errors`` maps a module's manifest ref to its per-invocation failure rate
    (absent means 0), or is a function giving a module's rate, ``None`` if it
    is unknown; a module with an unknown rate is not used, since no plan
    through it has an error bound (§31.4). Both objectives are additive over invocations, with map
    bodies counted ``length`` times, so combining the frontiers of sub-goals
    and discarding dominated results yields the exact frontier. Every plan
    uses the available inputs whose positions are in ``required``.
    """
    rate = errors if callable(errors) else (lambda m: errors.get(m.manifest.ref, 0.0))
    index = ProducerIndex(modules)
    memo: dict[tuple[tuple[TypeId, ...], TypeId, int, frozenset[int]], list[Option]] = {}

    def search(avail: tuple[TypeId, ...], t: TypeId, n: int,
               required: frozenset[int] = frozenset()) -> list[Option]:
        key = (avail, t, n, required)
        if key in memo:
            return memo[key]
        memo[key] = []
        if n == 0:
            return []
        given = _given(avail, t, required)
        if given is not None:
            memo[key] = [Option(given, 0.0, 0.0)]
            return memo[key]
        options: list[Option] = []
        for module, binding in _instances(index, avail, t, n):
            own_error = rate(module)
            if own_error is None:
                continue
            manifest = module.manifest
            contract = manifest.contract.instance(binding)
            fills = [search(inputs, out, n - 1, r) for inputs, out, r in slot_goals(contract)]
            calls = slot_calls(manifest, length, expected)
            assess = getattr(module, "assess", None)
            for shares in assignments(required, len(contract.inputs)):
                fronts = [search(avail, i, n - 1, r) for i, r in zip(contract.inputs, shares)]
                for filled in product(*fills):
                    slot_cost, slot_error = (assess(filled) if assess is not None else (
                        sum(c * f.cost for c, f in zip(calls, filled)),
                        sum(c * f.error for c, f in zip(calls, filled))))
                    for combo in product(*fronts):
                        options.append(Option(
                            Apply(module, tuple(o.plan for o in combo),
                                  tuple(f.plan for f in filled), binding),
                            manifest.cost + slot_cost + sum(o.cost for o in combo),
                            own_error + slot_error
                            + sum(o.error for o in combo)))
        element_goal = elem_type(t)
        if element_goal is not None:
            for a in map_candidates(index, avail, n):
                for body, source in product(search((a,), element_goal, n - 1),
                                            search(avail, seq_type(a), n - 1, required)):
                    options.append(Option(Map(a, body.plan, source.plan),
                                          length * body.cost + source.cost,
                                          length * body.error + source.error))
        memo[key] = _frontier(options)
        return memo[key]

    return search(tuple(available), goal, fuel, required)


def cheapest_within(frontier: Sequence[Option], max_error: float) -> Option | None:
    """The cheapest option whose error bound is at most ``max_error``."""
    return next((o for o in frontier if o.error <= max_error), None)
