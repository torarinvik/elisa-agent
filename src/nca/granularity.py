"""How many experts a library should hold, and how large each should be (§61).

Lengths are in bits: the length of a part is the base-two logarithm of how many
behaviours it is one of, and the address of an expert is the logarithm of how
many experts a route may name. A part a caller measures in examples or in any
other unit is accounted the same way, so long as addresses are in that unit.
"""

from __future__ import annotations

from collections.abc import Collection, Hashable, Mapping
from dataclasses import dataclass
from math import log2, sqrt


def saved(length: float, uses: int, address: float) -> float:
    """What one expert of ``length`` named by ``uses`` users saves over a copy held by each (§61.1)."""
    if uses < 1 or length < 0 or address < 0:
        raise ValueError("uses must be positive, and length and address nonnegative")
    return (uses - 1) * length - uses * address


def balanced(content: float, address: float) -> tuple[float, float]:
    """The size of expert and the length of route at which finding either by trial costs alike (§61.3).

    A route of that many experts of that size holds ``content`` bits. Fewer and larger experts are dearer to
    find than the route, more and smaller ones cheaper.
    """
    if content <= 0 or address <= 0:
        raise ValueError("content and address must be positive")
    size = sqrt(content * address)
    return size, content / size


def searched(content: float, address: float, steps: int) -> float:
    """The logarithm of the trials that find ``steps`` experts holding ``content`` bits and their route (§61.3)."""
    if steps < 1 or content < 0 or address < 0:
        raise ValueError("steps must be positive, and content and address nonnegative")
    size, route = content / steps, address * steps
    high = max(size, route)
    return high + log2(steps * 2.0 ** (size - high) + 2.0 ** (route - high))


@dataclass(frozen=True)
class Library:
    """Parts gathered into experts, the parts left to their users, and what the whole costs to hold (§61.2)."""

    experts: tuple[tuple[frozenset[Hashable], frozenset[Hashable]], ...]
    private: frozenset[Hashable]
    address: float
    cost: float
    apart: float


def gathered(users: Mapping[Hashable, Collection[Hashable]], lengths: Mapping[Hashable, float]) -> Library:
    """Gather parts into experts so that holding them costs least (§61.2).

    ``users`` names who uses each part. Parts with the same users make one expert: it is named once where
    they would be named apart. An expert is kept where it saves over a copy held by each user, at the address
    of the experts kept; the address falls as experts are dropped, so this is repeated until none is dropped.
    Returns the experts, each as its parts and its users, the parts left to their users, the address, the
    cost, and the cost with every part held apart by every user.
    """
    groups: dict[frozenset[Hashable], set[Hashable]] = {}
    for part, who in users.items():
        if lengths[part] < 0:
            raise ValueError("lengths must be nonnegative")
        groups.setdefault(frozenset(who), set()).add(part)
    held = {who: frozenset(parts) for who, parts in groups.items() if who}
    weight = {who: sum(lengths[part] for part in parts) for who, parts in held.items()}
    kept = sorted(held, key=lambda who: (-weight[who], sorted(map(repr, who))))
    while True:
        address = log2(len(kept)) if len(kept) > 1 else 0.0
        still = [who for who in kept if saved(weight[who], len(who), address) > 0]
        if len(still) == len(kept):
            break
        kept = still
    private = frozenset(part for who, parts in held.items() if who not in kept for part in parts)
    apart = sum(len(who) * weight[who] for who in held)
    cost = sum(weight[who] + len(who) * address if who in kept else len(who) * weight[who] for who in held)
    return Library(tuple((held[who], who) for who in kept), private, address, cost, apart)
