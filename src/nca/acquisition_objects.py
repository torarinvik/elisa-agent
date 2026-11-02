"""Retain known learned-runtime graphs while keeping external experts opaque (§36.34)."""

from collections.abc import Callable
from dataclasses import replace
from typing import Any

from nca.abi import Module
from nca.affine_learning import AffineAdapter, affine_object
from nca.discovery import Decoded, Decoder, decoder_object
from nca.numeric_objects import _ENCODERS, _increment, _parameters, encoder_object
from nca.objects import Primitive, Ref, Store, contract_data, contract_from, digest, manifest_data
from nca.packages import install, resolve_binding
from nca.regional_learning import RegionalExpert, RegionalPolicy
from nca.regional_objects import policy_object, regional_object
from nca.vector_learning import VectorAffineAdapter, vector_affine_object

Binding = tuple[Ref, int]


def _children(model: Module) -> tuple[Module, ...]:
    # Exact runtime types only: subclasses may implement different semantics.
    kind = type(model)
    if kind in (RegionalExpert, RegionalPolicy):
        return (model.incumbent, model.feature, *model.specialists.values())
    if kind is Decoded:
        return model.feature, model.decoder
    if kind in _ENCODERS:
        return (model.measurement,)
    return ()


def load_composition(manifest: dict[str, Any], indices: list[int],
                     dependencies: tuple[tuple[Module, ...], ...]) -> Decoded:
    if len(dependencies) != 2 or len(indices) != 2:
        raise ValueError("composition needs two scopes and export positions")
    selected = []
    for scope, index in zip(dependencies, indices, strict=True):
        if type(index) is not int or not 0 <= index < len(scope):
            raise ValueError("invalid composition export position")
        selected.append(scope[index])
    model = Decoded(selected[0], selected[1], contract_from(manifest["contract"]))
    model.manifest = replace(model.manifest, module_id=manifest["module_id"])
    return model


def _metadata(original: Module, rebuilt: Module) -> None:
    if replace(rebuilt.manifest, module_id=original.manifest.module_id) != original.manifest:
        raise ValueError("retained children changed learned model metadata")


def _object(store: Store, model: Module, bindings: tuple[Binding, ...],
            children: tuple[Module, ...], size: int) -> Primitive | None:
    kind = type(model)
    if kind is AffineAdapter:
        rebuilt = AffineAdapter(model.manifest.contract, model.slope, model.offset, model.manifest.cost)
        _metadata(model, rebuilt)
        return affine_object(rebuilt, size=size)
    if kind is VectorAffineAdapter:
        rebuilt = VectorAffineAdapter(model.manifest.contract, model._weights.tolist(),
                                      model.manifest.cost)
        _metadata(model, rebuilt)
        return vector_affine_object(rebuilt, size=size)
    if kind is Decoder:
        rebuilt = Decoder(model.manifest.contract, model._table, model.fallback, model.manifest.cost)
        _metadata(model, rebuilt)
        return decoder_object(rebuilt, size=size)
    if kind in _ENCODERS:
        factory, parameters = _parameters(model)
        rebuilt = factory(manifest=manifest_data(model.manifest), index=0,
                          cost=_increment(model), dependencies=((children[0],),), **parameters)
        _metadata(model, rebuilt)
        store.put(model.constructor)
        return encoder_object(store, rebuilt, bindings[0], size=size)
    if kind in (RegionalExpert, RegionalPolicy):
        incumbent, feature, *specialists = children
        if kind is RegionalExpert:
            rebuilt = RegionalExpert(incumbent, feature, model.key, specialists[0], model.overhead_cost)
            snapshot = regional_object
        else:
            rebuilt = RegionalPolicy(incumbent, feature,
                                      dict(zip(model.specialists, specialists, strict=True)),
                                      model.overhead_cost)
            snapshot = policy_object
        _metadata(model, rebuilt)
        return snapshot(store, rebuilt, bindings, size=size)
    if kind is Decoded:
        rebuilt = Decoded(children[0], children[1], model.manifest.contract)
        _metadata(model, rebuilt)
        references = tuple(ref for ref, _ in bindings)
        indices = [index for _, index in bindings]
        identity = digest({"contract": contract_data(model.manifest.contract),
                           "indices": indices, "dependencies": references})
        manifest = replace(rebuilt.manifest, module_id=f"learned-composition/{identity}")
        return Primitive(manifest, "nca.acquisition_objects:load_composition",
                         {"manifest": manifest_data(manifest), "indices": indices},
                         size=size, dependencies=references)
    return None


def store_acquired_model(store: Store, model: Module, bind: Callable[[Module], Binding], *,
                         size: Callable[[Module], int]) -> Binding:
    """Retain supported learned runtimes; bind other experts without inspecting bodies.

    Supports regional policies, feature/head composition, numeric encoders and
    categorical/scalar/vector fitted heads. Other leaves must already be
    content-identified. Byte sizes apply per
    learned node and exclude its dependencies. Sizes/factories must remain
    faithful, and models must remain stable throughout traversal. Writes are
    postorder, not transactional. No active library or training evidence changes.
    """
    saved: dict[int, tuple[Binding, Module]] = {}
    active: set[int] = set()
    pending = [(model, False)]
    known = (*_ENCODERS, RegionalExpert, RegionalPolicy, Decoded,
             Decoder, AffineAdapter, VectorAffineAdapter)
    while pending:
        node, leaving = pending.pop()
        identity = id(node)
        if identity in saved:
            continue
        children = _children(node)
        if not leaving:
            if identity in active:
                raise ValueError("acquired model graph contains a cycle")
            active.add(identity)
            pending.append((node, True))
            pending.extend((child, False) for child in reversed(children))
            continue
        if type(node) not in known:
            binding = bind(node)
            restored = resolve_binding(store, *binding, node)
        else:
            entries = tuple(saved[id(child)] for child in children)
            bindings = tuple(binding for binding, _ in entries)
            restored_children = tuple(module for _, module in entries)
            declared_size = size(node)
            if type(declared_size) is not int or declared_size < 0:
                raise ValueError("learned node size must be a nonnegative integer")
            obj = _object(store, node, bindings, restored_children, declared_size)
            assert obj is not None
            reference = store.put(obj)
            binding = reference, 0
            restored = install(store, reference)[0]
            _metadata(node, restored)
        saved[identity] = binding, restored
        active.remove(identity)
    return saved[id(model)][0]
