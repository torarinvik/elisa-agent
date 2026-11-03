"""Capability gaps: the single missing connectors that would complete a route
(THEORY §20.9).

When no route reaches a goal, a gap is a unary contract ``A → B`` such that
installing any expert with it lets the planner reach the goal. ``A`` must be
producible from the available types and the goal reachable from ``B``
(``NCA.gap_iff``); every candidate is confirmed by planning with a stand-in
for the missing expert, so the result agrees with the planner exactly, also
for experts with several inputs. ``fill`` asks a supplied acquirer, such as a
learner whose result passed the upgrade gate, for experts in that order.
"""

from __future__ import annotations

from collections.abc import Callable, Sequence
from dataclasses import dataclass
from typing import Any

from nca.abi import Contract, Manifest, Module, TypeId
from nca.planner import Plan, plan

Acquire = Callable[[Contract], Module | None]
"""Returns an expert with the given contract, or ``None`` if it cannot."""


@dataclass(frozen=True)
class Gap:
    contract: Contract
    route: Plan
    """The route found with a stand-in for the missing expert."""


@dataclass(frozen=True)
class Filled:
    gap: Gap
    module: Module
    route: Plan
    attempts: int


class _Missing:
    """A stand-in for an expert that does not exist yet; never invoked."""

    def __init__(self, contract: Contract) -> None:
        self.manifest = Manifest("kernel.gap", "0", contract, effects=frozenset())

    def invoke(self, *values: Any) -> Any:
        raise RuntimeError("a gap stand-in is never executed")


def producible(modules: Sequence[Module], available: Sequence[TypeId]) -> list[TypeId]:
    """Types reachable from ``available`` through ground experts without slots,
    in the order they are first reached."""
    found = list(dict.fromkeys(available))
    known = set(found)
    changed = True
    while changed:
        changed = False
        for module in modules:
            contract = module.manifest.contract
            if contract.slots or contract.output in known or not set(contract.inputs) <= known:
                continue
            if any(t.startswith("?") for t in (*contract.inputs, contract.output)):
                continue
            found.append(contract.output)
            known.add(contract.output)
            changed = True
    return found


def gaps(modules: Sequence[Module], available: Sequence[TypeId], goal: TypeId,
         fuel: int = 8) -> list[Gap]:
    """Every single connector ``A → B`` completing a route to ``goal``, with
    ``A`` producible and ``B`` consumed by some expert or the goal itself;
    empty if a route exists already."""
    if plan(modules, available, goal, fuel) is not None:
        return []
    sources = producible(modules, available)
    consumed = dict.fromkeys(t for m in modules for t in m.manifest.contract.inputs
                             if not t.startswith("?"))
    targets = [t for t in (goal, *consumed) if t not in sources]
    found = []
    for target in dict.fromkeys(targets):
        if plan(modules, (*available, target), goal, fuel) is None:
            continue
        for source in sources:
            contract = Contract((source,), target)
            route = plan((*modules, _Missing(contract)), available, goal, fuel)
            if route is not None:
                found.append(Gap(contract, route))
    return found


def fill(modules: Sequence[Module], available: Sequence[TypeId], goal: TypeId,
         acquire: Acquire, attempts: int, fuel: int = 8) -> Filled | None:
    """The first gap, in order, for which ``acquire`` supplies an expert with
    that contract, and the route through it; at most ``attempts`` requests."""
    for count, gap in enumerate(gaps(modules, available, goal, fuel)[:attempts], 1):
        module = acquire(gap.contract)
        if module is None:
            continue
        if module.manifest.contract != gap.contract:
            raise ValueError(f"acquired {module.manifest.module_id} does not have the "
                             "requested contract")
        route = plan((*modules, module), available, goal, fuel)
        if route is not None:
            return Filled(gap, module, route, count)
    return None
