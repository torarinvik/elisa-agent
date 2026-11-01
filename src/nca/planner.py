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
(THEORY §2.1, ``NCA.Contract.subst_determined``), found by matching.
"""

from __future__ import annotations

import heapq
from collections.abc import Iterator
from dataclasses import dataclass
from typing import Sequence, Union

from nca.abi import Binding, Contract, TypeId, elem_type, seq_type
from nca.registry import Module


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


class ProducerIndex:
    """Installed modules indexed by output type, preserving installation order.

    Mirrors the index of ``NCA.planIdx`` (``lean/NCA/Loading.lean``), proved to
    yield the same plans as scanning the library (``NCA.planIdx_eq``). A view
    limited to the first ``k`` modules serves layered planning.
    """

    def __init__(self, modules: Sequence[Module]) -> None:
        self.size = len(modules)
        self.outputs = [m.manifest.contract.output for m in modules]
        self.producers: dict[TypeId, list[tuple[int, Module]]] = {}
        self.generic: list[tuple[int, Module]] = []
        """Producers with polymorphic contracts, which may produce any instance."""
        self.sequence_outputs: list[tuple[int, TypeId]] = []
        self.needs: list[frozenset[TypeId]] = []
        self.consumers: dict[TypeId, list[int]] = {}
        self.unconditional: list[int] = []
        self._reach_cache: dict[tuple[tuple[TypeId, ...], int], frozenset[TypeId]] = {}
        self._cover_cache: dict[tuple[TypeId, int], bool] = {}
        for position, module in enumerate(modules):
            contract = module.manifest.contract
            needs = frozenset(i for i in contract.inputs if elem_type(i) is None)
            self.needs.append(needs)
            if contract.polymorphic:
                self.generic.append((position, module))
                continue
            self.producers.setdefault(contract.output, []).append((position, module))
            if elem_type(contract.output) is not None:
                self.sequence_outputs.append((position, contract.output))
            for input_type in needs:
                self.consumers.setdefault(input_type, []).append(position)
            if not needs:
                self.unconditional.append(position)

    def candidates(self, goal: TypeId, limit: int) -> Iterator[tuple[int, Module, Binding]]:
        """Producers of ``goal`` among the first ``limit`` modules, in installation
        order, each with the binding of its unique instance producing ``goal``
        (THEORY §2.1)."""
        exact = self.producers.get(goal, ())
        if not self.generic or self.generic[0][0] >= limit:
            for position, module in exact:
                if position >= limit:
                    return
                yield position, module, ()
            return
        merged = heapq.merge(((p, m, ()) for p, m in exact if p < limit),
                             ((p, m, None) for p, m in self.generic if p < limit),
                             key=lambda item: item[0])
        for position, module, binding in merged:
            if binding is None:
                binding = module.manifest.contract.producing(goal)
                if binding is None:
                    continue
            yield position, module, binding

    def covered(self, type_id: TypeId, limit: int) -> bool:
        """Whether a polymorphic producer among the first ``limit`` modules has
        an instance producing ``type_id``."""
        key = (type_id, limit)
        if key not in self._cover_cache:
            self._cover_cache[key] = any(m.manifest.contract.producing(type_id) is not None
                                         for p, m in self.generic if p < limit)
        return self._cover_cache[key]

    def satisfiable(self, needs: frozenset[TypeId], reach: frozenset[TypeId], limit: int) -> bool:
        """Whether every need may be derivable: reachable, or produced by an
        instance of a polymorphic producer."""
        return all(t in reach or self.covered(t, limit) for t in needs)

    def reachable(self, available: Sequence[TypeId], limit: int) -> frozenset[TypeId]:
        """Forward closure of ``available`` under the first ``limit`` contracts.

        Mirrors ``NCA.Closure``: sequence types count as always reachable, so a
        contract fires once all its non-sequence inputs are reachable. Horn-clause
        propagation touches only contracts consuming reachable types, so dormant
        modules elsewhere in the library cost nothing. Types that a polymorphic
        producer has an instance for count as reachable too, which keeps the
        closure an over-approximation of the derivable types.
        """
        key = (tuple(available), limit)
        if key in self._reach_cache:
            return self._reach_cache[key]
        reach = set(available)
        queue = list(available)
        remaining: dict[int, int] = {}
        if any(p < limit for p, _ in self.generic):
            for t in self.consumers:
                if t not in reach and self.covered(t, limit):
                    reach.add(t)
                    queue.append(t)

        def fire(position: int) -> None:
            output = self.outputs[position]
            if output not in reach:
                reach.add(output)
                queue.append(output)

        for position in self.unconditional:
            if position < limit:
                fire(position)
        while queue:
            for position in self.consumers.get(queue.pop(), ()):
                if position >= limit:
                    continue
                remaining[position] = remaining.get(position, len(self.needs[position])) - 1
                if remaining[position] == 0:
                    fire(position)
        result = frozenset(reach)
        self._reach_cache[key] = result
        return result


def _plan(index: ProducerIndex, limit: int, available: Sequence[TypeId], goal: TypeId,
          fuel: int, memo: Memo | None = None) -> Plan | None:
    """The planner, memoized on ``(available, goal, fuel)`` within one call.

    Producers with a non-sequence input outside the forward closure are skipped,
    as in ``NCA.planPruned``, which is proved to return exactly ``NCA.plan``
    given the closure oracle (``NCA.planPruned_eq``, ``NCA.derivable_closure``).

    Planning is a pure function of those arguments for a fixed index and limit,
    so memoization returns exactly what recomputation would; it bounds the work
    by the number of distinct subgoals instead of the number of search paths.
    """
    memo = {} if memo is None else memo
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
            needs = frozenset(i for i in contract.inputs if elem_type(i) is None)
            if not index.satisfiable(needs, reach, limit):
                continue
        else:
            contract = module.manifest.contract
            if not index.needs[position] <= reach:
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
    outputs = [t for position, t in index.sequence_outputs if position < limit]
    candidates = [e for t in (*available, *outputs) if (e := elem_type(t)) is not None]
    for element in candidates:
        body = _plan(index, limit, (element,), element_goal, fuel - 1, memo)
        source = _plan(index, limit, available, seq_type(element), fuel - 1, memo)
        if body is not None and source is not None:
            return Map(element, body, source)
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
    """
    if _plan(index, index.size, available, goal, fuel) is None:
        return None
    low, high = 0, index.size
    while low < high:
        middle = (low + high) // 2
        if _plan(index, middle, available, goal, fuel) is None:
            low = middle + 1
        else:
            high = middle
    return _plan(index, low, available, goal, fuel)
