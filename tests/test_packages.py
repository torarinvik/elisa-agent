"""Content-addressed experts and composites planned in their own scope (§28)."""

from pathlib import Path
from typing import Any

import pytest
import torch

from nca.abi import NOTHING, Calls, Contract, Manifest, Message, seq_type
from nca.cache import ResultCache
from nca.ladder import CALIBRATION, Rung, attested, calibration
from nca.objects import Attestation, Composite, Names, Primitive, Store, canonical, digest
from nca.packages import Export, install
from nca.planner import Apply, plan_stable
from nca.runtime import execute
from nca.workspace import Workspace

TEXT = "text.v1"
WORD = "word.v1"
INT = "int.v1"
ENTRY = f"{__name__}:make"


class Expert:
    def __init__(self, name: str, inputs: list[str], output: str, effects: list[str] | None,
                 cost: float = 1.0) -> None:
        self.name = name
        self.manifest = Manifest(name, "1.0.0", Contract(tuple(inputs), output), cost,
                                 effects=None if effects is None else frozenset(effects))

    def invoke(self, *values: Any) -> Any:
        return BEHAVIOR[self.name](*values)


BEHAVIOR = {
    "split": lambda text: text.split(),
    "length": len,
    "sum": sum,
    "count-letters": lambda word: sum(c.isalpha() for c in word),
    "over": lambda _: (0.01, 0.99),
}


def make(name: str, inputs: list[str], output: str, effects: list[str] | None = (),
         cost: float = 1.0) -> Expert:
    return Expert(name, inputs, output, effects if effects is None else list(effects), cost)


def primitive(name: str, inputs: list[str], output: str, cost: float = 1.0,
              effects: list[str] | None = ()) -> Primitive:
    arguments = {"name": name, "inputs": inputs, "output": output, "cost": cost,
                 "effects": None if effects is None else list(effects)}
    return Primitive(make(**arguments).manifest, ENTRY, arguments)


def counting_package(store: Store, exports: bool = True) -> str:
    """Splits text into words, reads each word with a required slot and sums."""
    members = (store.put(primitive("split", [TEXT], seq_type(WORD))),
               store.put(primitive("sum", [seq_type(INT)], INT)))
    return store.put(Composite("counting", "1.0.0", members, requires=(((WORD,), INT),),
                               exports=(Contract((TEXT,), INT),) if exports else None,
                               effects=frozenset()))


def test_references_are_digests_of_canonical_contents() -> None:
    assert canonical({"b": [1, (2,)], "a": "é"}) == '{"a":"é","b":[1,[2]]}'.encode()
    assert digest({"a": 1, "b": 2}) == digest({"b": 2, "a": 1})
    with pytest.raises(ValueError):
        canonical(float("nan"))
    one, other = primitive("sum", [seq_type(INT)], INT), primitive("sum", [seq_type(INT)], INT)
    assert one.ref == other.ref and one.ref.startswith("sha256:") and len(one.ref) == 71
    assert primitive("sum", [seq_type(INT)], INT, cost=2.0).ref != one.ref


def test_store_admits_only_well_formed_dags_and_round_trips(tmp_path: Path) -> None:
    store = Store()
    with pytest.raises(KeyError):
        store.put(Composite("orphan", "1", ("sha256:" + "0" * 64,)))
    impure = store.put(primitive("split", [TEXT], seq_type(WORD), effects=["io"]))
    with pytest.raises(ValueError):
        store.put(Composite("pure", "1", (impure,), effects=frozenset()))
    package = counting_package(store)
    note = store.put(Attestation(package, "audit", {"error": 0.01}, "tests"))
    with pytest.raises(KeyError):
        store.put(Attestation("sha256:" + "1" * 64, "audit", {}))
    store.save(tmp_path)
    reopened = Store.open(tmp_path)
    assert len(reopened) == len(store)
    assert reopened.get(package) == store.get(package)
    assert [a.claim for a in reopened.attestations(package, "audit")] == [{"error": 0.01}]
    assert reopened.get(note).ref == note
    (tmp_path / f"{package.removeprefix('sha256:')}.json").write_text("{}")
    with pytest.raises(ValueError):
        Store.open(tmp_path)


def test_names_point_at_references() -> None:
    names = Names()
    assert names.bind("counting", "sha256:a") is None
    assert names.bind("counting", "sha256:b") == "sha256:a"
    assert names.resolve("counting") == "sha256:b"


def test_flatten_keeps_member_order_and_shares_members() -> None:
    store = Store()
    split = store.put(primitive("split", [TEXT], seq_type(WORD)))
    length = store.put(primitive("length", [seq_type(WORD)], INT))
    inner = store.put(Composite("inner", "1", (split, length)))
    outer = store.put(Composite("outer", "1", (length, inner, split)))
    assert store.flatten(outer) == [length, split]
    assert list(store.walk(outer)) == [length, split, inner, outer]


def test_transparent_composites_install_their_members_once() -> None:
    store = Store()
    split = store.put(primitive("split", [TEXT], seq_type(WORD)))
    length = store.put(primitive("length", [seq_type(WORD)], INT))
    both = store.put(Composite("both", "1", (split, length, split)))
    modules = install(store, both)
    assert [m.manifest.module_id for m in modules] == ["split", "length"]
    assert [m.identity for m in modules] == [split, length]
    route = plan_stable(modules, (TEXT,), INT)
    assert execute(route, {TEXT: Message(TEXT, "a bc d", "input")}, Workspace(), 10).payload == 3


def test_exports_are_higher_order_experts_whose_requirements_the_planner_fills() -> None:
    store = Store()
    package = counting_package(store)
    reader = store.put(primitive("count-letters", [WORD], INT))
    world = store.put(Composite("world", "1", (reader, package)))
    modules = install(store, world)
    export = modules[-1]
    assert isinstance(export, Export)
    assert export.manifest.contract == Contract((TEXT,), INT, (((WORD,), INT),))
    # The requirement is read once per word: affine calls, declared exactly.
    assert export.manifest.calls == (Calls(0.0, 1.0),)
    assert export.manifest.effects == frozenset()
    route = plan_stable(modules, (TEXT,), INT)
    assert isinstance(route, Apply) and route.module is export
    result = execute(route, {TEXT: Message(TEXT, "ab, c!", "input")}, Workspace(), 10)
    assert result.payload == 3


def test_exports_hide_members_and_their_types() -> None:
    store = Store()
    sealed = install(store, counting_package(store))
    assert [m.manifest.contract.output for m in sealed] == [INT]
    assert plan_stable(sealed, (TEXT,), seq_type(WORD)) is None
    transparent = install(store, counting_package(store, exports=False))
    assert plan_stable(transparent, (TEXT,), seq_type(WORD)) is not None


def test_unimplementable_exports_are_rejected() -> None:
    store = Store()
    split = store.put(primitive("split", [TEXT], seq_type(WORD)))
    package = store.put(Composite("broken", "1", (split,), exports=(Contract((TEXT,), INT),)))
    with pytest.raises(ValueError, match="cannot implement"):
        install(store, package)


def test_composites_nest() -> None:
    store = Store()
    package = counting_package(store)
    reader = store.put(primitive("count-letters", [WORD], INT))
    # A sealed composite that satisfies the inner requirement itself.
    sealed = store.put(Composite("sealed", "1", (reader, package),
                                 exports=(Contract((TEXT,), INT),), effects=frozenset()))
    (export,) = install(store, sealed)
    assert export.manifest.contract.slots == ()
    route = plan_stable([export], (TEXT,), INT)
    assert execute(route, {TEXT: Message(TEXT, "abc de", "input")}, Workspace(), 10).payload == 5


class FirstOnly(Expert):
    """Reads only its first input."""

    def demand(self, index: int, demand: Any) -> Any:
        return demand if index == 0 else NOTHING


def first_only() -> FirstOnly:
    return FirstOnly("first", [TEXT, INT], WORD, [])


def test_installed_primitives_keep_their_implementations_demand() -> None:
    BEHAVIOR["first"] = lambda text, _: text
    store = Store()
    first = store.put(Primitive(first_only().manifest, f"{__name__}:first_only"))
    length = store.put(primitive("length", [TEXT], INT))
    modules = install(store, store.put(Composite("both", "1", (first, length))))
    route = plan_stable(modules, (TEXT,), WORD)
    assert isinstance(route, Apply) and route.module.manifest.module_id == "first"
    workspace = Workspace()
    assert execute(route, [Message(TEXT, "ab", "input")], workspace, 10).payload == "ab"
    assert not any(m.producer.startswith("length") for m in workspace.messages())


def test_declared_manifest_must_match_the_loaded_one() -> None:
    wrong = Primitive(make("sum", [seq_type(INT)], INT).manifest, ENTRY,
                      {"name": "sum", "inputs": [seq_type(INT)], "output": INT, "cost": 5.0})
    with pytest.raises(ValueError, match="not the declared"):
        wrong.load()


def test_sealed_exports_are_cached_as_one_pure_expert() -> None:
    store = Store()
    reader = store.put(primitive("count-letters", [WORD], INT))
    sealed = store.put(Composite("sealed", "1", (reader, counting_package(store)),
                                 exports=(Contract((TEXT,), INT),), effects=frozenset()))
    (export,) = install(store, sealed)
    route = plan_stable([export], (TEXT,), INT)
    cache = ResultCache()
    for _ in range(2):
        assert execute(route, [Message(TEXT, "abc de", "input")], Workspace(), 10,
                       cache=cache).payload == 5
    assert cache.stats.hits == 1 and len(cache) == 1


def test_calibration_is_an_attestation_beside_the_expert() -> None:
    store = Store()
    ref = store.put(Primitive(make("over", ["x"], "dist").manifest, ENTRY,
                              {"name": "over", "inputs": ["x"], "output": "dist"}))
    (expert,) = install(store, ref)
    rung = Rung(expert)
    rung.calibrate([0] * 10, torch.tensor([1] * 7 + [0] * 3))
    claim = calibration(rung, ref, decisions=[(0, 1), ((0,), (1,))], issuer="tests")
    note = store.put(claim)
    (stored,) = store.attestations(ref, CALIBRATION)
    assert stored.ref == note
    read = attested(expert, stored)
    assert read.temperatures == rung.temperatures and len(read.temperatures) == 3
    assert read.held_out is None
    other = store.put(primitive("sum", [seq_type(INT)], INT))
    (wrong,) = install(store, other)
    with pytest.raises(ValueError, match="another expert"):
        attested(wrong, stored)
