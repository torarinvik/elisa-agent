"""Content-addressed executable dependencies and their shared lazy lifecycle."""

from dataclasses import replace
from pathlib import Path
from typing import Any

import pytest

from nca.abi import Contract, Manifest, Module
from nca.loader import ExpertStore
from nca.objects import Attestation, Composite, Primitive, Store, canonical, digest
from nca.packages import install


class Linked:
    def __init__(self, name: str, table: list[list[Any]] | None = None,
                 dependencies: tuple[tuple[Module, ...], ...] = ()) -> None:
        self.manifest = Manifest(name, "1", Contract(("key",), "value"), effects=frozenset())
        self.table = dict(table or [])
        self.dependencies = dependencies

    def invoke(self, key: str) -> Any:
        return self.dependencies[0][0].invoke(key) if self.dependencies else self.table[key]


def artifact(name: str, table: list[list[Any]] | None = None,
             dependencies: tuple[str, ...] = ()) -> Primitive:
    return Primitive(Linked(name, table).manifest, f"{__name__}:Linked",
                     {"name": name, "table": table}, dependencies=dependencies)


def test_dependencies_round_trip_share_wrappers_and_load_once(tmp_path: Path) -> None:
    store = Store()
    child = artifact("learned-table", [["a", 1], ["b", 2]])
    child_ref = store.put(child)
    parents = [store.put(artifact(name, dependencies=(child_ref,))) for name in ("left", "right")]
    package = store.put(Composite("both", "1", tuple(parents), effects=frozenset()))
    assert list(store.walk(package)) == [child_ref, *parents, package]
    assert store.flatten(package) == parents  # Dependencies are private executable scopes.
    store.save(tmp_path)
    reopened = Store.open(tmp_path)
    resident = ExpertStore()
    modules = install(reopened, package, experts=resident)
    assert resident.stats.loads == 0
    assert [m.invoke("a") for m in modules] == [1, 1]
    assert [m.invoke("b") for m in modules] == [2, 2]
    assert resident.stats.loads == 3
    left = resident.resident["left@1"][0]
    right = resident.resident["right@1"][0]
    assert left.dependencies[0][0] is right.dependencies[0][0]
    assert left.dependencies[0][0].identity == child_ref
    changed = store.put(artifact("learned-table", [["a", 2], ["b", 1]]))
    assert artifact("left", dependencies=(changed,)).ref != parents[0]
    assert "dependencies" not in child.data()
    assert child.ref == digest({"kind": "primitive", "manifest": child.data()["manifest"],
                                "entry": child.entry, "arguments": dict(child.arguments),
                                "weights": None, "size": 0})


def test_dependency_admission_checks_presence_effects_and_reserved_arguments() -> None:
    store = Store()
    with pytest.raises(KeyError):
        store.put(artifact("missing", dependencies=("sha256:absent",)))
    child = artifact("child", [["a", 1]])
    reference = store.put(child)
    impure = store.put(replace(child, manifest=replace(child.manifest, effects=frozenset({"io"}))))
    with pytest.raises(ValueError, match="effects"):
        store.put(artifact("pure", dependencies=(impure,)))
    note = store.put(Attestation(reference, "test", {}))
    with pytest.raises(ValueError, match="attestation"):
        store.put(artifact("not-executable", dependencies=(note,)))
    with pytest.raises(ValueError, match="reserved"):
        store.put(replace(artifact("bad", dependencies=(reference,)), arguments={"dependencies": []}))
    with pytest.raises(ValueError, match="resolver"):
        artifact("unresolved", dependencies=(reference,)).load()


def test_dependencies_preserve_scope_order_and_decoded_object_identity(tmp_path: Path) -> None:
    store = Store()
    one = store.put(artifact("one", [["a", 1]]))
    two = store.put(artifact("two", [["a", 2]]))
    scope = store.put(Composite("scope", "1", (two, one), effects=frozenset()))
    parent = store.put(artifact("parent", dependencies=(scope, one)))
    resident = ExpertStore()
    module = install(store, parent, experts=resident)[0]
    assert module.invoke("a") == 2
    linked = resident.resident["parent@1"][0]
    assert [m.identity for m in linked.dependencies[0]] == [two, one]
    assert linked.dependencies[0][1] is linked.dependencies[1][0]
    # A digest-valid file must also decode to the object identified by that digest.
    data = artifact("noncanonical").data()
    data["dependencies"] = []  # The canonical representation omits an empty list.
    (tmp_path / f"{digest(data).removeprefix('sha256:')}.json").write_bytes(canonical(data))
    with pytest.raises(ValueError, match="decoded object's digest"):
        Store.open(tmp_path)


def test_preparation_accounts_for_dependency_bytes_before_loading() -> None:
    from nca.planner import plan_stable

    store = Store()
    child = store.put(replace(artifact("child", [["a", 1]]), size=2))
    parent = store.put(replace(artifact("parent", dependencies=(child,)), size=1))
    for budget in (2, 3):
        resident = ExpertStore(budget)
        module = install(store, parent, experts=resident)[0]
        route = plan_stable([module], ("key",), "value")
        assert route is not None
        if budget == 2:
            with pytest.raises(MemoryError, match="3 B"):
                resident.prepare(route)
            assert resident.stats.loads == 0 and resident.pinned == frozenset()
        else:
            resident.prepare(route)
            assert resident.stats.loads == 2 and resident.resident_bytes == 3
            assert resident.pinned == frozenset({"parent@1", "child@1"})
            assert module.invoke("a") == 1
