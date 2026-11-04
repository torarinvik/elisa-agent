"""Fresh zero-loss tests shared by acquisition mechanisms (§20.14, §31.9).

The candidate is fixed before this function runs. Sampling must give fresh
IID cases conditional on all earlier observations; reuse inside a subsequent
fit does not make those observations fresh again. No independence among the
candidate's internal components is required.
"""

from __future__ import annotations

from collections.abc import Callable, Sequence
from dataclasses import dataclass
from typing import Generic, TypeVar

T = TypeVar("T")


def validate_batch_limit(limit: int | None) -> None:
    if limit is not None and (type(limit) is not int or limit < 1):
        raise ValueError("certification batch limit must be a positive integer or None")


@dataclass(frozen=True)
class ZeroLossResult(Generic[T]):
    passed: bool | None
    """True on admission, False at disagreement, None on insufficient cases."""
    drawn: int
    retained: tuple[T, ...]


def zero_loss_test(sample: Callable[[int], Sequence[T] | None], agree: Callable[[T], bool], *,
                   cases: int, retain: int = 0,
                   batch_limit: int | None = None) -> ZeroLossResult[T]:
    """Draw in doubling batches, stopping at the first disagreeing batch.

    Retain at most ``retain`` observations for a later fit. ``drawn`` charges
    every returned case, including incomplete or oversized batches. A sampler
    or evaluator may raise; callers needing accounting through exceptions
    must charge their sampling callback before returning the batch.
    An optional positive ``batch_limit`` caps each draw. On rejection this
    wastes at most limit - 1 drawn labels beyond the first failing case, at
    the cost of potentially more sampling calls. Admission still requires
    exactly ``cases`` agreements. The bound assumes exact-size sampler replies.
    """
    if (isinstance(cases, bool) or not isinstance(cases, int) or cases < 1
            or isinstance(retain, bool) or not isinstance(retain, int) or retain < 0):
        raise ValueError("test cases must be positive and retained capacity nonnegative")
    validate_batch_limit(batch_limit)
    tested, batch, drawn = 0, 1, 0
    kept: list[T] = []
    while tested < cases:
        count = min(batch, cases - tested)
        if batch_limit is not None:
            count = min(count, batch_limit)
        held = sample(count)
        if held is not None:
            drawn += len(held)
        if held is None or len(held) != count:
            return ZeroLossResult(None, drawn, tuple(kept))
        kept.extend(held[:max(0, retain - len(kept))])
        if not all(agree(case) for case in held):
            return ZeroLossResult(False, drawn, tuple(kept))
        tested, batch = tested + count, 2 * count
    return ZeroLossResult(True, drawn, tuple(kept))
