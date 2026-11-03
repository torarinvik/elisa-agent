"""Consolidating corrected pieces through the gate (§43.10)."""

from collections.abc import Iterator, Sequence
from dataclasses import dataclass, field
from pathlib import Path
from typing import Any

import pytest

from nca.abi import Contract, Manifest, Message
from nca.effects import effect_scope, expert_scope
from nca.evidence import benchmark, evaluation
from nca.memory import MemoryRecord, MemoryStore
from nca.planner import Apply, Given
from nca.retention.consolidation import Example, consolidate
from nca.retention.routes import ProtectedRoute, RouteCatalog
from nca.retention.sampled import SampledGate

CONTRACT = Contract(("key",), "label")
KEYS = 60


def truth(key: int) -> int:
    return key % 7


@dataclass
class Incumbent:
    """Right on even keys."""

    @property
    def manifest(self) -> Manifest:
        return Manifest("incumbent", "1", CONTRACT, effects=frozenset())

    def invoke(self, key: int) -> int:
        return truth(key) if key % 2 == 0 else -1


@dataclass
class Patched:
    """A local correction of one key over an inner piece."""

    inner: Any
    key: int
    version: str = "1"

    @property
    def manifest(self) -> Manifest:
        return Manifest(f"patch-{self.key}", self.version, CONTRACT, effects=frozenset())

    def invoke(self, key: int) -> int:
        return truth(key) if key == self.key else self.inner.invoke(key)


@dataclass
class Table:
    """A compact consolidated piece: a lookup with a constant default."""

    entries: dict[int, int] = field(default_factory=dict)
    version: str = "1"

    @property
    def manifest(self) -> Manifest:
        return Manifest("table", self.version, CONTRACT, effects=frozenset())

    def invoke(self, key: int) -> int:
        return self.entries.get(key, -1)


def distill(examples: Sequence[Example]) -> Table:
    return Table({values[0]: output for values, output in examples})


def decode(record: MemoryRecord) -> tuple[Sequence[Message], int]:
    key = int(record.payload)
    return (Message("key", key, "key"),), truth(key)


def correct(output: Any, label: Any) -> bool:
    return output == label


Memory = tuple[MemoryStore, tuple[str, ...]]


@pytest.fixture
def memory(tmp_path: Path) -> Iterator[Memory]:
    store = MemoryStore(tmp_path / "memory.sqlite", capacity_bytes=100000,
                        read_effect="read", write_effect="write")
    try:
        with effect_scope(frozenset({"read", "write"})), expert_scope(frozenset({"read", "write"})):
            yield store, tuple(store.append(MemoryRecord("case", str(k).encode(), "src", k))
                               for k in range(KEYS))
    finally:
        store.close()


def setup(refs: tuple[str, ...]) -> tuple[RouteCatalog, Patched, tuple[Any, ...]]:
    piece: Any = Incumbent()
    for key in range(1, KEYS, 2):
        piece = Patched(piece, key)
    route = ProtectedRoute("root", ("key",), Apply(piece, (Given("key", 0),)), decode, correct)
    claims = (evaluation("root", benchmark(refs), [True] * len(refs), "lab", records=refs),)
    return RouteCatalog((route,), claims), piece, claims


def test_consolidation_distills_without_labels_and_retires_the_patched_piece(
        memory: Memory) -> None:
    store, refs = memory
    catalog, piece, _ = setup(refs)
    result = consolidate(catalog, piece, distill, [("root", ref) for ref in refs], store,
                         {"lab"}, budget=1, max_cases=KEYS)
    assert result.accepted and result.examples == KEYS
    assert result.update.catalog.routes["root"].plan.module is result.candidate
    assert result.retired == (piece,)
    assert all(result.candidate.invoke(k) == truth(k) for k in range(KEYS))


def test_lossy_consolidation_is_refused_and_retires_nothing(memory: Memory) -> None:
    store, refs = memory
    catalog, piece, _ = setup(refs)
    result = consolidate(catalog, piece, distill, [("root", ref) for ref in refs[:30]],
                         store, {"lab"}, budget=1, max_cases=KEYS)
    assert not result.accepted and result.retired == ()
    assert result.update.catalog is catalog


def test_sampled_consolidation_refuses_training_on_undrawn_cases(memory: Memory) -> None:
    store, refs = memory
    catalog, piece, claims = setup(refs)
    gate = SampledGate(store, claims, {"lab"}, tolerance=0.3, confidence=0.3, seed=1,
                       max_cases=KEYS)
    with pytest.raises(ValueError, match="not drawn"):
        consolidate(catalog, piece, distill, [("root", refs[0])], store, {"lab"},
                    budget=1, max_cases=KEYS, sampler=gate)
    probe = catalog.replace(((piece, Patched(piece, 0, "probe")),), store, {"lab"},
                            max_cases=KEYS, budget=1, sampler=gate)
    drawn = probe.sampled.routes[0].records
    result = consolidate(catalog, piece, distill, [("root", ref) for ref in drawn], store,
                         {"lab"}, budget=1, max_cases=KEYS, sampler=gate)
    assert result.update.sampled is not None
    assert set(drawn).isdisjoint(result.update.sampled.routes[0].records)


def test_training_routes_must_use_the_piece(memory: Memory) -> None:
    store, refs = memory
    catalog, piece, _ = setup(refs)
    with pytest.raises(ValueError, match="use the consolidated piece"):
        consolidate(catalog, Incumbent(), distill, [("root", refs[0])], store, {"lab"},
                    budget=1, max_cases=KEYS)
