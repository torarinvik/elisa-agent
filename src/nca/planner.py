"""Symbolic capability planners.

``plan`` mirrors ``NCA.plan`` (``lean/NCA/Planner.lean``), proved sound and
complete. ``plan_stable`` mirrors ``NCA.planStable`` (``lean/NCA/Routing.lean``),
which is additionally proved stable: installing modules never changes the
route of an already solvable task. ``NCA.plan_not_stable`` shows ``plan``
alone lacks that property.
"""

from __future__ import annotations

from dataclasses import dataclass
from typing import Sequence, Union

from nca.abi import TypeId
from nca.registry import Module


@dataclass(frozen=True)
class Given:
    type_id: TypeId


@dataclass(frozen=True)
class Apply:
    module: Module
    args: tuple["Plan", ...]


Plan = Union[Given, Apply]


def plan(
    modules: Sequence[Module],
    available: frozenset[TypeId],
    goal: TypeId,
    fuel: int = 8,
) -> Plan | None:
    """Backward-chain from ``goal`` to ``available`` types within ``fuel`` depth.

    Modules are tried in installation order; the first that yields a complete
    plan wins.
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
    return None


def plan_stable(
    modules: Sequence[Module],
    available: frozenset[TypeId],
    goal: TypeId,
    fuel: int = 8,
) -> Plan | None:
    """Plan with the shortest prefix of installed modules that succeeds."""
    for k in range(len(modules) + 1):
        result = plan(modules[:k], available, goal, fuel)
        if result is not None:
            return result
    return None
