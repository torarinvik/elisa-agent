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

For an unreachable goal, ``repair`` with ``media`` invents an intermediate
type: a *medium* founded on the goal, a fresh content-addressed constructor
joined to the goal by identity connectors in both directions. Founding changes
no reachability among existing types and the medium is reachable exactly when
its founder is (``NCA.founded_keeps``, ``NCA.founded_medium``). A medium only
helps once it has members besides its founder, so ``grow`` asks the acquirer to
connect every other type into it, pass after pass, until a pass adds none.
"""

from __future__ import annotations

from collections import deque
from itertools import combinations
from collections.abc import Callable, Sequence
from dataclasses import dataclass
import math
from typing import Any

from nca.abi import Contract, Manifest, Module, TypeId
from nca.objects import Constructor
from nca.planner import Plan, plan

Acquire = Callable[[Contract], Module | Sequence[Module] | None]
"""Returns an expert with the given contract, or ``None`` if it cannot. It may
return a sequence instead, the requested expert first, followed by companions
learned with it, such as the decoder learned with an encoder."""


@dataclass(frozen=True)
class Gap:
    contract: Contract
    route: Plan
    """The route found with a stand-in for the missing expert."""


@dataclass(frozen=True)
class Repaired:
    acquired: tuple[Module, ...]
    """Every expert supplied or founded, in order, including any the route
    does not use."""
    route: Plan
    requests: int


class Founder:
    """An identity connector between a medium and the type it is founded on."""

    def __init__(self, source: TypeId, target: TypeId, hub: TypeId) -> None:
        self.hub = hub
        self.manifest = Manifest(f"medium/{source}->{target}", "1", Contract((source,), target),
                                 cost=0.0, effects=frozenset())

    def invoke(self, value: Any) -> Any:
        return value


def medium(founder: TypeId) -> tuple[Constructor, Founder, Founder]:
    """A medium founded on ``founder``, with its connectors in and out; the
    same founder always gives the same medium."""
    constructor = Constructor("medium", "1.0.0", 0, f"A shared medium founded on {founder}: "
                              f"its values are those of {founder}.")
    hub = constructor.type()
    return constructor, Founder(founder, hub, hub), Founder(hub, founder, hub)


def grow(modules: Sequence[Module], hub: TypeId, candidates: Sequence[TypeId],
         acquire: Acquire) -> tuple[list[Module], int]:
    """The experts connecting ``candidates`` into the medium ``hub`` that
    ``acquire`` supplies, asked again after every pass that adds a member, and
    the number of requests made."""
    added: list[Module] = []
    requests = 0
    while True:
        members = {m.manifest.contract.inputs[0] for m in (*modules, *added)
                   if m.manifest.contract.output == hub}
        before = len(added)
        for candidate in candidates:
            if candidate in members or candidate == hub:
                continue
            requests += 1
            supplied = acquire(Contract((candidate,), hub))
            if supplied is not None:
                added += (supplied,) if not isinstance(supplied, Sequence) else supplied
                members.add(candidate)
        if len(added) == before:
            return added, requests


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
         fuel: int = 8, arity: int = 1, *,
         priority: Callable[[Contract], float] | None = None) -> list[Gap]:
    """Every single expert ``(A₁, …, Aₙ) → B`` with ``n ≤ arity`` completing a
    route to ``goal``, with each ``Aᵢ`` producible and ``B`` consumed by some
    expert or the goal itself (``NCA.horn_gap_iff``), fewest inputs first and
    inputs in the order they are produced; empty if a route exists already.
    Optional finite priorities reorder candidates, highest first, with stable
    ties. They never remove a candidate or change its validity certificate.
    The scorer must not mutate the library or perform acquisition."""
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
        for size in range(1, arity + 1):
            for inputs in combinations(sources, size):
                contract = Contract(inputs, target)
                route = plan((*modules, _Missing(contract)), available, goal, fuel)
                if route is not None:
                    found.append(Gap(contract, route))
    found.sort(key=lambda gap: len(gap.contract.inputs))
    if priority is not None:
        scores = [float(priority(gap.contract)) for gap in found]
        if not all(math.isfinite(score) for score in scores):
            raise ValueError("gap priorities must be finite")
        found = [gap for _, gap in sorted(zip(scores, found), key=lambda item: item[0],
                                         reverse=True)]
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
           acquire: Acquire, attempts: int, missing: int = 1, fuel: int = 8, *,
           media: Sequence[TypeId] | None = None, arity: int = 1,
           priority: Callable[[Contract], float] | None = None) -> Repaired | None:
    """Acquire connectors until a route reaches ``goal``: each round requests
    the connectors of a route needing the fewest missing ones, at most
    ``missing``, avoiding refused requests; at most ``attempts`` requests.
    With ``arity`` above one, single gaps with up to ``arity`` inputs are
    requested too, fewest inputs first: in place of the search when
    ``missing`` is one, and once it finds nothing otherwise.
    ``priority`` reorders the single-gap candidates. With ``missing > 1``
    it applies only to the fallback single-gap search, preserving the
    fewest-missing multi-step path. Learned scorers remain supplied policies.

    With ``media``, a medium is first founded on an unreachable goal that no
    existing medium reaches and grown over the types in ``media``; its
    requests are counted, and later goals share it."""
    acquired: list[Module] = []
    requests = 0
    if media is not None and plan(modules, available, goal, fuel) is None:
        existing = {m.hub for m in modules if isinstance(m, Founder)}
        if not any(plan(modules, (hub,), goal, fuel) for hub in existing):
            constructor, into, out = medium(goal)
            grown, requests = grow((*modules, into, out), constructor.type(), media, acquire)
            acquired += [into, out, *grown]
    refused: set[Contract] = set()
    while True:
        library = (*modules, *acquired)
        route = plan(library, available, goal, fuel)
        if route is not None:
            return Repaired(tuple(acquired), route, requests)
        unary = frozenset((c.inputs[0], c.output) for c in refused if len(c.inputs) == 1)
        single_search = missing == 1 and (arity > 1 or priority is not None)
        path = [] if single_search else [Contract((a,), b) for a, b in fewest_missing(
            library, available, goal, missing, unary) or ()]
        if not path and (arity > 1 or priority is not None):
            path = next(([gap.contract] for gap in gaps(library, available, goal, fuel, arity,
                                                       priority=priority)
                         if gap.contract not in refused), [])
        if not path:
            return None
        for contract in path:
            if requests == attempts:
                return None
            requests += 1
            supplied = acquire(contract)
            if supplied is None:
                refused.add(contract)
                break
            supplied = (supplied,) if not isinstance(supplied, Sequence) else tuple(supplied)
            if not supplied or supplied[0].manifest.contract != contract:
                raise ValueError("the acquired expert does not have the requested contract")
            acquired += supplied
