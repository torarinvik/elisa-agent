"""Persistence of learned conditional models through public object interfaces."""

from pathlib import Path

import pytest

from nca.abi import Contract, Manifest
from nca.discovery import train_tree
from nca.loader import ExpertStore
from nca.objects import Primitive, Store
from nca.packages import install
from nca.tree_objects import load_tree, tree_object


class Projection:
    def __init__(self, index: int) -> None:
        self.index = index
        self.manifest = Manifest(f"projection-{index}", "1", Contract(("input",), f"part{index}"),
                                 effects=frozenset())

    def invoke(self, value: tuple[int, ...]) -> int:
        return value[self.index]


def fixture() -> tuple[Store, list[str]]:
    store = Store()
    refs = [store.put(Primitive(Projection(i).manifest, f"{__name__}:Projection", {"index": i}))
            for i in range(2)]
    return store, refs


def test_tree_round_trip_and_unseen_fallback(tmp_path: Path) -> None:
    store, refs = fixture()
    features = [install(store, ref)[0] for ref in refs]
    incumbent = Projection(0)
    incumbent.manifest = Manifest("baseline", "1", Contract(("input",), "target"))
    rows = [((i % 2, (i // 2) % 2),) for i in range(64)]
    labels = ["same" if x[0][0] == x[0][1] else "different" for x in rows]
    tree = train_tree(incumbent, features, rows, labels, max_nodes=7, overhead_cost=1)
    bindings = [(ref, 0) for ref in refs]
    obj = tree_object(store, tree, bindings, size=64)
    assert obj.ref == tree_object(store, tree, bindings, size=64).ref
    reference = store.put(obj)
    store.save(tmp_path)
    resident = ExpertStore()
    restored = install(Store.open(tmp_path), reference, experts=resident)[0]
    assert resident.stats.loads == 0
    for row in [*rows, ((9, 9),), ((0, 9),)]:
        assert restored.invoke(*row) == tree.invoke(*row)
    assert resident.stats.loads == 3
    with pytest.raises(ValueError, match="trained content"):
        tree_object(store, tree, list(reversed(bindings)), size=64)
    tree.root.fallback = "changed"
    assert tree_object(store, tree, bindings, size=64).manifest.ref != obj.manifest.ref


def test_loader_rejects_backward_child_edges() -> None:
    with pytest.raises(ValueError, match="point forward"):
        load_tree({}, [{"chosen": "x", "counts": [["x", 1]], "feature": None,
                        "children": [[0, 0]]}], [])
