"""Constructors as content-addressed objects, and refinement by upcasts (§29)."""

from pathlib import Path
from typing import Any

import pytest

from nca.abi import Contract, Manifest, Message, parse_type
from nca.objects import Composite, Constructor, Primitive, Store
from nca.packages import Upcast, install
from nca.planner import Apply, plan_stable
from nca.runtime import execute
from nca.workspace import Workspace

ENTRY = f"{__name__}:make"
TEXT = "text.v1"

DISTRIBUTION = Constructor("distribution", "1.0.0", 0, "A tuple of class probabilities.")
DIGITS = Constructor("digit-distribution", "1.0.0", 0,
                     "Probabilities of the digits 0-9, as a 10-tuple.", (DISTRIBUTION.ref,))
CONFIDENT = Constructor("confident-digits", "1.0.0", 0,
                        "Digit probabilities whose largest entry exceeds 0.9.", (DIGITS.ref,))
BAG = Constructor("bag", "1.0.0", 1, "A finite multiset, as a list.")
SORTED_BAG = Constructor("sorted-bag", "1.0.0", 1, "A multiset as a sorted list.", (BAG.ref,))

BEHAVIOR = {
    "read": lambda text: tuple(float(i == len(text) % 10) for i in range(10)),
    "top": lambda distribution: max(range(len(distribution)), key=distribution.__getitem__),
    "sort": lambda text: sorted(text),
    "count": len,
}


class Expert:
    def __init__(self, name: str, inputs: list[str], output: str) -> None:
        self.name = name
        self.manifest = Manifest(name, "1.0.0", Contract(tuple(inputs), output),
                                 effects=frozenset())

    def invoke(self, *values: Any) -> Any:
        return BEHAVIOR[self.name](*values)


def make(name: str, inputs: list[str], output: str) -> Expert:
    return Expert(name, inputs, output)


def primitive(name: str, inputs: list[str], output: str) -> Primitive:
    arguments = {"name": name, "inputs": inputs, "output": output}
    return Primitive(make(**arguments).manifest, ENTRY, arguments)


def put_types(store: Store) -> None:
    for constructor in (DISTRIBUTION, DIGITS, CONFIDENT, BAG, SORTED_BAG):
        store.put(constructor)


def test_constructors_name_types_by_reference() -> None:
    assert DIGITS.type() == DIGITS.ref and DIGITS.ref.startswith("sha256:")
    assert parse_type(SORTED_BAG.type(TEXT)).name == SORTED_BAG.ref
    assert SORTED_BAG.type(DIGITS.type()) == f"{SORTED_BAG.ref}[{DIGITS.ref}]"
    with pytest.raises(ValueError, match="takes 1"):
        BAG.type()
    same_label = Constructor("distribution", "1.0.0", 0, "Log-probabilities.")
    assert same_label.ref != DISTRIBUTION.ref


def test_store_admits_only_resolved_constructors(tmp_path: Path) -> None:
    store = Store()
    with pytest.raises(KeyError):
        store.put(DIGITS)
    with pytest.raises(KeyError):
        store.put(primitive("read", [TEXT], DIGITS.type()))
    store.put(DISTRIBUTION)
    store.put(BAG)
    with pytest.raises(ValueError, match="arity"):
        store.put(Constructor("odd", "1", 1, "", (DISTRIBUTION.ref,)))
    with pytest.raises(ValueError, match="arity"):
        store.put(primitive("count", [BAG.ref], TEXT))
    with pytest.raises(ValueError, match="arity"):
        store.put(primitive("read", [TEXT], f"{DISTRIBUTION.ref}[{TEXT}]"))
    put_types(store)
    reader = store.put(primitive("read", [TEXT], DIGITS.type()))
    package = store.put(Composite("p", "1", (DIGITS.ref, reader),
                                  exports=(Contract((TEXT,), DIGITS.type()),),
                                  effects=frozenset()))
    store.save(tmp_path)
    reopened = Store.open(tmp_path)
    assert reopened.get(package) == store.get(package)
    assert reopened.get(CONFIDENT.ref) == CONFIDENT


def world(store: Store, *members: str) -> list:
    return install(store, store.put(Composite("world", "1", members)))


def test_upcasts_connect_independent_authors() -> None:
    store = Store()
    put_types(store)
    reader = store.put(primitive("read", [TEXT], DIGITS.type()))
    top = store.put(primitive("top", [DISTRIBUTION.type()], "int.v1"))
    assert plan_stable(world(store, reader, top), (TEXT,), "int.v1") is None
    modules = world(store, reader, top, DIGITS.ref)
    route = plan_stable(modules, (TEXT,), "int.v1")
    assert isinstance(route, Apply) and isinstance(route.args[0].module, Upcast)
    assert execute(route, [Message(TEXT, "abc", "input")], Workspace(), 10).payload == 3


def test_refinement_chains_and_parametric_constructors() -> None:
    store = Store()
    put_types(store)
    confident = store.put(primitive("read", [TEXT], CONFIDENT.type()))
    top = store.put(primitive("top", [DISTRIBUTION.type()], "int.v1"))
    modules = world(store, confident, top, CONFIDENT.ref, DIGITS.ref)
    route = plan_stable(modules, (TEXT,), "int.v1")
    assert execute(route, [Message(TEXT, "abcd", "input")], Workspace(), 10).payload == 4

    sort = store.put(primitive("sort", [TEXT], SORTED_BAG.type(TEXT)))
    count = store.put(primitive("count", [BAG.type(TEXT)], "int.v1"))
    route = plan_stable(world(store, sort, count, SORTED_BAG.ref), (TEXT,), "int.v1")
    assert execute(route, [Message(TEXT, "cab", "input")], Workspace(), 10).payload == 3
    upcast = route.args[0].module
    assert upcast.manifest.contract == Contract((f"{SORTED_BAG.ref}[?a0]",), f"{BAG.ref}[?a0]")


def test_upcasts_installed_later_keep_existing_routes() -> None:
    store = Store()
    put_types(store)
    reader = store.put(primitive("read", [TEXT], DIGITS.type()))
    direct = store.put(primitive("top", [DIGITS.type()], "int.v1"))
    general = store.put(primitive("top", [DISTRIBUTION.type()], "int.v1"))
    before = plan_stable(world(store, reader, direct, general), (TEXT,), "int.v1")
    after = plan_stable(world(store, reader, direct, general, DIGITS.ref), (TEXT,), "int.v1")
    assert before is not None and after is not None
    assert after.module.manifest == before.module.manifest
    assert after.args[0].module.manifest == before.args[0].module.manifest
