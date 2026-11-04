"""Finite links for the contradiction-screen guarantee (§20.16)."""

from collections.abc import Hashable, Sequence
from fractions import Fraction
from itertools import product
from typing import Any

from nca.abi import Contract, Manifest, Module
from nca.retention.acquisition import CertifiedAcquirer
from nca.retention.screening import FeasibilityScreen
from nca.retention.sampled import decision_level, required_cases
from nca.learning.affine import fit_affine
from functools import partial


def identity(value: Any) -> Hashable:
    return value


def separate(a: Any, b: Any) -> bool:
    return bool(a != b)


def make_screen(cases: int = 64) -> FeasibilityScreen:
    return FeasibilityScreen(cases=cases, confidence=0.05, key=identity, separates=separate)


def test_disjoint_pairs_force_errors_for_every_predictor() -> None:
    """Exhaust all six-case samples over two keys and two labels, and every
    deterministic predictor: NCA.contradictory_pairs_errors."""
    alphabet = tuple(product(range(2), repeat=2))
    for rows in product(alphabet, repeat=6):
        screen = make_screen(6)
        screen.reject(rows, 0.05)
        assert screen.last is not None
        pairs = screen.last.pairs
        endpoints = [i for pair in pairs for i in pair]
        assert len(set(endpoints)) == len(endpoints)
        for prediction in product(range(2), repeat=2):
            errors = sum(prediction[key] != label for key, label in rows)
            assert len(pairs) <= errors


def test_exact_probability_of_false_discard_is_below_allocated_level() -> None:
    """Enumerate the entire IID experiment with a known good predictor;
    no empirical confidence estimate or floating-point tail comparison."""
    probability = Fraction(0)
    for labels in product(range(2), repeat=8):
        screen = make_screen(8)
        if screen.reject([(0, label) for label in labels], 0.125):
            errors = sum(labels)
            probability += Fraction(1, 8) ** errors * Fraction(7, 8) ** (8 - errors)
    assert probability > 0
    assert probability <= Fraction(0.05) / 2


def test_approximate_agreement_requires_true_separation() -> None:
    screen = FeasibilityScreen(cases=64, confidence=0.05, key=identity,
                               separates=lambda a, b: abs(a - b) > 2)
    assert not screen.reject([(0, i % 2) for i in range(64)], 0.05)
    assert screen.last is not None and screen.last.pairs == ()
    assert screen.reject([(0, 3 * (i % 2)) for i in range(64)], 0.05)


def test_impossible_candidate_stops_before_fit_and_charges_prefix_only() -> None:
    def fit(contract: Contract, keys: Sequence[Hashable], labels: Sequence[Hashable]
            ) -> Module | None:
        raise AssertionError("contradictions should prevent training")

    def sample(contract: Contract, count: int) -> list[tuple[Any, Any]]:
        return [(0, i % 2) for i in range(count)]

    screen = make_screen()
    acquirer = CertifiedAcquirer(fit, sample, train=4096, tolerance=0.05,
                                 confidence=0.05, screen=screen)
    assert acquirer(Contract(("a",), "b")) is None
    assert acquirer.labels == 64 and screen.rejections == 1
    assert acquirer.certified == {}


def test_passing_prefix_is_reused_and_certification_is_fresh() -> None:
    calls: list[int] = []
    cursor = 0

    def sample(contract: Contract, count: int) -> list[tuple[Any, Any]]:
        nonlocal cursor
        calls.append(count)
        rows = [(float(i), 3.0 * i + 7) for i in range(cursor, cursor + count)]
        cursor += count
        return rows

    screen = FeasibilityScreen(cases=64, confidence=0.05, key=identity,
                               separates=lambda a, b: abs(a - b) >= 1)
    acquirer = CertifiedAcquirer(partial(fit_affine, cost=1.0), sample, train=80,
                                 tolerance=0.05, confidence=0.05, screen=screen,
                                 agree=lambda a, b: abs(a - b) < 0.5)
    # Distinct inputs never produce candidate pairs.
    assert acquirer(Contract(("a",), "b")) is not None
    assert calls[:2] == [64, 16]
    assert acquirer.labels == 80 + required_cases(0.05, decision_level(0.05, 0))


def test_short_prefix_is_inconclusive_and_labels_are_charged() -> None:
    screen = make_screen()

    def sample(contract: Contract, count: int) -> list[tuple[Any, Any]]:
        return [(0, i % 2) for i in range(count - 1)]

    def fit(contract: Contract, keys: Sequence[Hashable], labels: Sequence[Hashable]
            ) -> Module | None:
        raise AssertionError("incomplete training")

    acquirer = CertifiedAcquirer(fit, sample, train=4096, tolerance=0.05,
                                 confidence=0.05, screen=screen)
    assert acquirer(Contract(("a",), "b")) is None
    assert acquirer.labels == 63 and screen.decisions == 0


def test_nullary_acquisition_invokes_with_no_arguments() -> None:
    class Constant:
        def __init__(self, contract: Contract) -> None:
            self.manifest = Manifest("constant", "1", contract, effects=frozenset())

        def invoke(self) -> str:
            return "value"

    def sample(contract: Contract, count: int) -> list[tuple[Any, Any]]:
        return [((), "value")] * count

    def fit(contract: Contract, keys: Sequence[Hashable], labels: Sequence[Hashable]
            ) -> Module:
        return Constant(contract)

    acquirer = CertifiedAcquirer(fit, sample, train=80, tolerance=0.05,
                                 confidence=0.05, screen=make_screen())
    assert acquirer(Contract((), "a")) is not None
