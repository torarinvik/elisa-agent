import pytest

from nca.stats import paired_difference, wilson


def test_wilson_contains_estimate_and_shrinks_with_n() -> None:
    low, high = wilson(95, 100)
    assert low < 0.95 < high
    assert high - low > (lambda b: b[1] - b[0])(wilson(950, 1000))
    assert wilson(0, 10)[0] == 0.0 and wilson(10, 10)[1] == pytest.approx(1.0)
    assert wilson(50, 100) == pytest.approx((0.4038, 0.5962), abs=1e-4)


def test_paired_difference() -> None:
    first = [True] * 90 + [False] * 10
    second = [True] * 90 + [True] * 5 + [False] * 5
    mean, low, high = paired_difference(first, second)
    assert mean == pytest.approx(0.05)
    assert 0 < low < mean < high
    assert paired_difference(first, first) == (0.0, 0.0, 0.0)
