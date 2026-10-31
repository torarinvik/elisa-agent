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


def output_type(node: Plan) -> TypeId:
    if isinstance(node, Given):
        return node.type_id
    if isinstance(node, Apply):
        return node.module.manifest.contract.output
    return seq_type(output_type(node.body))


def elem_candidates(modules: Sequence[Module], available: Sequence[TypeId]) -> list[TypeId]:
    outputs = [m.manifest.contract.output for m in modules]
    return [e for t in (*available, *outputs) if (e := elem_type(t)) is not None]


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
    if fuel == 0:
        return None
    if goal in available:
        return Given(goal)
    for module in modules:
        contract = module.manifest.contract
        if contract.output != goal:
            continue
        args = []
        for input_type in contract.inputs:
            sub = plan(modules, available, input_type, fuel - 1)
            if sub is None:
                break
            args.append(sub)
        else:
            return Apply(module, tuple(args))
    element_goal = elem_type(goal)
    if element_goal is None:
        return None
    for element in elem_candidates(modules, available):
        body = plan(modules, (element,), element_goal, fuel - 1)
        source = plan(modules, available, seq_type(element), fuel - 1)
        if body is not None and source is not None:
            return Map(element, body, source)
    return None


def plan_stable(
    modules: Sequence[Module],
    available: Sequence[TypeId],
    goal: TypeId,
    fuel: int = 8,
) -> Plan | None:
    """Plan with the shortest prefix of installed modules that succeeds."""
    for k in range(len(modules) + 1):
        result = plan(modules[:k], available, goal, fuel)
        if result is not None:
            return result
    return None
