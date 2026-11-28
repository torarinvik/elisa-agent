"""Experiments that tell rules apart: narrowing by what tests show and the test that splits best (§65)."""
from itertools import product

from nca.evidence.experiments import fitting, splitting

TESTS = tuple(product((0, 1), repeat=3))
RULES = [{test: test[place] ^ turned for test in TESTS} for place in range(3) for turned in (0, 1)]


def test_narrowing_keeps_the_true_rule_and_one_left_is_it() -> None:
    for truth in RULES:
        shown: dict[tuple[int, ...], int] = {}
        left = list(RULES)
        made = 0
        while len(left) > 1:
            test = splitting(left, [test for test in TESTS if test not in shown])
            assert test is not None
            shown[test] = truth[test]
            left = fitting(RULES, shown)
            assert truth in left
            made += 1
        assert left == [truth]
        assert made <= 3


def test_no_fewer_tests_serve_than_the_rules_allow() -> None:
    most = 0
    for truth in RULES:
        shown: dict[tuple[int, ...], int] = {}
        while len(fitting(RULES, shown)) > 1:
            test = splitting(fitting(RULES, shown), [test for test in TESTS if test not in shown])
            assert test is not None
            shown[test] = truth[test]
        most = max(most, len(shown))
    assert len(RULES) > 2 ** (most - 1)


def test_a_rule_never_met_leaves_none_or_is_not_told() -> None:
    odd = {test: sum(test) % 2 for test in TESTS}
    assert fitting(RULES, odd) == []
    assert splitting(RULES[:1], TESTS) is None
    assert splitting(RULES, []) is None


def test_expected_gain_prices_the_test_once_and_ignores_impossible_observations() -> None:
    from nca.evidence.experiments import expected_test_gain

    prior = (.25, .25, .5)
    outcomes = ((1., 0., 0.), (1., 0., 0.), (0., 1., 0.))
    assert expected_test_gain(prior, outcomes, max, 4, .25) == .75
    assert expected_test_gain(prior, ((1.,),) * 3, max, 4, .25) == -.25
    assert expected_test_gain(prior, outcomes, max, 0, .25) == -.25


def test_expected_gain_rejects_mismatched_observation_spaces() -> None:
    import pytest
    from nca.evidence.experiments import expected_test_gain

    with pytest.raises(ValueError):
        expected_test_gain((.5, .5), ((.5, .5), (1.,)), max, 1, 0.)
