"""Experiments that tell rules apart (THEORY §65).

A rule gives each test an outcome. ``fitting`` keeps, of the rules that could hold, those agreeing with
what the tests made have shown (65.1: the true rule is kept; 65.2: one rule left is the true rule), and
``splitting`` chooses the next test as the one whose largest part of the rules still fitting is smallest
(65.3). The caller supplies the rules, as given or as counted from experience, and what a test and an
outcome are; an empty list from ``fitting`` says the rules supplied are short of the one that holds (65.4).
"""

from __future__ import annotations

from collections import Counter
from collections.abc import Hashable, Iterable, Mapping, Sequence
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
