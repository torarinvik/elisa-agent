"""Fresh fixed-count loss tests shared by acquisition mechanisms (§20.22).

The candidate is fixed before this function runs. Sampling must give fresh
IID cases conditional on all earlier observations; reuse inside a subsequent
fit does not make those observations fresh again. No independence among the
candidate's internal components is required.
"""

from __future__ import annotations

from collections.abc import Callable, Sequence
from dataclasses import dataclass
from typing import Generic, TypeVar

from nca.retention.sampled import required_cases
from nca.stats import clopper_pearson_within

T = TypeVar("T")


def validate_batch_limit(limit: int | None) -> None:
    if limit is not None and (type(limit) is not int or limit < 1):
        raise ValueError("certification batch limit must be a positive integer or None")


@dataclass(frozen=True)
class LossTestResult(Generic[T]):
    passed: bool | None
    """True on admission, False beyond the error cutoff, None on insufficient cases."""
    drawn: int
    retained: tuple[T, ...]
    errors: int = 0


ZeroLossResult = LossTestResult  # Preserve the original zero-error API name.


def validate_validation_cases(cases: int | None) -> None:
    if cases is not None and (type(cases) is not int or cases < 1):
        raise ValueError("validation cases must be a positive integer or None")


def validation_plan(tolerance: float, level: float, cases: int | None) -> tuple[int, int]:
    """Fix sample size and a conservatively certified error cutoff before draws.

    A negative cutoff means even a zero-error result cannot certify. Bisection
    returns a verified cutoff; numerical uncertainty may make it conservative.
    None preserves the original zero-error exponential sample-size rule.
    """
    validate_validation_cases(cases)
    if cases is None:
        return required_cases(tolerance, level), 0
    if not 0 < tolerance < 1 or not 0 < level < 1:
        raise ValueError("tolerance and level must lie in (0, 1)")
    if not clopper_pearson_within(0, cases, level, tolerance):
        return cases, -1
    low, high = 0, cases
    while low + 1 < high:
        middle = (low + high) // 2
        if clopper_pearson_within(middle, cases, level, tolerance):
            low = middle
        else:
            high = middle
    return cases, low


def loss_test(sample: Callable[[int], Sequence[T] | None], agree: Callable[[T], bool], *,
                   cases: int, retain: int = 0,
                   batch_limit: int | None = None, max_errors: int = 0) -> LossTestResult[T]:
    """Draw in doubling batches, rejecting as soon as errors exceed the cutoff.

    Retain at most ``retain`` observations for a later fit. ``drawn`` charges
    every returned case, including incomplete or oversized batches. A sampler
    or evaluator may raise; callers needing accounting through exceptions
    must charge their sampling callback before returning the batch.
    An optional positive ``batch_limit`` caps each draw. On rejection this
    wastes at most limit - 1 drawn labels beyond the decisive failing case, at
    the cost of potentially more sampling calls. Admission still requires
    exactly ``cases`` evaluations. The bound assumes exact-size sampler replies.
    The caller fixes cases and max_errors before observing this fresh stream.
    This evaluates a count rule; ``validation_plan`` supplies its statistical
    cutoff when certification, rather than raw counting, is required.
    """
    if (isinstance(cases, bool) or not isinstance(cases, int) or cases < 1
            or isinstance(retain, bool) or not isinstance(retain, int) or retain < 0):
        raise ValueError("test cases must be positive and retained capacity nonnegative")
    validate_batch_limit(batch_limit)
    if type(max_errors) is not int or not 0 <= max_errors < cases:
        raise ValueError("error cutoff must be an integer from zero through cases minus one")
    tested, batch, drawn, errors = 0, 1, 0, 0
    kept: list[T] = []
    while tested < cases:
        count = min(batch, cases - tested)
        if batch_limit is not None:
            count = min(count, batch_limit)
        held = sample(count)
        if held is not None:
            drawn += len(held)
        if held is None or len(held) != count:
            return LossTestResult(None, drawn, tuple(kept), errors)
        kept.extend(held[:max(0, retain - len(kept))])
        for case in held:
            errors += int(not agree(case))
            if errors > max_errors:
                return LossTestResult(False, drawn, tuple(kept), errors)
        tested, batch = tested + count, 2 * count
    return LossTestResult(True, drawn, tuple(kept), errors)


def zero_loss_test(sample: Callable[[int], Sequence[T] | None], agree: Callable[[T], bool], *,
                   cases: int, retain: int = 0,
                   batch_limit: int | None = None) -> LossTestResult[T]:
    """Compatibility entry point for the shared test with a zero-error cutoff."""
    return loss_test(sample, agree, cases=cases, retain=retain, batch_limit=batch_limit)
