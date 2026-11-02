"""Acquired graph retention preserves hierarchy and opaque expert provenance."""

from bisect import bisect_right
from collections.abc import Callable, Sequence
from dataclasses import replace
from pathlib import Path
from typing import NoReturn

import pytest

from nca.abi import Calls, Contract, Manifest, Module
from nca.acquisition_objects import store_acquired_model
from nca.affine_learning import AffineAdapter, affine_object, fit_affine
from nca.discovery import Decoded, Decoder, Proposal
from nca.loader import ExpertStore
from nca.numeric_learning import midpoint_boundary
from nca.objects import Primitive, Store
from nca.packages import install
from nca.regional_learning import propose_failure_partitions, propose_regional_experts
from test_numeric_learning import Measurement
from test_regional_objects import Identity


class CoarseFeature:
    manifest = Manifest("coarse", "1", Contract(("input",), "region"), effects=frozenset())

    def __init__(self, boundaries: list[float]) -> None:
        self.boundaries = tuple(boundaries)

    def invoke(self, value: float) -> int:
        return bisect_right(self.boundaries, value)


def sources(store: Store) -> tuple[Module, Module, Module]:
    refs = [store.put(Primitive(Identity.manifest, "test_regional_objects:Identity", size=8)),
            store.put(Primitive(CoarseFeature.manifest, f"{__name__}:CoarseFeature",
                                {"boundaries": [-0.33, 0.33]}, size=8)),
            store.put(Primitive(Measurement.manifest, "test_numeric_learning:Measurement", size=8))]
    return tuple(install(store, ref)[0] for ref in refs)


def hierarchy(incumbent: Module, feature: Module, reading: Module,
              rows: Sequence[tuple[float]], labels: Sequence[float]) -> Module:
    def correct(a: float, b: float) -> bool:
        return abs(a - b) < 1e-9

    def acquire(train: Sequence[tuple[float]], targets: Sequence[float]) -> list[Proposal]:
        return [Proposal(fit_affine(incumbent.manifest.contract,
                                    [r[0] for r in train], targets, cost=1))]

    def refine(seed: Module, train: Sequence[tuple[float]], targets: Sequence[float]) -> list[Proposal]:
        return propose_failure_partitions(seed, [reading], acquire, train, targets, correct,
                    max_measurements=1, max_regions=1, encoding_cost=0, overhead_cost=0,
                    place_boundary=midpoint_boundary)

    return propose_regional_experts(incumbent, feature, acquire, rows, labels, correct,
                max_regions=3, overhead_cost=0, max_combinations=1,
                refine=refine, max_refinements=1)[-1].expert


def test_hierarchy_retention_is_stable_shared_and_lazy(tmp_path: Path) -> None:
    store = Store()
    incumbent, feature, reading = sources(store)
    rows = [(i / 100,) for i in range(-100, 101)]
    labels = [2 * x - 1 if x < -0.33 else 2 * x + 1 if x < 0.33
              else 3 * x + 1 if x >= 0.9 else x for x, in rows]
    model = hierarchy(incumbent, feature, reading, rows, labels)
    bound = []

    def bind(module: Module) -> tuple[str, int]:
        bound.append(module.identity)
        return module.identity, 0

    reference, index = store_acquired_model(store, model, bind, size=lambda model: 32)
    assert len(bound) == len(set(bound)) == 3
    assert list(store.walk(reference)).count(incumbent.identity) == 1
    assert store_acquired_model(store, model, bind, size=lambda model: 32) == (reference, index)
    assert model.specialists[2].incumbent is incumbent
    store.save(tmp_path)
    resident = ExpertStore(budget=216)
    restored = install(Store.open(tmp_path), reference, experts=resident)[index]
    assert resident.stats.loads == 0
    values = [i / 103 for i in range(-103, 104)]
    assert [restored.invoke(x) for x in values] == [model.invoke(x) for x in values]
    assert resident.stats.loads == 9
    assert restored.manifest.cost == model.manifest.cost
    assert restored.manifest.contract == model.manifest.contract


@pytest.mark.parametrize("head", ["affine", "decoder"])
def test_feature_head_composition_is_retained_with_exact_wiring(tmp_path: Path, head: str) -> None:
    store = Store()
    source = sources(store)[0]
    contract = Contract(("output",), "target")
    fitted = (fit_affine(contract, [-1.0, 1.0], [-1.0, 3.0], cost=1) if head == "affine"
              else Decoder(contract, {-1.0: "a", 1.0: "b"}, "c", 1))
    model = Decoded(source, fitted, Contract(("input",), "target"))
    reference, index = store_acquired_model(store, model, lambda m: (m.identity, 0),
                                           size=lambda m: 16)
    store.save(tmp_path)
    restored = install(Store.open(tmp_path), reference)[index]
    assert [restored.invoke(x) for x in (-1.0, 0.37, 1.0)] == [
        model.invoke(x) for x in (-1.0, 0.37, 1.0)]
    obj = store.get(reference)
    malformed = replace(obj, arguments={**obj.arguments, "indices": [False, 0]})
    with pytest.raises(ValueError, match="export position"):
        malformed.load(lambda ref: install(store, ref))


def test_cycles_and_opaque_subclasses_are_not_silently_serialized() -> None:
    from nca.regional_learning import RegionalPolicy

    store = Store()
    incumbent, feature, _ = sources(store)
    wrong = store.put(Primitive(Identity.manifest, "test_regional_objects:Identity", {"scale": 2.0}))
    with pytest.raises(ValueError, match="content identity"):
        store_acquired_model(store, incumbent, lambda m: (wrong, 0), size=lambda m: 16)
    cycle = RegionalPolicy(incumbent, feature, {}, 0)
    cycle.incumbent = cycle
    with pytest.raises(ValueError, match="cycle"):
        store_acquired_model(store, cycle, lambda m: (m.identity, 0), size=lambda m: 16)

    class Different(AffineAdapter):
        def invoke(self, value: float) -> float:
            return 999.0

    base = AffineAdapter(Identity.manifest.contract, 1.0, 0.0, 1)
    ref = store.put(affine_object(base, size=16))
    opaque = Different(Identity.manifest.contract, 1.0, 0.0, 1)
    with pytest.raises(ValueError, match="content identity"):
        store_acquired_model(store, opaque, lambda m: (ref, 0), size=lambda m: 16)


def test_parameter_only_vector_model_needs_no_external_binding() -> None:
    from nca.vector_learning import fit_vector_affine

    model = fit_vector_affine(Contract(("input",), "output"),
                              [(0.0, 0.0), (1.0, 0.0), (0.0, 1.0)],
                              [(0.5,), (2.5,), (3.5,)], cost=1)
    store = Store()
    reference, index = store_acquired_model(store, model,
            lambda m: pytest.fail("known parameter models must not use the external binder"),
            size=lambda m: 32)
    restored = install(store, reference)[index]
    assert restored.invoke((0.37, 0.61)) == model.invoke((0.37, 0.61))


def test_retention_derives_names_without_accepting_other_metadata_changes() -> None:
    model = AffineAdapter(Identity.manifest.contract, 2.0, 1.0, 1)
    model.manifest = replace(model.manifest, module_id="named-model")
    store = Store()
    reference, index = store_acquired_model(store, model,
            lambda m: pytest.fail("parameter model should not be opaque"), size=lambda m: 16)
    restored = install(store, reference)[index]
    assert restored.invoke(0.37) == model.invoke(0.37)
    assert model.manifest.module_id == "named-model"
    model.manifest = replace(model.manifest, effects=frozenset({"unknown-effect"}))
    with pytest.raises(ValueError, match="model metadata"):
        store_acquired_model(store, model, lambda m: (reference, 0), size=lambda m: 16)


class PairedSlotSource:
    manifest = Manifest("slot-source", "1",
        Contract(("input",), "output", slots=((("input",), "output"),)),
        calls=(Calls(1),), effects=frozenset({"read"}), cost=0.7)

    def invoke(self, filling: Callable[[float], float], value: float) -> float:
        return filling(value)


@pytest.mark.parametrize("slotted", [False, True])
def test_nested_joint_retention_preserves_sharing_metadata_and_order(
        tmp_path: Path, slotted: bool) -> None:
    from nca.discovery import JointFeature

    store = Store()
    if slotted:
        ref = store.put(Primitive(PairedSlotSource.manifest,
                                 f"{__name__}:PairedSlotSource", size=8))
        source = other = install(store, ref)[0]
        args = (lambda x: 2 * x, 0.37)
    else:
        source, other, _ = sources(store)
        args = (0.37,)
    model = JointFeature(source, JointFeature(source, other, 0.3), 0.1)
    bound = []

    def bind(module: Module) -> tuple[str, int]:
        bound.append(module.identity)
        return module.identity, 0

    reference, index = store_acquired_model(store, model, bind, size=lambda m: 16)
    assert len(bound) == (1 if slotted else 2)
    assert list(store.walk(reference)).count(source.identity) == 1
    assert store_acquired_model(store, model, bind, size=lambda m: 16) == (reference, index)
    store.save(tmp_path)
    resident = ExpertStore(budget=128)
    restored = install(Store.open(tmp_path), reference, experts=resident)[index]
    assert resident.stats.loads == 0
    assert restored.invoke(*args) == model.invoke(*args)
    assert resident.stats.loads == (3 if slotted else 4)
    assert restored.manifest.contract == model.manifest.contract
    assert restored.manifest.cost == model.manifest.cost
    assert restored.manifest.calls == model.manifest.calls
    assert restored.manifest.effects == model.manifest.effects
    obj = store.get(reference)
    assert obj.arguments["pair_cost"] == 0.1
    assert store.get(obj.dependencies[1]).arguments["pair_cost"] == 0.3
    malformed = replace(obj, arguments={**obj.arguments, "indices": [False, 0]})
    with pytest.raises(ValueError, match="export position"):
        malformed.load(lambda ref: install(store, ref))


def test_joint_retention_rejects_cycles_subclasses_and_invalid_pairing_cost() -> None:
    from nca.discovery import JointFeature

    store = Store()
    source = sources(store)[0]
    model = JointFeature(source, source, 0)
    reference, _ = store_acquired_model(store, model, lambda m: (m.identity, 0), size=lambda m: 8)

    class Different(JointFeature):
        def invoke(self, *args: object) -> object:
            return None

    with pytest.raises(ValueError, match="content identity"):
        store_acquired_model(store, Different(source, source, 0),
                             lambda m: (reference, 0), size=lambda m: 8)
    model.left = model
    with pytest.raises(ValueError, match="cycle"):
        store_acquired_model(store, model, lambda m: (m.identity, 0), size=lambda m: 8)
    with pytest.raises(ValueError, match="pair cost"):
        JointFeature(source, source, -1)


class CoordinateFeature:
    def __init__(self, index: int) -> None:
        self.index = index
        self.manifest = Manifest(f"coordinate-{index}", "1",
            Contract(("input",), f"coordinate-{index}"), effects=frozenset(), cost=1)

    def invoke(self, value: tuple[int, ...]) -> int:
        return value[self.index]


def test_joint_head_graph_retains_opaque_features(tmp_path: Path) -> None:
    from nca.discovery import JointFeature

    store = Store()
    children = []
    for i in range(2):
        ref = store.put(Primitive(CoordinateFeature(i).manifest,
                    f"{__name__}:CoordinateFeature", {"index": i}, size=8))
        children.append(install(store, ref)[0])
    joint = JointFeature(*children, 0.25)
    head = Decoder(Contract((joint.manifest.contract.output,), "target"),
                   {(0, 0): "a", (0, 1): "b", (1, 0): "c", (1, 1): "d"}, "unknown", 1)
    model = Decoded(joint, head, Contract(("input",), "target"))
    reference, index = store_acquired_model(store, model, lambda m: (m.identity, 0), size=lambda m: 16)
    store.save(tmp_path)
    restored = install(Store.open(tmp_path), reference)[index]
    assert [restored.invoke(v) for v in [(0, 0), (0, 1), (1, 0), (1, 1), (2, 2)]] == (
        [model.invoke(v) for v in [(0, 0), (0, 1), (1, 0), (1, 1), (2, 2)]])


def test_learned_categorical_partition_and_head_can_be_retained(tmp_path: Path) -> None:
    from nca.discovery import fit_decoder
    from nca.interface_learning import fit_categorical_partition, propose_heads

    store = Store()
    ref = store.put(Primitive(CoordinateFeature(0).manifest,
                    f"{__name__}:CoordinateFeature", {"index": 0}, size=8))
    source = install(store, ref)[0]
    rows = [((i,),) for i in range(8)] * 4
    labels = [f"label-{value[0] % 2}" for value, in rows]
    feature = fit_categorical_partition(source, rows, labels, encoding_cost=1)
    incumbent = Identity()
    model = propose_heads(incumbent, [feature],
                lambda c, v, t, b: [Proposal(fit_decoder(c, v, t, cost=1))],
                rows, labels, max_features=1, max_heads=1)[0]
    for constructor in model.constructors:
        store.put(constructor)
    reference, index = store_acquired_model(store, model.expert,
                                           lambda m: (m.identity, 0), size=lambda m: 16)
    store.save(tmp_path)
    restored = install(Store.open(tmp_path), reference)[index]
    assert [restored.invoke((i,)) for i in range(12)] == [model.expert.invoke((i,)) for i in range(12)]


def test_prototype_interface_graph_can_be_retained(tmp_path: Path) -> None:
    from nca.discovery import fit_decoder
    from nca.projection_learning import fit_prototype_encoder
    from test_projection_learning import Measurement as VectorMeasurement

    store = Store()
    reference = store.put(Primitive(VectorMeasurement.manifest,
                                   "test_projection_learning:Measurement", size=8))
    source = install(store, reference)[0]
    rows = [((-2.0, 0.0),), ((-1.0, 0.0),), ((1.0, 0.0),), ((2.0, 0.0),)]
    encoder = fit_prototype_encoder(source, rows, ["a", "a", "b", "b"],
                                    max_centroids=2, encoding_cost=1)
    head = fit_decoder(Contract((encoder.constructor.type(),), "target"),
                        [encoder.invoke(*r) for r in rows], ["a", "a", "b", "b"], cost=1)
    model = Decoded(encoder, head, Contract(("input",), "target"))
    root, index = store_acquired_model(store, model, lambda m: (m.identity, 0), size=lambda m: 16)
    store.save(tmp_path)
    restored = install(Store.open(tmp_path), root)[index]
    fresh = [(-0.2, 0.1), (0.3, 0.1), (0.0, 0.0)]
    assert [restored.invoke(v) for v in fresh] == [model.invoke(v) for v in fresh]


def test_multiple_roots_expose_a_reusable_representation_without_graph_inspection(
        tmp_path: Path) -> None:
    from nca.acquisition_objects import store_acquired_models
    from nca.discovery import fit_decoder
    from nca.interface_learning import propose_heads
    from nca.projection_learning import fit_prototype_encoder
    from test_projection_learning import Measurement as VectorMeasurement

    store = Store()
    ref = store.put(Primitive(VectorMeasurement.manifest,
                             "test_projection_learning:Measurement", size=8))
    source = install(store, ref)[0]
    rows = [((-2.0, -2.0),), ((2.0, 2.0),), ((-2.0, 2.0),), ((2.0, -2.0),)]
    labels = ["a", "a", "b", "b"]
    encoder = fit_prototype_encoder(source, rows, labels, max_centroids=4,
                    centers_per_category=2, encoding_cost=1)
    head = fit_decoder(Contract((encoder.constructor.type(),), "primary"),
                        [encoder.invoke(*r) for r in rows], labels, cost=1)
    primary = Decoded(encoder, head, Contract(("input",), "primary"))
    bound, sized = [], []

    def bind(module: Module) -> tuple[str, int]:
        bound.append(module)
        return module.identity, 0

    def size(module: Module) -> int:
        sized.append(module)
        return 16

    roots = store_acquired_models(store, [primary, encoder, primary, encoder], bind, size=size)
    assert roots[0] == roots[2] and roots[1] == roots[3] and roots[0] != roots[1]
    assert bound == [source] and {id(m) for m in sized} == {id(primary), id(encoder), id(head)}
    assert len(sized) == 3
    assert store.get(roots[0][0]).dependencies[0] == roots[1][0]
    assert store_acquired_model(store, primary, bind, size=size) == roots[0]
    store.save(tmp_path)
    reopened = Store.open(tmp_path)
    resident = ExpertStore(budget=128)
    from nca.packages import install_scopes

    scopes = install_scopes(reopened, [roots[0][0], roots[1][0]], experts=resident)
    old, feature = scopes[0][roots[0][1]], scopes[1][roots[1][1]]
    assert resident.stats.loads == 0
    targets = ["p0", "p1", "p2", "p3"]
    fitted = []
    for representation in [old, feature]:
        fitted.append(propose_heads(Identity(), [Proposal(representation)],
            lambda c, v, t, b: [Proposal(fit_decoder(c, v, t, cost=1))],
            rows, targets, max_features=1, max_heads=1)[0].expert)
    assert [sum(m.invoke(*r) == t for r, t in zip(rows, targets)) for m in fitted] == [2, 4]
    assert [old.invoke(*r) for r in rows] == [primary.invoke(*r) for r in rows]
    assert fitted[1].manifest.contract == Identity.manifest.contract


def test_empty_acquisition_roots_do_not_call_bind_or_size() -> None:
    from nca.acquisition_objects import store_acquired_models

    def unexpected(module: Module) -> NoReturn:
        pytest.fail("empty roots must not invoke callbacks")

    assert store_acquired_models(Store(), [], unexpected, size=unexpected) == ()
