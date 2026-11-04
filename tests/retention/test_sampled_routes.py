"""Route catalogs and routers admitting updates on fresh sampled cases (§43.7)."""

from collections.abc import Iterator
from pathlib import Path

import pytest

from nca.effects import effect_scope, expert_scope
from nca.memory import MemoryRecord, MemoryStore
from nca.planner import Apply, Given
from nca.retention.routes import ReplayContext, RouteCatalog
from nca.retention.sampled import SampledGate
from nca.router import ReplayRejected, Router
from test_guarded_routes import Version, claim, route

Memory = tuple[MemoryStore, tuple[str, ...]]
VALUES = tuple(str(i).encode() for i in range(200))
EVEN = tuple(value for value in VALUES if int(value) % 2 == 0)


@pytest.fixture
def memory(tmp_path: Path) -> Iterator[Memory]:
    store = MemoryStore(tmp_path / "memory.sqlite", capacity_bytes=200000,
                        read_effect="read", write_effect="write")
    try:
        with effect_scope(frozenset({"read", "write"})), expert_scope(frozenset({"read", "write"})):
            yield store, tuple(store.append(MemoryRecord("case", value, "producer", float(i)))
                               for i, value in enumerate(VALUES))
    finally:
        store.close()


def sampler(store: MemoryStore, claims: tuple[object, ...]) -> SampledGate:
    return SampledGate(store, claims, {"lab"}, tolerance=0.2, confidence=0.2, seed=3,
                       max_cases=10000)


def test_sampled_publication_spends_one_sampler_across_snapshots(memory: Memory) -> None:
    store, refs = memory
    old = Version("1")
    claims = (claim("first", refs), claim("second", refs))
    catalog = RouteCatalog((route("first", old), route("second", old)), claims)
    gate = sampler(store, claims)
    rejected = catalog.replace(((old, Version("2", matches=())),), store, {"lab"},
                               max_cases=0, budget=1, sampler=gate)
    assert not rejected.accepted and rejected.catalog is catalog
    assert rejected.sampled is not None and rejected.sampled.index == 0
    drawn = set(rejected.sampled.routes[0].records)
    newer = Version("3")
    accepted = catalog.replace(((old, newer),), store, {"lab"}, max_cases=0, budget=1,
                               sampler=gate)
    assert accepted.accepted and accepted.sampled.index == 1
    assert accepted.catalog.routes["first"].plan.module is newer
    assert catalog.routes["first"].plan.module is old
    assert drawn.isdisjoint(accepted.sampled.routes[0].records)


def test_sampled_mode_protects_successes_acquired_after_attestation(memory: Memory) -> None:
    store, refs = memory
    original = Version("1", matches=EVEN)
    bits = tuple(int(value) % 2 == 0 for value in VALUES)
    claims = (claim("root", refs, bits),)
    gate = sampler(store, claims)
    catalog = RouteCatalog((route("root", original),), claims)
    improved = Version("2")
    first = catalog.replace(((original, improved),), store, {"lab"}, max_cases=0, budget=1,
                            sampler=gate)
    assert first.accepted
    forgetting = first.catalog.replace(((improved, Version("3", matches=EVEN)),), store,
                                       {"lab"}, max_cases=0, budget=1, sampler=gate)
    assert not forgetting.accepted and forgetting.catalog is first.catalog
    assert forgetting.sampled is not None and forgetting.sampled.routes[0].losses > 0


def test_missing_sampled_evidence_refuses_without_invocation(memory: Memory) -> None:
    store, refs = memory
    old, new = Version("1"), Version("2")
    small = (claim("root", refs[:3]),)
    catalog = RouteCatalog((route("root", old),), small)
    refused = catalog.replace(((old, new),), store, {"lab"}, max_cases=0, budget=1,
                              sampler=sampler(store, small))
    assert not refused.accepted and refused.sampled.insufficient == ("root",)
    assert old.calls == [] and new.calls == []
    with pytest.raises(ValueError, match="no retained evaluation"):
        catalog.replace(((old, new),), store, {"lab"}, max_cases=0, budget=1,
                        sampler=sampler(store, (claim("elsewhere", refs),)))
    with pytest.raises(ValueError, match="zero losses"):
        catalog.replace(((old, new),), store, {"lab"}, max_cases=0, budget=1, max_losses=1,
                        sampler=sampler(store, small))


def test_router_upgrades_through_a_sampled_replay_context(memory: Memory) -> None:
    store, refs = memory
    old, good, bad = Version("1"), Version("2"), Version("3", matches=())
    root = route("root", old)
    claims = (claim("root", refs),)
    router = Router(RouteCatalog((root,), claims))
    replay = ReplayContext(store, {"lab"}, max_cases=0, budget=1, sampler=sampler(store, claims))
    with pytest.raises(ReplayRejected):
        router.upgrade((old, bad), ("input",), "output", Apply(bad, (Given("input", 0),)),
                       replay=replay)
    candidate = Apply(good, (Given("input", 0),))
    router.upgrade((old, good), ("input",), "output", candidate, replay=replay)
    assert router.route((old,), ("input",), "output") is candidate
    assert router.last_update is not None and router.last_update.sampled is not None
