"""Artifact identity survives caller mutation and serialized admission."""

import pickle
import json
import random
import shutil
import subprocess
from concurrent.futures import ThreadPoolExecutor
from dataclasses import replace
from pathlib import Path
from typing import Any

import pytest

from nca.abi import Contract, Manifest
from nca.objects import Attestation, Constructor, Object, Primitive, Store, canonical
from nca.objects import store as storage


def primitive(arguments: dict | None = None) -> Primitive:
    return Primitive(Manifest("hypothetical", "1", Contract(("source",), "result")),
                     "hypothetical:Expert", arguments or {})


def test_admitted_bytes_survive_original_and_returned_view_mutation(tmp_path: Path) -> None:
    arguments = {"config": {"values": [1]}}
    obj = primitive(arguments)
    encoded = canonical(obj.data())
    store = Store()
    reference = store.put(obj)
    arguments["config"]["values"].append(2)
    assert obj.ref != reference
    view = store.get(reference)
    assert canonical(view.data()) == encoded and view.ref == reference
    view.arguments["config"]["values"].append(3)
    view.data()["arguments"]["config"]["values"].append(4)
    assert canonical(store.get(reference).data()) == encoded
    store.save(tmp_path)
    assert canonical(Store.open(tmp_path).get(reference).data()) == encoded


def test_attestation_index_returns_independent_views() -> None:
    store = Store()
    subject = store.put(primitive())
    claim = {"observations": [{"value": 1}]}
    note = Attestation(subject, "hypothetical", claim, "issuer")
    encoded = canonical(note.data())
    reference = store.put(note)
    claim["observations"][0]["value"] = 2
    store.attestations(subject)[0].claim["observations"][0]["value"] = 3
    store.get(reference).claim["observations"].append({"value": 4})
    assert len(store.attestations(subject)) == 1
    assert canonical(store.attestations(subject)[0].data()) == encoded


def test_duplicate_admission_and_index_publication_are_serialized() -> None:
    store = Store()
    subject = store.put(primitive())
    note = Attestation(subject, "hypothetical", {"values": [1]}, "issuer")
    with ThreadPoolExecutor(max_workers=8) as pool:
        references = list(pool.map(lambda _: store.put(note), range(64)))
    assert references == [note.ref] * 64
    assert len(store) == 2 and len(store.attestations(subject)) == 1


def test_colliding_admission_cannot_replace_retained_bytes(
        monkeypatch: pytest.MonkeyPatch) -> None:
    class CollidingHash:
        def hexdigest(self) -> str:
            return "0" * 64

    monkeypatch.setattr(storage.hashlib, "sha256", lambda _: CollidingHash())
    store = Store()
    first, second = primitive({"value": 1}), primitive({"value": 2})
    reference = store.put(first)
    with pytest.raises(ValueError, match="collision"):
        store.put(second)
    assert store.get(reference).data() == first.data()
    assert len(store) == 1


def test_non_round_trip_metadata_is_refused_before_admission() -> None:
    class ExtraField(Constructor):
        def data(self) -> dict:
            return {**super().data(), "extra": "not part of the object schema"}

    store = Store()
    with pytest.raises(ValueError, match="round-trip"):
        store.put(ExtraField("hypothetical", "1", 0, "opaque"))
    assert len(store) == 0


def test_save_refuses_existing_conflicting_contents(tmp_path: Path) -> None:
    store = Store()
    reference = store.put(primitive())
    path = tmp_path / f"{reference.removeprefix('sha256:')}.json"
    path.write_bytes(b"corrupt")
    with pytest.raises(ValueError, match="conflicts"):
        store.save(tmp_path)
    assert path.read_bytes() == b"corrupt"


def test_pickle_and_legacy_restore_rebuild_validated_snapshots() -> None:
    store = Store()
    reference = store.put(primitive({"values": [1]}))
    reopened = pickle.loads(pickle.dumps(store))
    assert reopened.get(reference).ref == reference
    legacy = Store.__new__(Store)
    legacy.__setstate__({"_objects": {reference: store.get(reference)}, "_about": {}})
    legacy.get(reference).arguments["values"].append(2)
    assert legacy.get(reference).ref == reference
    with pytest.raises(ValueError, match="fresh instance"):
        legacy.__setstate__({"_objects": {}})
    assert legacy.get(reference).ref == reference
    with pytest.raises(ValueError, match="digest"):
        Store.__new__(Store).__setstate__({"_objects": {reference: b"corrupt"}})


def replay_fixture(seed: int) -> tuple[dict[str, Any], list[dict[str, Any]]]:
    """Generate valid canonical records; schema-invalid cases are tested above."""
    rng = random.Random(seed)
    pool = [primitive({"config": {"values": [index], "text": "éα"}}) for index in range(8)]
    store = Store()
    probes, known = {"missing"}, set()
    hashes, events, rows = {}, [], []
    for step in range(64):
        action = rng.randrange(4)
        status, value = "outside", None
        if action < 2:
            obj = rng.choice(pool)
            if step % 11 == 0:
                obj = replace(obj, dependencies=("unavailable",))
            encoded, reference = canonical(obj.data()).decode(), obj.ref
            hashes[encoded] = reference
            probes.add(reference)
            events.append(["put", encoded, not obj.dependencies])
            try:
                result = store.put(obj)
                status = "duplicate" if result in known else "inserted"
                known.add(result)
            except KeyError:
                status = "rejected"
            except ValueError as error:
                assert "collision" in str(error)
                status = "collision"
        elif action == 2:
            reference = rng.choice(sorted(probes))
            events.append(["get", reference])
            try:
                view = store.get(reference)
                assert view.ref == reference
                value, status = canonical(view.data()).decode(), "found"
                # A caller may modify and subsequently resubmit a decoded view.
                view.arguments["config"]["values"].append(step)
                pool.append(view)
            except KeyError:
                status = "missing"
        else:
            events.append(["outside"])
            rng.choice(pool).arguments["config"]["values"].append(step)
        state = {}
        for reference in sorted(known):
            view = store.get(reference)
            assert view.ref == reference
            state[reference] = canonical(view.data()).decode()
        rows.append({"status": status, "value": value, "state": state})
    keys = sorted(probes)
    expected = [{**row, "state": [row["state"].get(key) for key in keys]} for row in rows]
    return {"hashes": list(hashes.items()), "probes": keys, "events": events}, expected


def test_run_retains_and_run_read_identity_match_executable_lean(
        monkeypatch: pytest.MonkeyPatch) -> None:
    """NCA.Artifacts.run_retains, admitted_read_stable and run_read_identity.

    Canonical object schemas are checked by Python; Lean instantiates its
    universally quantified codec boundary with their UTF-8 encodings. Digest
    tables include real SHA-256 and deliberately colliding digest functions.
    """
    lake = shutil.which("lake")
    if lake is None:
        pytest.skip("Lean differential checks require the development toolchain")
    fixtures, expected = [], []
    for collision in (False, True):
        with monkeypatch.context() as scoped:
            if collision:
                class CollidingHash:
                    def hexdigest(self) -> str:
                        return "0" * 64

                scoped.setattr(storage.hashlib, "sha256", lambda _: CollidingHash())
            for seed in range(4):
                fixture, result = replay_fixture(seed)
                fixtures.append(fixture)
                expected.append(result)
    lean = Path(__file__).resolve().parents[1] / "lean"
    subprocess.run([lake, "build", "NCA.Execution.Artifacts"], cwd=lean,
                   capture_output=True, text=True, check=True, timeout=120)
    result = subprocess.run(
        [lake, "env", "lean", "--run", "NCA/Execution/ArtifactReplay.lean"],
        cwd=lean, input=json.dumps(fixtures), capture_output=True, text=True,
        check=True, timeout=120,
    )
    actual = json.loads(result.stdout)
    assert len(actual) == len(expected)
    for fixture, (observed, wanted) in enumerate(zip(actual, expected, strict=True)):
        assert len(observed) == len(wanted)
        for step, (row, target) in enumerate(zip(observed, wanted, strict=True)):
            assert row == target, f"artifact replay fixture {fixture}, step {step}"


class TraversalStore(Store):
    def __init__(self) -> None:
        super().__init__()
        self.reads = 0

    def get(self, ref: str) -> Object:
        self.reads += 1
        return super().get(ref)


def test_iterative_traversal_matches_ordered_dag_reference() -> None:
    from nca.objects import Composite

    # All ordered five-node DAGs, with duplicate edges and mixed primitive /
    # composite nodes. Primitive dependencies belong to walk, never flatten.
    edges = [(a, b) for a in range(5) for b in range(a)]
    for mask in range(1 << len(edges)):
        store = TraversalStore()
        refs = []
        children: dict[str, tuple[str, ...]] = {}
        transparent: dict[str, bool] = {}
        for a in range(5):
            members = tuple(refs[b] for bit, (parent, b) in enumerate(edges)
                            if parent == a and mask & (1 << bit))
            members = (*reversed(members), *members[:1])
            is_composite = a > 0 and a % 2 == 0
            obj = (Composite(f"node-{a}", "1", members) if is_composite else
                   replace(primitive({"node": a}), dependencies=members))
            ref = store.put(obj)
            refs.append(ref)
            children[ref], transparent[ref] = members, is_composite

        reached: set[str] = set()

        def reference(node: str, flatten: bool, seen: set[str], output: list[str]) -> None:
            reached.add(node)
            if node in seen:
                return
            if not flatten or not transparent[node]:
                seen.add(node)
            if not flatten or transparent[node]:
                for child in children[node]:
                    reference(child, flatten, seen, output)
            if not flatten or not transparent[node]:
                output.append(node)

        for flatten in (False, True):
            expected: list[str] = []
            reached.clear()
            reference(refs[-1], flatten, set(), expected)
            store.reads = 0
            actual = store.flatten(refs[-1]) if flatten else list(store.walk(refs[-1]))
            assert actual == expected
            assert store.reads == len(reached)
            if not flatten:
                emitted: set[str] = set()
                for parent in actual:
                    assert set(children[parent]) <= emitted  # dependency_append_order
                    assert parent not in emitted
                    emitted.add(parent)


def test_deep_and_shared_composites_do_not_use_the_python_call_stack() -> None:
    import sys
    from nca.objects import Composite

    store = TraversalStore()
    first = store.put(primitive())
    reference = first
    depth = sys.getrecursionlimit() + 50
    for i in range(depth):
        reference = store.put(Composite(f"level-{i}", "1", (reference, reference)))
    store.reads = 0
    order = list(store.walk(reference))
    assert len(order) == depth + 1 and order[0] == first and order[-1] == reference
    assert store.reads == depth + 1
    store.reads = 0
    assert store.flatten(reference) == [first]
    assert store.reads == depth + 1


@pytest.mark.parametrize("exported", [False, True])
def test_deep_installation_is_lazy_and_does_not_recurse(exported: bool) -> None:
    import sys
    from nca.loader import ExpertStore, LazyExpert
    from nca.objects import Composite
    from nca.packages import Export, install

    store = Store()
    leaf = primitive()
    ref = store.put(leaf)
    depth = sys.getrecursionlimit() + 50
    for level in range(depth):
        ref = store.put(Composite(f"scope-{level}", "1", (ref,),
                                  exports=(leaf.manifest.contract,) if exported else None))
    residents = ExpertStore(budget=0)
    scope = install(store, ref, experts=residents)
    assert len(scope) == 1 and scope[0].manifest.contract == leaf.manifest.contract
    expert = scope[0]
    count = 0
    while isinstance(expert, Export):
        assert len(expert.members) == 1
        expert = expert.members[0]
        count += 1
    assert count == (depth if exported else 0)
    assert isinstance(expert, LazyExpert) and residents.stats.loads == 0
    assert residents.resident_bytes == 0


def test_scope_continuations_preserve_occurrences_sharing_and_empty_results() -> None:
    from nca.loader import ExpertStore
    from nca.objects import Composite
    from nca.packages import Export, install_scopes

    store = Store()
    leaf = primitive()
    ref = store.put(leaf)
    empty = store.put(Composite("empty", "1", ()))
    exported = store.put(Composite("exported", "1", (empty, ref),
                                   exports=(leaf.manifest.contract,)))
    root = store.put(Composite("root", "1", (empty, exported, exported, ref, ref)))
    residents = ExpertStore()
    roots = install_scopes(store, (root, empty, exported, ref), experts=residents)
    first, second, direct = roots[0]
    assert isinstance(first, Export) and isinstance(second, Export)
    assert first is not second and first is not roots[2][0]
    assert first.identity == second.identity == roots[2][0].identity
    assert first.members[0] is second.members[0] is roots[2][0].members[0] is direct is roots[3][0]
    assert roots[1] == [] and residents.stats.loads == 0
    dependent = store.put(replace(leaf, dependencies=(empty, empty)))
    scoped = install_scopes(store, (dependent, empty), experts=residents)
    assert scoped[1] == [] and scoped[0][0].dependencies == ()


def test_continuation_installation_matches_recursive_scope_graphs() -> None:
    import runpy
    from nca.abi import Module
    from nca.objects import Composite
    from nca.packages import Export, install_scopes

    reference = runpy.run_path(str(Path(__file__).parents[1] / "benchmarks" / "artifact_store.py"))[
        "recursive_install_scopes"]

    def signature(scopes: tuple[list[Module], ...]) -> tuple[Any, ...]:
        ids: dict[int, int] = {}
        pending: list[Module] = []

        def intern(module: Module) -> int:
            if id(module) not in ids:
                ids[id(module)] = len(pending)
                pending.append(module)
            return ids[id(module)]

        roots = tuple(tuple(intern(module) for module in scope) for scope in scopes)
        nodes = []
        cursor = 0
        while cursor < len(pending):
            module = pending[cursor]
            children = module.members if isinstance(module, Export) else getattr(module, "dependencies", ())
            nodes.append((type(module), module.identity, module.manifest,
                          getattr(module, "cache_identity", None),
                          tuple(intern(child) for child in children)))
            cursor += 1
        return roots, tuple(nodes)

    edges = [(a, b) for a in range(2, 5) for b in range(a)]
    for mask in range(1 << len(edges)):
        store = Store()
        refs = [store.put(primitive({"node": a})) for a in range(2)]
        for a in range(2, 5):
            members = (refs[0], *(refs[b] for bit, (parent, b) in reversed(tuple(enumerate(edges)))
                                  if parent == a and mask & (1 << bit)))
            obj = (replace(primitive({"node": a}), dependencies=members) if a == 3 else
                   Composite(f"scope-{a}", "1", members,
                             exports=(primitive().manifest.contract,) if a == 2 else None))
            refs.append(store.put(obj))
        roots = (refs[-1], refs[2], refs[0], refs[-1])
        assert signature(install_scopes(store, roots)) == signature(reference(store, roots))
