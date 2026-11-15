"""Probes that read how two values stand to one another (THEORY §55).

An observation gives a value, or nothing, at each of its slots. A probe reads
the value at a slot, whether two readings are the same, which of two is the
greater, or the step from one to the other. The readings compared may
themselves be relations or steps, and a step may be compared with a value. Where either is nothing, so is the reading.

A learner that looks only through sameness and order probes is taught for
every value at once: its readings are unchanged when the values are renamed
or rescaled (§55.3). The slots, their kinds and their values are the caller's,
and a learner finds which probes matter.

Values may be sets. ``melds`` reads whether the last set of a line holds just what a rule of two memberships
takes from the first two, and ``turns`` whether two pairs of sets of places on a ring are turned alike (§55.19).

``kept`` counts what the lines of a situation that are whole agree on and its last line keeps: a way of choosing
how a situation is completed from the situation alone, with nothing taught (§60).

``continued`` gives what follows one line of values from the line alone, by the steps of its steps (§60.7).

``found`` composes relations from values and steps and takes those the judgements pay for, in place of relations
written beforehand, and ``moved`` offers a relation at every place that stands alike (§59).
"""

from collections.abc import Callable, Collection, Hashable, Iterable, Mapping, Sequence
from itertools import combinations, pairwise, permutations
from math import log2
from typing import Any

import numpy as np

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


def analogies(places: Mapping[Hashable, Sequence[int]], readings: Mapping[Hashable, Probe] | None = None,
              ) -> tuple[Probe, ...]:
    """Whether two pairs of slots that stand alike take the same step (§55.5).

    ``places`` says where each slot of one kind stands. Two pairs stand alike
    when the second slot of each lies the same way and as far from the first.
    With ``readings`` the step is between what those probes read at the
    slots, not between the slots' values.
    """
    alike: dict[tuple[int, ...], list[Probe]] = {}
    for first, second in permutations(places, 2):
        apart = tuple(there - here for here, there in zip(places[first], places[second], strict=True))
        if apart > tuple(0 for _ in apart):
            ends = (readings[first], readings[second]) if readings else (value(first), value(second))
            alike.setdefault(apart, []).append(step(*ends))
    return tuple(same(one, other) for steps in alike.values() for one, other in combinations(steps, 2))


def sums(lines: Iterable[tuple[Hashable, Hashable, Hashable]]) -> tuple[Probe, ...]:
    """Whether the step between the ends of a line of three slots is the value between them (§55.13).

    For each line two probes: that the last is the first plus the middle, and that it is the first less the
    middle. The values need a nothing as well as a unit, as counts have.
    """
    return tuple(same(step(value(near), value(far)), value(between))
                 for first, between, last in lines for near, far in ((first, last), (last, first)))


def excesses(lines: Iterable[tuple[Hashable, Hashable, Hashable]]) -> tuple[Probe, ...]:
    """What the step between the ends of a line of three slots holds beyond the value between them (§55.15).

    For each line two readings, taking the step from the first to the last and from the last to the first.
    Two lines that keep one sum read the same wherever the values' nothing is put, which ``sums`` does not.
    """
    return tuple(step(value(between), step(value(near), value(far)))
                 for first, between, last in lines for near, far in ((first, last), (last, first)))


def agreeing(readings: Iterable[Sequence[Probe]]) -> tuple[Probe, ...]:
    """Whether each two readings of one group are the same: that one line does as another does (§55.14).

    A group holds the same reading taken on lines that stand alike, as a sum on each row.
    """
    return tuple(same(one, other) for group in readings for one, other in combinations(group, 2))


MELDS = ((True, True, True), (False, False, True), (True, True, False), (False, True, False), (True, False, False))
"""The ways a set is made of two that turn on both: whether it holds what the second alone holds, what the first
alone holds, and what both hold. What neither holds is in none."""


def meld(how: tuple[bool, bool, bool], first: Probe, second: Probe) -> Probe:
    """The set made of two sets read: ``how`` says whether it takes what only the second holds, what only the
    first holds, and what both hold."""
    return ("meld", how, first, second)


def turn(ring: int, first: Probe, second: Probe) -> Probe:
    """The turns of a ring of ``ring`` places that carry the first set of places read onto the second."""
    return ("turn", ring, first, second)


def share(first: Probe, second: Probe) -> Probe:
    """Whether two sets read have a member in common."""
    return ("share", first, second)


def count(held: Probe) -> Probe:
    """How many a set read holds."""
    return ("count", held)


def bag(*held: Probe) -> Probe:
    """What several readings hold between them, in whatever order."""
    return ("bag", *held)


def told(line: Sequence[Hashable], *, sets: bool = False, ring: int = 0) -> tuple[tuple[Probe, ...], ...]:
    """What is read of one line of slots: readings a rule along the line could keep from line to line (§60).

    Three groups, by how far a reading fixes the last slot (60.4): those that one value of it alone keeps, those
    that fix how many it holds and not which, and those that do not turn on it. Of numbers, the first are the
    step to the last, the step from the step before to that one and, in a line of three, what the step between
    the ends holds beyond the one between, either way; the last are whether each two are the same, the earlier
    steps and what the numbers hold between them. Of sets, the first are, in a line of three, whether the last
    is made of the first two in each way, and whether the last two are turned as the two before them are on a
    ring of ``ring`` places; the second are the first readings of how many each holds; the last are whether
    each two are the same, what they hold between them, and the other readings of how many each holds.
    """
    held = [value(slot) for slot in line]

    def numbers(read: Sequence[Probe]) -> tuple[tuple[Probe, ...], tuple[Probe, ...]]:
        steps = [step(one, other) for one, other in pairwise(read)]
        bends = [step(one, other) for one, other in pairwise(steps)]
        beyond = ((step(read[1], step(read[0], read[2])), step(read[1], step(read[2], read[0])))
                  if len(read) == 3 else ())
        return ((steps[-1], *bends[-1:], *beyond),
                (*(same(one, other) for one, other in combinations(read, 2)), *steps[:-1], *bends[:-1], bag(*read)))

    if not sets:
        fixing, loose = numbers(held)
        return fixing, (), loose
    turned = [turn(ring, one, other) for one, other in pairwise(held)] if ring else []
    shared = [share(one, other) for one, other in pairwise(turned)]
    many, loose = numbers([count(one) for one in held])
    return ((*((same(meld(how, held[0], held[1]), held[2]) for how in MELDS) if len(held) == 3 else ()),
             *shared[-1:]), many,
            (*(same(one, other) for one, other in combinations(held, 2)), bag(*held), *shared[:-1], *loose))


def kept(observation: Mapping[Hashable, Any], lines: Sequence[Sequence[Hashable]], *,
         sets: bool = False, ring: int = 0) -> tuple[int, ...]:
    """How many readings the lines before the last agree on and the last line keeps, group by group (§60).

    The groups are those of ``told``: a completion that keeps more of an earlier group is ahead whatever it
    keeps of the later ones (60.4). That the last is not made in some way, or not turned alike, does not turn on
    it and is counted in the last group; what a line holds between its slots is counted as fixing the last one
    where the last line's earlier slots hold all of it but one. A reading the earlier lines differ in, or that reads nothing of one
    of them, says nothing of the last.
    """
    groups = list(zip(*(told(line, sets=sets, ring=ring) for line in lines), strict=True))
    counts = [0] * len(groups)
    for place, group in enumerate(groups):
        for probes in zip(*group, strict=True):
            held, *rest = (read(observation, probe) for probe in probes)
            if held is None or any(other != held for other in rest):
                continue
            fixes = place
            if probes[-1][0] == "bag":
                before = read(observation, bag(*probes[-1][1:-1]))
                if before is not None and before < held and len(held) - len(before) == 1:
                    fixes = int(probes[-1][1][0] == "count")
            counts[-1 if held is False else fixes] += 1
    return tuple(counts)


Way = tuple[Callable[[Any, Any], Any], Callable[[Any, Any], Any]]
"""A way of stepping: what leads from one value to the next, and the value a step leads to from one. Either may
return nothing where there is no such step."""
STEPS: Way = (lambda first, second: second - first, lambda first, by: first + by)
"""Stepping by what is added."""


def continued(line: Sequence[Any], ways: Sequence[Way] = (STEPS,)) -> Any:
    """What follows a line of values, from the line alone (§60.7); nothing where the line is empty.

    The steps between neighbours are a line one shorter, and the steps between those another, each taken in
    one of ``ways``. The shallowest such line whose steps are all the same, two or more of them, is continued
    by that step, and each line above by the step so found; among lines as shallow, the one of the earlier
    ways. Where no line has steps that agree, the first way is followed down to a single step.
    """
    def unwound(lasts: Sequence[tuple[Way, Any]], by: Any) -> Any:
        for (_, lead), last in reversed(lasts):
            by = lead(last, by)
        return by

    if not line:
        return None
    towers: list[tuple[list[Any], list[tuple[Way, Any]]]] = [(list(line), [])]
    bottom = None
    while towers:
        below = []
        for held, lasts in towers:
            for way in ways:
                steps = [way[0](first, second) for first, second in pairwise(held)]
                if not steps or any(step is None for step in steps):
                    continue
                under = [*lasts, (way, held[-1])]
                if len(steps) > 1 and all(step == steps[0] for step in steps):
                    return unwound(under, steps[0])
                if len(steps) == 1 and bottom is None:
                    bottom = unwound(under, steps[0])
                below.append((steps, under))
        towers = below
    return line[0] if bottom is None else bottom


def melds(lines: Iterable[tuple[Hashable, Hashable, Hashable]]) -> tuple[Probe, ...]:
    """Whether the last set of a line of three slots is made of the first two, in each way of ``MELDS`` (§55.19)."""
    return tuple(same(meld(how, value(first), value(between)), value(last))
                 for first, between, last in lines for how in MELDS)


def turns(places: Mapping[Hashable, Sequence[int]], ring: int) -> tuple[Probe, ...]:
    """Whether two pairs of slots that stand alike hold sets of places turned alike on a ring (§55.19).

    Pairs stand alike as in ``analogies``. A set that a turn carries onto itself is carried onto another by
    several turns, so two pairs are turned alike when some turn serves both.
    """
    alike: dict[tuple[int, ...], list[Probe]] = {}
    for first, second in permutations(places, 2):
        apart = tuple(there - here for here, there in zip(places[first], places[second], strict=True))
        if apart > tuple(0 for _ in apart):
            alike.setdefault(apart, []).append(turn(ring, value(first), value(second)))
    return tuple(share(one, other) for found in alike.values() for one, other in combinations(found, 2))


def _slots(probe: Probe) -> list[Hashable]:
    if probe[0] == "value":
        return [probe[1]]
    return [slot for part in probe[1:] if isinstance(part, tuple) and part and isinstance(part[0], str)
            for slot in _slots(part)]


def _steps(probe: Probe) -> list[Probe]:
    """The steps a probe is built from, itself among them."""
    if probe[0] == "value":
        return []
    return [*([probe] if probe[0] == "step" else []), *(found for part in probe[1:] for found in _steps(part))]


def _moved(probe: Probe, slots: Mapping[Hashable, Hashable]) -> Probe:
    if probe[0] == "value":
        return value(slots[probe[1]])
    return (probe[0], *(_moved(part, slots) if isinstance(part, tuple) and part and isinstance(part[0], str) else part
                        for part in probe[1:]))


def lifted(held: Iterable[Probe], places: Mapping[Hashable, Sequence[int]]) -> tuple[Probe, ...]:
    """Probes one storey above those ``held``: analogies between the steps they are built from (§55.7).

    Each step in a held probe is moved to every place where all its slots
    stand, which gives one reading at each such place, and the analogies
    between those readings are offered. Probes built alike on the same
    slots are offered once.
    """
    at = {tuple(place): slot for slot, place in places.items()}
    offered: dict[Probe, None] = {}
    for found in dict.fromkeys(step for probe in held for step in _steps(probe)):
        home = max(tuple(places[slot]) for slot in _slots(found))
        readings: dict[Hashable, Probe] = {}
        for slot, place in places.items():
            moves = {tuple(places[one]): tuple(far - near + here for far, near, here in
                                                zip(places[one], home, place, strict=True))
                     for one in _slots(found)}
            if all(there in at for there in moves.values()):
                readings[slot] = _moved(found, {at[here]: at[there] for here, there in moves.items()})
        offered.update(dict.fromkeys(analogies({slot: places[slot] for slot in readings}, readings)))
    return tuple(offered)


def read(observation: Mapping[Hashable, Any], probe: Probe) -> Hashable:
    """One probe's reading of an observation."""
    if probe[0] == "value":
        return observation.get(probe[1])
    if probe[0] in ("count", "bag"):
        held = [read(observation, part) for part in probe[1:]]
        if any(one is None for one in held):
            return None
        return len(held[0]) if probe[0] == "count" else frozenset(held)
    first: Any = read(observation, probe[-2])
    second: Any = read(observation, probe[-1])
    if first is None or second is None:
        return None
    if probe[0] == "meld":
        only, alone, both = probe[1]
        return frozenset((second - first if only else frozenset()) | (first - second if alone else frozenset())
                         | (first & second if both else frozenset()))
    if probe[0] == "turn":
        return frozenset(by for by in range(probe[1]) if {(place + by) % probe[1] for place in first} == second)
    if probe[0] == "share":
        return bool(first & second)
    if probe[0] == "same":
        return bool(first == second)
    if probe[0] == "order":
        return int(second > first) - int(second < first)
    return second - first


def _size(probe: Probe) -> int:
    return len(_slots(probe))


def _told(good: np.ndarray, bad: np.ndarray, share: float) -> np.ndarray:
    """The bits each class of good and bad judgements tells beyond the share of good among them all (§59.2)."""
    held = good + bad
    lean = np.divide(good, held, out=np.full(held.shape, share), where=held > 0)
    with np.errstate(divide="ignore", invalid="ignore"):
        bits = (np.where(lean > 0, lean * np.log2(lean / share), 0.0)
                + np.where(lean < 1, (1 - lean) * np.log2((1 - lean) / (1 - share)), 0.0))
    return held * bits


def found(situations: Sequence[Mapping[Hashable, Any]], verdicts: Sequence[bool], slots: Sequence[Hashable], *,
          margin: float = 2.0, most: int = 40, deep: bool = True) -> tuple[Probe, ...]:
    """Relations composed over ``slots`` that the judgements pay for (§59).

    The numbers composed are each value, the step between two values and, with ``deep``, the step from a value
    to such a step; a relation is whether two of them are the same. The judgements are divided by the relation
    that tells most of their verdicts beyond what its name costs among the relations of its size, the logarithm
    of the judgements and ``margin`` bits; the classes it leaves are divided likewise. At most ``most`` are
    taken. A value that is no number reads as nothing. The work grows with the square of the numbers composed:
    with ``deep``, with the sixth power of the slots.
    """
    held = np.array([[situation.get(slot) if isinstance(situation.get(slot), int | float)
                      and not isinstance(situation.get(slot), bool) else np.nan for slot in slots]
                     for situation in situations], dtype=float).reshape(len(situations), len(slots))
    good = np.asarray(verdicts, dtype=bool)
    names: list[Probe] = [value(slot) for slot in slots]
    columns = [held[:, place] for place in range(len(slots))]
    for one, other in permutations(range(len(slots)), 2):
        names.append(step(value(slots[one]), value(slots[other])))
        columns.append(held[:, other] - held[:, one])
    for place in range(len(slots)) if deep else ():
        for between in range(len(slots), len(slots) ** 2):
            if slots[place] not in _slots(names[between]):
                names.append(step(value(slots[place]), names[between]))
                columns.append(columns[between] - held[:, place])
    if len(names) < 2 or not len(good):
        return ()
    numbers = np.array(columns).T
    read_ = ~np.isnan(numbers)
    sizes = np.array([_size(name) for name in names])
    together = sizes[:, None] + sizes[None, :]
    upper = np.triu(np.ones(together.shape, dtype=bool), 1)
    need = np.log2(np.maximum(np.bincount(together[upper]), 1))[together] + log2(len(good)) + margin
    taken: list[Probe] = []
    waiting = [np.ones(len(good), dtype=bool)]
    while waiting and len(taken) < most:
        live = waiting.pop(0)
        verdict = good[live]
        if verdict.all() or not verdict.any():
            continue
        share, here, there = float(verdict.mean()), numbers[live], read_[live]
        yes, no = verdict.astype(float), (~verdict).astype(float)
        told = np.empty(together.shape)
        for one in range(len(names)):
            both = there[:, [one]] & there
            same_ = (here[:, [one]] == here) & both
            other = both & ~same_
            told[one] = (_told(yes @ same_, no @ same_, share) + _told(yes @ other, no @ other, share)
                         + _told(yes @ ~both, no @ ~both, share))
        told = np.where(upper, told - need, -np.inf)
        one, other = np.unravel_index(int(told.argmax()), told.shape)
        if told[one, other] <= 0:
            continue
        relation = same(names[one], names[other])
        if relation not in taken:
            taken.append(relation)
        both = read_[:, one] & read_[:, other]
        alike = (numbers[:, one] == numbers[:, other]) & both
        waiting += [live & alike, live & both & ~alike, live & ~both]
    return tuple(taken)


def moved(probes: Iterable[Probe], moves: Iterable[Mapping[Hashable, Hashable]]) -> tuple[Probe, ...]:
    """Each probe at every place the moves take it to, each once (§59.4).

    A move gives, for each slot, the slot that stands as it does. A sameness and the same sameness written the
    other way round are one.
    """
    offered: dict[Hashable, Probe] = {}
    moves = list(moves)
    for probe in probes:
        for move in moves:
            image = _moved(probe, move)
            name = frozenset(image[1:]) if image[0] == "same" else image
            offered.setdefault(name, image)
    return tuple(offered.values())
