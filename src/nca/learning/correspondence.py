"""Structures that are the same under a renaming of their parts (THEORY §58).

A structure is some parts, each with a mark, and joins between pairs of them. Two structures are the same
under a renaming when the parts of one can be paired with the parts of the other, one to one, so that paired
parts have the same mark and two parts are joined exactly when their partners are. Nothing names a part: the
pairing is what is sought.

A part is described by its mark and the descriptions of the parts it is joined to, round after round. A renaming
keeps every description (``NCA.renaming_keeps_descriptions``), so parts are paired only with parts described
alike; that the descriptions agree does not make two structures the same (``NCA.counting_joins_does_not_tell``),
so the pairing is then sought part by part and every pairing returned has been checked join by join.

Where what was read does not say what joins what, a structure comes with doubts, each the ways one place may
be read, and two structures may be the same when some reading of each is (§58.4).

The parts, their marks and what joins them are the caller's.
"""

from collections import Counter
from collections.abc import Collection, Hashable, Iterator, Sequence
from itertools import product
from math import prod

Structure = tuple[Sequence[Hashable], Collection[tuple[int, int]]]
"""The mark of each part and the pairs of parts that are joined; a join holds both ways."""
Doubt = Sequence[Collection[tuple[int, int]]]
"""The ways one place of a structure may be read, each a set of joins."""


def _near(structure: Structure) -> list[set[int]]:
    marks, joins = structure
    near: list[set[int]] = [set() for _ in marks]
    for one, other in joins:
        if one == other or not (0 <= one < len(marks) and 0 <= other < len(marks)):
            raise ValueError("a join is between two different parts of the structure")
        near[one].add(other)
        near[other].add(one)
    return near


def described(structures: Sequence[Structure]) -> list[list[int]]:
    """A number for each part of each structure, the same for two parts exactly when they are described alike.

    A part's description is its mark and, as many times as they occur, the descriptions of the parts it is
    joined to, taken until no round tells more parts apart. The numbers compare parts of all the structures
    given, and of those alone.
    """
    nears = [_near(structure) for structure in structures]
    names: dict[Hashable, int] = {}
    held = [[names.setdefault(mark, len(names)) for mark in marks] for marks, _ in structures]
    while True:
        names = {}
        told = [[names.setdefault((before[part], tuple(sorted(before[other] for other in near[part]))), len(names))
                 for part in range(len(before))] for before, near in zip(held, nears, strict=True)]
        if len(names) == len({number for numbers in held for number in numbers}):
            return told
        held = told


def renaming(first: Structure, second: Structure) -> tuple[int, ...] | None:
    """For each part of the first structure the part of the second it is paired with, or nothing if no pairing
    keeps marks and joins."""
    mine, theirs = described([first, second])
    if sorted(mine) != sorted(theirs):
        return None
    near, other = _near(first), _near(second)
    alike: dict[int, list[int]] = {}
    for part, number in enumerate(theirs):
        alike.setdefault(number, []).append(part)
    order = sorted(range(len(mine)), key=lambda part: (len(alike[mine[part]]), -len(near[part])))
    paired: dict[int, int] = {}
    taken: set[int] = set()

    def pair(place: int) -> bool:
        if place == len(order):
            return True
        part = order[place]
        for partner in alike[mine[part]]:
            if partner not in taken and all((paired[earlier] in other[partner]) == (earlier in near[part])
                                            for earlier in paired):
                paired[part] = partner
                taken.add(partner)
                if pair(place + 1):
                    return True
                del paired[part]
                taken.discard(partner)
        return False

    return tuple(paired[part] for part in range(len(mine))) if pair(0) else None


def alike(first: Structure, second: Structure) -> bool:
    """Whether the two structures are the same under a renaming of their parts."""
    return renaming(first, second) is not None


def _joins(joins: Collection[tuple[int, int]]) -> set[tuple[int, int]]:
    return {(min(join), max(join)) for join in joins}


def readings(structure: Structure, doubts: Sequence[Doubt]) -> Iterator[Structure]:
    """The structures a structure read with doubts may be: the joins no doubt names with one way of each doubt."""
    marks, joins = structure
    sure = _joins(joins) - {join for doubt in doubts for way in doubt for join in _joins(way)}
    for chosen in product(*doubts):
        yield marks, sorted(sure.union(*map(_joins, chosen)))


def may_be_alike(first: Structure, second: Structure, mine: Sequence[Doubt] = (), theirs: Sequence[Doubt] = (),
                 most: int = 20_000) -> bool:
    """Whether some reading of the first structure is the same under a renaming as some reading of the second.

    Readings are compared only where as many parts have each number of joins. A structure with more than
    ``most`` readings is taken as it was given.
    """
    def tally(structure: Structure) -> tuple[int, ...]:
        met = Counter(part for join in structure[1] for part in join)
        return tuple(sorted(met[part] for part in range(len(structure[0]))))

    def ways(structure: Structure, doubts: Sequence[Doubt]) -> list[Structure]:
        return list(readings(structure, doubts)) if prod(map(len, doubts)) <= most else [structure]

    if len(first[0]) != len(second[0]):
        return False
    held: dict[tuple[int, ...], list[Structure]] = {}
    for way in ways(second, theirs):
        held.setdefault(tally(way), []).append(way)
    return any(alike(way, other) for way in ways(first, mine) for other in held.get(tally(way), ()))
