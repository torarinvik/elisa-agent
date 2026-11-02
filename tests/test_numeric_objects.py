"""Retain locally acquired numeric interfaces without copying measurement code."""

from collections.abc import Sequence
from pathlib import Path
from typing import Any

import pytest

from nca.abi import Module
from nca.discovery import train_tree
from nca.loader import ExpertStore
from nca.numeric_learning import propose_partition, propose_regions
from nca.numeric_objects import encoder_object, store_numeric_tree
from nca.objects import Primitive, Store
from nca.packages import install
from test_feature_acquisition import Baseline, Measurement


def measurements(store: Store) -> list[Module]:
    refs = [store.put(Primitive(Measurement(i).manifest, f"{__name__}:Measurement", {"index": i}))
            for i in range(2)]
    return [install(store, ref)[0] for ref in refs]


def bind(module: Module) -> tuple[str, int]:
    return module.identity, 0


@pytest.mark.parametrize("regions", [False, True])
def test_encoder_artifacts_preserve_codes_and_types(tmp_path: Path, regions: bool) -> None:
    store = Store()
    source = measurements(store)[0]
    rows = [((i / 40, 0.0),) for i in range(40)]
    labels = ["a" if x[0][0] < 0.3 else "b" if x[0][0] < 0.7 else "c" for x in rows]
    propose = propose_regions if regions else propose_partition
    kwargs = {"max_regions": 3} if regions else {}
    encoder = propose(Baseline(), source, rows, labels, encoding_cost=0.125,
                       decoder_cost=1, **kwargs)[0].expert.feature
    store.put(encoder.constructor)
    obj = encoder_object(store, encoder, bind(source), size=32)
    assert obj.ref == encoder_object(store, encoder, bind(source), size=32).ref
    reference = store.put(obj)
    store.save(tmp_path)
    resident = ExpertStore()
    restored = install(Store.open(tmp_path), reference, experts=resident)[0]
    assert resident.stats.loads == 0
    for row in [*rows, ((-1.0, 0.0),), ((2.0, 0.0),)]:
        assert restored.invoke(*row) == encoder.invoke(*row)
    assert restored.manifest.contract == encoder.manifest.contract
    assert restored.manifest.ref != encoder.manifest.ref
    assert resident.stats.loads == 2
    with pytest.raises(ValueError, match="content identity"):
        encoder_object(store, encoder, bind(measurements(store)[1]), size=32)


def test_locally_acquired_tree_round_trips_with_shared_measurements(tmp_path: Path) -> None:
    store = Store()
    sources = measurements(store)
    rows = [((i / 20, j / 20),) for i in range(20) for j in range(20)]
    labels = ["b" if x[0][1] < (0.3 if x[0][0] < 0.4 else 0.7) else "a" for x in rows]

    def acquire(subset: Sequence[tuple[Any, ...]], targets: Sequence[Any]) -> list[Module]:
        return [proposal.expert.feature for source in sources
                for proposal in propose_partition(Baseline(), source, subset, targets,
                                                    encoding_cost=0, decoder_cost=1)]

    tree = train_tree(Baseline(), [], rows, labels, max_nodes=31, overhead_cost=1, refine=acquire)
    reference = store_numeric_tree(store, tree, bind, tree_size=128, encoder_size=32)
    assert reference == store_numeric_tree(store, tree, bind, tree_size=128, encoder_size=32)
    store.save(tmp_path)
    resident = ExpertStore()
    restored = install(Store.open(tmp_path), reference, experts=resident)[0]
    assert resident.stats.loads == 0
    for row in [*rows, ((-1.0, 2.0),), ((2.0, -1.0),)]:
        assert restored.invoke(*row) == tree.invoke(*row)
    assert resident.stats.loads > 3
    model_ids = [obj.manifest.ref for ref in store.walk(reference)
                 if isinstance(obj := store.get(ref), Primitive)]
    assert len(model_ids) == len(set(model_ids))
