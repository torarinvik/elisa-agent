from itertools import combinations, permutations
from random import Random

import pytest

from nca.learning.correspondence import Structure, alike, described, renaming

RING: Structure = ((0,) * 6, [(0, 1), (1, 2), (2, 3), (3, 4), (4, 5), (5, 0)])
RINGS: Structure = ((0,) * 6, [(0, 1), (1, 2), (2, 0), (3, 4), (4, 5), (5, 3)])


def _renamed(structure: Structure, names: list[int]) -> Structure:
    marks, joins = structure
    moved = [marks[0]] * len(marks)
    for part, name in enumerate(names):
        moved[name] = marks[part]
    return tuple(moved), [(names[one], names[other]) for one, other in joins]


def _searched(first: Structure, second: Structure) -> bool:
    """Whether some pairing among all of them keeps marks and joins."""
    (marks, joins), (others, theirs) = first, second
    mine = {frozenset(join) for join in joins}
    wanted = {frozenset(join) for join in theirs}
    return len(marks) == len(others) and any(
        all(others[names[part]] == marks[part] for part in range(len(marks)))
        and {frozenset((names[one], names[other])) for one, other in mine} == wanted
        for names in permutations(range(len(marks))))


def test_a_structure_renamed_is_the_same_and_the_pairing_keeps_marks_and_joins() -> None:
    drawn = Random(0)
    for _ in range(40):
        size = drawn.randrange(2, 13)
        joins = [pair for pair in combinations(range(size), 2) if drawn.random() < 0.4]
        first: Structure = (tuple(drawn.randrange(2) for _ in range(size)), joins)
        names = list(range(size))
        drawn.shuffle(names)
        second = _renamed(first, names)
        found = renaming(first, second)
        assert found is not None and sorted(found) == list(range(size))
        assert all(second[0][found[part]] == first[0][part] for part in range(size))
        assert ({frozenset((found[one], found[other])) for one, other in joins}
                == {frozenset(join) for join in second[1]})


def test_parts_described_alike_need_not_make_structures_the_same() -> None:
    one, other = described([RING, RINGS])
    assert len(set(one)) == 1 and one == other
    assert not alike(RING, RINGS) and alike(RINGS, RINGS)


def test_the_search_agrees_with_trying_every_pairing() -> None:
    drawn, same = Random(1), 0
    for _ in range(150):
        joins = drawn.sample(list(combinations(range(6), 2)), 7)
        theirs = drawn.sample(list(combinations(range(6), 2)), 7)
        first, second = ((0,) * 6, joins), ((0,) * 6, theirs)
        assert alike(first, second) == _searched(first, second)
        same += alike(first, second)
    assert 0 < same < 150


def test_marks_keep_structures_apart_and_malformed_joins_are_refused() -> None:
    line: Structure = (("a", "b", "a"), [(0, 1), (1, 2)])
    assert alike(line, (("a", "a", "b"), [(0, 2), (2, 1)]))
    assert not alike(line, (("b", "a", "a"), [(0, 1), (1, 2)]))
    assert not alike(line, (("a", "b"), [(0, 1)]))
    assert alike(((), []), ((), []))
    with pytest.raises(ValueError):
        alike((("a",), [(0, 0)]), (("a",), []))
