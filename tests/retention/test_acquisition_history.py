"""Durable scoped refusal replay and unique statistical spending (§20.17)."""

from collections.abc import Hashable, Sequence
from pathlib import Path
from typing import Any
from functools import partial

import pytest

from nca.abi import Contract, Module
from nca.memory import MemoryFull, MemoryRecord
from nca.learning.affine import fit_affine
from nca.retention.acquisition import CertifiedAcquirer
from nca.retention.history import AcquisitionHistory
from nca.retention.sampled import decision_level, required_cases
from test_acquisition_screening import make_screen
from test_memory import authority, store


def no_fit(contract: Contract, keys: Sequence[Hashable], labels: Sequence[Hashable]
           ) -> Module | None:
    return None


def conflicting(contract: Contract, count: int) -> list[tuple[Any, Any]]:
    return [(0, i % 2) for i in range(count)]


def history(path: Path, context: str = "context-1", entries: int = 100) -> AcquisitionHistory:
    return AcquisitionHistory(store(path), context=context, type_id="record", producer="host",
                              entries=entries)


def acquirer(log: AcquisitionHistory) -> CertifiedAcquirer:
    return CertifiedAcquirer(no_fit, conflicting, train=4096, tolerance=0.05, confidence=0.05,
                              screen=make_screen(), history=log)


def test_refusal_survives_restart_without_new_labels_or_decisions(tmp_path: Path) -> None:
    path = tmp_path / "history.sqlite"
    first = acquirer(history(path))
    assert first.history is not None
    contract = Contract(("a",), "b")
    with authority():
        assert first(contract) is None
        assert first.labels == 64 and first.decisions == 1
        first.history.memory.close()
        second = acquirer(history(path))
        assert second.history is not None
        assert second(contract) is None
        assert second.labels == second.decisions == 0 and second.cache_hits == 1
        second.history.memory.close()


def test_scope_keys_distinguish_all_semantic_parameters(tmp_path: Path) -> None:
    log = history(tmp_path / "history.sqlite")
    contract = Contract(("a",), "b", slots=((("c",), "d"),), relevant=((0,),))
    base = log.key(contract, 0.05, 0.05, make_screen().confidence)
    variants = [Contract(("b",), "b", contract.slots, contract.relevant),
                Contract(("a",), "c", contract.slots, contract.relevant),
                Contract(("a",), "b"),
                Contract(("a",), "b", contract.slots)]
    assert all(log.key(c, 0.05, 0.05, make_screen().confidence) != base for c in variants)
    assert log.key(contract, 0.1, 0.05, make_screen().confidence) != base
    assert log.key(contract, 0.05, 0.1, make_screen().confidence) != base
    assert log.key(contract, 0.05, 0.05, None) != base
    log.context = "context-2"
    assert log.key(contract, 0.05, 0.05, make_screen().confidence) != base
    log.memory.close()


def test_context_change_retries_but_does_not_reset_spending(tmp_path: Path) -> None:
    path = tmp_path / "history.sqlite"
    with authority():
        first = acquirer(history(path))
        assert first.history is not None and first.screen is not None
        first(Contract(("a",), "b"))
        assert first.screen.last is not None
        original = first.screen.last.level
        first.history.memory.close()
        second = acquirer(history(path, "new-distribution"))
        assert second.history is not None and second.screen is not None
        second(Contract(("a",), "b"))
        assert second.labels == 64 and second.screen.last is not None
        assert second.screen.last.level < original
        assert second.screen.last.level == second.screen.confidence / 12
        second.history.memory.close()


def test_reservations_are_unique_across_handles_eviction_and_restart(tmp_path: Path) -> None:
    path = tmp_path / "history.sqlite"
    one, two = history(path), history(path)
    with authority():
        a, ref = one.reserve(b"key")
        b, _ = two.reserve(b"key")
        assert b > a
        one.memory.remove(ref)
        one.memory.close()
        one = history(path)
        c, _ = one.reserve(b"key")
        assert c > b
    one.memory.close()
    two.memory.close()


def test_evicted_refusal_retries_with_a_smaller_level(tmp_path: Path) -> None:
    log = history(tmp_path / "history.sqlite")
    acquire = acquirer(log)
    assert acquire.screen is not None
    contract = Contract(("a",), "b")
    with authority():
        acquire(contract)
        assert acquire.screen.last is not None
        level = acquire.screen.last.level
        rows = log.memory.scan(limit=10)
        log.memory.remove(rows[-1][1])
        acquire(contract)
        assert acquire.cache_hits == 0 and acquire.labels == 128
        assert acquire.screen.last.level < level
    log.memory.close()


def test_full_storage_stops_before_sampling(tmp_path: Path) -> None:
    log = AcquisitionHistory(store(tmp_path / "tiny.sqlite", capacity=0), context="ctx",
                             type_id="record", producer="host", entries=1)
    acquire = acquirer(log)
    with authority(), pytest.raises(MemoryFull):
        acquire(Contract(("a",), "b"))
    assert acquire.labels == acquire.decisions == 0
    log.memory.close()


def test_training_failure_is_not_cached_as_impossibility(tmp_path: Path) -> None:
    log = history(tmp_path / "history.sqlite")

    def sample(contract: Contract, count: int) -> list[tuple[Any, Any]]:
        return [(i, i) for i in range(count)]

    acquire = CertifiedAcquirer(no_fit, sample, train=80, tolerance=0.05, confidence=0.05,
                                screen=make_screen(), history=log)
    with authority():
        for _ in range(2):
            assert acquire(Contract(("a",), "b")) is None
        assert acquire.cache_hits == 0 and acquire.decisions == 2
        assert acquire.labels == 160
    log.memory.close()


def test_interrupted_sample_consumes_its_reservation_before_restart(tmp_path: Path) -> None:
    path = tmp_path / "history.sqlite"
    log = history(path)

    def crash(contract: Contract, count: int) -> list[tuple[Any, Any]]:
        raise RuntimeError("interrupted sample")

    acquire = CertifiedAcquirer(no_fit, crash, train=80, tolerance=0.05, confidence=0.05,
                                screen=make_screen(), history=log)
    with authority():
        with pytest.raises(RuntimeError, match="interrupted sample"):
            acquire(Contract(("a",), "b"))
        log.memory.close()
        resumed = acquirer(history(path))
        assert resumed.history is not None and resumed.screen is not None
        resumed(Contract(("a",), "b"))
        assert resumed.screen.last is not None
        assert resumed.screen.last.level == resumed.screen.confidence / 6
        resumed.history.memory.close()


def test_bounded_index_misses_can_only_trigger_new_reserved_tests(tmp_path: Path) -> None:
    log = history(tmp_path / "history.sqlite", entries=1)
    acquire = acquirer(log)
    with authority():
        for output in ("b", "c", "b", "c"):
            acquire(Contract(("a",), output))
        assert acquire.labels == 192 and acquire.decisions == 3
        assert acquire.cache_hits == 1
        assert acquire.screen is not None and acquire.screen.last is not None
        assert acquire.screen.last.level == acquire.screen.confidence / 30
    log.memory.close()


def test_atomic_position_api_preserves_duplicates_and_never_reuses_evicted_positions(
        tmp_path: Path) -> None:
    memory = store(tmp_path / "history.sqlite")
    with authority():
        record = MemoryRecord("record", b"x", "host", 0.0)
        position, reference = memory.append_position(record)
        assert memory.append_position(record) == (position, reference)
        memory.remove(reference)
        assert memory.append_position(record) == (position + 1, reference)
    memory.close()


def test_admission_spending_also_survives_restart_without_a_screen(tmp_path: Path) -> None:
    path = tmp_path / "history.sqlite"
    cursor = 0

    def sample(contract: Contract, count: int) -> list[tuple[Any, Any]]:
        nonlocal cursor
        rows = [(float(i), 3.0 * i + 7) for i in range(cursor, cursor + count)]
        cursor += count
        return rows

    with authority():
        for index in range(2):
            log = history(path)
            acquire = CertifiedAcquirer(partial(fit_affine, cost=1.0), sample, train=8,
                                        tolerance=0.05, confidence=0.05, history=log,
                                        agree=lambda a, b: abs(a - b) < 0.5)
            assert acquire(Contract(("a",), "b")) is not None
            assert acquire.labels == 8 + required_cases(0.05, decision_level(0.05, index))
            log.memory.close()
