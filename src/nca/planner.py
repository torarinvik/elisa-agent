"""Symbolic capability planners.

The depth-bounded search mirrors ``NCA.plan`` (``lean/NCA/Planner.lean``).
``plan`` tries increasing depths, as in ``NCA.planShallow``. ``plan_stable``
uses the earliest successful library prefix, as in ``NCA.planShallowStable``,
which is proved stable: installing modules never changes the route of an
already solvable task. Shallow planning alone lacks that property.

Available types are an ordered sequence, as in the Lean model, because their
order determines the order in which ``map`` candidates are tried.

A module whose contract declares slots (a higher-order expert, ``NCA.HPlan``)
is applied with one plan per slot, planned as a sub-goal whose only available
inputs are the slot's inputs, like a ``map`` body.

A polymorphic contract is applied at the one instance whose output is the goal
(THEORY §2.1, ``NCA.Contract.subst_determined``), found by matching. Variables
the goal leaves free are determined by solving the inputs as pattern goals
with unification (THEORY §2.2, ``NCA.answer_sound``). Elements of the
sequences that polymorphic producers make are ``map`` candidates too.
"""

from __future__ import annotations

import itertools
from collections.abc import Iterable, Iterator
from dataclasses import dataclass
from typing import Sequence, Union

from nca.abi import (App, Binding, Contract, Module, Term, TypeId, Var, elem_type, format_type,
                     parse_type, resolve, seq_type, type_variables, unify)
from nca.index import ProducerIndex, rename_apart


@dataclass(frozen=True)
class Given:
    """An available input: the one at ``position`` among the available types,
    or the first of type ``type_id`` when ``position`` is ``None``."""

    type_id: TypeId
    position: int | None = None


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
Memo = dict[tuple[tuple[TypeId, ...], TypeId, int, frozenset[int]], Union[Given, Apply, Map, None]]


def uses(node: Plan, available: Sequence[TypeId]) -> frozenset[int]:
    """The positions of the available inputs ``node`` reads (THEORY §20.8). A
    ``map`` body reads only its element, so a ``map`` uses what its source uses."""
    if isinstance(node, Given):
        position = available.index(node.type_id) if node.position is None else node.position
        return frozenset((position,))
    if isinstance(node, Apply):
        return frozenset().union(*(uses(a, available) for a in node.args))
    return uses(node.source, available)


def slot_goals(contract: Contract) -> list[tuple[tuple[TypeId, ...], TypeId, frozenset[int]]]:
    """Each slot of ``contract`` as a sub-goal: its inputs, its output, and the
    positions of the inputs every filling must use."""
    return [(inputs, output, frozenset(contract.relevant[i]) if i < len(contract.relevant)
             else frozenset())
            for i, (inputs, output) in enumerate(contract.slots)]


def assignments(required: frozenset[int], count: int) -> Iterator[tuple[frozenset[int], ...]]:
    """Ways to give each required position to one of ``count`` arguments: a
    requirement is met by an application exactly when it is met this way by
    its arguments (THEORY §20.8, Theorem 20.10). Ways that spread the positions over more
    arguments come first, so that each argument has as little to use as
    possible."""
    ordered = sorted(required)
    choices = sorted(itertools.product(range(count), repeat=len(ordered)),
                     key=lambda choice: (max((choice.count(j) for j in range(count)), default=0),
                                         choice))
    for choice in choices:
        yield tuple(frozenset(r for r, c in zip(ordered, choice) if c == j) for j in range(count))


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
          fuel: int, memo: Memo | None = None, required: frozenset[int] = frozenset(),
          ) -> Plan | None:
    """The planner, memoized on ``(available, goal, fuel, required)`` per library
    prefix, across calls on the same index (Theorem 12.18). The plan uses every
    available input whose position is in ``required``.

    Producers with a non-sequence input outside the forward closure are skipped,
    as in ``NCA.planPruned``, which is proved to return exactly ``NCA.plan``
    given the closure oracle (``NCA.planPruned_eq``, ``NCA.derivable_closure``).

    Planning is a pure function of those arguments for a fixed index and limit,
    so memoization returns exactly what recomputation would; it bounds the work
    by the number of distinct subgoals instead of the number of search paths.
    """
    memo = index.memo(limit) if memo is None else memo
    key = (tuple(available), goal, fuel, required)
    if key not in memo:
        memo[key] = _search(index, limit, available, goal, fuel, memo, required)
    return memo[key]


def _plan_all(index: ProducerIndex, limit: int,
              goals: Sequence[tuple[Sequence[TypeId], TypeId, frozenset[int]]], fuel: int,
              memo: Memo) -> tuple[Plan, ...] | None:
    """Plans for every ``(available, goal, required)`` sub-goal at depth
    ``fuel - 1``."""
    found = []
    for available, goal, required in goals:
        sub = _plan(index, limit, available, goal, fuel - 1, memo, required)
        if sub is None:
            return None
        found.append(sub)
    return tuple(found)


def _plan_args(index: ProducerIndex, limit: int, available: Sequence[TypeId],
               inputs: Sequence[TypeId], required: frozenset[int], fuel: int,
               memo: Memo) -> tuple[Plan, ...] | None:
    """Plans for ``inputs`` that together use every position in ``required``."""
    for shares in assignments(required, len(inputs)):
        args = _plan_all(index, limit, [(available, t, r) for t, r in zip(inputs, shares)],
                         fuel, memo)
        if args is not None:
            return args
    return None


def _search(index: ProducerIndex, limit: int, available: Sequence[TypeId], goal: TypeId,
            fuel: int, memo: Memo, required: frozenset[int] = frozenset()) -> Plan | None:
    if fuel == 0:
        return None
    positions = [k for k, t in enumerate(available) if t == goal]
    for k in positions:
        if required <= {k}:
            return Given(goal) if k == positions[0] else Given(goal, k)
    element_goal = elem_type(goal)
    made = None if element_goal is None else index.seq_elements(available, limit)
    # Theorem 12.20: an element outside the source oracle has no derivable sequence.
    if (element_goal is not None and made is not None and element_goal not in made
            and elem_type(element_goal) is None and not index.covered(element_goal, limit)):
        return None
    reach = index.reachable(available, limit)
    total = index.total(available, limit)
    for position, module, binding in index.candidates(goal, limit):
        if binding:
            if not index.may_produce(available, position, goal, limit):
                continue
            contract = module.manifest.contract.instance(binding)
            needs = frozenset(i for i in contract.inputs
                              if elem_type(i) is None and not type_variables(parse_type(i)))
            if not index.satisfiable(available, needs, limit):
                continue
        else:
            contract = module.manifest.contract
            if not (total or index.needs[position] <= reach):
                continue
        if contract.free:
            found = _apply_free(index, limit, available, module, binding, fuel, memo, required)
            if found is not None:
                return found
            continue
        args = _plan_args(index, limit, available, contract.inputs, required, fuel, memo)
        if args is None:
            continue
        slots = _plan_all(index, limit, slot_goals(contract), fuel, memo)
        if slots is not None:
            return Apply(module, args, slots, binding)
    if element_goal is None:
        return None
    candidates, order = index.element_candidates(available, limit)
    sources = index.sources(element_goal, limit)
    if sources is not None:
        candidates = sorted((a for a in sources if a in order), key=order.__getitem__)

    def map_over(element: TypeId) -> Map | None:
        if made is not None and element not in made and elem_type(element) is None:
            return None
        if not index.may_derive((element,), parse_type(element_goal), limit):
            return None
        body = _plan(index, limit, (element,), element_goal, fuel - 1, memo)
        source = _plan(index, limit, available, seq_type(element), fuel - 1, memo, required)
        return None if body is None or source is None else Map(element, body, source)

    for element in candidates:
        if (found := map_over(element)) is not None:
            return found
    if index.polymorphic_sequences(limit):
        for element in _polymorphic_sources(index, limit, available, order, fuel - 1, memo):
            if (found := map_over(element)) is not None:
                return found
    return None


def _polymorphic_sources(index: ProducerIndex, limit: int, available: Sequence[TypeId],
                         known: dict[TypeId, int], fuel: int, memo: Memo) -> Iterator[TypeId]:
    """Further ``map`` candidate elements, beyond ``known``, for sequences that
    polymorphic producers make: the elements the source oracle admits
    (Theorem 12.20), in sorted order, or, when it admits every type, the
    ground elements of the solutions of the pattern goal ``seq[?a]``, in
    search order (THEORY §2.2)."""
    made = index.seq_elements(available, limit)
    if made is not None:
        yield from sorted(made.difference(known))
        return
    seen = set(known)
    for _, solved in _solutions(index, limit, available, _SOURCE, {}, fuel, memo):
        element = resolve(_SOURCE.args[0], solved)
        if not type_variables(element) and (type_id := format_type(element)) not in seen:
            seen.add(type_id)
            yield type_id


_SOURCE = App("seq", (Var("element"),))
"""The pattern of ``map`` sources. Elements of sequences that only
polymorphic producers make are found by solving it (THEORY §2.2)."""



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
        renaming, inputs, output = rename_apart(module.manifest.contract, ())
        extended = dict(binding)
        if not unify(goal, output, extended):
            continue
        names = tuple(renaming.items())
        for args, solved in _solve_inputs(index, limit, available, inputs, extended,
                                          fuel, memo):
            yield _Open(module, args, names, fuel), solved
    if isinstance(goal, App) and goal.name == "seq" and len(goal.args) == 1:
        found, order = index.element_candidates(available, limit)
        candidates: Iterable[TypeId] = found
        body_goal = resolve(goal.args[0], binding)
        if not type_variables(body_goal):
            sources = index.sources(format_type(body_goal), limit)
            if sources is not None:
                candidates = sorted((a for a in sources if a in order), key=order.__getitem__)
        made = index.seq_elements(available, limit)
        if index.polymorphic_sequences(limit):
            candidates = itertools.chain(
                candidates, _polymorphic_sources(index, limit, available, order, fuel - 1, memo))
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
                  inputs: Sequence[Term], binding: dict[str, Term], fuel: int, memo: Memo,
                  ) -> Iterator[tuple[tuple[_Partial, ...], dict[str, Term]]]:
    """Solutions for every input in turn, backtracking over earlier inputs'
    alternatives."""
    if not inputs:
        yield (), binding
        return
    for first, extended in _solutions(index, limit, available, inputs[0], binding,
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
    slots = _plan_all(index, limit, slot_goals(contract), node.fuel, memo)
    if slots is None:
        return None
    return Apply(node.module, tuple(a for a in args if a is not None), slots, applied)


def _free_instances(index: ProducerIndex, limit: int, available: Sequence[TypeId],
                    module: Module, binding: Binding, fuel: int, memo: Memo,
                    distinct: bool = False,
                    ) -> Iterator[tuple[tuple[Plan, ...], Binding]]:
    """Argument plans and full bindings of ``module``, in search order, for a
    ground goal that matched it with ``binding``: its free variables
    determined by pattern search over its inputs at depth ``fuel - 1``.
    With ``distinct``, close only until each binding has one valid plan."""
    renaming, inputs, _ = rename_apart(module.manifest.contract, binding)
    found: set[Binding] = set()
    for args, solved in _solve_inputs(index, limit, available, inputs, {}, fuel, memo):
        free = {v: resolve(Var(r), solved) for v, r in renaming.items()}
        if any(type_variables(t) for t in free.values()):
            continue
        full = tuple(sorted((*binding, *((v, format_type(t)) for v, t in free.items()))))
        if distinct and full in found:
            continue
        closed = [_close(index, limit, a, solved, memo) for a in args]
        if all(a is not None for a in closed):
            if distinct:
                found.add(full)
            yield tuple(a for a in closed if a is not None), full


def _apply_free(index: ProducerIndex, limit: int, available: Sequence[TypeId], module: Module,
                binding: Binding, fuel: int, memo: Memo,
                required: frozenset[int] = frozenset()) -> Apply | None:
    """``module`` applied for a ground goal that matched it with ``binding``,
    its free variables determined by pattern search over its inputs. Under a
    requirement, each instance found is applied like a ground contract."""
    for args, full in _free_instances(index, limit, available, module, binding, fuel, memo,
                                      distinct=True):
        contract = module.manifest.contract.instance(full)
        if required:
            found = _plan_args(index, limit, available, contract.inputs, required, fuel, memo)
            if found is None:
                continue
            args = found
        slots = _plan_all(index, limit, slot_goals(contract), fuel, memo)
        if slots is not None:
            return Apply(module, args, slots, full)
    return None


def free_bindings(index: ProducerIndex, available: Sequence[TypeId], module: Module,
                  binding: Binding, fuel: int) -> list[Binding]:
    """The full bindings, each once in search order, of the instances of
    ``module`` producing a ground goal it matched with ``binding`` whose
    inputs pattern search plans from ``available`` at depth ``fuel - 1``
    (THEORY §2.2). These are the instances the planner can apply."""
    return [full for _, full in _free_instances(
        index, index.size, available, module, binding, fuel, index.memo(index.size), distinct=True)]


def map_candidates(index: ProducerIndex, available: Sequence[TypeId], fuel: int) -> list[TypeId]:
    """Every ``map`` candidate element the planner tries for a sequence goal
    at depth ``fuel``, each once in its order (THEORY §2): the enumerated
    elements, then those of sequences polymorphic producers make."""
    found, order = index.element_candidates(available, index.size)
    if index.polymorphic_sequences(index.size):
        found = [*found, *_polymorphic_sources(index, index.size, available, order, fuel - 1,
                                               index.memo(index.size))]
    return list(dict.fromkeys(found))


def _shallow(index: ProducerIndex, limit: int, available: Sequence[TypeId], goal: TypeId,
             fuel: int, required: frozenset[int] = frozenset()) -> Plan | None:
    """Try depth limits in order, retaining installation order within a limit."""
    for depth in range(1, fuel + 1):
        route = _plan(index, limit, available, goal, depth, required=required)
        if route is not None:
            return route
    return None


def plan(
    modules: Sequence[Module],
    available: Sequence[TypeId],
    goal: TypeId,
    fuel: int = 8,
    required: frozenset[int] = frozenset(),
) -> Plan | None:
    """Backward-chain from ``goal`` to ``available`` types within ``fuel`` depth,
    using every available input whose position is in ``required``.

    Prefer the lowest depth at which a plan is found; within that depth,
    modules are tried in installation order. A sequence goal with no producing
    module is planned by mapping an elementwise plan over a source sequence.
    """
    return _shallow(ProducerIndex(modules), len(modules), available, goal, fuel, required)


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
    (``NCA.plan_prefix_mono``): ``O(log n)`` depth-bounded checks, followed by
    increasing-depth search within the earliest successful prefix.
    A route found earlier on the same index is returned as it is: installing
    modules never changes a route (``NCA.planShallowStable_append``).
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
        route = _shallow(index, low, available, goal, fuel)
        index.routes[key] = (low, route)
    else:
        index.routes[key] = (index.size, None)
    return route
