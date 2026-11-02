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
from nca.projection_learning import PolynomialEncoder, ProjectionEncoder
from nca.tree_objects import tree_object


Binding = tuple[Ref, int]
Encoder = PartitionEncoder | RegionsEncoder | ProjectionEncoder | PolynomialEncoder
_ENCODERS = (PartitionEncoder, RegionsEncoder, ProjectionEncoder, PolynomialEncoder)


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


def load_projection(manifest: dict[str, Any], index: int, cost: float, direction: list[float],
                    dependencies: tuple[tuple[Module, ...], ...]) -> ProjectionEncoder:
    encoder = ProjectionEncoder(_measurement(dependencies, index), tuple(direction), cost)
    encoder.manifest = replace(encoder.manifest, module_id=manifest["module_id"])
    return encoder


def load_polynomial(manifest: dict[str, Any], index: int, cost: float, dimension: int,
                    degree: int, max_terms: int,
                    dependencies: tuple[tuple[Module, ...], ...]) -> PolynomialEncoder:
    encoder = PolynomialEncoder(_measurement(dependencies, index), dimension, degree,
                                max_terms=max_terms, cost=cost)
    encoder.manifest = replace(encoder.manifest, module_id=manifest["module_id"])
    return encoder


def _parameters(encoder: Encoder) -> tuple[Callable[..., Encoder], dict[str, Any]]:
    if isinstance(encoder, PartitionEncoder):
        return load_partition, {"boundary": encoder.boundary}
    if isinstance(encoder, RegionsEncoder):
        return load_regions, {"boundaries": list(encoder.boundaries)}
    if isinstance(encoder, ProjectionEncoder):
        return load_projection, {"direction": list(encoder.direction)}
    if isinstance(encoder, PolynomialEncoder):
        return load_polynomial, {"dimension": encoder.dimension, "degree": encoder.degree,
                                 "max_terms": max(1, len(encoder.terms))}
    raise TypeError("unsupported fitted encoder runtime")


def _increment(encoder: Encoder) -> float:
    cost = encoder.manifest.cost - encoder.measurement.manifest.cost
    if not math.isfinite(cost) or cost < 0:
        raise ValueError("encoding cost must be finite and nonnegative")
    return cost


def encoder_object(store: Store, encoder: Encoder, binding: Binding, *, size: int) -> Primitive:
    """Snapshot fitted parameters with a verified content-identified measurement.

    Store the generated constructor first. Factories reconstruct metadata from
    parameters/dependencies; Primitive.load checks it. External code fidelity is
    assumed. Size declares only this stage, not its dependency closure.
    """
    reference, index = binding
    resolve_binding(store, reference, index, encoder.measurement)
    factory, parameters = _parameters(encoder)
    arguments = {"index": index, "cost": _increment(encoder), **parameters}
    identity = digest({"parameters": arguments, "measurement": reference,
                       "constructor": encoder.constructor.ref})
    manifest = replace(encoder.manifest, module_id=f"learned-numeric/{identity}")
    arguments["manifest"] = manifest_data(manifest)
    return Primitive(manifest, f"{__name__}:{factory.__name__}", arguments,
                     size=size, dependencies=(reference,))


def store_encoder_chain(store: Store, encoder: Module, bind: Callable[[Module], Binding], *,
                        size: int) -> Binding:
    """Retain a fitted chain without copying the external measurement implementation.

    The binder must identify the original external leaf faithfully. Reconstruct
    each saved predecessor before rebinding its successor; no trained module is
    mutated. The returned binding names the final encoder. Constructors and
    dependency artifacts are admitted in order; no active library is changed.
    """
    stages: list[Encoder] = []
    seen: set[int] = set()
    leaf = encoder
    while isinstance(leaf, _ENCODERS):
        if id(leaf) in seen:
            raise ValueError("fitted encoder chain contains a cycle")
        seen.add(id(leaf))
        stages.append(leaf)
        leaf = leaf.measurement
    binding = bind(leaf)
    restored = resolve_binding(store, *binding, leaf)
    for stage in reversed(stages):
        factory, parameters = _parameters(stage)
        rebound = factory(manifest=manifest_data(stage.manifest), index=0,
                          cost=_increment(stage), dependencies=((restored,),), **parameters)
        if rebound.manifest != stage.manifest:
            raise ValueError("restored predecessor changed fitted encoder metadata")
        store.put(stage.constructor)
        reference = store.put(encoder_object(store, rebound, binding, size=size))
        binding = reference, 0
        restored = install(store, reference)[0]
    return binding


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
        if isinstance(feature, _ENCODERS):
            binding = store_encoder_chain(store, feature, bind, size=encoder_size)
            restored = install(store, binding[0])[binding[1]]
        else:
            binding = bind(feature)
            restored = resolve_binding(store, *binding, feature)
        features.append(restored)
        bindings.append(binding)
    rebound = FeatureTree(features, tree.root, tree.manifest)
    return store.put(tree_object(store, rebound, bindings, size=tree_size))
