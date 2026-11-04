"""Evidence-preserving eviction and record removal (§43.11)."""

import sqlite3
from collections.abc import Iterator
from pathlib import Path

import pytest

from nca.effects import effect_scope, expert_scope
from nca.evidence import benchmark, evaluation
from nca.memory import MemoryRecord, MemoryStore
from nca.planner import Apply, Given
from nca.retention.eviction import candidates, evict, protected
from nca.retention.routes import ProtectedRoute, RouteCatalog
from nca.retention.sampled import SampledGate
from test_consolidation import Incumbent, correct, decode

Memory = tuple[MemoryStore, tuple[str, ...]]
SCOPE = frozenset({"read", "write"})


def open_store(path: Path, capacity: int = 100000) -> MemoryStore:
    return MemoryStore(path, capacity_bytes=capacity, read_effect="read", write_effect="write")


@pytest.fixture
def memory(tmp_path: Path) -> Iterator[Memory]:
    store = open_store(tmp_path / "memory.sqlite")
    try:
        with effect_scope(SCOPE), expert_scope(SCOPE):
            yield store, tuple(store.append(MemoryRecord("case", str(k).encode(), "src", k))
                               for k in range(40))
    finally:
        store.close()


def test_remove_frees_capacity_and_keeps_positions_increasing(memory: Memory) -> None:
    store, refs = memory
    used, count = store.usage()
    freed = store.remove(refs[-1])
    assert store.usage() == (used - freed, count - 1)
    with pytest.raises(KeyError):
        store.get(refs[-1])
    with pytest.raises(KeyError):
        store.remove(refs[-1])
    fresh = store.append(MemoryRecord("case", b"new", "src", 99.0))
    positions = [position for position, _ in store.scan(limit=100)]
    assert positions == sorted(set(positions))
    assert store.scan(limit=100)[-1][1] == fresh


def test_parents_cannot_be_removed_while_children_remain(memory: Memory) -> None:
    store, refs = memory
    child = store.append(MemoryRecord("case", b"child", "src", 50.0, parents=(refs[0],)))
    with pytest.raises(ValueError, match="parent"):
        store.remove(refs[0])
    store.remove(child)
    store.remove(refs[0])


def test_existing_stores_gain_a_parent_index_on_open(tmp_path: Path) -> None:
    path = tmp_path / "old.sqlite"
    with effect_scope(SCOPE), expert_scope(SCOPE):
        store = open_store(path)
        parent = store.append(MemoryRecord("case", b"p", "src", 0.0))
        store.append(MemoryRecord("case", b"c", "src", 1.0, parents=(parent,)))
        store.close()
        with sqlite3.connect(path) as db:
            db.execute("DROP TABLE memory_parents")
        reopened = open_store(path)
        with pytest.raises(ValueError, match="parent"):
            reopened.remove(parent)
        reopened.close()


def catalog_and_gate(refs: tuple[str, ...]) -> tuple[RouteCatalog, SampledGate]:
    claims = (evaluation("root", benchmark(refs[:20]), [True] * 20, "lab", records=refs[:20]),)
    route = ProtectedRoute("root", ("key",), Apply(Incumbent(), (Given("key", 0),)), decode,
                           correct)
    return RouteCatalog((route,), claims), claims


def test_ordinary_eviction_never_removes_protected_records(memory: Memory) -> None:
    """``NCA.evict_keeps_protected``."""
    store, refs = memory
    catalog, claims = catalog_and_gate(refs)
    gate = SampledGate(store, claims, {"lab"}, tolerance=0.5, confidence=0.5, seed=2,
                       max_cases=100)
    guard = protected(catalog, gate)
    assert guard == frozenset(refs[:20])
    result = evict(store, refs, catalog=catalog, sampler=gate)
    assert set(result.kept) == set(refs[:20]) and set(result.removed) == set(refs[20:])
    assert all(store.get(ref) for ref in refs[:20])
    assert result.withdrawn == {} and result.unprotected == ()


def test_candidates_prefer_drawn_cases_then_append_order(memory: Memory) -> None:
    store, refs = memory
    claims = (evaluation("root", benchmark(refs[:20]), [True] * 20, "lab", records=refs[:20]),)
    gate = SampledGate(store, claims, {"lab"}, tolerance=0.5, confidence=0.5, seed=2,
                       max_cases=100)
    decision = gate.decide(["root"], lambda identity, record, baseline: False)
    drawn = decision.routes[0].records
    order = candidates(store, protected(sampler=gate), gate)
    assert order[:len(drawn)] == list(drawn)
    assert order[len(drawn):] == list(refs[20:])
    result = evict(store, order, sampler=gate, needed=1)
    assert len(result.removed) == 1 and result.removed[0] == drawn[0]


def test_forced_removal_withdraws_evidence_and_reports_it(memory: Memory) -> None:
    """``NCA.withdraw_fresh``: later draws use only remaining unused cases."""
    store, refs = memory
    catalog, claims = catalog_and_gate(refs)
    gate = SampledGate(store, claims, {"lab"}, tolerance=0.5, confidence=0.5, seed=2,
                       max_cases=100)
    first = gate.decide(["root"], lambda identity, record, baseline: False)
    drawn = set(first.routes[0].records)
    before = gate.remaining("root")
    victims = [ref for ref in refs[:20] if ref not in drawn][:3]
    result = evict(store, victims, catalog=catalog, sampler=gate, forced=True)
    assert set(result.removed) == set(victims)
    assert result.withdrawn == {"root": 3} and result.unprotected == ("root",)
    assert gate.remaining("root") == before - 3
    later = gate.decide(["root"], lambda identity, record, baseline: False)
    assert set(later.routes[0].records).isdisjoint(drawn | set(victims))


def test_evicted_drawn_cases_leave_the_pool_and_pending_records_are_kept(
        memory: Memory) -> None:
    store, refs = memory
    claims = (evaluation("root", benchmark(refs[:20]), [True] * 20, "lab", records=refs[:20]),)
    gate = SampledGate(store, claims, {"lab"}, tolerance=0.5, confidence=0.5, seed=2,
                       max_cases=100)
    drawn = gate.decide(["root"], lambda identity, record, baseline: False).routes[0].records
    result = evict(store, list(drawn), sampler=gate)
    assert set(result.removed) == set(drawn) and result.withdrawn == {}
    assert gate.drawn("root") == ()
    assert candidates(store, protected(sampler=gate), gate)[0] == refs[20]
    kept = evict(store, refs[20:25], sampler=gate, pending=refs[20:25])
    assert kept.removed == () and set(kept.kept) == set(refs[20:25])
