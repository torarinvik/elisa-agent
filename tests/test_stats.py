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


def test_clopper_pearson_upper_matches_closed_form_and_sample_sizes() -> None:
    from nca.stats import binomial_cdf, clopper_pearson_upper

    # With no errors the bound is 1 - alpha^(1/n) (section 17.6).
    for n in (14, 59, 299):
        assert clopper_pearson_upper(0, n, 0.05) == pytest.approx(1 - 0.05 ** (1 / n), abs=1e-6)
    upper = clopper_pearson_upper(3, 100, 0.1)
    assert binomial_cdf(3, 100, upper) == pytest.approx(0.1, abs=1e-6)
    assert clopper_pearson_upper(0, 0, 0.1) == 1.0


def test_certify_stops_at_first_failure() -> None:
    from nca.ladder import certify

    # (answered, wrong), most cautious first; the third fails, so the fourth
    # is never reached even though it would pass.
    assert certify([(100, 0), (150, 1), (200, 30), (300, 0)], 0.05, 0.1) == [0, 1]
    assert certify([(10, 0)], 0.05, 0.1) == []
    assert certify([(10, 0), (300, 0)], 0.05, 0.1, order=[1, 0]) == [1]


def test_certification_order_puts_certifiable_candidates_first() -> None:
    from nca.ladder import certification_order

    assert certification_order([(10, 0), (300, 3), (300, 30)], 0.1) == [1, 2, 0]


def test_finite_audit_family_budget_is_not_overspent() -> None:
    import math
    from nca.stats import family_audit_alpha

    for count in (1, 2, 3, 6, 100):
        level = family_audit_alpha(0.1, count)
        assert 0 < level <= 0.1 / count
        assert math.fsum([level] * count) <= 0.1
    assert family_audit_alpha(0.1, 1) == 0.1
    for total, count in ((0, 2), (1, 2), (float("nan"), 2), (0.1, 0), (0.1, 1.5),
                          (float.fromhex("0x0.0000000000001p-1022"), 2)):
        with pytest.raises(ValueError):
            family_audit_alpha(total, count)
