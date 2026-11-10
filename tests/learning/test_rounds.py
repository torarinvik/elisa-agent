import pytest

from nca.learning.rounds import Attempt, doubling_rounds, first_of


def costing(cost: int | None, dies_at: int | None = None) -> Attempt[str]:
    """An attempt that succeeds once allowed ``cost``, or stops for good at ``dies_at``."""
    def attempt(limit: int) -> tuple[str | None, int]:
        if dies_at is not None and limit > dies_at:
            return None, dies_at
        if cost is not None and limit >= cost:
            return "done", cost
        return None, limit
    return attempt


def test_cheap_attempts_finish_first_and_spending_is_capped_work() -> None:
    """``NCA.capped_work_monotone``: at a completed round, spending is the sum of costs capped at it."""
    results, spent = doubling_rounds([costing(3), costing(40), costing(None)], budget=3 + 8 + 8)
    assert results == ["done", None, None] and spent == 19
    results, spent = doubling_rounds([costing(3), costing(40), costing(None)], budget=3 + 40 + 64)
    assert results == ["done", "done", None] and spent == 107


def test_an_attempt_that_stops_below_its_limit_is_dropped() -> None:
    results, spent = doubling_rounds([costing(None, dies_at=5), costing(20)], budget=1000)
    assert results == [None, "done"] and spent == 25


def test_budget_is_never_exceeded_and_invalid_reports_are_refused() -> None:
    assert doubling_rounds([costing(None), costing(None)], budget=7)[1] == 7
    assert doubling_rounds([], budget=7) == ([], 0)
    with pytest.raises(ValueError, match="spending"):
        doubling_rounds([lambda limit: (None, limit + 1)], budget=4)
    with pytest.raises(ValueError, match="budget"):
        doubling_rounds([costing(1)], budget=-1)


def test_first_of_passes_an_unused_share_to_the_attempt_still_running() -> None:
    joined = first_of([costing(None, dies_at=3), costing(30)])
    assert joined(8) == (None, 8)
    assert joined(64) == ("done", 33)
    both = first_of([costing(None), costing(None)])
    assert both(9) == (None, 9) and both(20) == (None, 20)
    assert first_of([costing(None, dies_at=2), costing(None, dies_at=1)])(50) == (None, 3)


def test_first_of_inside_rounds_keeps_the_budget() -> None:
    results, spent = doubling_rounds([first_of([costing(None, dies_at=3), costing(30)]), costing(None)], budget=200)
    assert results[0] == "done" and results[1] is None and spent == 200
