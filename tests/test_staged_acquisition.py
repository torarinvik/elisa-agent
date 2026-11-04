"""Fresh tests and bounded staged training (§20.18)."""

from collections.abc import Hashable, Sequence
from functools import partial
from typing import Any
from fractions import Fraction

import pytest

from nca.abi import Contract, Manifest, Module
from nca.learning.affine import fit_affine
from nca.retention.acquisition import CertifiedAcquirer
from nca.retention.sampled import decision_level, required_cases
from nca.stats import family_audit_alpha


class Source:
    def __init__(self) -> None:
        self.cursor = 0

    def __call__(self, contract: Contract, count: int) -> list[tuple[Any, Any]]:
        rows = [(float(i), 3.0 * i + 7) for i in range(self.cursor, self.cursor + count)]
        self.cursor += count
        return rows


class Table:
    def __init__(self, contract: Contract, table: dict[Hashable, Hashable]) -> None:
        self.manifest = Manifest("table", "1", contract, effects=frozenset())
        self.table = table

    def invoke(self, key: Any) -> Any:
        return self.table.get(key)


def test_good_early_fit_stops_without_spending_the_maximum_training_budget() -> None:
    calls: list[int] = []

    def fit(contract: Contract, keys: Sequence[Hashable], labels: Sequence[Hashable]
            ) -> Module | None:
        calls.append(len(keys))
        return fit_affine(contract, keys, labels, cost=1.0)

    acquire = CertifiedAcquirer(fit, Source(), train=1024, tolerance=0.05, confidence=0.05,
                                stages=(8, 32, 128, 1024), agree=lambda a, b: abs(a - b) < 0.5)
    assert acquire(Contract(("a",), "b")) is not None
    assert calls == [8]
    level = family_audit_alpha(decision_level(0.05, 0), 4)
    assert acquire.labels == 8 + required_cases(0.05, level) < 1024


def test_failed_tests_are_training_only_and_never_reused_as_fresh_evidence() -> None:
    source = Source()
    seen: list[set[Hashable]] = []

    def fit(contract: Contract, keys: Sequence[Hashable], labels: Sequence[Hashable]
            ) -> Module:
        seen.append(set(keys))
        return Table(contract, dict(zip(keys, labels, strict=True)))

    acquire = CertifiedAcquirer(fit, source, train=8, tolerance=0.05, confidence=0.05,
                                stages=(2, 4, 8))
    assert acquire(Contract(("a",), "b")) is None
    assert [len(keys) for keys in seen] == [2, 4, 8]
    assert seen == [set(map(float, range(n))) for n in (2, 4, 8)]
    # Rejected test keys 2 and 4 become training at later stages. Every next
    # test still draws a new key, so a memorizer never passes. Each label is
    # charged once: eight eventually train, and one rejects the final stage.
    assert acquire.labels == source.cursor == 9
    assert acquire.certified == {}


def test_later_stage_can_learn_from_a_failed_test() -> None:
    sizes: list[int] = []

    def fit(contract: Contract, keys: Sequence[Hashable], labels: Sequence[Hashable]
            ) -> Module | None:
        sizes.append(len(keys))
        if len(keys) < 4:
            return Table(contract, dict(zip(keys, labels, strict=True)))
        assert 2.0 in keys  # The failed first test becomes training evidence.
        return fit_affine(contract, keys, labels, cost=1.0)

    acquire = CertifiedAcquirer(fit, Source(), train=8, tolerance=0.05, confidence=0.05,
                                stages=(2, 4, 8), agree=lambda a, b: a is not None
                                and abs(a - b) < 0.5)
    assert acquire(Contract(("a",), "b")) is not None
    assert sizes == [2, 4]
    level = family_audit_alpha(decision_level(0.05, 0), 3)
    assert acquire.labels == 4 + required_cases(0.05, level)


@pytest.mark.parametrize("stages", [(), (4, 2, 8), (2, 2, 8), (0, 8), (2, 4), (True, 8), (2.5, 8)])
def test_invalid_schedules_are_refused(stages: Sequence[int]) -> None:
    with pytest.raises(ValueError, match="stages"):
        CertifiedAcquirer(partial(fit_affine, cost=1.0), Source(), train=8,
                           tolerance=0.05, confidence=0.05, stages=stages)


def test_float_stage_shares_do_not_exceed_the_request_allocation() -> None:
    """Exact arithmetic check of the executable union-budget premise, for
    every subset of up to eight candidate tests, including early stopping."""
    for decision in range(20):
        budget = decision_level(0.05, decision)
        for count in range(1, 9):
            share = Fraction(family_audit_alpha(budget, count))
            for mask in range(1 << count):
                assert mask.bit_count() * share <= Fraction(budget)


def test_wrong_contract_is_rejected_before_any_certification() -> None:
    def fit(contract: Contract, keys: Sequence[Hashable], labels: Sequence[Hashable]
            ) -> Module:
        return Table(Contract(("other",), "output"), {})

    source = Source()
    acquire = CertifiedAcquirer(fit, source, train=8, tolerance=0.05, confidence=0.05,
                                stages=(2, 4, 8))
    with pytest.raises(ValueError, match="requested contract"):
        acquire(Contract(("a",), "b"))
    assert source.cursor == acquire.labels == 2
