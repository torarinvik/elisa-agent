"""Regional parameter artifacts retain wiring, lazy dependencies and key identity."""

from dataclasses import replace
from pathlib import Path

import pytest

from nca.abi import Contract, Manifest
from nca.affine_learning import affine_object, fit_affine
from nca.loader import ExpertStore
from nca.learning.numeric import fit_regions_encoder, midpoint_boundary, purity_tiebreak
from nca.learning.numeric_objects import store_encoder_chain
from nca.objects import Primitive, Store
from nca.packages import install
from nca.learning.regional import RegionalExpert
from nca.regional_objects import regional_object
from test_numeric_learning import Measurement


class Identity:
    manifest = Manifest("identity", "1", Contract(("input",), "output"), effects=frozenset())

    def __init__(self, scale: float = 1.0) -> None:
        self.scale = scale

    def invoke(self, value: float) -> float:
        return self.scale * value


def components(store: Store) -> tuple[RegionalExpert, tuple[tuple[str, int], ...]]:
    incumbent = store.put(Primitive(Identity.manifest, f"{__name__}:Identity", size=8))
    reading = store.put(Primitive(Measurement.manifest, "test_numeric_learning:Measurement", size=8))
    source = install(store, reading)[0]
    rows = [(i / 100,) for i in range(-100, 101)]
    router = fit_regions_encoder(source, rows, [-0.25 <= r[0] < 0.35 for r in rows],
                                 max_regions=3, encoding_cost=0,
                                 place_boundary=midpoint_boundary, tie_break=purity_tiebreak)
    feature = store_encoder_chain(store, router, lambda m: (m.identity, 0), size=16)
    fitted = fit_affine(Identity.manifest.contract, [0.0, 0.1], [0.7, 0.9], cost=1)
    specialist = store.put(affine_object(fitted, size=32))
    bindings = ((incumbent, 0), feature, (specialist, 0))
    modules = [install(store, reference)[index] for reference, index in bindings]
    return RegionalExpert(modules[0], modules[1], 1, modules[2], 0), bindings


def test_regional_artifact_round_trips_and_keys_define_distinct_models(tmp_path: Path) -> None:
    store = Store()
    model, bindings = components(store)
    obj = regional_object(store, model, bindings, size=16)
    reference = store.put(obj)
    assert obj.ref == regional_object(store, model, bindings, size=16).ref
    other = RegionalExpert(model.incumbent, model.feature, 0, model.specialist, model.overhead_cost)
    other_obj = regional_object(store, other, bindings, size=16)
    assert obj.ref != other_obj.ref and obj.manifest.ref != other_obj.manifest.ref
    store.save(tmp_path)
    resident = ExpertStore(budget=80)
    restored = install(Store.open(tmp_path), reference, experts=resident)[0]
    assert resident.stats.loads == 0
    values = [i / 103 for i in range(-103, 104)]
    assert [restored.invoke(x) for x in values] == [model.invoke(x) for x in values]
    assert resident.stats.loads == 5
    assert restored.manifest.contract == model.manifest.contract
    assert restored.manifest.cost == model.manifest.cost
    assert obj.dependencies == tuple(ref for ref, _ in bindings)


def test_regional_snapshot_rejects_wrong_bindings_and_malformed_positions() -> None:
    store = Store()
    model, bindings = components(store)
    wrong = store.put(Primitive(Identity.manifest, f"{__name__}:Identity", {"scale": 2.0}))
    with pytest.raises(ValueError, match="content identity"):
        regional_object(store, model, ((wrong, 0), *bindings[1:]), size=16)
    obj = regional_object(store, model, bindings, size=16)
    malformed = replace(obj, arguments={**obj.arguments, "indices": [False, 0, 0]})
    with pytest.raises(ValueError, match="export position"):
        malformed.load(lambda ref: install(store, ref))
    altered = replace(obj, arguments={**obj.arguments, "cost": 10.0})
    with pytest.raises(ValueError, match="not the declared"):
        altered.load(lambda ref: install(store, ref))


def test_regional_keys_use_structural_codec_without_lossy_coercion() -> None:
    store = Store()
    model, bindings = components(store)
    key = (1, ("tag", None))
    structural = RegionalExpert(model.incumbent, model.feature, key, model.specialist, 0)
    obj = regional_object(store, structural, bindings, size=16)
    loaded = obj.load(lambda ref: install(store, ref))
    assert loaded.key == key
    opaque = RegionalExpert(model.incumbent, model.feature, frozenset({1}), model.specialist, 0)
    with pytest.raises(TypeError, match="JSON scalars or tuples"):
        regional_object(store, opaque, bindings, size=16)


def test_combined_policy_round_trip_and_duplicate_key_rejection(tmp_path: Path) -> None:
    from nca.learning.regional import RegionalPolicy
    from nca.regional_objects import policy_object

    store = Store()
    original, bindings = components(store)
    left = store.put(affine_object(fit_affine(Identity.manifest.contract,
                     [-1.0, -0.5], [-3.0, -2.0], cost=1), size=32))
    policy = RegionalPolicy(original.incumbent, original.feature,
                             {0: install(store, left)[0], 2: original.specialist}, 0)
    grouped = (*bindings[:2], (left, 0), bindings[2])
    obj = policy_object(store, policy, grouped, size=16)
    ref = store.put(obj)
    assert ref == policy_object(store, policy, grouped, size=16).ref
    store.save(tmp_path)
    resident = ExpertStore(budget=112)
    restored = install(Store.open(tmp_path), ref, experts=resident)[0]
    assert resident.stats.loads == 0
    values = [-0.9, 0.0, 0.9]
    assert [restored.invoke(x) for x in values] == [policy.invoke(x) for x in values]
    assert resident.stats.loads == 6
    malformed = replace(obj, arguments={**obj.arguments, "keys": [0, 0]})
    with pytest.raises(ValueError, match="keys must be distinct"):
        malformed.load(lambda ref: install(store, ref))
