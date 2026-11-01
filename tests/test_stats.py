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
        clipped = np.clip(probabilities, 0.0, 1.0).astype(np.float64)
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
            assert fallback == pytest.approx(expected, rel=0, abs=2e-15)
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


def test_poisson_binomial_promotes_reduced_precision_probabilities(monkeypatch) -> None:
    import numpy as np
    import nca.stats as stats

    native = stats._NATIVE
    for dtype in (np.float16, np.float32):
        probabilities = np.full(1000, 0.1, dtype=dtype)
        promoted = probabilities.astype(np.float64)
        for implementation in (None, native):
            monkeypatch.setattr(stats, "_NATIVE", implementation)
            upper, lower = stats.poisson_binomial_tails(0, probabilities)
            assert upper == 1.0
            assert lower == pytest.approx((1.0 - promoted[0]) ** len(promoted), rel=1e-12)
            assert stats.poisson_binomial_tails(100, probabilities) == \
                stats.poisson_binomial_tails(100, promoted)
        assert stats.poisson_binomial_tails(len(probabilities), probabilities)[1] == 1.0


def test_poisson_binomial_nan_propagates_at_support_edges() -> None:
    import math
    from nca.stats import poisson_binomial_tails

    for observed in (0, 1):
        assert all(math.isnan(p) for p in poisson_binomial_tails(observed, [float("nan")]))


def test_poisson_binomial_upper_bound_against_exact_fractions(monkeypatch) -> None:
    import math
    from fractions import Fraction

    import numpy as np
    import nca.stats as stats

    rng = np.random.default_rng(894)
    cases = [[], [0.0, 1.0], [1e-200, 1e-200], [0.1, 0.3, 0.7]]
    cases += [np.array([0.1, 0.3, 0.7], dtype=dtype)
              for dtype in (np.float16, np.float32, np.longdouble)]
    cases += [rng.random(int(rng.integers(1, 9))).tolist() for _ in range(100)]
    native = stats._NATIVE
    for probabilities in cases:
        pmf = [Fraction(1)]
        for value in probabilities:
            p = Fraction(*value.as_integer_ratio())
            old = pmf
            pmf = [Fraction(0)] * (len(old) + 1)
            for i, mass in enumerate(old):
                pmf[i] += (1 - p) * mass
                pmf[i + 1] += p * mass
        for observed in range(len(probabilities) + 1):
            exact = sum(pmf[observed:])
            answers = []
            for implementation in (None, native):
                monkeypatch.setattr(stats, "_NATIVE", implementation)
                bound = stats.poisson_binomial_upper_bound(observed, probabilities)
                assert Fraction.from_float(bound) >= exact
                assert bound <= 1.0
                answers.append(bound)
            assert answers[0] == answers[1]
    assert stats.poisson_binomial_upper_bound(2, [1e-200, 1e-200]) > 0.0
    assert math.isnan(stats.poisson_binomial_upper_bound(0, [float("nan")]))
    assert stats.poisson_binomial_upper_bound(-1, []) == 1.0
    assert stats.poisson_binomial_upper_bound(1, []) == 0.0
    for implementation in (None, native):
        monkeypatch.setattr(stats, "_NATIVE", implementation)
        with np.errstate(under="raise"):
            assert stats.poisson_binomial_upper_bound(1, [1.0]) == 1.0
            assert stats.poisson_binomial_upper_bound(2, [1e-200, 1e-200]) > 0.0


def test_format_upper_bound_never_rounds_down() -> None:
    import math
    import random
    from decimal import Decimal, Inexact, localcontext
    from nca.stats import format_upper_bound

    rng = random.Random(3519)
    values = [0.0, 1.0, 0.515417709566158, 1e-5, math.ulp(0.0)]
    values += [rng.random() * 10 ** rng.randrange(-300, 1) for _ in range(100)]
    for digits in (1, 3, 8):
        for value in values:
            assert Decimal(format_upper_bound(value, digits)) >= Decimal.from_float(value)
    assert format_upper_bound(0.515417709566158) == "0.516"
    assert format_upper_bound(math.nan) == "nan"
    with localcontext() as context:
        context.traps[Inexact] = True
        assert format_upper_bound(0.515417709566158) == "0.516"
    with pytest.raises(ValueError, match="digits"):
        format_upper_bound(0.5, 0)


def test_native_poisson_binomial_handles_sparse_and_nonfinite_inputs() -> None:
    import numpy as np
    import nca.stats as stats

    if stats._NATIVE is None:
        pytest.skip("Elisa statistics kernel is not built")
    rng = np.random.default_rng(19)
    for n in (0, 1, 10, 100):
        for _ in range(30):
            probabilities = rng.choice([0.0, 0.0, 0.0, 0.1, 0.5, 1.0, float("nan")], n)
            expected = stats._poisson_binomial_pmf_reference(probabilities)
            actual = stats._NATIVE.poisson_binomial_pmf(probabilities, 1 - probabilities)
            np.testing.assert_array_equal(actual, expected)


def test_native_poisson_binomial_certain_events_shift_distribution() -> None:
    import numpy as np
    import nca.stats as stats

    if stats._NATIVE is None:
        pytest.skip("Elisa statistics kernel is not built")
    for probabilities in ([1.0] * 100, [0.0, 1.0, 0.1, 1.0, 0.2, 0.0],
                          [1.0, 1e-320, 0.5, 1.0], [1.0, float("nan"), 0.0, 1.0]):
        values = np.asarray(probabilities)
        expected = stats._poisson_binomial_pmf_reference(values)
        actual = stats._NATIVE.poisson_binomial_pmf(values, 1 - values)
        np.testing.assert_array_equal(actual, expected)


def test_clopper_pearson_upper_matches_closed_form_and_sample_sizes() -> None:
    from nca.stats import binomial_cdf, clopper_pearson_upper

    # With no errors the bound is 1 - alpha^(1/n) (section 17.6).
    for n in (14, 59, 299):
        assert clopper_pearson_upper(0, n, 0.05) == pytest.approx(1 - 0.05 ** (1 / n), abs=1e-6)
    upper = clopper_pearson_upper(3, 100, 0.1)
    assert binomial_cdf(3, 100, upper) == pytest.approx(0.1, abs=1e-6)
    assert clopper_pearson_upper(0, 0, 0.1) == 1.0


def test_binomial_cdf_outside_count_support() -> None:
    from nca.stats import binomial_cdf

    for n in (0, 1, 10):
        for rate in (0.0, 0.25, 1.0):
            assert binomial_cdf(-1, n, rate) == 0.0
            assert binomial_cdf(n, n, rate) == 1.0
            assert binomial_cdf(n + 10, n, rate) == 1.0
    with pytest.raises(ValueError, match="trial count"):
        binomial_cdf(0, -1, 0.5)


def test_poisson_binomial_tails_outside_count_support() -> None:
    from nca.stats import poisson_binomial_tails

    for probabilities in ([], [0.1, 0.2, 0.3]):
        assert poisson_binomial_tails(-1, probabilities) == (1.0, 0.0)
        assert poisson_binomial_tails(-10, probabilities) == (1.0, 0.0)
        assert poisson_binomial_tails(len(probabilities) + 1, probabilities) == (0.0, 1.0)


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
