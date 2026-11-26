"""Asking while unsure: what an asking is worth, a record of one's own askings, and askings at different charges (§76.13 to §76.15)."""
import itertools
import math
import random
from collections.abc import Generator, Hashable

import pytest

from nca.abi import Contract, Manifest, Request
from nca.kernel import Kernel
from nca.memory import WorkingMemory
from nca.thinking import Answer, Askings, Learning, Standing, Thought, Unsure, Worth, think, thinking, through
from nca.workspace import Workspace

SOURCE, READING, VERDICT = "source.hypothetical", "reading.hypothetical", "verdict.hypothetical"
CLOSE = "close-reading.hypothetical"


def memory() -> WorkingMemory:
    return WorkingMemory({"seen": 2})


class Reader:
    """An expert that gives the next of the readings it was made with."""

    manifest = Manifest("example.read", "1", Contract((SOURCE,), READING))

    def __init__(self, readings: list[int]) -> None:
        self.left = iter(readings)

    def invoke(self, source: int) -> int:
        return next(self.left)


class Hidden:
    """An inquiry into which of two things holds, from readings each right with a known chance. It stands at the
    number of readings taken and is as sure as they make it."""

    def __init__(self, first: int, right: float = 0.7, most: int = 5) -> None:
        self.readings, self.right, self.most = [first], right, most

    def standing(self) -> Standing:
        ones = sum(self.readings)
        odds = (self.right / (1.0 - self.right)) ** (2 * ones - len(self.readings))
        again = {"again": Request(READING, ((SOURCE, 0),))} if len(self.readings) < self.most else {}
        return Standing((1.0 / (1.0 + odds), odds / (1.0 + odds)), len(self.readings), again)

    def take(self, asking: Hashable, answer: object) -> None:
        assert asking == "again" and answer in (0, 1)
        self.readings.append(answer)


def trials(count: int, seed: int, right: float = 0.7, most: int = 5) -> list[tuple[int, list[int]]]:
    rng = random.Random(seed)
    return [(truth, [truth if rng.random() < right else 1 - truth for _ in range(most)])
            for truth in (rng.randrange(2) for _ in range(count))]


def recorded(count: int = 4000, seed: int = 0) -> Askings:
    """The askings of trials in which every reading was asked for."""
    askings = Askings(bands=40)
    for _, readings in trials(count, seed):
        inquiry = Hidden(readings[0])
        for reading in readings[1:]:
            before = inquiry.standing()
            inquiry.take("again", reading)
            askings.note(before.place, max(before.chances), "again", inquiry.standing().place, max(inquiry.standing().chances))
    return askings


def test_an_asking_is_worth_what_is_had_after_it_less_the_charge() -> None:
    """§76.13, by hand: two askings from one band, to chances in bands whose middles are 0.95 and 0.75."""
    askings = Askings(bands=10)
    askings.note("start", [0.62, 0.68], "again", "later", [0.93, 0.72])
    for charge in (0.0, 0.1, 1.0):
        worth = askings.worth(charge)
        assert worth.of("start", 0.65, "again") == pytest.approx((1.0 - charge) * 0.85)
        assert worth.had("start", 0.65) == pytest.approx(max(0.65, (1.0 - charge) * 0.85))
        assert worth.of("start", 0.35, "again") is None and worth.of("start", 0.65, "other") is None
        assert worth.of("later", 0.65, "again") is None and worth.had("unseen", 0.4) == 0.4
    further = Askings(bands=10, counts=askings.counts)
    further.note("later", 0.72, "more", "last", 0.99)  # from the less sure of the two a further asking is worth more than answering
    assert further.worth(0.1).of("start", 0.65, "again") == pytest.approx(0.9 * (0.95 + 0.9 * 0.95) / 2)
    assert askings.worth(0.1).of("start", 0.65, "again") == pytest.approx(0.9 * 0.85)


def test_what_cannot_be_a_record_of_askings_is_refused() -> None:
    back = Askings(bands=4)
    back.note("one", 0.6, "again", "two", 0.7)
    back.note("two", 0.7, "again", "one", 0.8)
    with pytest.raises(ValueError, match="lead back"):
        back.worth(0.1)
    for charge in (-0.1, 1.1, math.nan):
        with pytest.raises(ValueError, match="charge"):
            Askings().worth(charge)
    with pytest.raises(ValueError, match="bands"):
        Askings(bands=0)
    with pytest.raises(ValueError, match="between nought and one"):
        Askings().note("one", 1.2, "again", "two", 0.5)
    with pytest.raises(ValueError, match="one chance before and one after"):
        Askings().note("one", [0.2, 0.3], "again", "two", [0.5])
    with pytest.raises(ValueError, match="square table"):
        Askings(bands=4, counts={("one", "again", "two"): [[1.0, 0.0]]})


def test_a_dearer_asking_is_worth_no_more_and_answers_wherever_a_cheaper_one_did() -> None:
    """dearer_worth_no_more and dearer_puts_out (76.13), over every place and band of a record."""
    askings, charges = recorded(), (0.0, 0.01, 0.03, 0.1, 0.3, 1.0)
    worths = [askings.worth(charge) for charge in charges]
    chances = [(band + 0.5) / 40 for band in range(20, 40)]
    for cheaper, dearer in itertools.pairwise(worths):
        for place, chance in itertools.product(range(1, 5), chances):
            low, high = dearer.of(place, chance, "again"), cheaper.of(place, chance, "again")
            assert (low is None) == (high is None)
            if high is not None:
                assert low <= high + 1e-12 and dearer.had(place, chance) <= cheaper.had(place, chance) + 1e-12
                assert chance < high or chance >= low  # answering under the cheaper charge, it answers under the dearer
    assert all(worths[-1].of(place, chance, "again") in (None, 0.0) for place in range(1, 5) for chance in chances)


def asked_while_unsure(worth: Worth | Learning, truth: int, readings: list[int]) -> tuple[bool, int]:
    later = iter(readings[1:])
    thought = think([Unsure(Hidden(readings[0]), worth)], memory(), ask=lambda request: Answer(next(later)), rounds=len(readings))
    assert thought.out in (0, 1)
    return thought.out == truth, thought.asks


def test_asking_while_unsure_is_paid_at_least_as_any_fixed_number_of_askings() -> None:
    """taking_the_larger_is_best (76.13) on fresh trials: charged for each asking, asking by worth is paid no
    less than always taking a fixed number of readings; and a dearer charge asks less, as 76.11 has it."""
    askings, fresh = recorded(), trials(3000, seed=1)
    asked_before = math.inf
    for charge in (0.0, 0.02, 0.1, 0.4):
        got = [asked_while_unsure(askings.worth(charge), truth, readings) for truth, readings in fresh]
        paid = sum((1.0 - charge) ** asks for right, asks in got if right) / len(fresh)
        for count in (1, 3, 5):  # the majority of an odd number of readings
            fixed = sum(2 * sum(readings[:count]) > count if truth else 2 * sum(readings[:count]) < count for truth, readings in fresh)
            assert paid >= (1.0 - charge) ** (count - 1) * fixed / len(fresh) - 0.02
        asked = sum(asks for _, asks in got) / len(fresh)
        assert asked <= asked_before
        asked_before = asked
    assert asked_before == 0.0


def test_an_asking_never_recorded_is_not_made_and_an_asking_unserved_is_taken_as_nothing() -> None:
    assert asked_while_unsure(Askings().worth(0.0), 1, [1, 0, 0, 0, 0]) == (True, 0)

    class Deaf(Hidden):
        def take(self, asking: Hashable, answer: object) -> None:
            assert answer is None
            self.most = len(self.readings)  # nothing more is to be had

    thought = think([Unsure(Deaf(1), recorded(400).worth(0.0))], memory(), ask=through(Kernel([]), Workspace(), budget=4))
    assert (thought.out, thought.asks) == (1, 1)


def test_a_record_of_ones_own_askings_comes_to_pay_what_the_full_record_pays() -> None:
    """76.14: begun empty and kept only by the askings made from it, with each asking tried a stated number of
    times where it stands, the record comes to pay on fresh trials what the record of every asking pays; the
    tries are at most as many as the cells allow, and each gave up at most the charge."""
    charge, tries = 0.02, 12
    learning = Learning(Askings(bands=40), charge, tries, every=25)
    stream, fresh = trials(3000, seed=3), trials(3000, seed=1)
    got = [asked_while_unsure(learning, truth, readings) for truth, readings in stream]
    cells = {(place, band) for (place, _, _), table in learning.askings.counts.items() for band in table.sum(1).nonzero()[0]}
    assert learning.askings.noted == sum(asks for _, asks in got) and len(cells) <= 12

    def paid(worth: Worth) -> float:
        return sum((1.0 - charge) ** asks for right, asks in (asked_while_unsure(worth, *trial) for trial in fresh) if right) / len(fresh)

    full, own = paid(recorded().worth(charge)), paid(learning.askings.worth(charge))
    assert own >= full - 0.01
    late = sum((1.0 - charge) ** asks for right, asks in got[1000:] if right) / 2000  # learning still, yet paid alike
    assert late >= full - 0.02
    first = asked_while_unsure(Learning(Askings(bands=40), charge, tries=1), 1, [1, 1, 1, 1, 1])
    assert first == (True, 4)  # every asking untried is made, however sure the answer


def test_a_record_is_not_kept_of_what_was_not_served_and_malformed_learning_is_refused() -> None:
    class Deaf(Hidden):
        def take(self, asking: Hashable, answer: object) -> None:
            assert answer is None
            self.most = len(self.readings)

    learning = Learning(Askings(bands=40), 0.02, tries=3)
    thought = think([Unsure(Deaf(1), learning)], memory(), ask=through(Kernel([]), Workspace(), budget=4))
    assert (thought.out, thought.asks, learning.askings.noted) == (1, 1, 0)
    assert Learning(Askings(), 0.02, tries=0).untried("anywhere", 0.6, "again") is False
    for tries, every in ((-1, 1), (1.5, 1), (2, 0)):
        with pytest.raises(ValueError, match="number of askings"):
            Learning(Askings(), 0.02, tries, every)


class Second:
    """A dearer expert whose readings are right more often."""

    manifest = Manifest("example.read-closely", "1", Contract((SOURCE,), CLOSE))

    def __init__(self, readings: list[int]) -> None:
        self.left = iter(readings)

    def invoke(self, source: int) -> int:
        return next(self.left)


class Both:
    """An inquiry into which of two things holds, held outside any expert, with two askings: a further reading
    right with one known chance, and a close reading, to be had once, right with a greater one."""

    def __init__(self, first: int, right: float = 0.7, close: float = 0.95, most: int = 4) -> None:
        self.readings, self.closely, self.right, self.close, self.most = [first], [], right, close, most

    def standing(self) -> Standing:
        odds = (self.right / (1.0 - self.right)) ** (2 * sum(self.readings) - len(self.readings))
        odds *= (self.close / (1.0 - self.close)) ** (2 * sum(self.closely) - len(self.closely))
        asking = {"again": Request(READING, ((SOURCE, 0),))} if len(self.readings) < self.most else {}
        asking |= {} if self.closely else {"closely": Request(CLOSE, ((SOURCE, 0),))}
        return Standing((1.0 / (1.0 + odds), odds / (1.0 + odds)), (len(self.readings), len(self.closely)), asking)

    def take(self, asking: Hashable, answer: object) -> None:
        (self.readings if asking == "again" else self.closely).append(answer)


def both(count: int, seed: int) -> list[tuple[int, list[int], list[int]]]:
    rng = random.Random(seed)
    return [(truth, [truth if rng.random() < 0.7 else 1 - truth for _ in range(4)], [truth if rng.random() < 0.95 else 1 - truth])
            for truth in (rng.randrange(2) for _ in range(count))]


def asked_of_both(worth: Worth | Learning, trial: tuple[int, list[int], list[int]], open_to: tuple[str, ...] = ("again", "closely")) -> tuple[bool, dict[str, int]]:
    """One trial through a kernel in which one expert serves the further readings and another the close one."""
    truth, readings, closely = trial
    made = {"again": 0, "closely": 0}

    class Part(Both):
        def standing(self) -> Standing:
            whole = super().standing()
            return Standing(whole.chances, whole.place, {name: request for name, request in whole.open.items() if name in open_to})

        def take(self, asking: Hashable, answer: object) -> None:
            made[asking] += 1
            super().take(asking, answer)

    ask = through(Kernel([Reader(readings[1:]), Second(closely)]), Workspace(), budget=8)
    thought = think([Unsure(Part(readings[0]), worth)], memory(), ask=ask, rounds=8)
    return thought.out == truth, made


def test_askings_served_by_different_experts_at_different_charges_are_weighed_in_one_rule() -> None:
    """§76.15. The record is learned from the rule's own askings; then one asker over both askings is paid no
    less than an asker over either alone, and the close reading made dearer is asked for less often and the
    further reading no less often, with nothing changed but the charge stated."""
    def paid(charge: dict[str, float], got: list[tuple[bool, dict[str, int]]]) -> float:
        return sum((1.0 - charge["again"]) ** made["again"] * (1.0 - charge["closely"]) ** made["closely"]
                   for right, made in got if right) / len(got)

    fresh, before = both(1200, seed=5), None
    for dear in (0.03, 0.08, 0.2):
        charge = {"again": 0.02, "closely": dear}
        learning = Learning(Askings(bands=20), charge, tries=10, every=25)
        for trial in both(1000, seed=4):
            asked_of_both(learning, trial)
        worth = learning.askings.worth(charge)
        got = [asked_of_both(worth, trial) for trial in fresh]
        for alone in ("again", "closely"):
            assert paid(charge, got) >= paid(charge, [asked_of_both(worth, trial, (alone,)) for trial in fresh]) - 0.01
        made = {name: sum(asked[name] for _, asked in got) for name in ("again", "closely")}
        if before is not None:
            assert made["closely"] <= before["closely"] and made["again"] >= before["again"]
        before = made
    assert before["closely"] < 0.5 * len(fresh) < before["again"]  # at a fifth of the prize the close reading is seldom worth it


def test_each_asking_is_worth_what_follows_less_its_own_charge_and_needs_one() -> None:
    askings = Askings(bands=10)
    askings.note("start", [0.62, 0.68], "again", "later", [0.93, 0.72])
    askings.note("start", [0.62, 0.68], "closely", "sure", [0.97, 0.91])
    worth = askings.worth({"again": 0.1, "closely": 0.3})
    assert worth.of("start", 0.65, "again") == pytest.approx(0.9 * 0.85) and worth.charged("closely") == 0.3
    assert worth.of("start", 0.65, "closely") == pytest.approx(0.7 * 0.95) and worth.had("start", 0.65) == pytest.approx(0.9 * 0.85)
    assert askings.worth({"again": 0.1, "closely": 0.1}).had("start", 0.65) == pytest.approx(0.9 * 0.95)
    one = Askings(bands=10)
    one.note("start", [0.62, 0.68], "again", "later", [0.93, 0.72])
    assert one.worth(0.1).had("start", 0.65) <= askings.worth({"again": 0.1, "closely": 0.3}).had("start", 0.65)  # more askings, no less
    with pytest.raises(ValueError, match="needs its charge"):
        askings.worth({"again": 0.1})
    with pytest.raises(ValueError, match="between nought and one"):
        askings.worth({"again": 0.1, "closely": 1.3})


class Decides:
    """An expert that finds out which of two things holds, asking whoever runs it for further readings."""

    manifest = Manifest("example.decide", "1", Contract((READING,), VERDICT))

    def __init__(self, worth: Worth) -> None:
        self.worth = worth
        self.thought: Thought | None = None

    def invoke(self, first: int) -> Generator[Request, object, int]:
        self.thought = yield from thinking([Unsure(Hidden(first), self.worth)], memory(), rounds=8)
        return self.thought.out


def test_thinking_hands_an_asking_to_whoever_runs_the_expert() -> None:
    """An expert the kernel runs decides as ``think`` with the kernel in hand decides (76.6)."""
    worth = recorded().worth(0.02)
    for truth, readings in trials(40, seed=2):
        direct = asked_while_unsure(worth, truth, readings)
        expert = Decides(worth)
        ask = through(Kernel([Reader(readings[1:]), expert]), Workspace(), budget=16)
        verdict = ask(Request(VERDICT, ((READING, readings[0]),), required=frozenset({0}))).value
        assert (verdict == truth, expert.thought.asks) == direct
    held = memory()
    stepped = thinking([Unsure(Hidden(1), recorded(400).worth(0.0))], held, rounds=1)
    asking = next(stepped)
    assert isinstance(asking, Request) and asking.type_id == READING
    with pytest.raises(StopIteration) as done:
        stepped.send(0)
    assert done.value.value.out is None and done.value.value.asks == 1  # a second asking is not yielded
    with pytest.raises(ValueError, match="rounds"):
        next(thinking([], held, rounds=-1))
