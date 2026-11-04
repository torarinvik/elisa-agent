"""Retain locally acquired numeric interfaces without copying measurement code."""

from collections.abc import Sequence
from pathlib import Path
from typing import Any

import pytest

from nca.abi import Contract, Manifest, Module
from nca.learning.discovery import train_tree
from nca.loader import ExpertStore
from nca.learning.numeric import midpoint_boundary, propose_partition, propose_regions
from nca.learning.numeric_objects import encoder_object, store_numeric_tree
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
@pytest.mark.parametrize("midpoint", [False, True])
def test_encoder_artifacts_preserve_codes_and_types(tmp_path: Path, regions: bool,
                                                   midpoint: bool) -> None:
    store = Store()
    source = measurements(store)[0]
    rows = [((i / 40, 0.0),) for i in range(40)]
    labels = ["a" if x[0][0] < 0.3 else "b" if x[0][0] < 0.7 else "c" for x in rows]
    propose = propose_regions if regions else propose_partition
    kwargs = {"max_regions": 3} if regions else {}
    encoder = propose(Baseline(), source, rows, labels, encoding_cost=0.125,
                       decoder_cost=1, place_boundary=midpoint_boundary if midpoint else None,
                       **kwargs)[0].expert.feature
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


class VectorMeasurement:
    """External measurement fixture: artifacts retain its entry, never its code."""

    manifest = Manifest("vector-measurement", "1", Contract(("input",), "features"),
                        effects=frozenset())

    def __init__(self, scale: float = 1.0) -> None:
        self.scale = scale

    def invoke(self, value: tuple[float, ...]) -> tuple[float, ...]:
        return tuple(self.scale * x for x in value)


def test_acquired_nonlinear_package_round_trips_lazily(tmp_path: Path) -> None:
    from nca.learning.discovery import decoder_object
    from nca.learning.numeric_objects import store_encoder_chain
    from nca.objects import Composite
    from nca.learning.projections import propose_polynomial_partitions

    store = Store()
    source_ref = store.put(Primitive(VectorMeasurement.manifest, f"{__name__}:VectorMeasurement",
                                     size=16))
    source = install(store, source_ref)[0]
    rows = [((s * 1.0, t * 1.0),) for s, t in ((1, 1), (-1, -1), (1, -1), (-1, 1))]
    proposal = propose_polynomial_partitions(Baseline(), source, rows,
                [True, True, False, False], degrees=(2,), max_terms=5, limit=1,
                lifting_cost=1, projection_cost=1, encoding_cost=1, decoder_cost=1,
                place_boundary=midpoint_boundary, reuse_observations=True)[0]
    encoder = proposal.expert.feature
    original_source = encoder.measurement.measurement.measurement
    reference, index = store_encoder_chain(store, encoder, bind, size=32)
    assert index == 0
    assert store_encoder_chain(store, encoder, bind, size=32) == (reference, index)
    assert encoder.measurement.measurement.measurement is original_source
    assert list(store.walk(reference)).count(source_ref) == 1
    head_ref = store.put(decoder_object(proposal.expert.decoder, size=16))
    package = store.put(Composite("acquired", "1", (reference, head_ref),
                                 exports=(Baseline.manifest.contract,), effects=frozenset()))
    tree = train_tree(Baseline(), [encoder], rows, [True, True, False, False],
                      max_nodes=3, overhead_cost=0)
    tree_ref = store_numeric_tree(store, tree, bind, tree_size=64, encoder_size=32)
    store.save(tmp_path)
    reopened = Store.open(tmp_path)
    restored_tree = install(reopened, tree_ref)[0]
    resident = ExpertStore(budget=128)
    export = install(reopened, package, experts=resident)[0]
    assert resident.stats.loads == 0
    fresh = [(i / 10, j / 10) for i in range(-9, 10) for j in range(-9, 10)]
    assert [export.invoke(x) for x in fresh] == [proposal.expert.invoke(x) for x in fresh]
    assert [restored_tree.invoke(x) for x in fresh] == [tree.invoke(x) for x in fresh]
    assert resident.stats.loads == 5
    assert export.manifest.contract == proposal.expert.manifest.contract
    assert export.manifest.cost == proposal.expert.manifest.cost
    for constructor in proposal.constructors:
        assert reopened.get(constructor.ref) == constructor
    primitive_entries = [reopened.get(ref).entry for ref in reopened.walk(package)
                         if isinstance(reopened.get(ref), Primitive)]
    assert primitive_entries.count(f"{__name__}:VectorMeasurement") == 1


def test_encoder_chain_rejects_wrong_external_binding_and_cycles() -> None:
    from nca.learning.numeric_objects import store_encoder_chain
    from nca.learning.projections import PolynomialEncoder, ProjectionEncoder

    store = Store()
    first, second = [store.put(Primitive(VectorMeasurement.manifest,
                     f"{__name__}:VectorMeasurement", {"scale": scale})) for scale in (1.0, 2.0)]
    source = install(store, first)[0]
    lift = PolynomialEncoder(source, 2, 2, max_terms=5, cost=1)
    count = len(store)
    with pytest.raises(ValueError, match="content identity"):
        store_encoder_chain(store, lift, lambda module: (second, 0), size=32)
    assert len(store) == count
    projection = ProjectionEncoder(source, (1.0, 1.0), 1)
    projection.measurement = projection
    with pytest.raises(ValueError, match="cycle"):
        store_encoder_chain(store, projection, bind, size=32)
