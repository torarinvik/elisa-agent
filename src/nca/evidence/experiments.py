"""Experiments that tell rules apart (THEORY §65).

A rule gives each test an outcome. ``fitting`` keeps, of the rules that could hold, those agreeing with
what the tests made have shown (65.1: the true rule is kept; 65.2: one rule left is the true rule), and
``splitting`` chooses the next test as the one whose largest part of the rules still fitting is smallest
(65.3). The caller supplies the rules, as given or as counted from experience, and what a test and an
outcome are; an empty list from ``fitting`` says the rules supplied are short of the one that holds (65.4).
"""

from __future__ import annotations

from collections import Counter
from collections.abc import Callable, Hashable, Iterable, Mapping, Sequence
from math import fsum, isclose, isfinite
from typing import TypeVar

Test = TypeVar("Test", bound=Hashable)
Outcome = TypeVar("Outcome", bound=Hashable)
Rule = Mapping[Test, Outcome]


def fitting(rules: Iterable[Rule[Test, Outcome]], shown: Mapping[Test, Outcome]) -> list[Rule[Test, Outcome]]:
    """The rules that give every test made the outcome it showed."""
    return [rule for rule in rules if all(rule[test] == outcome for test, outcome in shown.items())]


def splitting(rules: Sequence[Rule[Test, Outcome]], tests: Iterable[Test]) -> Test | None:
    """The test whose largest part of ``rules`` is smallest, the first of those that tie; nothing where there
    is no test or no test tells any two of the rules apart."""
    best: Test | None = None
    least = len(rules)
    for test in tests:
        largest = max(Counter(rule[test] for rule in rules).values(), default=0)
        if largest < least:
            best, least = test, largest
    return best


def expected_test_gain(
    prior: Sequence[float],
    likelihoods: Sequence[Sequence[float]],
    continuation: Callable[[tuple[float, ...]], float],
    opportunities: int,
    price: float,
) -> float:
    """Net expected value of one observation over repeated future opportunities.

    Each hypothesis has a prior probability and a distribution over the same
    possible observations. The caller values its best continuation at each
    posterior, in reward per remaining opportunity. Price is paid once.
    Observations of zero predictive probability never reach the callback.
    """
    belief = tuple(prior)
    models = tuple(tuple(row) for row in likelihoods)

    def distribution(values: tuple[float, ...]) -> bool:
        return all(isfinite(p) and p >= 0 for p in values) and isclose(fsum(values), 1.0)

    if not distribution(belief) or len(models) != len(belief):
        raise ValueError("expected one observation distribution per prior hypothesis")
    if any(len(row) != len(models[0]) or not distribution(row) for row in models):
        raise ValueError("expected probability distributions over a common observation space")
    if opportunities < 0 or not isfinite(price) or price < 0:
        raise ValueError("expected nonnegative opportunities and a finite nonnegative price")
    if not opportunities:
        return -price

    gains = []
    before = continuation(belief)
    for likelihood in zip(*models, strict=True):
        joint = tuple(p * q for p, q in zip(belief, likelihood, strict=True))
        chance = fsum(joint)
        if chance:
            posterior = tuple(p / chance for p in joint)
            gains.append(chance * (continuation(posterior) - before))
    return opportunities * fsum(gains) - price
