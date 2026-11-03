"""Capability gaps: the missing connectors that would complete a route
(THEORY §20.9).

When no route reaches a goal, a gap is a unary contract ``A → B`` such that
installing any expert with it lets the planner reach the goal. ``A`` must be
producible from the available types and the goal reachable from ``B``
(``NCA.gap_iff``); every candidate is confirmed by planning with a stand-in
for the missing expert, so the result agrees with the planner exactly, also
for experts with several inputs.

``repair`` closes gaps of any size: it finds a route needing the fewest
missing connectors (``NCA.Repair``), asks a supplied acquirer, such as a
learner whose result passed the upgrade gate, for each in turn, keeps what it
supplies, and searches again around any it refuses.
"""

from __future__ import annotations

from collections import deque
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
class Repaired:
    acquired: tuple[Module, ...]
    """Every expert supplied, in order, including any the route does not use."""
    route: Plan
    requests: int


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


def _ground(contract: Contract) -> bool:
    return not contract.slots and not any(
        t.startswith("?") for t in (*contract.inputs, contract.output))


def fewest_missing(modules: Sequence[Module], available: Sequence[TypeId], goal: TypeId,
                   missing: int, refused: frozenset[tuple[TypeId, TypeId]] = frozenset()
                   ) -> list[tuple[TypeId, TypeId]] | None:
    """The missing connectors along a route to ``goal`` needing the fewest of
    them, at most ``missing``, never one in ``refused``; ``None`` if none.

    A 0-1 breadth-first search over types: an installed ground expert steps
    from one of its inputs at no cost once its other inputs are producible,
    and a missing connector steps between any two types at cost one."""
    known = set(producible(modules, available))
    universe = list(dict.fromkeys([*available, goal, *(
        t for m in modules if _ground(m.manifest.contract)
        for t in (*m.manifest.contract.inputs, m.manifest.contract.output))]))
    steps: dict[TypeId, list[TypeId]] = {}
    for module in modules:
        contract = module.manifest.contract
        if not _ground(contract):
            continue
        for k, source in enumerate(contract.inputs):
            if all(t in known for j, t in enumerate(contract.inputs) if j != k):
                steps.setdefault(source, []).append(contract.output)
    distance = dict.fromkeys(available, 0)
    previous: dict[TypeId, tuple[TypeId, bool]] = {}
    queue = deque(dict.fromkeys(available))
    while queue:
        here = queue.popleft()
        for there in steps.get(here, ()):
            if distance.get(there, missing + 1) > distance[here]:
                distance[there], previous[there] = distance[here], (here, False)
                queue.appendleft(there)
        if distance[here] < missing:
            for there in universe:
                if (there != here and (here, there) not in refused
                        and distance.get(there, missing + 1) > distance[here] + 1):
                    distance[there], previous[there] = distance[here] + 1, (here, True)
                    queue.append(there)
    if goal not in distance:
        return None
    path, here = [], goal
    while here in previous:
        source, new = previous[here]
        if new:
            path.append((source, here))
        here = source
    return path[::-1]


def repair(modules: Sequence[Module], available: Sequence[TypeId], goal: TypeId,
           acquire: Acquire, attempts: int, missing: int = 1, fuel: int = 8) -> Repaired | None:
    """Acquire connectors until a route reaches ``goal``: each round requests
    the connectors of a route needing the fewest missing ones, at most
    ``missing``, avoiding refused requests; at most ``attempts`` requests."""
    acquired: list[Module] = []
    refused: set[tuple[TypeId, TypeId]] = set()
    requests = 0
    while True:
        library = (*modules, *acquired)
        route = plan(library, available, goal, fuel)
        if route is not None:
            return Repaired(tuple(acquired), route, requests)
        path = fewest_missing(library, available, goal, missing, frozenset(refused))
        if not path:
            return None
        for source, target in path:
            if requests == attempts:
                return None
            requests += 1
            contract = Contract((source,), target)
            module = acquire(contract)
            if module is None:
                refused.add((source, target))
                break
            if module.manifest.contract != contract:
                raise ValueError(f"acquired {module.manifest.module_id} does not have the "
                                 "requested contract")
            acquired.append(module)
