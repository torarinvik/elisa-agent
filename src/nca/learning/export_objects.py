"""Retain composite execution settings and the actual installed member graph."""

from typing import Any

from nca.abi import Module
from nca.objects import Composite, Primitive, Ref, object_from
from nca.packages import Export


def load_export(composite: dict[str, Any], export_index: int, indices: list[int],
                budget: int, length: int, fuel: int,
                dependencies: tuple[tuple[Module, ...], ...]) -> Export:
    obj = object_from(composite)
    if not isinstance(obj, Composite) or obj.exports is None:
        raise ValueError("retained export needs a composite with explicit exports")
    if type(export_index) is not int or not 0 <= export_index < len(obj.exports):
        raise ValueError("invalid retained export position")
    if len(indices) != len(dependencies):
        raise ValueError("retained export needs aligned member bindings")
    members = []
    for scope, index in zip(dependencies, indices, strict=True):
        if type(index) is not int or not 0 <= index < len(scope):
            raise ValueError("invalid retained member position")
        members.append(scope[index])
    return Export(obj, export_index, members, budget=budget, length=length, fuel=fuel)


def export_object(model: Export, bindings: tuple[tuple[Ref, int], ...], *,
                  size: int) -> Primitive:
    return Primitive(model.manifest, "nca/export@1",
                     {"composite": model.composite.data(), "export_index": model.export_index,
                      "indices": [index for _, index in bindings], "budget": model.budget,
                      "length": model.length, "fuel": model.fuel},
                     dependencies=tuple(ref for ref, _ in bindings), size=size,
                     accounts_inside=True)
