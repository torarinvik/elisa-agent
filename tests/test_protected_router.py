"""Protected routing uses the normal upgrade/rollback path without bypasses."""

from collections.abc import Sequence
from concurrent.futures import ThreadPoolExecutor
from dataclasses import replace
from pathlib import Path
from threading import Event

import pytest

from nca.abi import Contract, Manifest, Message
from nca.effects import effect_scope, expert_scope
from nca.guarded_routes import ProtectedRoute, ReplayContext, RouteCatalog
from nca.memory import MemoryRecord, MemoryStore
from nca.planner import Apply, Given
from nca.router import ReplayRejected, Router
from test_guarded_routes import Version, claim, correct, decode, route
from test_guarded_routes import memory as memory


def context(store: MemoryStore, cases: int = 2, budget: int = 2) -> ReplayContext:
    return ReplayContext(store, {"lab"}, max_cases=cases, budget=budget)


def test_normal_upgrade_and_rollback_are_guarded(
    memory: tuple[MemoryStore, tuple[str, ...]],
) -> None:
    store, refs = memory
    old, good, bad = Version("1"), Version("2"), Version("3", matches=())
    root = route("root", old)
    catalog = RouteCatalog((root,), (claim("root", refs),))
    router = Router(catalog)
    failed = Apply(bad, (Given("input", 0),))
    with pytest.raises(ReplayRejected) as error:
        router.upgrade((old, bad), ("input",), "output", failed, replay=context(store))
    assert router.catalog is catalog
    assert router.last_update is error.value.update
    assert router.route((), ("input",), "output") is root.plan
    candidate = Apply(good, (Given("input", 0),))
    previous = router.upgrade((old, good), ("input",), "output", candidate, replay=context(store))
    assert previous is root.plan
    assert router.route((old,), ("input",), "output") is candidate
    assert router.last_update.accepted
    router.rollback("output", previous, available=("input",), replay=context(store))
    assert router.route((), ("input",), "output") is previous


def test_rollback_cannot_discard_new_retained_successes(
    memory: tuple[MemoryStore, tuple[str, ...]],
) -> None:
    store, refs = memory
    old, good = Version("1", matches=(b"a",)), Version("2")
    root = route("root", old)
    router = Router(RouteCatalog((root,), (claim("root", refs, (True, False)),)))
    candidate = Apply(good, (Given("input", 0),))
    previous = router.upgrade((old, good), ("input",), "output", candidate, replay=context(store))
    with pytest.raises(ReplayRejected):
        router.rollback("output", previous, available=("input",), replay=context(store))
    assert router.route((), ("input",), "output") is candidate
    assert not router.last_update.current.accepted


def test_protected_mutation_cannot_bypass_replay(
    memory: tuple[MemoryStore, tuple[str, ...]],
) -> None:
    store, refs = memory
    old, bad = Version("1"), Version("2", matches=())
    root = route("root", old)
    router = Router(RouteCatalog((root,), (claim("root", refs),)))
    candidate = Apply(bad, (Given("input", 0),))
    with pytest.raises(PermissionError):
        router.upgrade((old, bad), ("input",), "output", candidate)
    with pytest.raises(PermissionError):
        router.rollback("output", root.plan)
    with pytest.raises(PermissionError):
        router.rollback("output", None, available=("input",), replay=context(store))
    with pytest.raises(TypeError):
        router.pins["output"] = candidate
    with pytest.raises(PermissionError):
        router.pins = {"output": candidate}
    assert old.calls == bad.calls == []
    assert router.route((), ("input",), "output") is root.plan


def test_unknown_signatures_do_not_fall_back_to_planning(
    memory: tuple[MemoryStore, tuple[str, ...]],
) -> None:
    _, refs = memory
    old = Version("1")
    root = route("root", old)
    router = Router(RouteCatalog((root,), (claim("root", refs),)))
    assert router.route((), ("other",), "other") is None  # Given would otherwise solve it.
    assert router.route((old,), ("wrong",), "output") is None
    assert router.route((), ("input",), "output") is root.plan


def test_protection_preserves_existing_pins_and_detaches_legacy_aliases(
    memory: tuple[MemoryStore, tuple[str, ...]],
) -> None:
    _, refs = memory
    old = Version("1")
    router = Router()
    pin = route("root", old).plan
    router.upgrade((old,), ("input",), "output", pin)
    alias = router.pins
    wrong = RouteCatalog((route("root", old),), (claim("root", refs),))
    with pytest.raises(ValueError, match="discard"):
        router.protect(wrong)
    assert router.catalog is None
    root = ProtectedRoute("root", ("input",), pin, decode, correct)
    catalog = RouteCatalog((root,), (claim("root", refs),))
    router.protect(catalog)
    alias.clear()
    assert router.route((), ("input",), "output") is pin
    with pytest.raises(PermissionError):
        router.protect(catalog)


def test_ambiguous_bindings_are_explicit_but_all_roots_remain_protected(
    memory: tuple[MemoryStore, tuple[str, ...]],
) -> None:
    store, refs = memory
    old = Version("1")
    roots = (route("first", old), route("second", old))
    catalog = RouteCatalog(roots, (claim("first", refs[:1]), claim("second", refs[1:])))
    with pytest.raises(ValueError, match="ambiguous"):
        Router(catalog)
    bindings = {(("input",), "output"): "first"}
    router = Router(catalog, bindings=bindings)
    bindings.clear()
    update = router.replace_experts(((old, Version("2", matches=(b"a",))),), context(store))
    assert update.affected == ("first", "second") and not update.accepted
    assert router.catalog is catalog
    assert router.route((), ("input",), "output") is roots[0].plan
    with pytest.raises(ValueError):
        Router(catalog, bindings={(("wrong",), "output"): "first"})


def test_replan_allows_different_internal_wiring(
    memory: tuple[MemoryStore, tuple[str, ...]],
) -> None:
    store, refs = memory
    old, new = Version("1"), Version("2")
    wrapper = Version("1", name="wrapper", contract=Contract(("output",), "output"))
    root = route("root", old)
    router = Router(RouteCatalog((root,), (claim("root", refs),)))
    candidate = Apply(wrapper, (Apply(new, (Given("input", 0),)),))
    router.upgrade((old, new, wrapper), ("input",), "output", candidate, replay=context(store))
    assert router.route((), ("input",), "output") is candidate


def test_missing_registered_evidence_blocks_expert_replacement(
    memory: tuple[MemoryStore, tuple[str, ...]],
) -> None:
    store, refs = memory
    old, new = Version("1"), Version("2")
    first = route("first", old)
    second = replace(route("second", old), available=("input", "extra"))
    catalog = RouteCatalog((first, second), (claim("first", refs[:1]),))
    # Missing evidence for the second root still blocks the whole update.
    router = Router(catalog)
    with pytest.raises(ValueError, match="no retained"):
        router.replace_experts(((old, new),), context(store))
    assert router.catalog is catalog


def test_reentrant_upgrade_cannot_publish_and_the_lock_recovers(
    memory: tuple[MemoryStore, tuple[str, ...]],
) -> None:
    store, refs = memory
    old, new = Version("1"), Version("2")
    candidate = Apply(new, (Given("input", 0),))
    entered = [False]

    def nested(record: MemoryRecord) -> tuple[Sequence[Message], bytes]:
        if not entered[0]:
            entered[0] = True
            router.upgrade((old, new), ("input",), "output", candidate, replay=context(store))
        return decode(record)

    root = replace(route("root", old), decode=nested)
    catalog = RouteCatalog((root,), (claim("root", refs),))
    router = Router(catalog)
    with pytest.raises(RuntimeError, match="mutation"):
        router.upgrade((old, new), ("input",), "output", candidate, replay=context(store))
    assert router.catalog is catalog and router.last_update is None
    router.upgrade((old, new), ("input",), "output", candidate, replay=context(store))
    assert router.route((), ("input",), "output") is candidate


def test_lookup_keeps_old_snapshot_during_replay(
    memory: tuple[MemoryStore, tuple[str, ...]],
    tmp_path: Path,
) -> None:
    _, refs = memory
    old, new = Version("1"), Version("2")
    entered, resume = Event(), Event()

    def paused(record: MemoryRecord) -> tuple[Sequence[Message], bytes]:
        entered.set()
        if not resume.wait(3):
            raise RuntimeError("test replay was not resumed")
        return decode(record)

    root = replace(route("root", old), decode=paused)
    catalog = RouteCatalog((root,), (claim("root", refs[:1]),))
    router = Router(catalog)
    candidate = Apply(new, (Given("input", 0),))

    def update() -> None:
        handle = MemoryStore(
            tmp_path / "memory.sqlite",
            capacity_bytes=10000,
            read_effect="read",
            write_effect="write",
        )
        try:
            with effect_scope(frozenset({"read"})), expert_scope(frozenset({"read"})):
                router.upgrade(
                    (old, new), ("input",), "output", candidate, replay=context(handle, cases=1)
                )
        finally:
            handle.close()

    with ThreadPoolExecutor(max_workers=1) as worker:
        pending = worker.submit(update)
        try:
            assert entered.wait(2)
            assert router.route((), ("input",), "output") is root.plan
            assert router.catalog is catalog
        finally:
            resume.set()
        pending.result(timeout=5)
    assert router.route((), ("input",), "output") is candidate


def test_replay_context_is_not_silently_ignored_by_unprotected_router(
    memory: tuple[MemoryStore, tuple[str, ...]],
) -> None:
    store, _ = memory
    old = Version("1")
    router = Router()
    plan = route("root", old).plan
    with pytest.raises(PermissionError):
        router.upgrade((old,), ("input",), "output", plan, replay=context(store))
    with pytest.raises(PermissionError):
        router.rollback("output", plan, replay=context(store))
    with pytest.raises(PermissionError):
        router.replace_experts(((old, Version("2")),), context(store))


def test_expert_replacement_publishes_all_bound_signatures(
    memory: tuple[MemoryStore, tuple[str, ...]],
) -> None:
    store, refs = memory
    old, new = Version("1"), Version("2")
    first = route("first", old)

    def extra(record: MemoryRecord) -> tuple[Sequence[Message], bytes]:
        return (
            Message("input", record.payload, "input"),
            Message("extra", None, "input"),
        ), record.payload

    second = replace(route("second", old), available=("input", "extra"), decode=extra)
    catalog = RouteCatalog((first, second), (claim("first", refs[:1]), claim("second", refs[1:])))
    router = Router(catalog)
    update = router.replace_experts(((old, new),), context(store))
    assert update.accepted and update.affected == ("first", "second")
    assert router.route((), ("input",), "output").module is new
    assert router.route((), ("input", "extra"), "output").module is new
    assert catalog.routes["first"].plan.module is old


def test_router_replay_denies_unrequested_effects(
    memory: tuple[MemoryStore, tuple[str, ...]],
) -> None:
    from nca.effects import EffectDenied, require_effect

    store, refs = memory
    old = Version("1")
    performed = []

    class Effectful(Version):
        @property
        def manifest(self) -> Manifest:
            return replace(super().manifest, effects=frozenset({"write"}))

        def invoke(self, value: bytes) -> bytes:
            require_effect("write")
            performed.append(value)
            return value

    new = Effectful("2")
    root = route("root", old)
    catalog = RouteCatalog((root,), (claim("root", refs[:1]),))
    router = Router(catalog)
    candidate = Apply(new, (Given("input", 0),))
    with pytest.raises(EffectDenied):
        router.upgrade((old, new), ("input",), "output", candidate, replay=context(store, cases=1))
    assert performed == [] and router.catalog is catalog
    allowed = replace(context(store, cases=1), effects=frozenset({"write"}))
    with effect_scope(frozenset({"read"})):
        with pytest.raises(EffectDenied):
            router.upgrade((old, new), ("input",), "output", candidate, replay=allowed)
    assert performed == []
    router.upgrade((old, new), ("input",), "output", candidate, replay=allowed)
    assert performed == [b"a"]


def test_replay_effect_limits_are_frozen(memory: tuple[MemoryStore, tuple[str, ...]]) -> None:
    store, _ = memory
    effects = {"write"}
    replay = replace(context(store), effects=effects)
    effects.clear()
    assert replay.effects == frozenset({"write"})
    with pytest.raises(TypeError):
        replace(replay, effects="write")
