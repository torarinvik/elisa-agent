"""Parameter artifacts for acquired regional wiring (§36.29)."""

from collections.abc import Sequence
from dataclasses import replace
from typing import Any

from nca.abi import Module
from nca.objects import Json, Primitive, Ref, Store, digest, manifest_data
from nca.packages import resolve_binding
from nca.learning.regional import RegionalExpert, RegionalPolicy
from nca.value_codec import decode_value, encode_value

_ENTRIES = {"load_regional": "nca/regional@1", "load_policy": "nca/regional-policy@1"}


def load_regional(manifest: dict[str, Any], key: Json, indices: list[int], cost: float,
                   dependencies: tuple[tuple[Module, ...], ...]) -> RegionalExpert:
    modules = _modules(indices, dependencies, 3)
    incumbent, feature, specialist = modules
    model = RegionalExpert(incumbent, feature, decode_value(key), specialist, cost)
    model.manifest = replace(model.manifest, module_id=manifest["module_id"])
    return model


def _modules(indices: list[int], dependencies: tuple[tuple[Module, ...], ...],
             count: int) -> list[Module]:
    if len(dependencies) != count or len(indices) != count:
        raise ValueError("regional wiring needs aligned dependency scopes and export positions")
    modules = []
    for scope, index in zip(dependencies, indices, strict=True):
        if type(index) is not int or not 0 <= index < len(scope):
            raise ValueError("invalid regional dependency export position")
        modules.append(scope[index])
    return modules


def load_policy(manifest: dict[str, Any], keys: list[Json], indices: list[int], cost: float,
                dependencies: tuple[tuple[Module, ...], ...]) -> RegionalPolicy:
    decoded = [decode_value(key) for key in keys]
    if len(set(decoded)) != len(decoded):
        raise ValueError("regional policy keys must be distinct")
    modules = _modules(indices, dependencies, len(keys) + 2)
    model = RegionalPolicy(modules[0], modules[1], dict(zip(decoded, modules[2:], strict=True)), cost)
    model.manifest = replace(model.manifest, module_id=manifest["module_id"])
    return model


def regional_object(store: Store, model: RegionalExpert,
                    bindings: Sequence[tuple[Ref, int]], *, size: int) -> Primitive:
    """Snapshot identified components in incumbent/feature/specialist order.

    Store fitted components first and construct the runtime from their installed
    versions. Each binding must match that component's identity and manifest.
    Size declares this interpreter's resident bytes only, excluding dependencies.
    Factories recompute metadata; Primitive.load verifies the stored declaration.
    """
    return _snapshot(store, model, (model.incumbent, model.feature, model.specialist), bindings,
                     {"key": encode_value(model.key)}, "load_regional", size)


def policy_object(store: Store, model: RegionalPolicy,
                  bindings: Sequence[tuple[Ref, int]], *, size: int) -> Primitive:
    """Retain incumbent, feature and specialists in the policy's mapping order."""
    return _snapshot(store, model, (model.incumbent, model.feature, *model.specialists.values()),
                     bindings, {"keys": [encode_value(key) for key in model.specialists]},
                     "load_policy", size)


def _snapshot(store: Store, model: RegionalPolicy, components: Sequence[Module],
              bindings: Sequence[tuple[Ref, int]], arguments: dict[str, Json],
              factory: str, size: int) -> Primitive:
    if len(bindings) != len(components):
        raise ValueError("one binding is required for each regional component")
    for component, (reference, index) in zip(components, bindings, strict=True):
        resolve_binding(store, reference, index, component)
    references = tuple(reference for reference, _ in bindings)
    arguments.update(indices=[index for _, index in bindings], cost=model.overhead_cost)
    identity = digest({"parameters": arguments, "dependencies": references})
    manifest = replace(model.manifest, module_id=f"learned-regional/{identity}")
    arguments["manifest"] = manifest_data(manifest)
    return Primitive(manifest, _ENTRIES[factory], arguments,
                     size=size, dependencies=references)
