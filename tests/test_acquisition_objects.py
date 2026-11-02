"""Acquired graph retention preserves hierarchy and opaque expert provenance."""

from bisect import bisect_right
from collections.abc import Sequence
from dataclasses import replace
from pathlib import Path

import pytest

from nca.abi import Contract, Manifest, Module
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
