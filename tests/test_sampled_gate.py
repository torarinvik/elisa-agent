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


def test_required_cases_is_the_smallest_size_of_zero_loss_miss() -> None:
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
