"""Symbolic capability planners.

``plan`` mirrors ``NCA.plan`` (``lean/NCA/Planner.lean``), proved sound and
complete. ``plan_stable`` mirrors ``NCA.planStable`` (``lean/NCA/Routing.lean``),
which is additionally proved stable: installing modules never changes the
route of an already solvable task. ``NCA.plan_not_stable`` shows ``plan``
alone lacks that property.

Available types are an ordered sequence, as in the Lean model, because their
order determines the order in which ``map`` candidates are tried.

A module whose contract declares slots (a higher-order expert, ``NCA.HPlan``)
is applied with one plan per slot, planned as a sub-goal whose only available
inputs are the slot's inputs, like a ``map`` body.

A polymorphic contract is applied at the one instance whose output is the goal
(THEORY §2.1, ``NCA.Contract.subst_determined``), found by matching. Variables
the goal leaves free are determined by solving the inputs as pattern goals
with unification (THEORY §2.2, ``NCA.answer_sound``).
"""

from __future__ import annotations

from collections.abc import Iterator
from dataclasses import dataclass
from typing import Sequence, Union

from nca.abi import (App, Binding, Contract, Module, Term, TypeId, Var, elem_type, format_type,
                     parse_type, resolve, seq_type, type_variables, unify)
from nca.index import ProducerIndex, rename_apart


@dataclass(frozen=True)
class Given:
    type_id: TypeId


@dataclass(frozen=True)
class Apply:
    module: Module
    args: tuple["Plan", ...]
    slots: tuple["Plan", ...] = ()
    """One plan per slot of the module's contract, each from the slot's inputs."""
    binding: Binding = ()
    """The instance of a polymorphic contract that is applied (THEORY §2.1)."""

    @property
    def contract(self) -> Contract:
        """The applied instance of the module's contract."""
        return self.module.manifest.contract.instance(self.binding)


@dataclass(frozen=True)
class Map:
    """Run ``body`` on each element (of type ``element``) of ``source``."""

    element: TypeId
    body: "Plan"
    source: "Plan"


Plan = Union[Given, Apply, Map]
Memo = dict[tuple[tuple[TypeId, ...], TypeId, int], Union[Given, Apply, Map, None]]


def output_type(node: Plan) -> TypeId:
    if isinstance(node, Given):
        return node.type_id
    if isinstance(node, Apply):
        return node.contract.output
    return seq_type(output_type(node.body))


def elem_candidates(modules: Sequence[Module], available: Sequence[TypeId]) -> list[TypeId]:
    """Element types of the available sequence types and of the ground sequence
    types modules produce, in that order."""
    outputs = [m.manifest.contract.output for m in modules if not m.manifest.contract.polymorphic]
    return [e for t in (*available, *outputs) if (e := elem_type(t)) is not None]


def _plan(index: ProducerIndex, limit: int, available: Sequence[TypeId], goal: TypeId,
          fuel: int, memo: Memo | None = None) -> Plan | None:
    """The planner, memoized on ``(available, goal, fuel)`` per library prefix,
    across calls on the same index (Theorem 12.18).

    Producers with a non-sequence input outside the forward closure are skipped,
    as in ``NCA.planPruned``, which is proved to return exactly ``NCA.plan``
    given the closure oracle (``NCA.planPruned_eq``, ``NCA.derivable_closure``).

    Planning is a pure function of those arguments for a fixed index and limit,
    so memoization returns exactly what recomputation would; it bounds the work
    by the number of distinct subgoals instead of the number of search paths.
    """
    memo = index.memo(limit) if memo is None else memo
    key = (tuple(available), goal, fuel)
    if key not in memo:
        memo[key] = _search(index, limit, available, goal, fuel, memo)
    return memo[key]


def _plan_all(index: ProducerIndex, limit: int,
              goals: Sequence[tuple[Sequence[TypeId], TypeId]], fuel: int,
              memo: Memo) -> tuple[Plan, ...] | None:
    """Plans for every ``(available, goal)`` sub-goal at depth ``fuel - 1``."""
    found = []
    for available, goal in goals:
        sub = _plan(index, limit, available, goal, fuel - 1, memo)
        if sub is None:
            return None
        found.append(sub)
    return tuple(found)


def _search(index: ProducerIndex, limit: int, available: Sequence[TypeId], goal: TypeId,
            fuel: int, memo: Memo) -> Plan | None:
    if fuel == 0:
        return None
    if goal in available:
        return Given(goal)
    reach = index.reachable(available, limit)
    for position, module, binding in index.candidates(goal, limit):
        if binding:
            contract = module.manifest.contract.instance(binding)
            needs = frozenset(i for i in contract.inputs
                              if elem_type(i) is None and not type_variables(parse_type(i)))
            if not index.satisfiable(needs, reach, limit):
                continue
        else:
            contract = module.manifest.contract
            if not index.needs[position] <= reach:
                continue
        if contract.free:
            found = _apply_free(index, limit, available, module, binding, fuel, memo)
            if found is not None:
                return found
            continue
        args = _plan_all(index, limit, [(available, t) for t in contract.inputs], fuel, memo)
        if args is None:
            continue
        slots = _plan_all(index, limit, list(contract.slots), fuel, memo)
        if slots is not None:
            return Apply(module, args, slots, binding)
    element_goal = elem_type(goal)
    if element_goal is None:
        return None
    candidates, order = index.element_candidates(available, limit)
    sources = index.sources(element_goal, limit)
    if sources is not None:
        candidates = sorted((a for a in sources if a in order), key=order.__getitem__)
    made = index.seq_elements(available, limit)
    for element in candidates:
        if made is not None and element not in made and elem_type(element) is None:
            continue
        if not index.may_derive((element,), parse_type(element_goal), limit):
            continue
        body = _plan(index, limit, (element,), element_goal, fuel - 1, memo)
        source = _plan(index, limit, available, seq_type(element), fuel - 1, memo)
        if body is not None and source is not None:
            return Map(element, body, source)
    return None



@dataclass(frozen=True)
class _Open:
    """An application found for a pattern goal, before the answer substitution
    is known: the module, its argument plans, and its variables' names in the
    search (renamed apart)."""

    module: Module
    args: tuple["_Partial", ...]
    renaming: tuple[tuple[str, str], ...]
    fuel: int


@dataclass(frozen=True)
class _OpenMap:
    element: TypeId
    body: "_Partial"
    source: Plan


_Partial = Union[Plan, _Open, _OpenMap]
def _solutions(index: ProducerIndex, limit: int, available: Sequence[TypeId], pattern: Term,
               binding: dict[str, Term], fuel: int, memo: Memo,
               ) -> Iterator[tuple[_Partial, dict[str, Term]]]:
    """Plans producing instances of ``pattern`` under ``binding``, with the
    binding each extends, in search order (THEORY §2.2)."""
    if fuel == 0:
        return
    goal = resolve(pattern, binding)
    if not type_variables(goal):
        found = _plan(index, limit, available, format_type(goal), fuel, memo)
        if found is not None:
            yield found, binding
        return
    for type_id in available:
        extended = dict(binding)
        if unify(goal, parse_type(type_id), extended):
            yield Given(type_id), extended
    for position in index.pattern_candidates(available, goal, limit):
        module = index.modules[position]
        renaming, contract = rename_apart(module.manifest.contract, ())
        extended = dict(binding)
        if not unify(goal, parse_type(contract.output), extended):
            continue
        names = tuple(renaming.items())
        for args, solved in _solve_inputs(index, limit, available, contract.inputs, extended,
                                          fuel, memo):
            yield _Open(module, args, names, fuel), solved
    if isinstance(goal, App) and goal.name == "seq" and len(goal.args) == 1:
        candidates, order = index.element_candidates(available, limit)
        body_goal = resolve(goal.args[0], binding)
        if not type_variables(body_goal):
            sources = index.sources(format_type(body_goal), limit)
            if sources is not None:
                candidates = sorted((a for a in sources if a in order), key=order.__getitem__)
        made = index.seq_elements(available, limit)
        for element in candidates:
            if made is not None and element not in made and elem_type(element) is None:
                continue
            if not index.may_derive((element,), body_goal, limit):
                continue
            source = _plan(index, limit, available, seq_type(element), fuel - 1, memo)
            if source is None:
                continue
            for body, solved in _solutions(index, limit, (element,), goal.args[0], binding,
                                           fuel - 1, memo):
                yield _OpenMap(element, body, source), solved


def _solve_inputs(index: ProducerIndex, limit: int, available: Sequence[TypeId],
                  inputs: Sequence[TypeId], binding: dict[str, Term], fuel: int, memo: Memo,
                  ) -> Iterator[tuple[tuple[_Partial, ...], dict[str, Term]]]:
    """Solutions for every input in turn, backtracking over earlier inputs'
    alternatives."""
    if not inputs:
        yield (), binding
        return
    for first, extended in _solutions(index, limit, available, parse_type(inputs[0]), binding,
                                      fuel - 1, memo):
        for rest, solved in _solve_inputs(index, limit, available, inputs[1:], extended, fuel,
                                          memo):
            yield (first, *rest), solved


def _close(index: ProducerIndex, limit: int, node: _Partial, binding: dict[str, Term],
           memo: Memo) -> Plan | None:
    """``node`` with the answer substitution applied, its slots planned; ``None``
    if a variable is undetermined (the candidate is ambiguous) or a slot has no
    plan."""
    if isinstance(node, _OpenMap):
        body = _close(index, limit, node.body, binding, memo)
        return None if body is None else Map(node.element, body, node.source)
    if not isinstance(node, _Open):
        return node
    values = {v: resolve(Var(r), binding) for v, r in node.renaming}
    if any(type_variables(t) for t in values.values()):
        return None
    args = [_close(index, limit, a, binding, memo) for a in node.args]
    if any(a is None for a in args):
        return None
    applied = tuple(sorted((v, format_type(t)) for v, t in values.items()))
    contract = node.module.manifest.contract.instance(applied)
    slots = _plan_all(index, limit, list(contract.slots), node.fuel, memo)
    if slots is None:
        return None
    return Apply(node.module, tuple(a for a in args if a is not None), slots, applied)


def _apply_free(index: ProducerIndex, limit: int, available: Sequence[TypeId], module: Module,
                binding: Binding, fuel: int, memo: Memo) -> Apply | None:
    """``module`` applied for a ground goal that matched it with ``binding``,
    its free variables determined by pattern search over its inputs."""
    renaming, contract = rename_apart(module.manifest.contract, binding)
    for args, solved in _solve_inputs(index, limit, available, contract.inputs, {}, fuel, memo):
        free = {v: resolve(Var(r), solved) for v, r in renaming.items()}
        if any(type_variables(t) for t in free.values()):
            continue
        closed = [_close(index, limit, a, solved, memo) for a in args]
        if any(a is None for a in closed):
            continue
        full = tuple(sorted((*binding, *((v, format_type(t)) for v, t in free.items()))))
        contract = module.manifest.contract.instance(full)
        slots = _plan_all(index, limit, list(contract.slots), fuel, memo)
        if slots is not None:
            return Apply(module, tuple(a for a in closed if a is not None), slots, full)
    return None


def plan(
    modules: Sequence[Module],
    available: Sequence[TypeId],
    goal: TypeId,
    fuel: int = 8,
) -> Plan | None:
    """Backward-chain from ``goal`` to ``available`` types within ``fuel`` depth.

    Modules are tried in installation order; the first that yields a complete
    plan wins. A sequence goal with no producing module is planned by mapping
    an elementwise plan over a source sequence.
    """
    return _plan(ProducerIndex(modules), len(modules), available, goal, fuel)


def plan_stable(
    modules: Sequence[Module],
    available: Sequence[TypeId],
    goal: TypeId,
    fuel: int = 8,
) -> Plan | None:
    """Plan with the shortest prefix of installed modules that succeeds."""
    return plan_stable_indexed(ProducerIndex(modules), available, goal, fuel)


def plan_stable_indexed(
    index: ProducerIndex,
    available: Sequence[TypeId],
    goal: TypeId,
    fuel: int = 8,
) -> Plan | None:
    """``plan_stable`` by binary search over the prefix length.

    Correct because planning success is monotone in the prefix
    (``NCA.plan_prefix_mono``): ``O(log n)`` planner calls instead of ``n + 1``.
    A route found earlier on the same index is returned as it is: installing
    modules never changes a route (``NCA.planStable_append``, Theorem 3.3).
    """
    key = (tuple(available), goal, fuel)
    found = index.routes.get(key)
    if found is not None and (found[1] is not None or found[0] == index.size):
        return found[1]
    route = None
    if _plan(index, index.size, available, goal, fuel) is not None:
        low, high = 0, index.size
        while low < high:
            middle = (low + high) // 2
            if _plan(index, middle, available, goal, fuel) is None:
                low = middle + 1
            else:
                high = middle
        route = _plan(index, low, available, goal, fuel)
    index.routes[key] = (index.size, route)
    return route
