"""Sampled admission on fresh retained cases (§43.7)."""

import math
from collections.abc import Iterator
from pathlib import Path

import pytest

from nca.effects import effect_scope, expert_scope
from nca.evidence import benchmark, evaluation
from nca.memory import MemoryRecord, MemoryStore
from nca.objects import Attestation
from nca.retention.sampled import SampledGate, decision_level, required_cases

Memory = tuple[MemoryStore, tuple[str, ...]]


@pytest.fixture
def memory(tmp_path: Path) -> Iterator[Memory]:
    store = MemoryStore(tmp_path / "memory.sqlite", capacity_bytes=100000,
                        read_effect="read", write_effect="write")
    try:
        with effect_scope(frozenset({"read", "write"})), expert_scope(frozenset({"read", "write"})):
            refs = tuple(store.append(MemoryRecord("case", str(i).encode(), "source@1", float(i)))
                         for i in range(120))
            yield store, refs
    finally:
        store.close()


def retained(identity: str, refs: tuple[str, ...], bits: tuple[bool, ...]) -> Attestation:
    return evaluation(identity, benchmark(refs), bits, "lab", records=refs)


def gate(store: MemoryStore, claims: tuple[Attestation, ...]) -> SampledGate:
    return SampledGate(store, claims, {"lab"}, tolerance=0.5, confidence=0.5, seed=7,
                       max_cases=1000)


def test_required_cases_preserves_minimal_sizes_on_ordinary_levels() -> None:
    """``NCA.zeroLoss_miss``: ``log(1/α) ≤ ε m`` and no smaller ``m`` qualifies."""
    for tolerance in (0.01, 0.05, 0.2, 0.5, 0.9):
        for level in (1e-9, 1e-4, 0.01, 0.2, 0.9):
            cases = required_cases(tolerance, level)
            assert math.log(1 / level) <= tolerance * cases
            assert cases == 1 or math.log(1 / level) > tolerance * (cases - 1)
            assert (1 - tolerance) ** cases <= level


def test_decision_levels_never_exceed_the_budget() -> None:
    """``NCA.decisionLevel_total``."""
    for count in (1, 10, 1000):
        total = sum(decision_level(0.05, k) for k in range(count))
        assert total == pytest.approx(0.05 * (1 - 1 / (count + 1)))
        assert total < 0.05


def test_no_case_informs_two_decisions_even_after_refusal_or_error(memory: Memory) -> None:
    """``NCA.allocate_fresh``: drawn cases are retired whatever the outcome."""
    store, refs = memory
    sampled = gate(store, (retained("old", refs, (True,) * len(refs)),))
    seen: list[str] = []
    rejected = sampled.decide(["old"], lambda identity, record, baseline: baseline)
    assert not rejected.accepted and rejected.index == 0
    seen += rejected.routes[0].records

    def failing(identity: str, record: MemoryRecord, baseline: bool) -> bool:
        raise RuntimeError("evaluator failed")

    before = sampled.remaining("old")
    with pytest.raises(RuntimeError):
        sampled.decide(["old"], failing)
    assert sampled.remaining("old") < before
    while True:
        decision = sampled.decide(["old"], lambda identity, record, baseline: False)
        if decision.insufficient:
            break
        assert decision.accepted
        seen += decision.routes[0].records
    assert len(seen) == len(set(seen))


def test_insufficient_evidence_refuses_without_drawing_or_spending(memory: Memory) -> None:
    store, refs = memory
    sampled = gate(store, (retained("small", refs[:2], (True, True)),
                           retained("large", refs[2:], (True,) * 118)))
    called: list[str] = []

    def evaluate(identity: str, record: MemoryRecord, baseline: bool) -> bool:
        called.append(identity)
        return False

    refused = sampled.decide(["small", "large"], evaluate)
    assert refused.insufficient == ("small",) and refused.index is None
    assert not refused.accepted and called == []
    assert sampled.remaining("large") == 118
    assert sampled.decide(["large"], evaluate).index == 0


def test_losses_see_each_drawn_case_with_its_baseline(memory: Memory) -> None:
    store, refs = memory
    bits = tuple(i % 2 == 0 for i in range(len(refs)))
    sampled = gate(store, (retained("old", refs, bits),))
    seen: dict[bytes, bool] = {}

    def loss(identity: str, record: MemoryRecord, baseline: bool) -> bool:
        seen[record.payload] = baseline
        return baseline

    decision = sampled.decide(["old"], loss)
    drawn = {store.get(ref).payload for ref in decision.routes[0].records}
    assert seen.keys() == drawn
    assert all(baseline == (int(payload) % 2 == 0) for payload, baseline in seen.items())
    assert decision.routes[0].losses == sum(seen.values())
    assert not decision.accepted


def test_added_cases_queue_behind_the_cursor_and_conflicts_fail(memory: Memory) -> None:
    store, refs = memory
    sampled = gate(store, (retained("old", refs[:60], (True,) * 60),))
    first = sampled.decide(["old"], lambda identity, record, baseline: False)
    sampled.add((retained("old", refs[:90], (True,) * 90),))
    assert sampled.remaining("old") == 90 - len(first.routes[0].records)
    with pytest.raises(ValueError, match="disagree"):
        sampled.add((retained("old", refs[:1], (False,)),))
    assert sampled.decide([], lambda identity, record, baseline: baseline).accepted


@pytest.mark.parametrize("native", [False, True])
def test_sample_size_covers_extreme_binary64_levels_and_exact_ceiling(
        native: bool, monkeypatch: pytest.MonkeyPatch) -> None:
    import random
    import struct
    from decimal import Decimal, localcontext
    from fractions import Fraction
    from nca.native import load
    from nca.retention import sampled

    kernel = getattr(load("stats"), "negative_log_upper", None)
    if native and kernel is None:
        pytest.skip("native logarithm helper unavailable or disabled")
    monkeypatch.setattr(sampled, "_LOG_UPPER", kernel if native else None)
    levels = (math.nextafter(1.0, 0.0), 0.05, 1e-300, 1e-320, math.ulp(0.0))
    tolerances = (math.nextafter(1.0, 0.0), 0.05, 1e-320, math.ulp(0.0))
    pairs = [(tolerance, level) for tolerance in tolerances for level in levels]
    rng = random.Random(4127)
    for _ in range(128):
        values = [struct.unpack(">d", rng.randrange(1, 0x3ff0000000000000).to_bytes(8, "big"))[0]
                  for _ in range(2)]
        pairs.append((values[0], values[1]))
    with localcontext() as context:
        context.prec = 160
        for tolerance, level in pairs:
            cases = required_cases(tolerance, level)
            upper = kernel(level) if native else math.nextafter(-math.log(level), math.inf)
            exact = -Decimal.from_float(level).ln()
            assert Decimal.from_float(upper) >= exact
            # log_upper_ceil_size: exact binary ratios avoid rounded products.
            assert Fraction(tolerance) * cases >= Fraction(upper)
            assert Fraction(tolerance) * (cases - 1) < Fraction(upper)
            covered = Fraction(tolerance) * cases
            assert Decimal(covered.numerator) / Decimal(covered.denominator) >= exact


def test_extreme_positive_confidence_can_finish_actual_acquisition() -> None:
    from collections.abc import Hashable, Sequence
    from typing import Any
    from nca.abi import Contract, Module
    from nca.learning.discovery import fit_decoder
    from nca.retention.acquisition import CertifiedAcquirer

    def fit(contract: Contract, keys: Sequence[Hashable], labels: Sequence[Hashable]) -> Module:
        return fit_decoder(contract, keys, labels, cost=1.0)

    def sample(contract: Contract, count: int) -> list[tuple[Any, Any]]:
        return [(0, 0)] * count

    acquire = CertifiedAcquirer(fit, sample, train=1, tolerance=0.5, confidence=1e-320)
    assert acquire(Contract(("source",), "target")) is not None
    assert acquire.labels == 1 + required_cases(0.5, decision_level(1e-320, 0))


def test_decision_levels_never_round_above_the_exact_spending_share() -> None:
    from fractions import Fraction

    total = Fraction()
    for index in range(10000):
        level = decision_level(0.05, index)
        target = Fraction(0.05) / ((index + 1) * (index + 2))
        assert Fraction(level) <= target
        assert Fraction(math.nextafter(level, math.inf)) > target
        total += Fraction(level)
    assert total <= Fraction(0.05)  # rounded_decision_budget
    # The exact denominator exceeds binary64 range, but its quotient does not.
    index = 10**155
    level = decision_level(0.05, index)
    target = Fraction(0.05) / ((index + 1) * (index + 2))
    assert 0 < Fraction(level) <= target
    assert Fraction(math.nextafter(level, math.inf)) > target
    for index in (0, 4, 1000, 10**200):
        target = Fraction(4 * math.ulp(0.0)) / ((index + 1) * (index + 2))
        if target < Fraction(math.ulp(0.0)):
            with pytest.raises(ValueError, match="underflow"):
                decision_level(4 * math.ulp(0.0), index)
        else:
            assert Fraction(decision_level(4 * math.ulp(0.0), index)) <= target


@pytest.mark.parametrize("index", [-1, True, False, 1.5, "1", None])
def test_decision_indices_must_be_nonnegative_integers(index: object) -> None:
    with pytest.raises(ValueError, match="index"):
        decision_level(0.05, index)


def test_sampled_routes_use_conservative_family_allocation(
        memory: Memory, monkeypatch: pytest.MonkeyPatch) -> None:
    from fractions import Fraction
    from nca.retention import sampled as module
    from nca.stats import family_audit_alpha

    store, refs = memory
    claims = tuple(retained(str(i), refs[40*i:40*(i+1)], (True,) * 40) for i in range(3))
    instance = SampledGate(store, claims, {"lab"}, tolerance=0.5, confidence=0.05,
                           seed=7, max_cases=1000)
    seen: list[float] = []
    original = module.required_cases

    def capture(tolerance: float, level: float) -> int:
        seen.append(level)
        return original(tolerance, level)

    monkeypatch.setattr(module, "required_cases", capture)
    for index in range(2):
        assert instance.decide(["0", "1", "2"], lambda identity, record, baseline: False).accepted
        exact = Fraction(0.05) / ((index + 1) * (index + 2))
        assert 3 * Fraction(seen[index]) <= exact
        assert seen[index] == family_audit_alpha(decision_level(0.05, index), 3)
    assert seen[1] < decision_level(0.05, 1) / 3  # Raw division rounds this witness upward.


def test_exact_subnormal_stage_share_is_not_discarded() -> None:
    from collections.abc import Hashable, Sequence
    from typing import Any
    from nca.abi import Contract, Module
    from nca.learning.discovery import fit_decoder
    from nca.retention.acquisition import CertifiedAcquirer

    def fit(contract: Contract, keys: Sequence[Hashable], labels: Sequence[Hashable]) -> Module:
        return fit_decoder(contract, keys, labels, cost=1.0)

    def sample(contract: Contract, count: int) -> list[tuple[Any, Any]]:
        return [(0, 0)] * count

    acquire = CertifiedAcquirer(fit, sample, train=2, stages=(1, 2), tolerance=0.5,
                                 confidence=4 * math.ulp(0.0))
    assert acquire(Contract(("source",), "target")) is not None
    assert acquire.labels == 1 + required_cases(0.5, math.ulp(0.0))
