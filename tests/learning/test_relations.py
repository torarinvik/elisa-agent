from collections.abc import Hashable, Sequence
from fractions import Fraction
from itertools import permutations
from random import Random

from nca.learning.inquiry import Inquiry
from nca.learning.relations import (
    STEPS,
    Way,
    continued,
    cuts,
    agreeing,
    analogies,
    between,
    bag,
    count,
    excesses,
    found,
    kept,
    lifted,
    meld,
    melds,
    moved,
    order,
    pool,
    read,
    same,
    share,
    step,
    sums,
    told,
    turn,
    turns,
    value,
)


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


def test_a_sum_is_read_as_a_step_that_is_a_value_where_sameness_order_and_steps_read_two_rows_alike() -> None:
    line = ("first", "second", "last")
    plus, minus = sums([line])
    summed, other = dict(zip(line, (1, 3, 4), strict=True)), dict(zip(line, (1, 3, 6), strict=True))
    asked = (*pool({"held": line}, ordered=("held",)), *analogies({"first": (0,), "second": (1,), "last": (2,)}))
    assert [read(summed, probe) for probe in asked] == [read(other, probe) for probe in asked]
    assert read(summed, plus) is True and read(other, plus) is False and read(summed, minus) is False
    assert read({"first": 5, "second": 2, "last": 3}, minus) is True
    assert read({"first": 5, "second": 2}, plus) is None


def test_two_rows_agreeing_on_being_sums_tells_a_right_last_row_where_its_own_reading_does_not() -> None:
    rows = [tuple((row, column) for column in range(3)) for row in range(2)]
    (agree,) = agreeing([[sums([row])[0] for row in rows]])
    seen = [dict(zip((*rows[0], *rows[1]), values, strict=True))
            for values in ((1, 2, 3, 2, 2, 4), (1, 2, 3, 2, 2, 5), (1, 2, 4, 2, 2, 5), (1, 2, 4, 2, 2, 4))]
    assert [read(one, agree) for one in seen] == [True, False, True, False]
    assert [read(one, sums([rows[1]])[0]) for one in seen] == [True, False, False, True]


def test_rows_keeping_one_sum_agree_in_excess_wherever_the_ladder_is_numbered_from() -> None:
    rows = [tuple((row, column) for column in range(3)) for row in range(2)]
    (more, less) = agreeing([[excesses([row])[way] for row in rows] for way in (0, 1)])
    (plain,) = agreeing([[sums([row])[0] for row in rows]])
    for shift in (0, 1, -3):
        kept = dict(zip((*rows[0], *rows[1]), (value + shift for value in (1, 2, 3, 2, 4, 6)), strict=True))
        broken = dict(zip((*rows[0], *rows[1]), (value + shift for value in (1, 2, 3, 2, 4, 7)), strict=True))
        lessened = dict(zip((*rows[0], *rows[1]), (value + shift for value in (5, 2, 3, 6, 1, 5)), strict=True))
        assert read(kept, more) is True and read(broken, more) is False
        assert read(lessened, less) is True and read(lessened, more) is False
    shifted = dict(zip((*rows[0], *rows[1]), (2, 3, 4, 3, 5, 7), strict=True))
    assert read(shifted, sums([rows[0]])[0]) is False and read(shifted, plain) is True
    assert read({rows[0][0]: 1}, more) is None


def test_a_relation_no_one_wrote_is_found_from_judgements_and_nothing_is_found_where_nothing_is_told() -> None:
    """Good exactly when the last line has the first line's total; no slot alone, nor any two, says so."""
    drawn = Random(0)
    slots = [(row, column) for row in range(2) for column in range(3)]
    situations, verdicts = [], []
    for number in range(300):
        first = [drawn.randrange(6) for _ in range(3)]
        last = [drawn.randrange(6) for _ in range(3)]
        if number % 2:
            last[2] = sum(first) - last[0] - last[1]
        situations.append(dict(zip(slots, (*first, *last), strict=True)))
        verdicts.append(sum(first) == sum(last))
    relations = found(situations, verdicts, slots)
    assert 1 <= len(relations) <= 2
    assert [read(situation, relations[0]) for situation in situations] == verdicts
    assert found(situations, [drawn.random() < 0.5 for _ in situations], slots) == ()
    assert found(situations[:6], verdicts[:6], slots) == ()
    assert found([], [], slots) == () and found(situations, verdicts, slots[:1]) == ()
    assert found([{slots[0]: "a", slots[1]: None}] * 40, [True, False] * 20, slots[:2]) == ()


def test_a_relation_is_offered_at_every_place_that_stands_alike_and_reads_the_moved_situation() -> None:
    slots = [(row, column) for row in range(2) for column in range(2)]
    relation = same(value((0, 0)), step(value((0, 1)), value((1, 1))))
    swapped = {(row, column): (1 - row, column) for row, column in slots}
    turned = {(row, column): (column, row) for row, column in slots}
    still = {slot: slot for slot in slots}
    images = moved([relation, same(value((0, 0)), value((0, 1)))], [still, swapped, turned])
    assert images[0] == relation and len(images) == 6
    assert moved([same(value(1), value(2))], [{1: 2, 2: 1}, {1: 1, 2: 2}]) == (same(value(2), value(1)),)
    held = {(0, 0): 3, (0, 1): 1, (1, 0): 7, (1, 1): 4}
    back = {slot: held[swapped[slot]] for slot in slots}
    assert read(held, moved([relation], [swapped])[0]) == read(back, relation)


def test_a_set_made_of_two_is_read_in_each_way_and_sets_of_places_turned_alike_share_a_turn() -> None:
    first, second = frozenset({0, 1}), frozenset({1, 3})
    seen = {"a": first, "b": second, "c": first | second, "d": first - second}
    line = [("a", "b", "c")]
    assert [read(seen, probe) for probe in melds(line)] == [True, False, False, False, False]
    assert [read({**seen, "c": seen["d"]}, probe) for probe in melds(line)] == [False, False, False, True, False]
    assert read(seen, meld((True, True, False), value("a"), value("b"))) == frozenset({0, 3})
    assert read({"a": first}, melds(line)[0]) is None
    places = {(row, column): (row, column) for row in range(2) for column in range(3)}
    ring = 4
    turned = {(0, 0): frozenset({0}), (0, 1): frozenset({1}), (0, 2): frozenset({2}),
              (1, 0): frozenset({1, 2}), (1, 1): frozenset({2, 3}), (1, 2): frozenset({3, 0})}
    asked = turns(places, ring)
    assert len(asked) == len(set(asked)) and share(turn(ring, value((0, 0)), value((0, 1))),
                                                   turn(ring, value((1, 1)), value((1, 2)))) in asked
    assert all(read(turned, probe) is True for probe in asked if probe[1][2][1][0] == probe[1][3][1][0]
               and probe[2][2][1][0] == probe[2][3][1][0]
               and probe[1][3][1][1] - probe[1][2][1][1] == 1)
    broken = {**turned, (1, 2): frozenset({0, 1})}
    assert read(broken, share(turn(ring, value((1, 0)), value((1, 1))), turn(ring, value((1, 1)), value((1, 2))))) is False
    whole = frozenset(range(ring))
    assert read({"a": whole, "b": whole}, turn(ring, value("a"), value("b"))) == whole
    assert read({"a": first, "b": second}, turn(ring, value("a"), value("b"))) == frozenset()


def test_the_last_line_is_completed_by_what_the_whole_lines_agree_on_with_nothing_taught() -> None:
    lines = [((row, 0), (row, 1), (row, 2)) for row in range(3)]
    shown = {(0, 0): 1, (0, 1): 3, (0, 2): 5, (1, 0): 4, (1, 1): 6, (1, 2): 8, (2, 0): 2, (2, 1): 4}
    scores = {last: kept({**shown, (2, 2): last}, lines) for last in range(10)}
    assert max(scores, key=scores.__getitem__) == 6 and sorted(scores.values())[-2] < scores[6]
    dealt = {(0, 0): 7, (0, 1): 2, (0, 2): 5, (1, 0): 2, (1, 1): 5, (1, 2): 7, (2, 0): 5, (2, 1): 7}
    scores = {last: kept({**dealt, (2, 2): last}, lines) for last in range(10)}
    assert max(scores, key=scores.__getitem__) == 2 and scores[2][0] == 1 and scores[7][0] == 0
    assert kept({**shown, (0, 1): None, (2, 2): 6}, lines) == (0, 0, 1)
    summed = {(0, 0): 1, (0, 1): 2, (0, 2): 3, (1, 0): 2, (1, 1): 3, (1, 2): 5, (2, 0): 0, (2, 1): 0}
    scores = {last: kept({**summed, (2, 2): last}, lines) for last in range(10)}
    assert max(scores, key=scores.__getitem__) == 0 and (scores[0], scores[7]) == ((1, 0, 0), (0, 0, 2))
    assert max(scores, key=lambda last: sum(scores[last])) != 0
    down = [((0, column), (1, column), (2, column)) for column in range(3)]
    assert kept({**summed, (2, 0): 4, (2, 1): 1}, lines[:2])[0] == 1
    assert kept({**summed, (2, 0): 4, (2, 1): 1}, down[:2])[0] == 0
    filled = {(0, 0): frozenset({0}), (0, 1): frozenset({2}), (0, 2): frozenset({0, 2}),
              (1, 0): frozenset({1, 3}), (1, 1): frozenset({0}), (1, 2): frozenset({0, 1, 3}),
              (2, 0): frozenset({2}), (2, 1): frozenset({2, 3})}
    offered = [frozenset({2, 3}), frozenset({2}), frozenset({0, 1, 3}), frozenset({1, 2, 3})]
    scores = [kept({**filled, (2, 2): last}, lines, sets=True, ring=4) for last in offered]
    assert scores.index(max(scores)) == 0 and scores[0][0] > scores[3][0] and scores[0][1] < scores[3][1]
    dealt = {(0, 0): frozenset({0}), (0, 1): frozenset({1}), (0, 2): frozenset({2}),
             (1, 0): frozenset({1}), (1, 1): frozenset({2}), (1, 2): frozenset({0}),
             (2, 0): frozenset({2}), (2, 1): frozenset({0}), (2, 2): frozenset({1})}
    assert kept(dealt, lines, sets=True, ring=0) == (1, 4, 13)
    assert read({"a": frozenset({4, 5})}, count(value("a"))) == 2
    assert read({"a": 1, "b": 2, "c": 1}, bag(value("a"), value("b"), value("c"))) == frozenset({1, 2})
    assert [len(group) for group in told(lines[0])] == [4, 0, 5]
    assert [len(group) for group in told(lines[0], sets=True, ring=4)] == [6, 4, 9]
    pairs = [((row, 0), (row, 1)) for row in range(2)]
    assert [kept({(0, 0): 2, (0, 1): 5, (1, 0): 1, (1, 1): last}, pairs)[0] for last in (4, 1, 5)] == [1, 0, 0]
    fours = [tuple((row, column) for column in range(4)) for row in range(3)]
    rising = {(row, column): 2 * row + column for row in range(3) for column in range(4)}
    assert max(range(12), key=lambda last: kept({**rising, (2, 3): last}, fours)) == 7


def test_a_line_is_continued_by_the_steps_of_its_steps_with_nothing_taught() -> None:
    assert continued([3, 7, 11, 15]) == 19
    assert continued([2, 3, 6, 11]) == 18
    assert continued([1, 0, 5, 22]) == 57
    assert continued([4, 4, 4]) == 4 and continued([9]) == 9 and continued([]) is None
    assert continued([5, 8]) == 11

    def ratio(first: Fraction, second: Fraction, _: int) -> Fraction | None:
        return second / first if first else None

    times: Way = (ratio, lambda first, by, _: first * by)
    doubling = [Fraction(term) for term in (5, 8, 14, 26)]
    assert continued(doubling, (STEPS, times)) == 50 and continued(doubling) == 47
    assert continued([Fraction(term) for term in (3, 6, 12, 24)], (STEPS, times)) == 48
    assert continued([Fraction(term) for term in (0, 2, 6, 12)], (STEPS, times)) == 20


def test_a_line_alike_at_a_stride_is_continued_from_a_stride_back_and_steps_may_be_taken_by_their_place() -> None:
    assert continued([1, 4, 5, 8, 9], strides=2) == 12 and continued([1, 4, 5, 8, 9]) == -4
    assert continued([7, 2, 9, 7, 2], strides=3) == 9
    assert continued([2, 3, 6, 11], strides=3) == 18
    assert continued([0, 1, 3, 4, 6, 7], strides=2) == 9
    placed: Way = (lambda first, second, place: Fraction(second - first, place),
                   lambda first, by, place: first + by * place)
    assert continued([3, 5, 17, 23], (STEPS, placed), strides=2) == 47
    assert continued([3, 5, 17, 23], (STEPS, placed)) == 7
    assert continued([0, 2, 6, 12], (STEPS, placed), strides=2) == 20


def test_a_bare_set_of_slots_is_cut_into_lines_every_way_once() -> None:
    slots = list(range(9))
    found = list(cuts(slots, 8, 3))
    assert len(found) == 10080 and len({(frozenset(lines), spare) for lines, spare in found}) == 10080
    assert (((0, 1, 2), (3, 4, 5)), (6, 7)) in found and (((2, 1, 0), (5, 4, 3)), (6, 7)) in found
    assert all(8 not in line and len(line) == 3 for lines, _ in found for line in lines)
    assert all(sorted([*spare, *(slot for line in lines for slot in line)]) == slots[:8] for lines, spare in found)
    assert sorted(cuts(slots[:4], 3, 2)) == sorted((((one, other),), (spare,)) for one, other, spare in permutations(range(3)))


def test_the_word_between_two_names_passes_each_statement_the_way_it_is_met() -> None:
    statements = [("above", "a", "b"), ("beside", "c", "b"), ("above", "c", "d"), ("above", "e", "f")]
    assert between(statements, "a", "d") == (("above", False), ("beside", True), ("above", False))
    assert between(statements, "d", "a") == (("above", True), ("beside", False), ("above", True))
    assert between(statements, "a", "a") == ()
    assert between(statements, "a", "f") is None
    assert between([("far", "a", "c"), *statements, ("near", "a", "d")], "a", "d") == (("near", False),)
