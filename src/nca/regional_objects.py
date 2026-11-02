"""Parameter artifacts for acquired regional wiring (§36.29)."""

from collections.abc import Sequence
from dataclasses import replace
from typing import Any

from nca.abi import Module
from nca.objects import Json, Primitive, Ref, Store, digest, manifest_data
from nca.packages import resolve_binding
from nca.regional_learning import RegionalExpert
from nca.value_codec import decode_value, encode_value


def load_regional(manifest: dict[str, Any], key: Json, indices: list[int], cost: float,
                   dependencies: tuple[tuple[Module, ...], ...]) -> RegionalExpert:
    if len(dependencies) != 3 or len(indices) != 3:
        raise ValueError("regional wiring needs three dependency scopes and export positions")
    modules = []
    for scope, index in zip(dependencies, indices, strict=True):
        if type(index) is not int or not 0 <= index < len(scope):
            raise ValueError("invalid regional dependency export position")
        modules.append(scope[index])
    incumbent, feature, specialist = modules
    model = RegionalExpert(incumbent, feature, decode_value(key), specialist, cost)
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
    if len(bindings) != 3:
        raise ValueError("one binding is required for each regional component")
    for component, (reference, index) in zip(
            (model.incumbent, model.feature, model.specialist), bindings, strict=True):
        resolve_binding(store, reference, index, component)
    references = tuple(reference for reference, _ in bindings)
    arguments = {"key": encode_value(model.key), "indices": [index for _, index in bindings],
                 "cost": model.overhead_cost}
    identity = digest({"parameters": arguments, "dependencies": references})
    manifest = replace(model.manifest, module_id=f"learned-regional/{identity}")
    arguments["manifest"] = manifest_data(manifest)
    return Primitive(manifest, "nca.regional_objects:load_regional", arguments,
                     size=size, dependencies=references)
