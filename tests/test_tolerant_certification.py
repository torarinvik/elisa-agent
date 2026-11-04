"""Fixed-size bounded-error admission, not repeated peeking (§20.22)."""

from fractions import Fraction
from itertools import product
from math import comb
from typing import Any

import pytest

from nca.abi import Contract, Manifest, Message
from nca.planner import Apply, Given
from nca.retention.acquisition import CertifiedAcquirer
from nca.retention.certification import loss_test, validation_plan
from nca.retention.ensembles import EnsembleSearch, VoteCase, VoteFailure
from nca.retention.sampled import decision_level
from nca.stats import family_audit_alpha


def cdf(k: int, n: int, p: Fraction) -> Fraction:
    return sum((comb(n, i) * p**i * (1-p)**(n-i) for i in range(k+1)), Fraction())


def test_cutoffs_match_exact_binomial_tables() -> None:
    for n, tolerance, level in product(range(1, 15), (0.125, 0.25, 0.5, 0.75), (0.015625, 0.125, 0.5)):
        cases, allowed = validation_plan(tolerance, level, n)
        expected = max((k for k in range(n) if cdf(k, n, Fraction(tolerance)) < Fraction(level)), default=-1)
        assert cases == n and allowed == expected


def test_all_small_loss_streams_match_fixed_count_rule_and_stopping_prefix() -> None:
    for n in range(1, 8):
        for bits in product((False, True), repeat=n):
            for allowed, cap in product(range(n), (None, 1, 3)):
                drawn = scored = 0

                def sample(count: int) -> tuple[bool, ...]:
                    nonlocal drawn
                    batch = bits[drawn:drawn+count]
                    drawn += len(batch)
                    return batch

                def agree(bit: bool) -> bool:
                    nonlocal scored
                    scored += 1
                    return bit

                result = loss_test(sample, agree, cases=n, max_errors=allowed, batch_limit=cap, retain=3)
                failures = [i for i, bit in enumerate(bits) if not bit]
                accepted = len(failures) <= allowed
                evaluated = n if accepted else failures[allowed]+1
                assert result.passed == accepted and scored == evaluated
                assert result.errors == (len(failures) if accepted else allowed+1)
                assert result.drawn == drawn <= n
                assert result.retained == bits[:min(3, drawn)]
                if cap is not None:
                    assert drawn < evaluated + cap


def test_exact_false_admission_mass_obeys_shared_stage_request_budget() -> None:
    total = Fraction()
    for index in range(20):
        level = family_audit_alpha(decision_level(0.1, index), 3)
        n, allowed = validation_plan(0.2, level, 64)
        mass = cdf(allowed, n, Fraction(1, 4)) if allowed >= 0 else Fraction()
        assert mass <= Fraction(level)
        total += 3 * mass
    assert total <= Fraction(0.1)


class Constant:
    manifest = Manifest("constant", "1", Contract(("source",), "result"), effects=frozenset())

    def invoke(self, value: int) -> int:
        return 0


@pytest.mark.parametrize("cases", [None, 64])
def test_acquirer_accepts_a_bounded_error_only_in_fixed_size_mode(cases: int | None) -> None:
    cursor = fits = 0

    def sample(contract: Contract, count: int) -> list[tuple[int, int]]:
        nonlocal cursor
        rows = [(i, int(i == 1)) for i in range(cursor, cursor+count)]
        cursor += count
        return rows

    def fit(*args: Any) -> Constant:
        nonlocal fits
        fits += 1
        return Constant()

    acquirer = CertifiedAcquirer(fit, sample, train=1, tolerance=0.2, confidence=0.1,
                                 validation_cases=cases)
    result = acquirer(Constant.manifest.contract)
    assert (result is not None) == (cases is not None)
    assert fits == acquirer.decisions == 1
    assert acquirer.labels == (2 if cases is None else 65)


@pytest.mark.parametrize("reject", [False, True])
def test_ensemble_feedback_closes_test_and_keeps_first_failure_and_success_prefix(reject: bool) -> None:
    cursor = 0
    feedback: list[VoteFailure] = []

    def sample(count: int) -> list[VoteCase]:
        nonlocal cursor
        cases = [((Message("source", i, "input"),), int(i % 2 == 1 if reject else i == 1))
                 for i in range(cursor, cursor+count)]
        cursor += count
        return cases

    search = EnsembleSearch(counts=(1,), tolerance=0.2, confidence=0.1, budget=1,
                            validation_cases=64, retain_controls=64, retain_training=64)
    result = search(Constant.manifest.contract, lambda old: Apply(Constant(), (Given("source"),)),
                    sample, feedback=feedback.append)
    assert (result is None) == reject
    assert search.labels == cursor and search.requests == search.tests == 1
    if reject:
        assert len(feedback) == 1
        failed = feedback[0]
        assert failed.case[0][0].payload == 1
        assert [case[0][0].payload for case in failed.controls] == [0]
        assert failed.drawn == cursor and len(failed.training) == cursor
    else:
        assert feedback == [] and search.labels == search.evaluations == result.cases == 64


def test_insufficient_size_never_fits_proposes_or_samples() -> None:
    def forbidden(*args: Any) -> Any:
        pytest.fail("an uncertifiable fixed size must stop before work")

    acquirer = CertifiedAcquirer(forbidden, forbidden, train=1, tolerance=0.1,
                                 confidence=0.05, validation_cases=1)
    assert acquirer(Constant.manifest.contract) is None and acquirer.labels == 0
    search = EnsembleSearch(counts=(1,), tolerance=0.1, confidence=0.05,
                            budget=1, validation_cases=1)
    assert search(Constant.manifest.contract, forbidden, forbidden) is None
    assert search.requests == search.labels == search.tests == 0


def test_incomplete_draw_after_tolerated_error_is_charged_but_inconclusive() -> None:
    calls = 0

    def sample(count: int) -> tuple[bool, ...]:
        nonlocal calls
        calls += 1
        return (False,)  # Second request needs two; its reply cannot be scored.

    result = loss_test(sample, bool, cases=8, max_errors=1, retain=8)
    assert result.passed is None and result.drawn == 2 and result.errors == 1
    assert result.retained == (False,) and calls == 2


@pytest.mark.parametrize("cases", [0, -1, True, 1.5])
def test_invalid_fixed_sizes_are_refused(cases: Any) -> None:
    with pytest.raises(ValueError, match="validation cases"):
        validation_plan(0.1, 0.05, cases)


@pytest.mark.parametrize("allowed", [-1, 4, True, 1.5])
def test_invalid_error_cutoff_never_samples(allowed: Any) -> None:
    def forbidden(count: int) -> None:
        pytest.fail("invalid error cutoff must not sample")

    with pytest.raises(ValueError, match="error cutoff"):
        loss_test(forbidden, bool, cases=4, max_errors=allowed)


def test_tolerant_stages_reuse_failed_cases_only_for_later_training() -> None:
    class Bad(Constant):
        def invoke(self, value: int) -> int:
            return 1

    fits: list[tuple[int, ...]] = []
    final_draws: list[int] = []
    cursor = 0

    def sample(contract: Contract, count: int) -> list[tuple[int, int]]:
        nonlocal cursor
        indices = list(range(cursor, cursor+count))
        cursor += count
        if len(fits) == 2:
            final_draws.extend(indices)
        return [(i, 0) for i in indices]

    def fit(contract: Contract, keys: Any, labels: Any) -> Constant:
        fits.append(tuple(keys))
        return Bad() if len(fits) == 1 else Constant()

    acquire = CertifiedAcquirer(fit, sample, train=3, stages=(1, 3), tolerance=0.2,
                                confidence=0.1, validation_cases=64)
    assert acquire(Constant.manifest.contract) is not None
    assert fits == [(0,), (0, 1, 2)]
    assert len(final_draws) == 64 and set(final_draws).isdisjoint(fits[-1])
