import pickle
from random import Random

import pytest

from nca.learning.inquiry import Inquiry

Situation = tuple[int, ...]


def read(situation: Situation, probe: int) -> int:
    return situation[probe]


def taught(inquiry: Inquiry, acceptable: object, *, rounds: int, seed: int = 7, width: int = 12) -> int:
    """Teach a choice among six random candidates and return the takeovers."""
    rng, takeovers = Random(seed), 0
    for _ in range(rounds):
        candidates = [tuple(rng.randrange(2) for _ in range(width)) for _ in range(6)]
        good = [candidate for candidate in candidates if acceptable(candidate)]
        chosen = candidates[inquiry.choose([(candidate, "take") for candidate in candidates], rng)]
        if good and not acceptable(chosen):
            takeovers += 1
            inquiry.judge(chosen, "take", False)
            inquiry.judge(good[0], "take", True)
    return takeovers


def test_an_empty_view_grows_to_the_probes_the_target_depends_on() -> None:
    inquiry = Inquiry(range(12), read, largest=2)
    assert inquiry.looking_at == ()
    early = taught(inquiry, lambda seen: seen[2] == 1 and seen[9] == 0, rounds=300)
    late = taught(inquiry, lambda seen: seen[2] == 1 and seen[9] == 0, rounds=300, seed=8)
    assert {2, 9} <= set(inquiry.looking_at) and len(inquiry.view) <= 4
    assert late == 0 and early <= 30
    assert inquiry.looked < 12 * 6 * 600 / 2 and inquiry.studied == 12 * inquiry.judgements


def test_the_price_of_a_class_keeps_probes_from_being_bought_to_split_classes() -> None:
    """Verdicts no probe explains: a free class buys probes for them, a priced one does not."""
    rng = Random(3)
    cases = [(tuple(rng.randrange(4) for _ in range(12)), rng.random() < 0.5) for _ in range(60)]
    free, priced = Inquiry(range(12), read, largest=2, price=0.0), Inquiry(range(12), read, largest=2)
    for situation, good in cases:
        free.judge(situation, "take", good)
        priced.judge(situation, "take", good)
    assert len(free.view) >= 4 and len(priced.view) <= 1


def test_each_action_is_explained_by_its_own_probes_and_a_saved_learner_is_made_again() -> None:
    rng, inquiry = Random(1), Inquiry(range(10), read, largest=1)
    depends = {"a": 3, "b": 7, "c": 1}
    for _ in range(150):
        situation, action = tuple(rng.randrange(3) for _ in range(10)), rng.choice("abc")
        inquiry.judge(situation, action, situation[depends[action]] == 1)
    assert sorted(inquiry.looking_at) == [1, 3, 7]
    restored = pickle.loads(pickle.dumps(inquiry))
    for action, probe in depends.items():
        situation = tuple(1 if index == probe else 0 for index in range(10))
        good, bad = restored.votes(situation, action)
        assert good > bad and restored.votes(situation, action) == inquiry.votes(situation, action)


def test_actions_that_are_one_action_turned_are_joined_and_taught_together() -> None:
    """Action ``i`` of four is good where probe ``i`` is set; a turn moves each probe one place round the four."""
    cycle = tuple((index + 1) % 4 if index < 4 else index for index in range(8))
    twice = tuple(cycle[place] for place in cycle)
    thrice = tuple(cycle[place] for place in twice)
    rng, joined, apart = Random(2), Inquiry(range(8), read, largest=1, turns=(cycle, twice, thrice)), None
    apart = Inquiry(range(8), read, largest=1)
    for _ in range(60):
        situation, action = tuple(rng.randrange(2) for _ in range(8)), rng.randrange(4)
        for inquiry in (joined, apart):
            inquiry.judge(situation, action, situation[action] == 1)
    assert {joined.frame(action)[0] for action in range(4)} == {joined.cases[0][1]}
    assert all(action in joined.looking_for(action) for action in range(4))
    assert len(joined.view) <= 2 and len(apart.view) == 4
    fresh = Inquiry(range(8), read, largest=1, turns=(cycle, twice, thrice))
    for _ in range(12):
        situation = tuple(rng.randrange(2) for _ in range(8))
        for action in (0, 1):
            fresh.judge(situation, action, situation[action] == 1)
    fresh.judge((0, 0, 1, 0, 0, 0, 0, 0), 2, True)
    fresh.judge((0, 0, 0, 0, 0, 0, 0, 0), 2, False)
    fresh.judge((1, 1, 0, 0, 1, 1, 1, 1), 2, False)
    good, bad = fresh.votes((0, 0, 1, 0, 1, 0, 1, 0), 2)
    assert good > bad


def test_actions_with_unlike_targets_stay_apart() -> None:
    cycle = tuple((index + 1) % 4 if index < 4 else index for index in range(8))
    rng, inquiry = Random(3), Inquiry(range(8), read, largest=1, turns=(cycle,))
    for _ in range(80):
        situation, action = tuple(rng.randrange(2) for _ in range(8)), rng.randrange(2)
        inquiry.judge(situation, action, situation[0] == 1 if action == 0 else situation[5] == 0)
    assert inquiry.frame(0)[0] != inquiry.frame(1)[0]
    with pytest.raises(ValueError, match="turn"):
        Inquiry(range(3), read, largest=1, turns=((0, 0, 1),))


def test_a_shortlist_finds_the_same_probes_in_a_large_pool() -> None:
    whole, short = Inquiry(range(12), read, largest=3), Inquiry(range(12), read, largest=3, shortlist=4)
    for inquiry in (whole, short):
        taught(inquiry, lambda seen: seen[2] == 1 and seen[9] == 0, rounds=300)
    assert {2, 9} <= set(short.looking_at) and len(short.view) <= len(whole.view) + 2
    with pytest.raises(ValueError, match="shortlist"):
        Inquiry(range(3), read, largest=2, shortlist=0)


def test_the_view_keeps_within_its_limit_and_malformed_pools_are_refused() -> None:
    inquiry = Inquiry(range(12), read, largest=2, limit=1)
    taught(inquiry, lambda seen: seen[2] == 1 and seen[9] == 0, rounds=100)
    assert len(inquiry.view) == 1
    with pytest.raises(ValueError, match="distinct"):
        Inquiry((0, 0), read, largest=1)
    with pytest.raises(ValueError, match="non-negative"):
        Inquiry((0, 1), read, largest=1, price=-1.0)
