"""Probes that read how two values stand to one another (THEORY §55).

An observation gives a value, or nothing, at each of its slots. A probe reads
the value at a slot, whether two readings are the same, which of two is the
greater, or the step from one to the other. The readings compared may
themselves be relations or steps. Where either is nothing, so is the reading.

A learner that looks only through sameness and order probes is taught for
every value at once: its readings are unchanged when the values are renamed
or rescaled (§55.3). The slots, their kinds and their values are the caller's,
and a learner finds which probes matter.
"""

from collections.abc import Collection, Hashable, Mapping, Sequence
from itertools import combinations, permutations
from typing import Any

Probe = tuple[Hashable, ...]


def value(slot: Hashable) -> Probe:
    """The value at a slot."""
    return ("value", slot)


def same(first: Probe, second: Probe) -> Probe:
    """Whether two readings are equal."""
    return ("same", first, second)


def order(first: Probe, second: Probe) -> Probe:
    """Which of two readings is the greater: 1 if the second, -1 if the first, 0 if neither."""
    return ("order", first, second)


def step(first: Probe, second: Probe) -> Probe:
    """The second reading less the first."""
    return ("step", first, second)


def pool(kinds: Mapping[Hashable, Sequence[Hashable]], ordered: Collection[Hashable] = ()) -> tuple[Probe, ...]:
    """Whether each two slots of one kind hold the same value and, for an ordered kind, which holds the greater."""
    pairs = [(kind, value(first), value(second)) for kind, slots in kinds.items()
             for first, second in combinations(slots, 2)]
    return (*(same(first, second) for _, first, second in pairs),
            *(order(first, second) for kind, first, second in pairs if kind in ordered))


def analogies(places: Mapping[Hashable, Sequence[int]]) -> tuple[Probe, ...]:
    """Whether two pairs of slots that stand alike take the same step (§55.5).

    ``places`` says where each slot of one kind stands. Two pairs stand alike
    when the second slot of each lies the same way and as far from the first.
    """
    alike: dict[tuple[int, ...], list[Probe]] = {}
    for first, second in permutations(places, 2):
        apart = tuple(there - here for here, there in zip(places[first], places[second], strict=True))
        if apart > tuple(0 for _ in apart):
            alike.setdefault(apart, []).append(step(value(first), value(second)))
    return tuple(same(one, other) for steps in alike.values() for one, other in combinations(steps, 2))


def read(observation: Mapping[Hashable, Any], probe: Probe) -> Hashable:
    """One probe's reading of an observation."""
    if probe[0] == "value":
        return observation.get(probe[1])
    first: Any = read(observation, probe[1])
    second: Any = read(observation, probe[2])
    if first is None or second is None:
        return None
    if probe[0] == "same":
        return bool(first == second)
    if probe[0] == "order":
        return int(second > first) - int(second < first)
    return second - first
