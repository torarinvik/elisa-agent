"""Symbolic capability planners.

``plan`` mirrors ``NCA.plan`` (``lean/NCA/Planner.lean``), proved sound and
complete. ``plan_stable`` mirrors ``NCA.planStable`` (``lean/NCA/Routing.lean``),
which is additionally proved stable: installing modules never changes the
route of an already solvable task. ``NCA.plan_not_stable`` shows ``plan``
alone lacks that property.

Available types are an ordered sequence, as in the Lean model, because their
order determines the order in which ``map`` candidates are tried.
"""

from __future__ import annotations

from dataclasses import dataclass
from typing import Sequence, Union

from nca.abi import TypeId, elem_type, seq_type
from nca.registry import Module


@dataclass(frozen=True)
class Given:
    type_id: TypeId


@dataclass(frozen=True)
class Apply:
    module: Module
    args: tuple["Plan", ...]


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
        return node.module.manifest.contract.output
    return seq_type(output_type(node.body))


def elem_candidates(modules: Sequence[Module], available: Sequence[TypeId]) -> list[TypeId]:
    outputs = [m.manifest.contract.output for m in modules]
    return [e for t in (*available, *outputs) if (e := elem_type(t)) is not None]


class ProducerIndex:
    """Installed modules indexed by output type, preserving installation order.

    Mirrors the index of ``NCA.planIdx`` (``lean/NCA/Loading.lean``), proved to
    yield the same plans as scanning the library (``NCA.planIdx_eq``). A view
    limited to the first ``k`` modules serves layered planning.
    """

    def __init__(self, modules: Sequence[Module]) -> None:
        self.size = len(modules)
        self.producers: dict[TypeId, list[tuple[int, Module]]] = {}
        self.sequence_outputs: list[tuple[int, TypeId]] = []
        for position, module in enumerate(modules):
            output = module.manifest.contract.output
            self.producers.setdefault(output, []).append((position, module))
            if elem_type(output) is not None:
                self.sequence_outputs.append((position, output))


def _plan(index: ProducerIndex, limit: int, available: Sequence[TypeId], goal: TypeId,
          fuel: int, memo: Memo | None = None) -> Plan | None:
    """The planner, memoized on ``(available, goal, fuel)`` within one call.

    Planning is a pure function of those arguments for a fixed index and limit,
    so memoization returns exactly what recomputation would; it bounds the work
    by the number of distinct subgoals instead of the number of search paths.
    """
    memo = {} if memo is None else memo
    key = (tuple(available), goal, fuel)
    if key not in memo:
        memo[key] = _search(index, limit, available, goal, fuel, memo)
    return memo[key]


def _search(index: ProducerIndex, limit: int, available: Sequence[TypeId], goal: TypeId,
            fuel: int, memo: Memo) -> Plan | None:
    if fuel == 0:
        return None
    if goal in available:
        return Given(goal)
    for position, module in index.producers.get(goal, ()):
        if position >= limit:
            break
        args = []
        for input_type in module.manifest.contract.inputs:
            sub = _plan(index, limit, available, input_type, fuel - 1, memo)
            if sub is None:
                break
            args.append(sub)
        else:
            return Apply(module, tuple(args))
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
