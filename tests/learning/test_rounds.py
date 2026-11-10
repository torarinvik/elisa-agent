import pytest

from nca.learning.rounds import Attempt, doubling_rounds


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
