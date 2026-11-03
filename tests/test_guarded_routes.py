"""Managed explicit-route replacement cannot bypass affected-root replay."""

from collections.abc import Iterator, Sequence
from dataclasses import dataclass, field, replace
from pathlib import Path
from typing import Any

import pytest

from nca.abi import Contract, Manifest, Message, seq_type
from nca.effects import effect_scope, expert_scope
from nca.evidence import benchmark, evaluation
from nca.guarded_routes import ProtectedRoute, RouteCatalog
from nca.memory import MemoryRecord, MemoryStore
from nca.planner import Apply, Given, Map
from nca.runtime import BudgetExceeded


@dataclass
class Version:
    version: str
    matches: tuple[bytes, ...] | None = None
    name: str = "expert"
    contract: Contract = Contract(("input",), "output")
    calls: list[Any] = field(default_factory=list)

    @property
    def identity(self) -> str:
        return f"{self.name}@{self.version}"

    @property
    def manifest(self) -> Manifest:
        return Manifest(self.name, self.version, self.contract, effects=frozenset())

    def invoke(self, value: bytes) -> bytes:
        self.calls.append(value)
        return value if self.matches is None or value in self.matches else b"wrong"


def decode(record: MemoryRecord) -> tuple[Sequence[Message], bytes]:
    return (Message("input", record.payload, "input"),), record.payload


def correct(value: Any, label: Any) -> bool:
    return value == label


def route(anchor: str, module: Version) -> ProtectedRoute:
    return ProtectedRoute(anchor, ("input",), Apply(module, (Given("input", 0),)), decode, correct)


@pytest.fixture
def memory(tmp_path: Path) -> Iterator[tuple[MemoryStore, tuple[str, ...]]]:
    store = MemoryStore(
        tmp_path / "memory.sqlite", capacity_bytes=10000, read_effect="read", write_effect="write"
    )
    try:
        with effect_scope(frozenset({"read", "write"})), expert_scope(frozenset({"read", "write"})):
            refs = tuple(
                store.append(MemoryRecord("case", value, "producer", float(i)))
                for i, value in enumerate((b"a", b"b"))
            )
            yield store, refs
    finally:
        store.close()


def claim(anchor: str, refs: tuple[str, ...], bits: tuple[bool, ...] | None = None) -> Any:
    return evaluation(
        anchor,
        benchmark(refs),
        bits if bits is not None else (True,) * len(refs),
        "lab",
        records=refs,
    )


def test_publication_is_atomic_and_old_snapshots_remain_pinned(
    memory: tuple[MemoryStore, tuple[str, ...]],
) -> None:
    store, refs = memory
    old, other = Version("1"), Version("1", name="other")
    catalog = RouteCatalog(
        (route("first", old), route("second", old), route("unrelated", other)),
        (claim("first", refs), claim("second", refs)),
    )
    rejected = catalog.replace(
        ((old, Version("2", matches=())),), store, {"lab"}, max_cases=4, budget=1
    )
    assert rejected.affected == ("first", "second")
    assert not rejected.accepted and rejected.catalog is catalog
    newer = Version("3")
    accepted = catalog.replace(((old, newer),), store, {"lab"}, max_cases=4, budget=1)
    assert accepted.accepted and accepted.previous is catalog
    assert accepted.catalog is not catalog
    assert accepted.catalog.routes["first"].plan.module is newer
    assert catalog.routes["first"].plan.module is old
    assert accepted.catalog.routes["unrelated"] is catalog.routes["unrelated"]
    with pytest.raises(TypeError):
        accepted.catalog.routes["new"] = route("new", newer)


def test_successes_acquired_after_original_attestation_are_protected(
    memory: tuple[MemoryStore, tuple[str, ...]],
) -> None:
    store, refs = memory
    original = Version("1", matches=(b"a",))
    catalog = RouteCatalog((route("root", original),), (claim("root", refs, (True, False)),))
    improved = Version("2")
    first = catalog.replace(((original, improved),), store, {"lab"}, max_cases=2, budget=1)
    assert first.accepted
    forgetting = first.catalog.replace(
        ((improved, Version("3", matches=(b"a",))),), store, {"lab"}, max_cases=2, budget=1
    )
    assert forgetting.retained.accepted  # Original baseline alone would miss this loss.
    assert not forgetting.current.accepted
    assert not forgetting.accepted and forgetting.catalog is first.catalog
    assert forgetting.current.routes[0].losses == 1


def test_every_affected_route_needs_evidence_before_any_invocation(
    memory: tuple[MemoryStore, tuple[str, ...]],
) -> None:
    store, refs = memory
    old, new = Version("1"), Version("2")
    catalog = RouteCatalog(
        (route("covered", old), route("missing", old)), (claim("covered", refs),)
    )
    with pytest.raises(ValueError, match="no retained"):
        catalog.replace(((old, new),), store, {"lab"}, max_cases=10, budget=1)
    assert old.calls == new.calls == []


def test_slots_maps_and_arguments_are_included(memory: tuple[MemoryStore, tuple[str, ...]]) -> None:
    store, refs = memory
    old, new = Version("1"), Version("2")

    class Slot:
        manifest = Manifest(
            "slot",
            "1",
            Contract(("input",), "output", ((("input",), "output"),)),
            effects=frozenset(),
        )

        def invoke(self, filling: Any, value: Any) -> Any:
            return filling(value)

    body = Apply(old, (Given("input", 0),))
    slotted = ProtectedRoute(
        "slot-root", ("input",), Apply(Slot(), (Given("input", 0),), (body,)), decode, correct
    )

    def decode_sequence(record: MemoryRecord) -> tuple[Sequence[Message], list[bytes]]:
        values = [record.payload]
        return (Message(seq_type("input"), values, "input"),), values

    mapped = ProtectedRoute(
        "map-root",
        (seq_type("input"),),
        Map("input", body, Given(seq_type("input"), 0)),
        decode_sequence,
        correct,
    )
    outer = Version("1", name="outer", contract=Contract(("output",), "output"))
    nested = ProtectedRoute("argument-root", ("input",), Apply(outer, (body,)), decode, correct)
    catalog = RouteCatalog(
        (slotted, mapped, nested),
        tuple(claim(anchor, refs[:1]) for anchor in ("slot-root", "map-root", "argument-root")),
    )
    outcome = catalog.replace(((old, new),), store, {"lab"}, max_cases=3, budget=2)
    assert outcome.accepted
    assert outcome.affected == ("slot-root", "map-root", "argument-root")
    a, b, c = outcome.catalog.routes.values()
    assert a.plan.slots[0] is b.plan.body is c.plan.args[0]
    assert a.plan.slots[0].module is new
    assert body.module is old


@pytest.mark.parametrize("budget,cost", [(0, None), (1, 0.5)])
def test_budget_errors_do_not_publish(
    memory: tuple[MemoryStore, tuple[str, ...]], budget: int, cost: float | None
) -> None:
    store, refs = memory
    old = Version("1")
    catalog = RouteCatalog((route("root", old),), (claim("root", refs),))
    with pytest.raises(BudgetExceeded):
        catalog.replace(
            ((old, Version("2")),), store, {"lab"}, max_cases=2, budget=budget, cost_budget=cost
        )
    assert catalog.routes["root"].plan.module is old


def test_metadata_is_snapshotted_and_returned_as_independent_copies(
    memory: tuple[MemoryStore, tuple[str, ...]],
) -> None:
    store, refs = memory
    old = Version("1")
    assertion = claim("root", refs)
    catalog = RouteCatalog((route("root", old),), (assertion,))
    assertion.claim["outcomes"] = "00"
    catalog.retained[0].claim["outcomes"] = "00"
    assert catalog.retained[0].claim["outcomes"] == "11"
    outcome = catalog.replace(
        ((old, Version("2", matches=())),), store, {"lab"}, max_cases=2, budget=1
    )
    assert not outcome.accepted


def test_bad_changes_are_rejected(memory: tuple[MemoryStore, tuple[str, ...]]) -> None:
    store, refs = memory
    old, new = Version("1"), Version("2")
    catalog = RouteCatalog((route("root", old),), (claim("root", refs),))
    wrong = Version("3", contract=Contract(("other",), "output"))
    for changes in [
        ((old, old),),
        ((old, Version("1")),),
        ((old, wrong),),
        ((old, new), (old, new)),
    ]:
        with pytest.raises(ValueError):
            catalog.replace(changes, store, {"lab"}, max_cases=2, budget=1)
    assert old.calls == new.calls == []


def test_untrusted_and_missing_records_never_publish(
    memory: tuple[MemoryStore, tuple[str, ...]],
) -> None:
    store, refs = memory
    old = Version("1")
    catalog = RouteCatalog((route("root", old),), (claim("root", refs),))
    with pytest.raises(ValueError, match="trusted"):
        catalog.replace(((old, Version("2")),), store, {"other"}, max_cases=2, budget=1)
    missing = RouteCatalog((route("root", old),), (claim("root", ("missing",)),))
    with pytest.raises(KeyError):
        missing.replace(((old, Version("2")),), store, {"lab"}, max_cases=1, budget=1)
    assert old.calls == []


def test_no_match_is_an_explicit_noop(memory: tuple[MemoryStore, tuple[str, ...]]) -> None:
    store, refs = memory
    old = Version("1")
    catalog = RouteCatalog((route("root", old),), (claim("root", refs),))
    outcome = catalog.replace(
        ((Version("1", name="unused"), Version("2", name="unused")),),
        store,
        set(),
        max_cases=0,
        budget=0,
    )
    assert outcome.accepted and outcome.affected == () and outcome.catalog is catalog
    assert old.calls == []


def test_registration_checks_types_and_anchor_coverage() -> None:
    module = Version("1")
    with pytest.raises(ValueError, match="well typed"):
        RouteCatalog((replace(route("root", module), available=("wrong",)),), ())
    with pytest.raises(ValueError, match="duplicate"):
        RouteCatalog((route("root", module), route("root", module)), ())
    with pytest.raises(ValueError, match="registered"):
        RouteCatalog((route("root", module),), (claim("unknown", ("record",)),))


def test_polymorphic_binding_is_preserved(memory: tuple[MemoryStore, tuple[str, ...]]) -> None:
    store, refs = memory
    contract = Contract(("?a",), "?a")
    old, new = Version("1", contract=contract), Version("2", contract=contract)
    plan = Apply(old, (Given("input", 0),), binding=(("a", "input"),))
    catalog = RouteCatalog(
        (ProtectedRoute("root", ("input",), plan, decode, correct),), (claim("root", refs),)
    )
    outcome = catalog.replace(((old, new),), store, {"lab"}, max_cases=2, budget=1)
    assert outcome.accepted
    assert outcome.catalog.routes["root"].plan.binding == plan.binding


def test_opaque_implementations_stay_pinned(memory: tuple[MemoryStore, tuple[str, ...]]) -> None:
    store, refs = memory
    old = Version("1")

    class Opaque:
        manifest = Manifest("opaque", "1", old.contract, effects=frozenset())
        identity = "opaque@1"

        def invoke(self, value: bytes) -> bytes:
            return old.invoke(value)

    root = ProtectedRoute(
        "root", ("input",), Apply(Opaque(), (Given("input", 0),)), decode, correct
    )
    catalog = RouteCatalog((root,), (claim("root", refs),))
    update = catalog.replace(
        ((old, Version("2", matches=())),), store, {"lab"}, max_cases=0, budget=0
    )
    assert update.accepted and update.affected == () and update.catalog is catalog
    assert root.plan.module.invoke(b"a") == b"a"


def test_decoding_is_independent_for_current_and_candidate(
    memory: tuple[MemoryStore, tuple[str, ...]],
) -> None:
    store, refs = memory

    class Mutating(Version):
        def invoke(self, value: list[bytes]) -> bytes:
            original = value.pop()
            return original

    class Fresh(Version):
        def invoke(self, value: list[bytes]) -> bytes:
            return value[0]

    def decode_list(record: MemoryRecord) -> tuple[Sequence[Message], bytes]:
        return (Message("input", [record.payload], "input"),), record.payload

    old, new = Mutating("1"), Fresh("2")
    root = replace(route("root", old), decode=decode_list)
    catalog = RouteCatalog((root,), (claim("root", refs),))
    assert catalog.replace(((old, new),), store, {"lab"}, max_cases=2, budget=1).accepted


def test_signed_retained_metadata_survives_catalog_snapshot(
    memory: tuple[MemoryStore, tuple[str, ...]],
) -> None:
    pytest.importorskip("cryptography")
    from nca.trust import Ed25519Signer, Trust

    store, refs = memory
    old = Version("1")
    signer = Ed25519Signer()
    catalog = RouteCatalog((route("root", old),), (signer.sign(claim("root", refs)),))
    assert catalog.replace(
        ((old, Version("2")),), store, Trust({signer.issuer}), max_cases=2, budget=1
    ).accepted


def test_multiple_sources_publish_together_or_not_at_all(
    memory: tuple[MemoryStore, tuple[str, ...]],
) -> None:
    store, refs = memory
    first = Version("1", name="first")
    second = Version("1", name="second", contract=Contract(("output",), "output"))
    plan = Apply(second, (Apply(first, (Given("input", 0),)),))
    catalog = RouteCatalog(
        (ProtectedRoute("root", ("input",), plan, decode, correct),), (claim("root", refs[:1]),)
    )
    new_first = Version("2", name="first")
    bad_second = Version("2", name="second", matches=(), contract=second.contract)
    refused = catalog.replace(
        ((first, new_first), (second, bad_second)), store, {"lab"}, max_cases=1, budget=2
    )
    assert not refused.accepted and refused.catalog is catalog
    assert catalog.routes["root"].plan.module is second
    assert catalog.routes["root"].plan.args[0].module is first
    new_second = Version("3", name="second", contract=second.contract)
    accepted = catalog.replace(
        ((first, new_first), (second, new_second)), store, {"lab"}, max_cases=1, budget=2
    )
    assert accepted.accepted
    assert accepted.catalog.routes["root"].plan.module is new_second
    assert accepted.catalog.routes["root"].plan.args[0].module is new_first


def test_case_budget_is_checked_before_route_invocation(
    memory: tuple[MemoryStore, tuple[str, ...]],
) -> None:
    store, refs = memory
    old, new = Version("1"), Version("2")
    catalog = RouteCatalog((route("root", old),), (claim("root", refs),))
    with pytest.raises(ValueError, match="case budget"):
        catalog.replace(((old, new),), store, {"lab"}, max_cases=1, budget=1)
    assert old.calls == new.calls == []


def test_rewritten_snapshot_updates_reverse_dependencies(
    memory: tuple[MemoryStore, tuple[str, ...]],
) -> None:
    store, refs = memory
    old, new, third = Version("1"), Version("2"), Version("3")
    catalog = RouteCatalog((route("root", old),), (claim("root", refs),))
    first = catalog.replace(((old, new),), store, {"lab"}, max_cases=2, budget=1)
    second = first.catalog.replace(((new, third),), store, {"lab"}, max_cases=2, budget=1)
    assert second.accepted and second.affected == ("root",)
    assert second.catalog.routes["root"].plan.module is third
    obsolete = second.catalog.replace(((old, Version("4")),), store, set(), max_cases=0, budget=0)
    assert obsolete.accepted and obsolete.affected == () and obsolete.catalog is second.catalog


def test_cyclic_explicit_routes_are_rejected() -> None:
    module = Version("1")
    plan = Apply(module, ())
    object.__setattr__(plan, "args", (plan,))
    with pytest.raises(ValueError, match="cyclic"):
        RouteCatalog((ProtectedRoute("root", ("input",), plan, decode, correct),), ())


@pytest.mark.parametrize("changed", ["source", "unrelated"])
def test_in_place_manifest_changes_cannot_reuse_validation(
    memory: tuple[MemoryStore, tuple[str, ...]],
    changed: str,
) -> None:
    store, refs = memory
    old, other = Version("1"), Version("1", name="other")
    catalog = RouteCatalog((route("root", old), route("unrelated", other)), (claim("root", refs),))
    target = old if changed == "source" else other
    target.version = "mutated"
    with pytest.raises(ValueError, match="manifest changed in place"):
        catalog.replace(((old, Version("2")),), store, {"lab"}, max_cases=2, budget=1)
    assert old.calls == []
