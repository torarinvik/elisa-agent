"""Plan type checking, pinned routes, and evidence-based upgrades.

``infer`` mirrors ``NCA.infer`` (``lean/NCA/Types/Check.lean``), proved to accept
exactly the well-typed plans; slot fillings are checked against the slots'
inputs alone, as in ``NCA.HTyped``, and must use the inputs the slot declares
relevant. ``Router`` mirrors ``NCA.route`` and
``NCA.upgrade`` (``lean/NCA/Planning/Upgrade.lean``): pins override stable planning,
an upgrade pins a checked plan for one goal, and upgrades are proved local,
reversible, and stable under module installation.

``sign_test`` decides whether an upgrade is supported by evidence.
"""

from __future__ import annotations

import math
from typing import Sequence

from nca.abi import Module, TypeId, canonical_type, parse_type, seq_type, type_variables
from nca.planner import Apply, Given, Plan, plan_stable, slot_goals, uses


def infer(modules: Sequence[Module], available: Sequence[TypeId], node: Plan) -> TypeId | None:
    """The type ``node`` produces, or ``None`` if it is not well-typed."""
    if isinstance(node, Given):
        if node.position is None:
            return node.type_id if node.type_id in available else None
        in_range = 0 <= node.position < len(available)
        return node.type_id if in_range and available[node.position] == node.type_id else None
    if isinstance(node, Apply):
        if not any(m is node.module for m in modules) or not _instantiates(node):
            return None
        contract = node.contract
        arg_types = [infer(modules, available, arg) for arg in node.args]
        if len(node.slots) != len(contract.slots) or any(
                infer(modules, inputs, filling) != output
                or not required <= uses(filling, inputs)
                for filling, (inputs, output, required) in zip(node.slots, slot_goals(contract))):
            return None
        return contract.output if tuple(arg_types) == contract.inputs else None
    body = infer(modules, (node.element,), node.body)
    source = infer(modules, available, node.source)
    if body is None or source != seq_type(node.element):
        return None
    return seq_type(body)


def _instantiates(node: Apply) -> bool:
    """Whether ``node.binding`` binds exactly the variables of the module's
    contract, free ones included, each to a ground type in canonical form."""
    names = [name for name, _ in node.binding]
    if frozenset(names) != node.module.manifest.contract.variables or len(names) != len(set(names)):
        return False
    try:
        return all(canonical_type(t) == t and not type_variables(parse_type(t))
                   for _, t in node.binding)
    except ValueError:
        return False


class Router:
    def __init__(self) -> None:
        self.pins: dict[TypeId, Plan] = {}

    def route(self, modules: Sequence[Module], available: Sequence[TypeId], goal: TypeId,
              fuel: int = 8) -> Plan | None:
        return self.pins.get(goal) or plan_stable(modules, available, goal, fuel)

    def upgrade(self, modules: Sequence[Module], available: Sequence[TypeId], goal: TypeId,
                candidate: Plan) -> Plan | None:
        """Pin ``candidate`` for ``goal``; return the previous pin for rollback."""
        if infer(modules, available, candidate) != goal:
            raise ValueError(f"candidate route does not produce {goal}")
        previous = self.pins.get(goal)
        self.pins[goal] = candidate
        return previous

    def rollback(self, goal: TypeId, previous: Plan | None) -> None:
        if previous is None:
            self.pins.pop(goal, None)
        else:
            self.pins[goal] = previous


def sign_test(current: Sequence[bool], candidate: Sequence[bool], alpha: float = 0.05) -> tuple[bool, float]:
    """One-sided exact sign test on paired per-sample correctness.

    Among samples where the routes disagree in correctness, ``wins`` are those
    only the candidate gets right. Under the null hypothesis that neither route
    is better, ``wins ~ Binomial(discordant, 1/2)``. Returns whether to accept
    the candidate and the p-value ``P(X >= wins)``.
    """
    wins = sum(c and not o for o, c in zip(current, candidate))
    losses = sum(o and not c for o, c in zip(current, candidate))
    n = wins + losses
    p_value = sum(math.comb(n, k) for k in range(wins, n + 1)) / 2**n if n else 1.0
    return p_value < alpha, p_value
