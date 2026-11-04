"""Durable exact memory, permissions, provenance and transactional capacity."""
from collections.abc import Iterator
from concurrent.futures import ThreadPoolExecutor
from contextlib import contextmanager
from pathlib import Path
import sqlite3

import pytest

from nca.effects import EffectDenied, effect_scope, expert_scope
from nca.memory import MemoryFull, MemoryRecord, MemoryStore

READ = "test.recall"
WRITE = "test.append"
BOTH = frozenset({READ, WRITE})


@contextmanager
def authority(effects: frozenset[str] = BOTH) -> Iterator[None]:
    with effect_scope(effects), expert_scope(effects):
        yield


def record(value: bytes = b"\x00\xff", **kwargs: object) -> MemoryRecord:
    return MemoryRecord("observation", value, "producer@version", 1.0, **kwargs)


def store(path: Path, capacity: int = 10000) -> MemoryStore:
    return MemoryStore(path, capacity_bytes=capacity, read_effect=READ, write_effect=WRITE)


def test_durable_exact_recall_and_idempotence(tmp_path: Path) -> None:
    path = tmp_path / "memory.sqlite"
    original = record(confidence=0.7)
    memory = store(path)
    with authority():
        reference = memory.append(original)
        usage = memory.usage()
        assert reference == original.ref
        assert memory.get(reference) == original
        assert memory.append(original) == reference
        assert memory.usage() == usage == (len(original.encode()) + len(reference), 1)
    memory.close()
    reopened = store(path)
    with authority():
        assert reopened.get(reference) == original
        assert reopened.usage() == usage
    reopened.close()


def test_supersession_preserves_old_evidence(tmp_path: Path) -> None:
    memory = store(tmp_path / "memory.sqlite")
    with authority():
        old = record(b"old", confidence=0.4)
        old_ref = memory.append(old)
        new = record(b"new", parents=(old_ref,), supersedes=old_ref, confidence=0.9)
        new_ref = memory.append(new)
        assert memory.get(new_ref) == new
        assert memory.get(old_ref) == old
        assert memory.usage()[1] == 2
        wrong_type = MemoryRecord("other", b"new", "producer", 2.0,
                                  parents=(old_ref,), supersedes=old_ref)
        with pytest.raises(ValueError, match="different type"):
            memory.append(wrong_type)
        assert memory.usage()[1] == 2
    memory.close()


def test_permissions_are_separate_and_checked_before_io(tmp_path: Path) -> None:
    memory = store(tmp_path / "memory.sqlite")
    with pytest.raises(EffectDenied):
        memory.append(record())
    with authority(frozenset({WRITE})):
        reference = memory.append(record())
        with pytest.raises(EffectDenied):
            memory.get(reference)
        with pytest.raises(EffectDenied):
            memory.usage()
    with authority(frozenset({READ})):
        assert memory.get(reference) == record()
        with pytest.raises(EffectDenied):
            memory.append(record(b"denied"))
    memory.close()


def test_quota_rejection_is_atomic_and_duplicates_fit_when_full(tmp_path: Path) -> None:
    original = record()
    capacity = len(original.encode()) + len(original.ref)
    memory = store(tmp_path / "memory.sqlite", capacity)
    with authority():
        reference = memory.append(original)
        with pytest.raises(MemoryFull):
            memory.append(record(b"another"))
        assert memory.usage() == (capacity, 1)
        assert memory.append(original) == reference
        assert memory.get(reference) == original
    memory.close()


def test_missing_parent_rejection_does_not_spend_quota(tmp_path: Path) -> None:
    memory = store(tmp_path / "memory.sqlite")
    with authority():
        with pytest.raises(ValueError, match="parent does not exist"):
            memory.append(record(parents=("missing",)))
        assert memory.usage() == (0, 0)
        with pytest.raises(KeyError):
            memory.get("missing")
    memory.close()


def test_capacity_cannot_be_changed_by_reopening(tmp_path: Path) -> None:
    path = tmp_path / "memory.sqlite"
    memory = store(path, 0)
    memory.close()
    with pytest.raises(ValueError, match="capacity"):
        store(path, 1)
    reopened = store(path, 0)
    with authority():
        with pytest.raises(MemoryFull):
            reopened.append(record())
        assert reopened.usage() == (0, 0)
    reopened.close()


def test_concurrent_handles_cannot_overcommit_quota(tmp_path: Path) -> None:
    path = tmp_path / "memory.sqlite"
    samples = [record(bytes([value])) for value in range(8)]
    charge = len(samples[0].encode()) + len(samples[0].ref)
    capacity = 2 * charge
    initial = store(path, capacity)
    initial.close()

    def append(value: MemoryRecord) -> bool:
        memory = store(path, capacity)
        try:
            with authority():
                try:
                    memory.append(value)
                    return True
                except MemoryFull:
                    return False
        finally:
            memory.close()

    with ThreadPoolExecutor(max_workers=4) as executor:
        accepted = list(executor.map(append, samples))
    assert sum(accepted) == 2
    memory = store(path, capacity)
    with authority():
        assert memory.usage() == (capacity, 2)
        for value, kept in zip(samples, accepted, strict=True):
            if kept:
                assert memory.get(value.ref) == value
    memory.close()


def test_corrupted_record_is_not_recalled_as_valid(tmp_path: Path) -> None:
    path = tmp_path / "memory.sqlite"
    memory = store(path)
    with authority():
        reference = memory.append(record())
    # Host-side file corruption is outside the permission boundary.
    with sqlite3.connect(path) as database:
        database.execute("UPDATE memory_records SET encoded=? WHERE ref=?", (b"{}", reference))
    with authority(), pytest.raises(ValueError, match="digest mismatch"):
        memory.get(reference)
    memory.close()


@pytest.mark.parametrize("kwargs", [
    {"confidence": -0.1}, {"confidence": float("nan")}, {"confidence": 1.1},
    {"supersedes": "absent"}, {"parents": (3,)},
])
def test_invalid_record_metadata(kwargs: dict[str, object]) -> None:
    with pytest.raises((ValueError, TypeError)):
        record(**kwargs)


def test_invalid_payload_time_identity_and_capacity(tmp_path: Path) -> None:
    with pytest.raises(TypeError):
        record(bytearray(b"mutable"))
    with pytest.raises(ValueError):
        MemoryRecord("observation", b"x", "", 0.0)
    with pytest.raises(ValueError):
        MemoryRecord("observation", b"x", "producer", float("inf"))
    for capacity in [-1, True, 1.5]:
        with pytest.raises(ValueError):
            store(tmp_path / "unused.sqlite", capacity)


def test_recall_expert_uses_runtime_permissions_and_risk(tmp_path: Path) -> None:
    from nca.abi import Contract, Manifest, Message
    from nca.planner import Apply, Given
    from nca.runtime import RiskLedger, execute
    from nca.workspace import Workspace

    memory = store(tmp_path / "memory.sqlite")
    with authority(frozenset({WRITE})):
        reference = memory.append(record(confidence=0.8))

    class Recall:
        manifest = Manifest("recall", "1", Contract(("reference",), "observation"),
                            effects=frozenset({READ}))

        def invoke(self, reference: str) -> bytes:
            return memory.get(reference).payload

        def risk(self, output: bytes, reference: str) -> float:
            confidence = memory.get(reference).confidence
            return 1 - confidence if confidence is not None else 1.0

    ledger = RiskLedger()
    module = Recall()
    with effect_scope(frozenset({READ})):
        answer = execute(Apply(module, (Given("reference"),)),
                         (Message("reference", reference, "input"),), Workspace(), 1,
                         ledger=ledger)
    assert answer.payload == record().payload
    assert ledger.charge == pytest.approx(0.2)
    assert ledger.invocations[0].expert is module
    assert ledger.invocations[0].values == (reference,)
    memory.close()


def test_durable_store_rejects_ephemeral_database() -> None:
    with pytest.raises(ValueError, match="file-backed WAL"):
        store(Path(":memory:"))


def test_bounded_scan_can_resume_after_reopen_and_concurrent_append(tmp_path: Path) -> None:
    path = tmp_path / "memory.sqlite"
    memory = store(path)
    with authority():
        refs = [memory.append(record(bytes([i]))) for i in range(3)]
        assert memory.scan(limit=0) == ()
        assert memory.scan(limit=2) == ((1, refs[0]), (2, refs[1]))
        assert memory.scan(after=2, limit=2) == ((3, refs[2]),)
    memory.close()
    memory = store(path)
    other = store(path)
    with authority():
        fourth = other.append(record(b"fourth"))
        assert memory.scan(after=3, limit=2) == ((4, fourth),)
        assert memory.scan(after=4, limit=1) == ()
        for cursor, limit in [(-1, 1), (True, 1), (0, -1), (0, 1.5)]:
            with pytest.raises(ValueError):
                memory.scan(after=cursor, limit=limit)
    with pytest.raises(EffectDenied):
        memory.scan(limit=1)
    other.close()
    memory.close()
