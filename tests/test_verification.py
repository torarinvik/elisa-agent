"""Verified answers (§41)."""

from typing import Any

import pytest

from nca.abi import Contract, Manifest
from nca.planner import Apply, Given
from nca.verification import answer_verified, verified_bound, verifier_rates

TEXT, TOTAL = "text.v1", "total.v1"


class Counter:
    """Counts letters, wrong on texts containing "x", reporting a fixed risk."""

    manifest = Manifest("count", "1", Contract((TEXT,), TOTAL))

    def __init__(self, reported: float) -> None:
        self.reported = reported

    def invoke(self, text: str) -> int:
        return sum(c.isalpha() for c in text) + ("x" in text)

    def risk(self, output: int, *inputs: Any) -> float:
        return self.reported


def test_the_verified_bound() -> None:
    assert verified_bound(0.9, 0.0, 0.5) == 0.0
    assert verified_bound(0.2, 0.01, 0.0) == pytest.approx(0.01 * 0.2 / 0.8)
    assert verified_bound(0.2, 0.01, 0.5) == pytest.approx(0.01 * 0.2 / (0.8 * 0.5))
    assert verified_bound(1.0, 0.01, 0.0) == 1.0


def test_an_exact_verifier_answers_what_the_ledger_alone_cannot() -> None:
    plan = Apply(Counter(0.3), (Given(TEXT),))
    rows = [("ab c",), ("x y",), ("abcd",)]

    def verify(text: str, answer: int) -> bool:
        return answer == sum(c.isalpha() for c in text)

    choices = answer_verified(plan, (TEXT,), rows, 0.05, verify, 0.0, 0.0)
    assert [c.answer for c in choices] == [3, None, 4]
    assert [c.bound for c in choices] == [0.0, 1.0, 0.0]
    # An inexact verifier shrinks the charge of 0.3 to 0.043 here, which
    # passes a target of 0.05 but not one of 0.04.
    loose = answer_verified(plan, (TEXT,), rows, 0.05, verify, 0.1, 0.0)
    assert loose[0].bound == pytest.approx(0.1 * 0.3 / 0.7) and loose[0].answer == 3
    assert answer_verified(plan, (TEXT,), rows, 0.04, verify, 0.1, 0.0)[0].answer is None


def test_rates_are_upper_bounds_on_miss_and_false_rejection() -> None:
    accepted = [True] * 90 + [False] * 10 + [True] * 2 + [False] * 98
    correct = [True] * 100 + [False] * 100
    miss, false_reject = verifier_rates(accepted, correct, 0.05)
    assert 0.02 < miss < 0.1 and 0.1 < false_reject < 0.2
    assert verifier_rates([True], [True], 0.05)[0] == 1.0
