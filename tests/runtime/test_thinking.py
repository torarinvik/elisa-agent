"""Thinking: the output decision, concepts asked in turn, and what they cost (§76)."""
import itertools
import math
import random
from collections.abc import Generator, Hashable

import pytest

from nca.abi import Contract, Manifest, Request
from nca.kernel import Kernel
from nca.memory import WorkingMemory
from nca.thinking import (Answer, Askings, Learning, Opinion, Standing, Thought, Thresholds, Unsure, Worth, decides, think,
                          thinking, through)
from nca.workspace import Workspace

COUNT, DOUBLE = "count.hypothetical", "double.hypothetical"
SOURCE, READING, VERDICT = "source.hypothetical", "reading.hypothetical", "verdict.hypothetical"

GRID = [0.0, 0.1, 0.25, 0.5, 0.75, 0.9, 1.0]


class Fixed:
    """A concept that gives one opinion, counts how often it is asked and notes that it was."""

    def __init__(self, opinion: Opinion, cost: float = 1.0, name: str = "fixed") -> None:
        self.opinion, self.cost, self.name, self.asked = opinion, cost, name, 0

    def think(self, memory: WorkingMemory) -> Opinion:
        self.asked += 1
        memory.scratch.note(self.name, self.asked, life=1)
        return self.opinion


def memory() -> WorkingMemory:
    return WorkingMemory({"seen": 2})


def test_the_rule_takes_the_smaller_risk() -> None:
    """rule_risks_least and least_risk_le (76.1), over a grid of risks and of chances of putting out."""
    for act, wait in itertools.product(GRID, GRID):
        taken = act if decides(1.0 - act, wait, act, Thresholds()) else wait
        assert taken == min(act, wait)
        for out in GRID:
            assert min(act, wait) <= out * act + (1 - out) * wait + 1e-12


def test_one_number_says_where_the_risk_lies() -> None:
    """share_le_iff (76.1): the share of the risk in putting out now decides as the quotient does."""
    for act, wait, ratio in itertools.product(GRID, GRID, [0.5, 1.0, 2.0]):
        thought = Thought(None, 0, 1.0 - act, wait, act, 1, 1.0)
        if act + wait > 0 and abs(ratio * act - wait) > 1e-9:
            assert (thought.tilt <= 1 / (1 + ratio)) == decides(1.0, wait, act, Thresholds(ratio=ratio))
    assert Thought(None, 0, 1.0, 0.0, 0.0, 1, 1.0).tilt == 0.5
    assert Thought(None, 0, 0.0, 0.0, 1.0, 1, 1.0).tilt == 1.0 and Thought(None, 0, 1.0, 1.0, 0.0, 1, 1.0).tilt == 0.0


def test_misread_risks_cost_at_most_twice_what_they_are_off() -> None:
    """read_risks_cost_little (76.2), over a grid of true risks and of misreadings within a bound."""
    for act, wait, off in itertools.product(GRID, GRID, [0.0, 0.05, 0.2]):
        for a, w in itertools.product([-off, 0.0, off], repeat=2):
            read_act, read_wait = min(1.0, max(0.0, act + a)), min(1.0, max(0.0, wait + w))
            taken = act if decides(1.0 - read_act, read_wait, read_act, Thresholds()) else wait
            assert taken <= min(act, wait) + 2 * off + 1e-12


def test_a_threshold_below_one_costs_at_most_what_it_lacks_of_one() -> None:
    """threshold_costs_little (76.2)."""
    for act, wait, ratio in itertools.product(GRID, GRID, [0.25, 0.5, 1.0]):
        taken = act if decides(1.0 - act, wait, act, Thresholds(ratio=ratio)) else wait
        assert taken <= min(act, wait) + (1 - ratio) * act + 1e-12


def test_the_best_hypothesis_is_put_out_where_going_on_is_the_greater_risk() -> None:
    thought = think([Fixed(Opinion(chances=[0.2, 0.7, 0.1], wait=0.5))], memory())
    assert thought == Thought(1, 1, 0.7, 0.5, pytest.approx(0.3), 1, 1.0)
    assert thought.ratio == pytest.approx(0.5 / 0.3)
    waited = think([Fixed(Opinion(chances=[0.2, 0.7, 0.1], wait=0.1))], memory())
    assert waited.out is None and waited.best == 1 and waited.ratio < 1


def test_a_likely_hypothesis_below_the_threshold_of_chance_is_not_put_out() -> None:
    concept = Fixed(Opinion(chances=[0.6, 0.4], wait=1.0))
    assert think([concept], memory(), Thresholds(prob=0.5)).out == 0
    assert think([concept], memory(), Thresholds(prob=0.7)).out is None


def test_no_later_concept_is_asked_once_a_hypothesis_is_put_out() -> None:
    """A sure cheap concept spares the dear one (76.5)."""
    cheap, dear = Fixed(Opinion(chances=[0.9, 0.1], wait=0.5), cost=1.0), Fixed(Opinion(chances=[0.1, 0.9]), cost=10.0)
    thought = think([cheap, dear], memory())
    assert (thought.out, thought.asked, thought.cost, dear.asked) == (0, 1, 1.0, 0)


def test_a_later_concept_refines_what_the_earlier_ones_said() -> None:
    risks, chances = Fixed(Opinion(wait=0.6), cost=1.0, name="risks"), Fixed(Opinion(chances=[0.3, 0.5]), cost=4.0, name="chances")
    held = memory()
    thought = think([risks, chances], held)
    assert (thought.out, thought.chance, thought.wait, thought.asked, thought.cost) == (1, 0.5, 0.6, 2, 5.0)
    assert held.scratch.read("risks") == 1 and held.scratch.read("chances") == 1
    unsure, sure = Fixed(Opinion(chances=[0.5, 0.4], wait=0.2)), Fixed(Opinion(chances=[0.05, 0.95]))
    refined = think([unsure, sure], memory())
    assert (refined.out, refined.asked) == (1, 2)


def test_a_risk_of_putting_out_now_that_a_concept_reads_is_used_in_place_of_the_chance() -> None:
    assert think([Fixed(Opinion(chances=[0.9], wait=0.3, act=0.6))], memory()).out is None
    assert think([Fixed(Opinion(chances=[0.5], wait=0.3, act=0.2))], memory()).out == 0


def test_thinking_stops_within_the_budget_and_where_a_concept_settles_the_step() -> None:
    first, second, third = (Fixed(Opinion(wait=0.0), cost=2.0) for _ in range(3))
    thought = think([first, second, third], memory(), budget=5.0)
    assert (thought.out, thought.asked, thought.cost, third.asked) == (None, 2, 4.0, 0)
    settled, never = Fixed(Opinion(wait=0.0, settled=True)), Fixed(Opinion(chances=[1.0], wait=1.0))
    assert think([settled, never], memory()).out is None and never.asked == 0


def test_thresholds_may_turn_on_how_the_step_stands() -> None:
    concept = Fixed(Opinion(chances=[0.6, 0.4], wait=0.9))
    seen: list[Thought] = []

    def careful(so_far: Thought) -> Thresholds:
        seen.append(so_far)
        return Thresholds(prob=0.5 if so_far.wait > 0.5 else 0.99)

    assert think([concept], memory(), careful).out == 0
    assert seen == [Thought(None, 0, 0.6, 0.9, pytest.approx(0.4), 1, 1.0)]


def test_asking_in_turn_costs_no_more_than_asking_all() -> None:
    """cost_le_all (76.5): over every prefix at which thinking may stop."""
    costs = [1.0, 3.0, 9.0]
    for stop in range(len(costs)):
        concepts = [Fixed(Opinion(chances=[1.0] if at == stop else None, wait=1.0 if at == stop else None), cost)
                    for at, cost in enumerate(costs)]
        thought = think(concepts, memory())
        assert thought.cost == sum(costs[:stop + 1]) <= sum(costs)


def test_what_is_out_of_range_is_refused() -> None:
    with pytest.raises(ValueError):
        think([Fixed(Opinion(chances=[1.5]))], memory())
    with pytest.raises(ValueError):
        think([Fixed(Opinion(chances=[]))], memory())
    with pytest.raises(ValueError):
        think([Fixed(Opinion(wait=-0.1))], memory())
    with pytest.raises(ValueError):
        think([Fixed(Opinion(), cost=-1.0)], memory())
    assert math.isinf(Thought(0, 0, 1.0, 0.5, 0.0, 1, 1.0).ratio)


class Doubler:
    """An expert that doubles a count, at a declared cost."""

    manifest = Manifest("example.double", "1", Contract((COUNT,), DOUBLE), cost=3.0)

    def invoke(self, count: int) -> int:
        return 2 * count


class Asks:
    """A concept that asks the kernel for the double of a count and puts out what it was given."""

    cost = 1.0

    def __init__(self, always: bool = False) -> None:
        self.always = always

    def think(self, memory: WorkingMemory) -> Opinion:
        if DOUBLE in memory.scratch and not self.always:
            return Opinion(chances=[1.0], hypotheses=[("answer", memory.scratch.read(DOUBLE))], wait=1.0)
        return Opinion(chances=[0.9, 0.1], hypotheses=[Request(DOUBLE, {COUNT: 21}), "guess"], wait=1.0)


def test_a_hypothesis_is_whatever_could_be_done_and_is_put_out_as_it_is() -> None:
    thought = think([Fixed(Opinion(chances=[0.2, 0.8], hypotheses=["left", ("press", 3)], wait=1.0))], memory())
    assert thought.out == ("press", 3) and thought.best == 1
    with pytest.raises(ValueError):
        think([Fixed(Opinion(chances=[0.2, 0.8], hypotheses=["only"]))], memory())


def test_an_asking_of_the_kernel_is_served_within_the_step_and_thought_goes_on_with_its_answer() -> None:
    held, workspace = memory(), Workspace()
    thought = think([Asks()], held, ask=through(Kernel([Doubler()]), workspace, budget=4))
    assert thought.out == ("answer", 42) and (thought.asks, thought.asked, thought.cost) == (1, 2, 5.0)
    assert held.scratch.read(DOUBLE) == 42
    held.advance()
    assert DOUBLE not in held.scratch


def test_an_asking_the_kernel_cannot_serve_gives_no_value_and_askings_are_bounded() -> None:
    held = memory()
    thought = think([Asks()], held, ask=through(Kernel([]), Workspace(), budget=4))
    assert thought.out == ("answer", None) and thought.asks == 1
    served: list[Request] = []

    def ask(request: Request) -> Answer:
        served.append(request)
        return Answer(len(served), 2.0)

    endless = think([Asks(always=True)], memory(), ask=ask, rounds=3)
    assert endless.out is None and (endless.asks, len(served), endless.asked, endless.cost) == (3, 3, 4, 10.0)
    refused = think([Asks()], memory(), ask=through(Kernel([Doubler()]), Workspace(), budget=4, cost_budget=1.0))
    assert refused.out == ("answer", None)


def test_without_a_way_to_ask_an_asking_is_put_out_like_any_hypothesis() -> None:
    thought = think([Asks()], memory())
    assert thought.out == Request(DOUBLE, {COUNT: 21}) and thought.asks == 0


def test_kernel_checks_both_remaining_thinking_cost_and_per_request_limit() -> None:
    for budget, request_limit, expected, cost in (
        (2., None, ("answer", None), 2.), (5., None, ("answer", 42), 5.),
        (5., 1., ("answer", None), 2.), (4., None, None, 4.),
    ):
        workspace = Workspace()
        ask = through(Kernel([Doubler()]), workspace, budget=4, cost_budget=request_limit)
        result = think([Asks()], memory(), budget=budget, ask=ask)
        assert (result.out, result.cost) == (expected, cost)
        assert workspace.spent == (3. if cost >= 4 else 0.)
    workspace = Workspace()
    repeat = think([Asks(always=True)], memory(), budget=6., rounds=10,
                   ask=through(Kernel([Doubler()]), workspace, budget=4))
    assert repeat.cost == 6. and workspace.spent == 3.


def test_malformed_thinking_limits_and_charges_are_rejected_before_publication() -> None:
    for rounds in (-1, 1.5):
        with pytest.raises(ValueError, match="rounds"):
            think([], memory(), rounds=rounds)
    with pytest.raises(ValueError, match="budget"):
        think([], memory(), budget=math.nan)
    for charge in (-1., math.nan, math.inf):
        held = memory()
        with pytest.raises(ValueError, match="request cost"):
            think([Asks()], held, ask=lambda _: Answer(42, charge))
        assert DOUBLE not in held.scratch


def test_partial_kernel_route_is_charged_even_when_the_result_is_refused() -> None:
    class First(Doubler):
        manifest = Manifest("example.first", "1", Contract((COUNT,), "example.intermediate"), cost=2.)

    class Last(Doubler):
        manifest = Manifest("example.last", "1", Contract(("example.intermediate",), DOUBLE), cost=4.)

    workspace, held = Workspace(), memory()
    result = think([Asks()], held, budget=5., ask=through(Kernel([First(), Last()]), workspace, budget=4))
    assert (result.out, result.cost, workspace.spent) == (("answer", None), 4., 2.)
    assert held.scratch.read(DOUBLE) is None


def test_every_reported_chance_is_validated_before_selection() -> None:
    for invalid in (math.nan, math.inf, -0.01, 1.01):
        for chances in ((invalid, .8), (.8, invalid)):
            with pytest.raises(ValueError, match="chance"):
                think([Fixed(Opinion(chances=chances))], memory())
    with pytest.raises(ValueError, match="corresponding chances"):
        think([Fixed(Opinion(hypotheses=("candidate",)))], memory())
    assert think([Fixed(Opinion(chances=(.7, .7)))], memory()).out == 0


def test_confidence_and_both_directions_of_the_displayed_risk_ratio() -> None:
    lower = Thresholds(prob=.55, ratio=1.)
    upper = Thresholds(prob=.55, ratio=1., ratio_bound="maximum")
    for chance, wait, act in ((.68, .85, .15), (.56, .25, .75), (.91, .8, .2), (.4, .25, .75),
                              (.7, .25, .25), (1., .8, 0.), (1., 0., 0.)):
        for bounds in (lower, upper):
            t = think([Fixed(Opinion(chances=(chance,), wait=wait, act=act))], memory(), bounds)
            meets = t.ratio >= bounds.ratio if bounds == lower else t.ratio <= bounds.ratio
            assert (t.out is not None) == (chance >= bounds.prob and meets)
    for prob in (-.1, 1.1, math.nan):
        with pytest.raises(ValueError, match="confidence"):
            Thresholds(prob=prob)
    for ratio in (-1., math.inf, math.nan):
        with pytest.raises(ValueError, match="ratio"):
            Thresholds(ratio=ratio)


def test_direct_decision_rejects_invalid_evidence() -> None:
    with pytest.raises(ValueError, match="chance"):
        decides(math.nan, .2, .8, Thresholds())
    with pytest.raises(ValueError, match="risk"):
        decides(.7, -1., .3, Thresholds())


def test_additional_pass_refines_a_carried_hypothesis_on_the_same_input() -> None:
    class Reconsider:
        cost = 1.0

        def think(self, memory: WorkingMemory) -> Opinion:
            if "visited" in memory.scratch:
                return Opinion(wait=.8)
            memory.scratch.note("visited", True, life=1)
            return Opinion(chances=[.7], hypotheses=["candidate"], wait=.1)

    concept = Reconsider()
    assert think([concept], memory()).out is None
    decision = think([concept], memory(), passes=10)
    assert (decision.out, decision.asked, decision.cost) == ("candidate", 2, 2.)
    limited = think([concept], memory(), passes=10, budget=1.)
    assert (limited.out, limited.asked, limited.wait) == (None, 1, .1)


def test_refinement_stops_at_settlement_or_the_pass_limit_even_for_free_concepts() -> None:
    for settled, visits in ((True, 1), (False, 4)):
        concept = Fixed(Opinion(chances=[.5], wait=0., settled=settled), cost=0.)
        decision = think([concept], memory(), passes=4)
        assert decision.out is None and decision.asked == concept.asked == visits
    assert think([], memory(), passes=10**9).asked == 0
    for invalid in (0, -1, True, 1.5):
        with pytest.raises(ValueError, match="passes"):
            think([], memory(), passes=invalid)


def test_an_answer_restarts_the_opinion_and_shares_the_remaining_refinements() -> None:
    class Gather:
        cost = 1.

        def think(self, memory: WorkingMemory) -> Opinion:
            if DOUBLE in memory.scratch:
                return Opinion(wait=1.)
            if "visited" in memory.scratch:
                return Opinion(chances=[1.], hypotheses=[Request(DOUBLE, {COUNT: 21})])
            memory.scratch.note("visited", True, life=1)
            return Opinion(chances=[.1], wait=0.)

    held = memory()
    decision = think([Gather()], held, ask=lambda request: Answer(42, 2.), passes=2)
    assert held.scratch.read(DOUBLE) == 42
    assert decision == Thought(None, None, 0., 1., 1., 3, 5., 1)


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
