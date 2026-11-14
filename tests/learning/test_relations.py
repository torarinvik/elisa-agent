from collections.abc import Hashable, Sequence
from random import Random

from nca.learning.inquiry import Inquiry
from nca.learning.relations import analogies, lifted, order, pool, read, same, step, value


def test_probes_read_values_sameness_order_and_steps() -> None:
    seen = {"a": 3, "b": 3, "c": 8}
    assert read(seen, value("a")) == 3 and read(seen, value("z")) is None
    assert read(seen, same(value("a"), value("b"))) is True and read(seen, same(value("a"), value("c"))) is False
    assert read(seen, order(value("a"), value("c"))) == 1 and read(seen, order(value("c"), value("a"))) == -1
    assert read(seen, order(value("a"), value("b"))) == 0 and read(seen, same(value("a"), value("z"))) is None
    assert read(seen, step(value("a"), value("c"))) == 5
    assert read(seen, same(step(value("a"), value("c")), step(value("b"), value("c")))) is True


def test_the_pool_does_not_grow_with_the_values() -> None:
    probes = pool({"mark": ("a", "b", "c"), "size": ("p", "q")}, ordered=("size",))
    assert len(probes) == len(set(probes)) == 3 + 1 + 1
    assert order(value("p"), value("q")) in probes and order(value("a"), value("b")) not in probes


def test_sameness_taught_on_some_values_holds_on_values_never_shown() -> None:
    """Good when two marks are the same: taught on four marks, asked about others (THEORY 55.1, 55.2)."""
    rng, slots = Random(1), ("left", "right", "other")
    relating = Inquiry((*map(value, slots), *pool({"mark": slots})), read, largest=2)
    valuing = Inquiry(tuple(map(value, slots)), read, largest=2)
    for _ in range(80):
        seen = {slot: rng.randrange(4) for slot in slots}
        for learner in (relating, valuing):
            learner.judge(seen, "take", seen["left"] == seen["right"])
    assert relating.looking_at == (same(value("left"), value("right")),)
    for left, right in ((7, 7), (7, 9), ("new", "new"), ("new", "other")):
        seen = {"left": left, "right": right, "other": 5}
        good, bad = relating.votes(seen, "take")
        assert (good > bad) == (left == right)
        assert valuing.votes(seen, "take") == (0, 0)


def test_order_taught_on_small_values_holds_on_large_ones() -> None:
    rng, slots = Random(2), ("first", "second", "third")
    learner = Inquiry(pool({"size": slots}, ordered=("size",)), read, largest=2)
    for _ in range(80):
        seen = {slot: rng.randrange(6) for slot in slots}
        learner.judge(seen, "take", seen["first"] < seen["third"])
    for first, third in ((10**9, 10**9 + 1), (10**9, 5), (-3.5, -3.25), (4, 4)):
        good, bad = learner.votes({"first": first, "second": 0, "third": third}, "take")
        assert (good > bad) == (first < third)


def test_a_step_that_repeats_is_found_among_relations_between_relations() -> None:
    """Good when the third value continues the step from the first to the second (THEORY 55.5)."""
    rng, slots = Random(3), ("first", "second", "third")
    steps = [step(value(slots[one]), value(slots[other])) for one, other in ((0, 1), (1, 2), (0, 2))]
    probes = (*pool({"size": slots}, ordered=("size",)), same(steps[0], steps[1]), same(steps[0], steps[2]),
              same(steps[1], steps[2]))
    learner = Inquiry(probes, read, largest=2)
    for _ in range(120):
        seen = {slot: rng.randrange(5) for slot in slots}
        learner.judge(seen, "take", seen["third"] - seen["second"] == seen["second"] - seen["first"])
    assert learner.looking_at == (same(steps[0], steps[1]),)
    for values in ((100, 250, 400), (100, 250, 401), (9, 9, 9), (-2, -7, -12)):
        good, bad = learner.votes(dict(zip(slots, values, strict=True)), "take")
        assert (good > bad) == (values[2] - values[1] == values[1] - values[0])


def test_a_step_taught_on_a_small_grid_holds_on_a_larger_one() -> None:
    """Good when the last cell continues its row as the row above does; cells are named from the last (55.5)."""
    rng = Random(4)
    places = {(row, column): (row, column) for row in range(-2, 1) for column in range(-2, 1)}
    probes = analogies(places)
    assert len(probes) == len(set(probes)) == 52
    learner = Inquiry((*pool({"size": tuple(places)}, ordered=("size",)), *probes), read, largest=2)
    for _ in range(150):
        seen = {(row, column): rng.randrange(6) for row in (-1, 0) for column in (-1, 0)}
        learner.judge(seen, "take", seen[0, 0] - seen[0, -1] == seen[-1, 0] - seen[-1, -1])
    for last in (41, 40):
        rows = {(-2, -2): 3, (-2, -1): 9, (-2, 0): 1, (-1, -2): 50, (-1, -1): 20, (-1, 0): 31, (0, -2): 7, (0, -1): 30}
        good, bad = learner.votes(rows | {(0, 0): last}, "take")
        assert (good > bad) == (last == 41)


def test_a_rule_one_storey_up_is_taught_through_the_lift_of_what_is_held_and_not_without() -> None:
    """Good when the last value keeps the step of steps: beyond the pool, within its lift (THEORY 55.7)."""
    places = {(0, column): (0, column) for column in range(-4, 1)}
    slots = tuple(places)
    held = same(step(value(slots[2]), value(slots[3])), step(value(slots[3]), value(slots[4])))
    lift = lifted([held], places)
    first = {slot: step(value(before), value(slot)) for before, slot in zip(slots, slots[1:], strict=False)}
    assert same(step(first[slots[2]], first[slots[3]]), step(first[slots[3]], first[slots[4]])) in lift
    assert len(lift) == len(set(lift)) == 4 and lifted(lift, places) != lift
    base = (*pool({"size": slots}, ordered=("size",)), *analogies(places))

    def taught(probes: tuple[Hashable, ...]) -> Inquiry:
        rng, learner = Random(5), Inquiry(probes, read, largest=2)
        for _ in range(150):
            row = [rng.randrange(-9, 10) for _ in slots]
            if rng.random() < 0.5:
                row[4] = 3 * row[3] - 3 * row[2] + row[1]
            learner.judge(dict(zip(slots, row, strict=True)), "take", keeps(row))
        return learner

    def keeps(row: Sequence[int]) -> bool:
        return row[4] - 2 * row[3] + row[2] == row[3] - 2 * row[2] + row[1]

    grown, flat = taught((*base, *lift)), taught(base)
    for row in ((0, 1, 4, 9, 16), (0, 1, 4, 9, 17), (500, 300, 0, -400, -900), (2, 2, 2, 2, 3)):
        good, bad = grown.votes(dict(zip(slots, row, strict=True)), "take")
        assert (good > bad) == keeps(row)
    assert flat.votes(dict(zip(slots, (0, 1, 4, 9, 16), strict=True)), "take")[0] <= flat.votes(
        dict(zip(slots, (0, 1, 4, 9, 17), strict=True)), "take")[0]
