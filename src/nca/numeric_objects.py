"""Retain acquired numeric interfaces as versioned model artifacts (§36.16)."""

import math
from collections.abc import Callable
from dataclasses import replace
from typing import Any

from nca.abi import Module
from nca.discovery import FeatureTree
from nca.numeric_learning import PartitionEncoder, RegionsEncoder
from nca.objects import Primitive, Ref, Store, digest, manifest_data
from nca.packages import install, resolve_binding
from nca.tree_objects import tree_object


Binding = tuple[Ref, int]


def _measurement(dependencies: tuple[tuple[Module, ...], ...], index: int) -> Module:
    if len(dependencies) != 1 or type(index) is not int or not 0 <= index < len(dependencies[0]):
        raise ValueError("numeric encoder needs one scope and a valid export position")
    return dependencies[0][index]


def load_partition(manifest: dict[str, Any], index: int, cost: float, boundary: float,
                   dependencies: tuple[tuple[Module, ...], ...]) -> PartitionEncoder:
    encoder = PartitionEncoder(_measurement(dependencies, index), boundary, cost)
    encoder.manifest = replace(encoder.manifest, module_id=manifest["module_id"])
    return encoder


def load_regions(manifest: dict[str, Any], index: int, cost: float, boundaries: list[float],
                 dependencies: tuple[tuple[Module, ...], ...]) -> RegionsEncoder:
    if any(type(b) is not float or not math.isfinite(b) for b in boundaries) or any(
            a >= b for a, b in zip(boundaries, boundaries[1:])):
        raise ValueError("region boundaries must be finite floats in increasing order")
    encoder = RegionsEncoder(_measurement(dependencies, index), tuple(boundaries), cost)
    encoder.manifest = replace(encoder.manifest, module_id=manifest["module_id"])
    return encoder


def encoder_object(store: Store, encoder: PartitionEncoder | RegionsEncoder,
                   binding: Binding, *, size: int) -> Primitive:
    """Snapshot parameters after verifying the original measurement artifact binding.

    Store the generated constructor before admitting this primitive. Its factory
    reconstructs metadata from the measurement and parameters; Primitive.load
    checks it against the stored manifest. External code fidelity is assumed.
    """
    reference, index = binding
    resolve_binding(store, reference, index, encoder.measurement)
    cost = encoder.manifest.cost - encoder.measurement.manifest.cost
    if not math.isfinite(cost) or cost < 0:
        raise ValueError("encoding cost must be finite and nonnegative")
    arguments = {"index": index, "cost": cost}
    if isinstance(encoder, PartitionEncoder):
        entry = "nca.numeric_objects:load_partition"
        arguments["boundary"] = encoder.boundary
    else:
        entry = "nca.numeric_objects:load_regions"
        arguments["boundaries"] = list(encoder.boundaries)
    identity = digest({"parameters": arguments, "measurement": reference,
                       "constructor": encoder.constructor.ref})
    manifest = replace(encoder.manifest, module_id=f"learned-numeric/{identity}")
    arguments["manifest"] = manifest_data(manifest)
    return Primitive(manifest, entry, arguments, size=size, dependencies=(reference,))


def store_numeric_tree(store: Store, tree: FeatureTree, bind: Callable[[Module], Binding], *,
                       tree_size: int, encoder_size: int) -> Ref:
    """Retain a tree with acquired numeric encoders and any already identified features.

    The binder identifies measurement scopes or existing features. Reconstructed
    encoders preserve behavior by their faithful parameter factories; equality
    is not inferred merely from matching contracts. No library names or active
    routes are changed. Sizes are caller-declared resident bytes per artifact.
    """
    features = []
    bindings = []
    for feature in tree.features:
        if isinstance(feature, (PartitionEncoder, RegionsEncoder)):
            store.put(feature.constructor)
            obj = encoder_object(store, feature, bind(feature.measurement), size=encoder_size)
            reference = store.put(obj)
            binding = reference, 0
            restored = install(store, reference)[0]
        else:
            binding = bind(feature)
            restored = resolve_binding(store, *binding, feature)
        features.append(restored)
        bindings.append(binding)
    rebound = FeatureTree(features, tree.root, tree.manifest)
    return store.put(tree_object(store, rebound, bindings, size=tree_size))
