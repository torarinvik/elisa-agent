"""Asking while unsure: what an asking is worth, a record of one's own askings, askings at different charges, how
sure to be, whom to trust, an asking made only so often and what an inquiry is promised (§76.13 to §76.19)."""
import itertools
import math
import random
from collections.abc import Generator, Hashable

import pytest

from nca.abi import Contract, Manifest, Request
from nca.kernel import Kernel
from nca.memory import WorkingMemory
from nca.asking import Askings, Learning, Promise, Standing, Sureness, Trust, Unsure, Worth
from nca.thinking import Answer, Thought, think, thinking, through
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


def test_ones_own_askings_say_how_sure_to_be_with_no_word_on_what_was_right() -> None:
    """§76.16. An inquiry that takes its readings to be right 0.8 of the time when they are right 0.7 of the
    time states odds to the power log 4 / log (7/3) of the true ones. From the askings made for its own ends
    a power is found that lies between one and that power and near it, and read through it the chances stated
    for the final answers are less than half as far from the share right; an inquiry whose chances are right
    is left as it is."""
    for stated, power in ((0.8, math.log(4.0) / math.log(7.0 / 3.0)), (0.7, 1.0), (0.62, math.log(0.62 / 0.38) / math.log(7.0 / 3.0))):
        sure = Sureness()
        learning = Learning(Askings(bands=20), 0.02, tries=10, every=25, sure=sure)
        gaps = {}
        for name, worth in (("as stated", Learning(Askings(bands=20), 0.02, tries=10, every=25)), ("read", learning)):
            got = []
            for truth, readings in trials(1800, seed=6):
                later = iter(readings[1:])
                thought = think([Unsure(Hidden(readings[0], right=stated), worth)], memory(), ask=lambda request, later=later: Answer(next(later)), rounds=5)
                got.append((thought.out == truth, thought.chance))
            late = got[800:]
            gaps[name] = sum(chance for _, chance in late) / len(late) - sum(right for right, _ in late) / len(late)
        found = sure.power()
        assert min(1.0, power) - 0.02 <= found <= max(1.0, power) + 0.02 and abs(math.log(found / power)) <= 0.2
        assert abs(gaps["read"]) <= max(0.01, 0.5 * abs(gaps["as stated"])) and (stated == 0.7 or abs(gaps["as stated"]) >= 0.04)
    few = Sureness()
    for before, after in ((0.6, 0.9), (0.7, 0.95), (0.6, 0.4)):  # three askings contradict nothing
        few.note(before, after)
    assert few.power() == 1.0 and Sureness().power() == 1.0
    bare = Sureness(errors=0.0)  # held against no error at all, the power is the root itself
    for before, after in ((0.665, 0.863), (0.665, 0.863), (0.665, 0.404)) * 2:  # a true 0.75 that becomes 0.95 or 0.35, odds to the power 0.625
        bare.note(before, after)
    assert bare.power() == pytest.approx(0.625, abs=0.02)
    with pytest.raises(ValueError, match="shrink"):
        Sureness(shrink=1.5)
    with pytest.raises(ValueError, match="standard errors"):
        Sureness(errors=-1.0)
    with pytest.raises(ValueError, match="between nought and one"):
        Sureness().note(0.4, 1.2)


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
        got = [asked_of_both(learning.askings.worth(charge), trial) for trial in fresh]
        for alone in ("again", "closely"):  # an asker over one asking knows the record of that asking only
            part = Askings(20, {key: table for key, table in learning.askings.counts.items() if key[1] == alone}).worth(charge)
            assert paid(charge, got) >= paid(charge, [asked_of_both(part, trial, (alone,)) for trial in fresh]) - 0.01
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


class Told(Both):
    """The same inquiry saying what each source said in place of the chances that follow from it."""

    def standing(self) -> Standing:
        whole = super().standing()
        lean = (2 * sum(self.readings) - len(self.readings)) / 2.0
        said = {"again": (-lean, lean)} | ({"closely": (1.0 - self.closely[0], float(self.closely[0]))} if self.closely else {})
        return Standing((), whole.place, whole.open, None, said)


def told(worth: Worth | Learning, trial: tuple[int, list[int], list[int]], trust: Trust) -> tuple[bool, dict[str, int]]:
    """One trial of an asker that makes its chances from what the sources said, by the trust it holds."""
    truth, readings, closely = trial
    inquiry = Told(readings[0])
    ask = through(Kernel([Reader(readings[1:]), Second(closely)]), Workspace(), budget=8)
    thought = think([Unsure(inquiry, worth, trust=trust)], memory(), ask=ask, rounds=8)
    return thought.out == truth, {"again": len(inquiry.readings) - 1, "closely": len(inquiry.closely)}


def test_trust_begun_at_nothing_is_learned_from_the_dear_answers_the_rule_itself_asks_for() -> None:
    """§76.17. With no trial named beforehand, the weight of the further readings begins at nought and the only
    word on what was right is the close reading on the trials where the rule or a try asked for it. The asker
    comes to believe a reading about as far as its true odds say and is paid on fresh trials what an asker told
    the true chances is paid, for names on a part of the trials only."""
    charge = {"again": 0.02, "closely": 0.3}

    def paid(got: list[tuple[bool, dict[str, int]]]) -> float:
        return sum((1.0 - charge["again"]) ** made["again"] * (1.0 - charge["closely"]) ** made["closely"]
                   for right, made in got if right) / len(got)

    stream, fresh = both(1500, seed=4), both(1500, seed=5)
    trust, learning = Trust("closely", 0.95), Learning(Askings(bands=20), charge, tries=10, every=25)
    assert trust.chances({"again": (-1.5, 1.5)}) == [0.5, 0.5]  # nobody is trusted yet
    made = [told(learning, trial, trust)[1] for trial in stream]
    assert len(trust.named) == sum(asked["closely"] for asked in made) < len(stream) / 2
    assert abs(trust.weights["again"] - math.log(0.7 / 0.3)) < 0.25
    known = Learning(Askings(bands=20), charge, tries=10, every=25)
    for trial in stream:
        asked_of_both(known, trial)
    own = paid([told(learning.askings.worth(charge), trial, trust.fixed()) for trial in fresh])
    assert own >= paid([asked_of_both(known.askings.worth(charge), trial) for trial in fresh]) - 0.015


def test_a_coin_names_an_inquiry_at_every_standing_it_passed_and_a_fixed_trust_keeps_nothing() -> None:
    """§76.17 (iii). An inquiry the coin chose is not answered before the namer has been asked, and every
    standing it passed is kept with the name; without the coin and with nothing recorded, nothing is asked and
    nothing kept; a trust taken as fixed keeps no names and tosses no coin."""
    trials, nothing = both(40, seed=6), Askings(bands=20).worth({"again": 0.02, "closely": 0.12})
    always = Trust("closely", 0.95, coin=1.0)
    got = [told(nothing, trial, always) for trial in trials]
    assert all(made == {"again": 0, "closely": 1} for _, made in got) and len(always.named) == len(trials)
    assert [right for right, _ in got] == [trial[2][0] == trial[0] for trial in trials]  # the namer's word is taken
    learning = Learning(Askings(bands=20), {"again": 0.02, "closely": 0.12}, tries=1)
    passed = Trust("closely", 0.95, coin=1.0)
    _, made = told(learning, trials[0], passed)
    assert made["closely"] == 1 and len(passed.named) == made["again"] + 1  # each standing before the name
    never = Trust("closely", 0.95)
    assert all(made == {"again": 0, "closely": 0} for _, made in (told(nothing, trial, never) for trial in trials)) and not never.named
    kept = always.fixed()
    assert not kept.tossed() and kept.weights == always.weights
    kept.note({"again": (0.5, -0.5)}, 0)
    assert not kept.named


def test_what_cannot_be_a_trust_or_a_word_is_refused() -> None:
    assert Trust("namer", 0.9).chances({"namer": (0.0, 1.0)}) == pytest.approx([0.1, 0.9])
    assert Trust("namer", 0.9, start=1.0).chances({"one": (0.0, math.log(3.0))}) == pytest.approx([0.25, 0.75])
    for bad in ({"believed": 1.0}, {"believed": 0.9, "pull": 0.0}, {"believed": 0.9, "coin": 1.5}, {"believed": 0.9, "every": 0}):
        with pytest.raises(ValueError):
            Trust("namer", **bad)
    with pytest.raises(ValueError, match="one number for each of the same answers"):
        Trust("namer", 0.9).chances({"one": (0.1, 0.2), "other": (0.1, 0.2, 0.3)})


def test_an_asking_kept_to_a_limit_is_weighed_at_its_price_and_promised_at_its_charge() -> None:
    """76.18. By hand: an asking that leads from a chance of 0.6 to one of 0.875 is weighed at charge and price
    and promised at the charge alone, and is not made where the price takes it under the answer. Then, learned:
    a close reading asked for in every inquiry is, given a limit of one inquiry in five, asked for in about
    that share, by a price that rose from nought; each asking's own number of tries leaves the one unnamed
    untried."""
    led = Askings(bands=4)
    led.note("first", 0.6, "dear", "last", 0.9)
    priced = Worth(led, {"dear": 0.1}, price={"dear": 0.1})
    assert priced.of("first", 0.6, "dear") == pytest.approx(0.8 * 0.875)
    assert priced.had("first", 0.6) == pytest.approx(0.9 * 0.875) == Worth(led, {"dear": 0.1}).had("first", 0.6)
    assert Worth(led, {"dear": 0.1}, price={"dear": 0.3}).had("first", 0.6) == 0.6
    halved = Worth(Askings(bands=4), 0.1, read=lambda chance: 0.5 * chance)  # a reading goes with the worth it valued
    assert halved.had("nowhere", 0.8) == pytest.approx(0.4)
    assert think([Unsure(Hidden(1, most=1), halved)], memory()).chance == pytest.approx(0.35)

    charge, late = {"again": 0.02, "closely": 0.03}, {}
    for limit in (None, {"closely": 0.2}):
        learning = Learning(Askings(bands=20), charge, tries=10, every=25, limit=limit)
        got = [asked_of_both(learning, trial) for trial in both(2400, seed=4)][1200:]
        late[limit is None] = sum(made["closely"] for _, made in got) / len(got)
    assert late[True] > 0.9 and 0.15 <= late[False] <= 0.25 and learning.price["closely"] > 0.1
    own = Learning(Askings(bands=20), charge, tries={"again": 3})
    assert own.untried("anywhere", 0.6, "again") and not own.untried("anywhere", 0.6, "closely")

    for bad in ({"limit": {"closely": -0.1}}, {"limit": {"elsewhere": 0.1}}, {"step": 0.0}, {"tries": {"again": -1}}):
        with pytest.raises(ValueError, match="limit|step|number of askings"):
            Learning(Askings(), charge, **({"tries": 1} | bad))
    with pytest.raises(ValueError, match="limit"):
        Learning(Askings(), 0.02, tries=1, limit={"closely": 0.1})
    with pytest.raises(ValueError, match="price"):
        Worth(led, {"dear": 0.1}, price={"dear": -0.1})


def test_a_promise_given_less_its_own_drift_is_what_the_inquiries_come_to_hold() -> None:
    """76.19. Records counted from thirty and from sixty trials promise, at the first place, a point and more
    above and below what fresh inquiries are paid. The promise less what the last place then held, kept with no
    word on what was right, is that miss: given less its mean, the promise is within a fifth of a point of what
    is paid, the inquiry's chances being right. An inquiry in which an asking was tried is left out."""
    fresh, charge = trials(3000, seed=1), 0.02
    for count in (30, 60):
        worth, promise, promised, paid = recorded(count, seed=7).worth(charge), Promise(), 0.0, 0.0
        for truth, readings in fresh:
            later, inquiry = iter(readings[1:]), Hidden(readings[0])
            promised += worth.had(1, max(inquiry.standing().chances)) / len(fresh)
            thought = think([Unsure(inquiry, worth, promise=promise)], memory(), ask=lambda request: Answer(next(later)), rounds=5)
            paid += (thought.out == truth) * (1.0 - charge) ** thought.asks / len(fresh)
        assert promise.inquiries == len(fresh) - 1  # the last is counted when another begins
        assert abs(promised - paid) > 0.01 and abs(promise.of(promised) - paid) < 0.002

    kept = Promise()
    kept.begun(0.9)
    kept.holds(0.8)
    kept.begun(0.7)
    kept.void()
    kept.holds(0.1)
    kept.begun(0.6)
    assert (kept.inquiries, kept.over) == (1, pytest.approx(0.1)) and kept.of(0.9) == pytest.approx(0.8)
    learning, tried = Learning(Askings(bands=40), charge, tries=2), Promise()
    for _, readings in fresh[:40]:
        later = iter(readings[1:])
        think([Unsure(Hidden(readings[0]), learning, promise=tried)], memory(), ask=lambda request: Answer(next(later)), rounds=5)
    assert 0 < tried.inquiries < 39


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
