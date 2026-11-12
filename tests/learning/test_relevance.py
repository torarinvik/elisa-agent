from itertools import product
from math import comb
from random import Random

import pytest

from nca.learning.relevance import Relevance


def test_a_judgement_carries_to_observations_agreeing_on_what_matters() -> None:
    relevance = Relevance(3, largest=1)
    relevance.judge((1, 0, 0), "take", True)
    relevance.judge((0, 0, 0), "take", False)
    relevance.judge((1, 1, 1), "take", True)
    good, bad = relevance.votes((1, 1, 0), "take")
    assert good > bad and relevance.votes((0, 1, 1), "take") == (0, 1)


def test_a_correct_teacher_is_bounded_by_the_set_that_matters() -> None:
    """A choice among candidates whose acceptability reads components 2 and 5 of eight (THEORY 53.4)."""
    rng, relevance, takeovers = Random(7), Relevance(8, largest=2), 0

    def acceptable(observation: tuple[int, ...]) -> bool:
        return observation[2] == 1 and observation[5] == 0

    for _ in range(400):
        candidates = [tuple(rng.randrange(2) for _ in range(8)) for _ in range(6)]
        good = [candidate for candidate in candidates if acceptable(candidate)]
        chosen = candidates[relevance.choose([(candidate, "take") for candidate in candidates], rng)]
        if good and not acceptable(chosen):
            takeovers += 1
            relevance.judge(chosen, "take", False)
            relevance.judge(good[0], "take", True)
    assert takeovers <= 1 * 2**2 + sum(comb(8, size) for size in range(3))
    for observation in product(range(2), repeat=8):
        good, bad = relevance.votes(observation, "take")
        assert (good > bad) == acceptable(observation) or good == bad == 0


def test_a_teacher_who_contradicts_themselves_is_outweighed_not_obeyed() -> None:
    """One judgement in ten is reversed: refuting sets loses every one, weighing them keeps the right one ahead."""
    rng = Random(3)
    judgements = [(observation, (observation[1] == 1) != (rng.random() < 0.1))
                  for observation in (tuple(rng.randrange(2) for _ in range(6)) for _ in range(300))]
    strict, weighed = Relevance(6, largest=2), Relevance(6, largest=2, keep=0.5)
    for observation, good in judgements:
        strict.judge(observation, "take", good)
        weighed.judge(observation, "take", good)
    assert strict.surviving((0,) * 6) == 0 and weighed.judgements == 300
    for observation in product(range(2), repeat=6):
        good, bad = weighed.votes(observation, "take")
        assert (good > bad) == (observation[1] == 1)


def test_the_direction_of_an_ordered_component_is_learned_from_the_teachers_choices() -> None:
    """Acceptability reads component 0; among acceptable candidates the teacher takes the largest component 1."""

    def takeovers(relevance: Relevance) -> int:
        rng, count = Random(5), 0
        for _ in range(300):
            candidates = [(rng.randrange(2), rng.randrange(10)) for _ in range(6)]
            acceptable = [candidate for candidate in candidates if candidate[0] == 1]
            if not acceptable:
                continue
            best = max(acceptable, key=lambda candidate: candidate[1])
            chosen = candidates[relevance.choose([(candidate, "take") for candidate in candidates], rng)]
            if chosen[0] != 1 or chosen[1] != best[1]:
                count += 1
                relevance.judge(chosen, "take", False)
                relevance.judge(best, "take", True)
                relevance.prefer(best, [candidate for candidate in candidates if candidate != best], "take")
        return count

    ordered, symbols = Relevance(2, largest=1, keep=0.3, ordered=(1,)), Relevance(2, largest=1, keep=0.3)
    assert 4 * takeovers(ordered) < takeovers(symbols)
    assert ordered.direction(1) > 0 and symbols.judgements > ordered.judgements


def test_each_context_finds_its_own_components() -> None:
    relevance = Relevance(3, largest=1, always=(0,))
    for context, matters in (("a", 1), ("b", 2)):
        for values in product(range(2), repeat=2):
            observation = (context, *values)
            relevance.judge(observation, "take", observation[matters] == 1)
    assert relevance.votes(("a", 1, 0), "take")[0] > 0 and relevance.votes(("b", 1, 0), "take")[1] > 0
    assert relevance.surviving(("a", 0, 0)) == relevance.surviving(("b", 0, 0)) == 1


def test_actions_kept_apart_find_their_own_components() -> None:
    """Action ``a`` is good where component 0 is set and ``b`` where component 1 is: no one component serves both."""
    together, apart = Relevance(2, largest=1, keep=0.3), Relevance(2, largest=1, keep=0.3, apart=True)
    for observation in product(range(2), repeat=2):
        for relevance in (together, apart):
            relevance.judge(observation, "a", observation[0] == 1)
            relevance.judge(observation, "b", observation[1] == 1)
    assert apart.surviving((0, 0), "a") == apart.surviving((0, 0), "b") == 3
    for observation in product(range(2), repeat=2):
        good, bad = apart.votes(observation, "a")
        assert (good > bad) == (observation[0] == 1)
        good, bad = apart.votes(observation, "b")
        assert (good > bad) == (observation[1] == 1)
    weights = [together.votes((1, 0), "a"), apart.votes((1, 0), "a")]
    assert weights[1][0] - weights[1][1] > weights[0][0] - weights[0][1]


def test_a_guess_avoids_pairs_judged_bad() -> None:
    relevance = Relevance(2, largest=1)
    relevance.judge((0, 0), "take", False)
    relevance.judge((1, 0), "take", True)
    assert relevance.surviving((0, 0)) == 1
    pairs = [((0, 1), "take"), ((2, 1), "take")]
    assert all(relevance.choose(pairs, Random(seed)) == 1 for seed in range(20))
    assert relevance.choose([((0, 1), "take"), ((1, 1), "take")], Random(0)) == 1


def test_malformed_observations_and_sets_are_refused() -> None:
    with pytest.raises(ValueError, match="distinct"):
        Relevance(2, largest=1, always=(0, 0))
    with pytest.raises(ValueError, match="components"):
        Relevance(2, largest=1).votes((0,), "take")
    with pytest.raises(ValueError, match="ordered"):
        Relevance(1, largest=1, ordered=(1,))
    with pytest.raises(ValueError, match="share"):
        Relevance(1, largest=1, keep=1.0)
    with pytest.raises(ValueError, match="nothing"):
        Relevance(1, largest=1).choose([], Random(0))
