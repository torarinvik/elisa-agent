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


def test_poisson_binomial_matches_enumeration_and_fallback(monkeypatch) -> None:
    import itertools
    import math

    import numpy as np
    import nca.stats as stats

    rng = np.random.default_rng(412)
    cases = [[], [0, 1], [0.0, 1.0], [-1.0, 0.2, 2.0],
             np.array([0.1, 0.2, 0.3], dtype=np.float16),
             np.array([0.1, 0.2, 0.3], dtype=np.float32)]
    cases += [rng.random(n).tolist() for n in range(1, 9)]
    native = stats._NATIVE
    for probabilities in cases:
        clipped = np.clip(probabilities, 0.0, 1.0)
        for observed in range(len(probabilities) + 1):
            outcomes = [(sum(bits), math.prod(p if bit else 1 - p
                         for p, bit in zip(clipped, bits)))
                        for bits in itertools.product((0, 1), repeat=len(clipped))]
            expected = (sum(p for count, p in outcomes if count >= observed),
                        sum(p for count, p in outcomes if count <= observed))
            monkeypatch.setattr(stats, "_NATIVE", None)
            fallback = stats.poisson_binomial_tails(observed, probabilities)
            monkeypatch.setattr(stats, "_NATIVE", native)
            accelerated = stats.poisson_binomial_tails(observed, probabilities)
            tolerance = 5e-4 if clipped.dtype == np.float16 else 1e-7 if clipped.dtype == np.float32 else 2e-15
            assert fallback == pytest.approx(expected, abs=tolerance)
            assert accelerated == pytest.approx(fallback, rel=0, abs=2e-15)


def test_native_poisson_binomial_matches_reference() -> None:
    import numpy as np
    import nca.stats as stats

    if stats._NATIVE is None:
        pytest.skip("Elisa statistics kernel is not built")
    assert stats._NATIVE.poisson_binomial_pmf([0.5], []) == []
    rng = np.random.default_rng(413)
    for n in (0, 1, 2, 31, 256, 1000):
        probabilities = rng.random(n)
        expected = stats._poisson_binomial_pmf_reference(probabilities)
        actual = np.asarray(stats._NATIVE.poisson_binomial_pmf(probabilities, 1 - probabilities))
        np.testing.assert_allclose(actual, expected, rtol=1e-14, atol=1e-300)


def test_poisson_binomial_preserves_input_precision(monkeypatch) -> None:
    import numpy as np
    import nca.stats as stats

    native = stats._NATIVE
    if native is None:
        pytest.skip("Elisa statistics kernel is not built")
    rng = np.random.default_rng(72)
    for dtype in (np.float16, np.float32, np.float64):
        for n in (1, 10, 100):
            probabilities = rng.random(n).astype(dtype)
            monkeypatch.setattr(stats, "_NATIVE", None)
            reference = stats.poisson_binomial_tails(n // 3, probabilities)
            monkeypatch.setattr(stats, "_NATIVE", native)
            assert stats.poisson_binomial_tails(n // 3, probabilities) == reference


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
