"""Durable finite-evidence non-regression across affected routes."""

from collections.abc import Iterator
from dataclasses import replace
from pathlib import Path

import pytest

from nca.effects import effect_scope, expert_scope
from nca.evidence import benchmark, evaluation
from nca.memory import MemoryRecord, MemoryStore
from nca.objects import Attestation
from nca.retention import replay_gate


@pytest.fixture
def memory(tmp_path: Path) -> Iterator[tuple[MemoryStore, tuple[str, ...]]]:
    store = MemoryStore(
        tmp_path / "memory.sqlite", capacity_bytes=10000, read_effect="read", write_effect="write"
    )
    try:
        with effect_scope(frozenset({"read", "write"})), expert_scope(frozenset({"read", "write"})):
            refs = tuple(
                store.append(MemoryRecord("case", str(i).encode(), "source@1", float(i)))
                for i in range(4)
            )
            yield store, refs
    finally:
        store.close()


def retained(identity: str, refs: tuple[str, ...], bits: tuple[bool, ...]) -> Attestation:
    return evaluation(identity, benchmark(refs), bits, "lab", records=refs)


def test_route_losses_cannot_be_offset_by_another_routes_wins(
    memory: tuple[MemoryStore, tuple[str, ...]],
) -> None:
    store, refs = memory
    claims = (
        retained("old-a", refs[:2], (True, True)),
        retained("old-b", refs[2:], (False, False)),
    )
    result = replay_gate(
        store,
        claims,
        {"lab"},
        lambda identity, record: identity == "old-b" or record.payload == b"0",
        max_cases=4,
    )
    assert not result.accepted
    assert [(r.losses, r.wins, r.accepted) for r in result.routes] == [(1, 0, False), (0, 2, True)]
    permitted = replay_gate(
        store,
        claims,
        {"lab"},
        lambda identity, record: identity == "old-b" or record.payload == b"0",
        max_cases=4,
        max_losses=1,
    )
    assert permitted.accepted


def test_zero_loss_preserves_every_retained_success(
    memory: tuple[MemoryStore, tuple[str, ...]],
) -> None:
    store, refs = memory
    claims = (retained("old", refs, (True, False, True, False)),)
    result = replay_gate(store, claims, {"lab"}, lambda identity, record: True, max_cases=4)
    assert result.accepted
    assert result.routes[0].losses == 0
    assert result.routes[0].wins == 2


def test_family_is_frozen_before_any_evaluation(
    memory: tuple[MemoryStore, tuple[str, ...]],
) -> None:
    store, refs = memory
    first = retained("first", refs[:1], (True,))
    second = retained("second", refs[1:2], (True,))

    def evaluate(identity: str, record: MemoryRecord) -> bool:
        if identity == "first":
            second.claim["outcomes"] = "0"
            second.claim["records"][:] = [refs[3]]
            return True
        assert record.payload == b"1"
        return False

    result = replay_gate(store, (first, second), {"lab"}, evaluate, max_cases=2)
    assert not result.accepted
    assert result.routes[1].losses == 1


def test_budget_and_family_errors_happen_before_callbacks(
    memory: tuple[MemoryStore, tuple[str, ...]],
) -> None:
    store, refs = memory
    claim = retained("route", refs, (True,) * 4)
    calls = []

    def evaluate(identity: str, record: MemoryRecord) -> bool:
        calls.append(identity)
        return True

    for claims, budget in [
        ((claim,), 3),
        ((claim, replace(claim, claim={**claim.claim, "outcomes": "0000"})), 8),
        ((claim, replace(claim, issuer="other")), 8),
    ]:
        with pytest.raises(ValueError):
            replay_gate(store, claims, {"lab"}, evaluate, max_cases=budget)
    assert calls == []


def test_missing_evidence_prevents_result(memory: tuple[MemoryStore, tuple[str, ...]]) -> None:
    store, _ = memory
    claim = retained("route", ("missing",), (True,))
    with pytest.raises(KeyError):
        replay_gate(store, (claim,), {"lab"}, lambda identity, record: True, max_cases=1)


@pytest.mark.parametrize(
    "mutation",
    [
        {"outcomes": "x"},
        {"outcomes": ""},
        {"records": []},
        {"records": ["same", "same"]},
        {"benchmark": "wrong"},
        {"identity": "another-subject"},
    ],
)
def test_malformed_claim_is_rejected(
    memory: tuple[MemoryStore, tuple[str, ...]], mutation: dict
) -> None:
    store, refs = memory
    claim = retained("route", refs[:1], (True,))
    broken = replace(claim, claim={**claim.claim, **mutation})
    with pytest.raises(ValueError):
        replay_gate(store, (broken,), {"lab"}, lambda identity, record: True, max_cases=10)


def test_legacy_evaluation_without_memory_binding_is_not_replay_evidence(
    memory: tuple[MemoryStore, tuple[str, ...]],
) -> None:
    store, refs = memory
    claim = evaluation("route", benchmark(refs), (True,) * 4, "lab")
    with pytest.raises(ValueError):
        replay_gate(store, (claim,), {"lab"}, lambda identity, record: True, max_cases=4)


def test_evaluator_must_return_boolean(memory: tuple[MemoryStore, tuple[str, ...]]) -> None:
    store, refs = memory
    with pytest.raises(TypeError):
        replay_gate(
            store,
            (retained("route", refs[:1], (True,)),),
            {"lab"},
            lambda identity, record: 1,
            max_cases=1,
        )


def test_signed_baseline_is_verified(memory: tuple[MemoryStore, tuple[str, ...]]) -> None:
    pytest.importorskip("cryptography")
    from nca.evidence.trust import Ed25519Signer, Trust

    store, refs = memory
    signer = Ed25519Signer()
    claim = signer.sign(retained("route", refs[:1], (True,)))
    trust = Trust({signer.issuer})
    assert replay_gate(store, (claim,), trust, lambda identity, record: True, max_cases=1).accepted
    forged = replace(claim, claim={**claim.claim, "outcomes": "0"})
    with pytest.raises(ValueError, match="trusted"):
        replay_gate(store, (forged,), trust, lambda identity, record: True, max_cases=1)


def test_empty_family_protects_nothing(memory: tuple[MemoryStore, tuple[str, ...]]) -> None:
    store, _ = memory
    result = replay_gate(store, (), set(), lambda identity, record: False, max_cases=0)
    assert result.accepted and result.routes == ()


@pytest.mark.parametrize("value", [-1, True, 1.5])
def test_invalid_replay_budget(memory: tuple[MemoryStore, tuple[str, ...]], value: object) -> None:
    store, _ = memory
    with pytest.raises(ValueError):
        replay_gate(store, (), set(), lambda identity, record: True, max_cases=value)
    with pytest.raises(ValueError):
        replay_gate(store, (), set(), lambda identity, record: True, max_cases=0, max_losses=value)


def test_retained_evaluation_validates_its_binding() -> None:
    for refs, bits, bench in [
        ((), (), benchmark(())),
        (("x", "x"), (True, True), benchmark(("x", "x"))),
        (("x",), (True,), "wrong"),
        (("x",), (1,), benchmark(("x",))),
    ]:
        with pytest.raises(ValueError):
            evaluation("route", bench, bits, "lab", records=refs)


def test_single_string_does_not_act_as_substring_issuer_policy(
    memory: tuple[MemoryStore, tuple[str, ...]],
) -> None:
    store, refs = memory
    with pytest.raises(TypeError):
        replay_gate(
            store,
            (retained("route", refs[:1], (True,)),),
            "laboratory",
            lambda identity, record: True,
            max_cases=1,
        )


def test_retained_binding_survives_artifact_store_round_trip(
    memory: tuple[MemoryStore, tuple[str, ...]],
    tmp_path: Path,
) -> None:
    from nca.abi import Contract, Manifest
    from nca.objects import Primitive, Store

    episodes, refs = memory
    artifacts = Store()
    identity = artifacts.put(
        Primitive(Manifest("route", "1", Contract(("input",), "output")), "contributor:load")
    )
    claim = retained(identity, refs, (True,) * len(refs))
    artifacts.put(claim)
    directory = tmp_path / "artifacts"
    artifacts.save(directory)
    reopened = Store.open(directory)
    (saved,) = reopened.attestations(identity)
    assert saved.ref == claim.ref
    assert replay_gate(
        episodes, (saved,), {"lab"}, lambda route, record: True, max_cases=len(refs)
    ).accepted


def test_multiple_baselines_union_distinct_cases_per_route(
    memory: tuple[MemoryStore, tuple[str, ...]],
) -> None:
    store, refs = memory
    first = retained("route", refs[:2], (True, True))
    second = retained("route", refs[1:3], (True, True))
    calls = []

    def evaluate(identity: str, record: MemoryRecord) -> bool:
        calls.append(record.payload)
        return record.payload != b"2"

    result = replay_gate(store, (first, second, first), {"lab"}, evaluate, max_cases=3)
    assert len(result.routes) == 1
    assert result.routes[0].records == refs[:3]
    assert calls == [b"0", b"1", b"2"]
    assert result.routes[0].losses == 1
    assert not result.accepted
