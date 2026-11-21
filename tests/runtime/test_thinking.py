"""Thinking: the output decision, concepts asked in turn, and what they cost (§76)."""
import itertools
import math

import pytest

from nca.abi import Contract, Manifest, Request
from nca.kernel import Kernel
from nca.memory import WorkingMemory
from nca.thinking import Answer, Opinion, Thought, Thresholds, decides, think, through
from nca.workspace import Workspace

COUNT, DOUBLE = "count.hypothetical", "double.hypothetical"

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
