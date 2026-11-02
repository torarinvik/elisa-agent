"""Persist learned conditional structures as data for the generic tree runtime."""

from collections.abc import Sequence
from dataclasses import replace
from typing import Any

from nca.abi import Module
from nca.discovery import FeatureTree, _Decision
from nca.objects import (Json, Primitive, Ref, Store, canonical, digest,
                         manifest_data, manifest_from)
from nca.packages import install


def _scalar(value: Any) -> Json:
    if type(value) not in (str, int, float, bool, type(None)):
        raise TypeError("stored tree keys and labels must be JSON scalars")
    canonical(value)
    return value


def load_tree(manifest: dict[str, Any], nodes: list[dict[str, Any]], indices: list[int],
              dependencies: tuple[tuple[Module, ...], ...] = ()) -> FeatureTree:
    """Reconstruct a forward-linked node table without loading feature implementations."""
    if not nodes or len(indices) != len(dependencies):
        raise ValueError("tree data needs nodes and aligned feature bindings")
    features = []
    for scope, index in zip(dependencies, indices, strict=True):
        if type(index) is not int or not 0 <= index < len(scope):
            raise ValueError("invalid feature export position")
        features.append(scope[index])
    decoded = [_Decision(_scalar(n["chosen"]),
                         tuple((_scalar(label), count) for label, count in n["counts"]))
               for n in nodes]
    for position, (data, node) in enumerate(zip(nodes, decoded, strict=True)):
        feature = data["feature"]
        if feature is not None and (type(feature) is not int or not 0 <= feature < len(features)):
            raise ValueError("invalid tree feature position")
        node.feature = feature
        for key, child in data["children"]:
            if type(child) is not int or not position < child < len(nodes):
                raise ValueError("tree child positions must point forward")
            key = _scalar(key)
            if key in node.children:
                raise ValueError("duplicate tree key")
            node.children[key] = decoded[child]
    return FeatureTree(features, decoded[0], manifest_from(manifest))


def tree_object(store: Store, tree: FeatureTree, bindings: Sequence[tuple[Ref, int]], *,
                size: int) -> Primitive:
    """Snapshot a learned tree with verified content-identified feature bindings.

    The caller supplies dependency scopes and export positions. Their identities
    and manifests must match the features used for training. Size declares only
    the interpreter's resident bytes; dependency bytes are accounted separately.
    Scalar keys/labels are supported; no repr conversion or implicit code copy
    is used. Feature code and weights must remain faithful to their artifacts.
    """
    if len(bindings) != len(tree.features):
        raise ValueError("one binding is required for each trained feature")
    for feature, (reference, index) in zip(tree.features, bindings, strict=True):
        scope = install(store, reference)
        if type(index) is not int or not 0 <= index < len(scope):
            raise ValueError("invalid feature export position")
        selected = scope[index]
        identity = getattr(feature, "identity", None)
        if (identity is None or identity != getattr(selected, "identity", None)
                or feature.manifest != selected.manifest):
            raise ValueError("feature binding must match its trained content identity and manifest")
    ordered = [tree.root]
    positions = {tree.root: 0}
    nodes: list[dict[str, Json]] = []
    for node in ordered:
        children = []
        for key, child in node.children.items():
            if child in positions:
                raise ValueError("stored structure must be a tree without shared or cyclic nodes")
            positions[child] = len(ordered)
            ordered.append(child)
            children.append([_scalar(key), positions[child]])
        nodes.append({"chosen": _scalar(node.fallback), "feature": node.feature,
                      "counts": [[_scalar(label), count] for label, count in node.counts],
                      "children": children})
    arguments = {"manifest": manifest_data(tree.manifest), "nodes": nodes,
                 "indices": [index for _, index in bindings]}
    references = tuple(reference for reference, _ in bindings)
    identity = digest({"model": arguments, "dependencies": references})
    manifest = replace(tree.manifest, module_id=f"learned-tree/{identity}")
    arguments["manifest"] = manifest_data(manifest)
    return Primitive(manifest, "nca.tree_objects:load_tree", arguments,
                     size=size, dependencies=references)
