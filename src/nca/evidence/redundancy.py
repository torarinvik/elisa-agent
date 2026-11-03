"""Majority over redundant routes (THEORY §31.7).

A route's risk grows with its depth (§31), since any failing expert spoils it.
``disjoint_routes`` plans up to ``count`` routes that share no expert, except
those ``shared`` admits (for example ones that never fail), and ``vote`` runs
them all and answers what more than half agree on, abstaining otherwise. With
``t = ⌈(k+1)/2⌉`` of ``k`` routes, the vote is correct unless ``t`` of them
fail (``NCA.vote_correct``), so if their failures are independent its risk is
at most the ``t``-th elementary symmetric polynomial of their risks
(``NCA.vote_risk``, ``vote_risk``), which falls exponentially in ``k`` while a
single route's grows linearly in depth. Independence is an assumption about
how the experts were obtained, such as from independent data; routes sharing
no expert are necessary for it, not sufficient.
"""

from __future__ import annotations

from collections.abc import Callable, Mapping, Sequence
from dataclasses import dataclass
from typing import Any

from nca.abi import Message, Module, TypeId
from nca.cache import value_digest
from nca.planner import Apply, Map, Plan, plan
from nca.runtime import Resolver, execute
from nca.workspace import Workspace


def _never(module: Module) -> bool:
    return False


def _experts(node: Plan) -> list[Module]:
    if isinstance(node, Apply):
        return [node.module, *(m for arg in (*node.args, *node.slots) for m in _experts(arg))]
    if isinstance(node, Map):
        return [*_experts(node.body), *_experts(node.source)]
    return []


def disjoint_routes(modules: Sequence[Module], available: Sequence[TypeId], goal: TypeId,
                    count: int, fuel: int = 8,
                    shared: Callable[[Module], bool] = _never) -> list[Plan]:
    """Up to ``count`` routes to ``goal``, planned greedily, no two using the
    same expert unless ``shared`` admits it."""
    remaining = list(modules)
    routes: list[Plan] = []
    while len(routes) < count:
        route = plan(remaining, available, goal, fuel)
        if route is None:
            break
        routes.append(route)
        used = {id(m) for m in _experts(route) if not shared(m)}
        if not used:
            break
        remaining = [m for m in remaining if id(m) not in used]
    return routes


def threshold(routes: int) -> int:
    """The fewest failing routes that can spoil a vote over ``routes``."""
    return (routes + 1) // 2


@dataclass(frozen=True)
class Vote:
    answer: Any
    """The value more than half the routes produced, or ``None``."""
    agreeing: int
    routes: int


def vote(routes: Sequence[Plan], inputs: Mapping[TypeId, Message] | Sequence[Message],
         budget: int, resolver: Resolver | None = None) -> Vote:
    """Run every route on ``inputs`` and answer the strict majority value.
    Values without a canonical digest are compared by equality."""
    tallies: list[tuple[Any, str | None, int]] = []
    for route in routes:
        value = execute(route, inputs, Workspace(), budget, resolver).payload
        digest = value_digest(value)
        for position, (seen, key, votes) in enumerate(tallies):
            if (key == digest) if digest is not None and key is not None else seen == value:
                tallies[position] = (seen, key, votes + 1)
                break
        else:
            tallies.append((value, digest, 1))
    best = max(tallies, key=lambda entry: entry[2], default=(None, None, 0))
    winner = 2 * best[2] > len(routes)
    return Vote(best[0] if winner else None, best[2] if winner else 0, len(routes))


def vote_risk(risks: Sequence[float]) -> float:
    """A bound on the probability that a vote over routes with these
    independent risks is wrong or abstains: ``e_t(risks)`` for
    ``t = threshold(len(risks))``, capped at 1."""
    t = threshold(len(risks))
    if t == 0:
        return 1.0
    sums = [1.0] + [0.0] * t
    for risk in risks:
        for size in range(t, 0, -1):
            sums[size] += sums[size - 1] * risk
    return min(1.0, sums[t])
