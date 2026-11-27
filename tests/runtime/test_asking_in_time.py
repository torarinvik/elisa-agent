"""Asking where only the answer given is judged and where an asking takes time (§76.20, §76.21)."""
import random
from collections.abc import Hashable

import pytest

from nca.abi import Request
from nca.asking import OVER, Askings, Learning, Standing, Unsure, Worth
from nca.memory import WorkingMemory
from nca.thinking import Answer, think

SOURCE, READING = "source.hypothetical", "reading.hypothetical"
AGAIN = Request(READING, ((SOURCE, 0),))


class Flattered:
    """Which of two things holds, from a reading right 0.7 of the time and stated so. A second source may be
    asked: it is right 0.55 of the time and what it says is stated at 0.95."""

    def __init__(self, first: int) -> None:
        self.first, self.second = first, None

    def standing(self) -> Standing:
        if self.second is None:
            return Standing((0.7, 0.3) if self.first == 0 else (0.3, 0.7), "first", {"second": AGAIN})
        return Standing((0.95, 0.05) if self.second == 0 else (0.05, 0.95), "second")

    def take(self, asking: Hashable, answer: object) -> None:
        self.second = answer


def flattered(judge: bool, count: int = 1500) -> tuple[float, float]:
    """The share right and the askings an inquiry over the later half of ``count`` inquiries."""
    rng, learning, got = random.Random(2), Learning(Askings(bands=20), 0.0, tries=5, every=5), []
    for _ in range(count):
        truth = rng.randrange(2)
        unsure = Unsure(Flattered(truth if rng.random() < 0.7 else 1 - truth), learning)
        thought = think([unsure], WorkingMemory({}), ask=lambda request, truth=truth: Answer(truth if rng.random() < 0.55 else 1 - truth), rounds=3)
        if judge:
            unsure.judged(float(thought.out == truth))
        got.append((thought.out == truth, thought.asks))
    late = got[count // 2:]
    return sum(right for right, _ in late) / len(late), sum(asks for _, asks in late) / len(late)


def test_an_asking_whose_answers_flatter_is_found_out_by_what_the_answers_given_were_paid() -> None:
    """76.20. With no judgement the record takes the second source at its word and asks it every time, right
    0.55 of the time. Told only whether each answer given was paid, it comes to value answering after that
    asking at what it was paid, stops asking, and is right as often as its first reading."""
    right, asks = flattered(judge=False)
    assert asks > 0.95 and right < 0.6
    right, asks = flattered(judge=True)
    assert asks < 0.05 and right > 0.66

    record = Askings(bands=10)
    for paid in (1.0, 0.0, 0.0, 0.0):
        record.judged("here", 0.93, paid)
    worth = Worth(record, 0.0, pull=4.0)
    assert worth.answer("here", 0.93) == pytest.approx((1.0 + 4.0 * 0.93) / 8.0) == worth.had("here", 0.93)
    assert worth.answer("elsewhere", 0.93) == pytest.approx(0.93) and worth.answer("here", 0.6) == pytest.approx(0.6)
    with pytest.raises(ValueError, match="share"):
        record.judged("here", 0.9, 1.5)
    with pytest.raises(ValueError, match="weight"):
        Worth(record, 0.0, pull=0.0)


class Timed:
    """Which of two things holds, from readings each right 0.75 of the time, in a world of a ``kind`` that may
    end the inquiry while a further reading is taken. It stands at its kind and the readings taken."""

    def __init__(self, kind: str, first: int) -> None:
        self.kind, self.readings, self.gone = kind, [first], False

    def standing(self) -> Standing:
        if self.gone:
            return Standing((0.0,), OVER, hypotheses=(None,))
        odds = 3.0 ** (2 * sum(self.readings) - len(self.readings))
        return Standing((1.0 / (1.0 + odds), odds / (1.0 + odds)), (self.kind, len(self.readings)),
                        {"again": AGAIN} if len(self.readings) < 5 else {})

    def take(self, asking: Hashable, answer: object) -> None:
        self.readings.append(answer)


def test_one_asker_answers_at_once_where_waiting_ends_the_inquiry_and_thinks_on_where_it_does_not() -> None:
    """76.21. Nothing is charged for an asking and nothing differs between the two worlds in what the asker is
    told: in one a further reading ends the inquiry unpaid six times in ten, in the other never. From its own
    record, which holds the inquiries that ended as led to a place where nothing is had, the asker comes to
    answer at once in the first and to ask on in the second, and is paid in each what the better of asking
    never and asking always is paid there, to within three points."""
    rng, learning = random.Random(5), Learning(Askings(bands=20), 0.0, tries=5, every=10)

    def run(kind: str, worth: Learning | Worth, limit: int | None = None) -> tuple[bool, int]:
        truth = rng.randrange(2)
        inquiry = Timed(kind, truth if rng.random() < 0.75 else 1 - truth)
        unsure = Unsure(inquiry, worth)

        def ask(request: Request) -> Answer:
            if kind == "hurried" and rng.random() < 0.6:
                inquiry.gone = True
                unsure.over()
            return Answer(truth if rng.random() < 0.75 else 1 - truth)

        if limit is not None:  # a fixed number of askings, whatever the record says
            for _ in range(limit):
                if not inquiry.gone:
                    answer = ask(AGAIN)
                    inquiry.gone or inquiry.take("again", answer.value)
            standing = inquiry.standing()
            return (not inquiry.gone) and max(range(2), key=lambda k: (standing.chances[k], -k)) == truth, limit
        thought = think([unsure], WorkingMemory({}), ask=ask, rounds=6)
        if thought.out is not None:
            unsure.judged(float(thought.out == truth))
        return thought.out == truth, thought.asks

    late: dict[str, list[tuple[bool, int]]] = {"hurried": [], "unhurried": []}
    for n in range(6000):
        kind = ("hurried", "unhurried")[n % 2]
        got = run(kind, learning)
        if n >= 3000:
            late[kind].append(got)
    paid = {kind: sum(right for right, _ in got) / len(got) for kind, got in late.items()}
    asks = {kind: sum(count for _, count in got) / len(got) for kind, got in late.items()}
    fixed = {(kind, limit): sum(run(kind, learning, limit)[0] for _ in range(3000)) / 3000 for kind in late for limit in (0, 4)}
    assert asks["hurried"] < 0.1 and asks["unhurried"] > 1.5
    assert fixed["hurried", 0] > fixed["hurried", 4] + 0.5 and fixed["unhurried", 4] > fixed["unhurried", 0] + 0.08
    for kind in late:
        assert paid[kind] > max(fixed[kind, 0], fixed[kind, 4]) - 0.03
    assert OVER in learning.askings.answers and repr(OVER) == "OVER"


def test_askings_that_lead_back_are_worth_the_least_that_solves_them() -> None:
    """asking_once_more_has_no_less and back_to_where_it_stood_ties (76.22)."""
    still = Askings(bands=10)
    still.note("here", [0.52] * 6, "wait", "here", [0.52] * 6)  # an asking that shows nothing new
    worth = still.worth(0.0)
    assert worth.of("here", 0.55, "wait") == pytest.approx(0.55) and worth.had("here", 0.55) == pytest.approx(0.55)
    for chance in (0.5, 0.52, 0.55, 0.59):  # it never beats the answer, wherever in the band the chance lies
        assert worth.of("here", chance, "wait") <= worth.answer("here", chance)
    turning = Askings(bands=10)  # one time in four the wait shows the answer; the other three it leads back
    turning.note("here", [0.25] * 8, "wait", "here", [0.25] * 6 + [0.95] * 2)
    for charge in (0.0, 0.1):
        share = 1.0 - charge  # what is had solves h = share (3 h + 0.95) / 4 where that is above answering
        solved = max(0.25, share * 0.95 / (4.0 - 3.0 * share))
        assert turning.worth(charge).had("here", 0.25) == pytest.approx(solved, abs=1e-6)
    for sweeps, most in ((1, 1), (2, 2), (5, 5)):  # so many sweeps are what asking at most so many times has
        had = 0.25
        for _ in range(most):
            had = max(0.25, (3.0 * had + 0.95) / 4.0)
        assert Worth(turning, 0.0, sweeps=sweeps).had("here", 0.25) == pytest.approx(had)
    rising = [Worth(turning, 0.0, sweeps=sweeps).had("here", 0.25) for sweeps in range(1, 30)]
    assert all(later >= earlier for earlier, later in zip(rising, rising[1:], strict=False))
    two = Askings(bands=4)  # two places that lead to each other and nowhere else are worth the better answer
    two.note("one", 0.625, "again", "two", 0.875)
    two.note("two", 0.875, "again", "one", 0.625)
    assert two.worth(0.0).had("one", 0.625) == pytest.approx(0.875) and two.worth(0.0).had("two", 0.875) == pytest.approx(0.875)
    assert two.worth(0.0).of("two", 0.875, "again") == pytest.approx(0.875)  # a tie, which the rule gives to the answer
    assert two.worth(0.1).had("one", 0.625) == pytest.approx(0.9 * 0.875)
    with pytest.raises(ValueError, match="swept"):
        Worth(two, 0.0, sweeps=0)


def counted(seed: int, times: int, dearer: tuple[float, float]) -> Askings:
    """A record of two askings from one standing, where 52 of 80 answers given were paid: the plain one led to
    a best chance of 0.75 or 0.95 as a coin fell, and the dear one to one of ``dearer``."""
    coin, askings = random.Random(seed), Askings(bands=10)
    for given in range(80):
        askings.judged("start", 0.65, float(given < 52))
    for name, shown in (("plain", (0.75, 0.95)), ("dear", dearer)):
        askings.note("start", [0.65] * times, name, "after " + name, [coin.choice(shown) for _ in range(times)])
    return askings


def test_a_dearer_asking_is_taken_only_where_the_record_tells_it_apart() -> None:
    """holding_to_the_plainer_loses_the_gap and tries_to_the_root_are_a_falling_share (76.23)."""
    order, seeds = ("plain", "dear"), range(200)
    alike = [counted(seed, 40, (0.75, 0.95)) for seed in seeds]  # the two askings are worth the same
    larger = [Worth(askings, 0.0).offer("start", 0.65, order) for askings in alike]
    apart = [Worth(askings, 0.0, told=2.0).offer("start", 0.65, order) for askings in alike]
    assert 60 <= sum(offer[1] == "dear" for offer in larger) <= 140  # the larger of two counts is a coin
    assert sum(offer is not None and offer[1] == "dear" for offer in apart) <= 10  # told apart about one time in forty-four
    assert sum(offer is not None and offer[1] == "plain" for offer in apart) >= 180  # and the plain one from answering at 0.65
    for askings, offer in zip(alike, apart, strict=True):
        worth = Worth(askings, 0.0, told=2.0)
        assert worth.had("start", 0.65) == (worth.answer("start", 0.65) if offer is None else pytest.approx(offer[0]))
    for times, least in ((40, 150), (160, 199)):  # worth a tenth more, it is found as the counts grow
        found = [Worth(counted(seed, times, (0.95, 0.95)), 0.0, told=2.0).offer("start", 0.65, order) for seed in seeds]
        assert sum(offer is not None and offer[1] == "dear" for offer in found) >= least
    assert not Worth(Askings(10, alike[0].counts), 0.0, told=2.0).offer("start", 0.65, order)  # no answer judged: nothing told apart
    learning = Learning(counted(0, 5, (0.75, 0.95)), 0.0, tries=3, told=2.0)  # ninety visits: tried to nine
    assert learning.askings.visits("start", 0.65) == 90 and learning.untried("start", 0.65, "dear")
    learning.askings.note("start", [0.65] * 10, "plain", "after plain", [0.95] * 10)  # a hundred: the plain one has its ten
    assert learning.untried("start", 0.65, "dear") and not learning.untried("start", 0.65, "plain")
    assert not Learning(learning.askings, 0.0, tries=3).untried("start", 0.65, "dear")
    assert not Learning(learning.askings, 0.0, tries=0, told=2.0).untried("start", 0.65, "dear")  # an asking tried never stays so
    with pytest.raises(ValueError, match="told apart"):
        Worth(Askings(), 0.0, told=-1.0)
