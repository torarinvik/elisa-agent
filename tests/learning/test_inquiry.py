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
