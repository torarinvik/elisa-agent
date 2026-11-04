"""Exact dependence and numerical checks for majority risk (§31.8)."""

from fractions import Fraction
from itertools import combinations, product
from math import prod

import pytest

from nca.evidence.redundancy import dependent_vote_risk, threshold, vote_risk


def test_bound_covers_arbitrary_two_atom_joint_distributions() -> None:
    """Enumerate dependent joint failure laws, including common-mode errors,
    exclusive failures and negative correlation. Marginals are exact dyadics."""
    for k in range(1, 6):
        for a, b, weight in product(range(1 << k), range(1 << k), (1, 2, 3)):
            q = Fraction(weight, 4)
            risks = [float(q * ((a >> i) & 1) + (1 - q) * ((b >> i) & 1))
                     for i in range(k)]
            failure = q * (a.bit_count() >= threshold(k)) + (1 - q) * (
                b.bit_count() >= threshold(k))
            assert failure <= Fraction(dependent_vote_risk(risks))


def test_omitting_largest_risks_matches_all_subset_bounds() -> None:
    for values in product((0.0, 0.25, 0.5, 0.75, 1.0), repeat=4):
        risks = list(map(Fraction, values))
        t = threshold(len(risks))
        bounds = [Fraction(1)]
        for r in range(t):
            for omit in combinations(range(len(risks)), r):
                bounds.append(sum((p for i, p in enumerate(risks) if i not in omit),
                                  Fraction(0)) / (t - r))
        expected = min(bounds)
        actual = dependent_vote_risk(values)
        assert Fraction(actual) >= expected
        assert actual == float(expected)  # These denominators are powers of two.
    assert dependent_vote_risk([0.9, 0.01, 0.01]) == pytest.approx(0.02)


def test_independent_bound_is_rounded_up_from_exact_products() -> None:
    for values in product((0.01, 0.1, 0.3), repeat=5):
        t = threshold(len(values))
        exact = min(Fraction(1), sum((prod(Fraction(values[i]) for i in subset)
                                     for subset in combinations(range(len(values)), t)), Fraction(0)))
        assert Fraction(vote_risk(values)) >= exact


@pytest.mark.parametrize("bad", [-0.1, 1.1, float("nan"), float("inf")])
def test_invalid_marginals_are_refused(bad: float) -> None:
    for bound in (vote_risk, dependent_vote_risk):
        with pytest.raises(ValueError, match="risks"):
            bound([0.1, bad])


def test_common_mode_failures_do_not_gain_an_independence_guarantee() -> None:
    assert vote_risk([0.1] * 7) < 0.1
    assert dependent_vote_risk([0.1] * 7) >= 0.1
    assert dependent_vote_risk([]) == 1.0
    assert dependent_vote_risk([0.0] * 4) == 0.0


def test_underflow_does_not_turn_positive_risk_into_zero() -> None:
    tiny = float.fromhex("0x0.0000000000001p-1022")
    exact = 35 * Fraction(tiny) ** 4
    assert exact > 0
    assert Fraction(vote_risk([tiny] * 7)) >= exact
