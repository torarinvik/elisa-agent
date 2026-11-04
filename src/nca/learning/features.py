"""Bounded construction of feature trees from public typed experts (§36.59–60)."""

from collections.abc import Sequence
from dataclasses import replace
from itertools import product
from typing import Any

from nca.abi import Module
from nca.learning.discovery import Decoded, _total_calls


class AppliedFeature:
    """A slot-free transformation over ordered features of one external input.

    Branches are evaluated separately, even when an object is repeated. No
    purity, caching or shared execution is inferred. This in-memory interpreter
    does not yet have a parameter artifact codec.
    """

    def __init__(self, transform: Module, features: Sequence[Module]) -> None:
        self.transform, self.features = transform, tuple(features)
        head = transform.manifest
        if not self.features or head.contract.slots or head.contract.polymorphic:
            raise ValueError("feature application needs positive arity and a ground slot-free head")
        source = self.features[0].manifest.contract
        if (tuple(f.manifest.contract.output for f in self.features) != head.contract.inputs
                or any(replace(f.manifest.contract, output=source.output) != source
                       for f in self.features)):
            raise ValueError("feature arguments must match ordered head inputs and external signature")
        manifests = tuple(f.manifest for f in self.features)
        all_manifests = (*manifests, head)
        effects = (None if any(m.effects is None for m in all_manifests)
                   else frozenset().union(*(m.effects for m in all_manifests)))
        self.manifest = replace(head,
            module_id=f"apply({head.ref};{','.join(m.ref for m in manifests)})",
            contract=replace(source, output=head.contract.output),
            cost=sum(m.cost for m in all_manifests), effects=effects,
            calls=_total_calls(manifests), expected_calls=_total_calls(manifests, True) or None)

    def invoke(self, *inputs: Any) -> Any:
        return self.transform.invoke(*(feature.invoke(*inputs) for feature in self.features))


def compose_features(seeds: Sequence[Module], transforms: Sequence[Module], *,
                     max_depth: int, limit: int) -> list[Module]:
    """Enumerate seeds and compatible feature trees in breadth-first order.

    Depth is maximum transformations on a seed-to-root branch. Seeds share
    external inputs, slots and relevance. Transformations must have a ground,
    positive-arity, slot-free contract; other entries are inapplicable here.
    Models are never invoked or trained by search. Without truncation all such
    trees through max_depth occur, including cycles and repeated input types.
    Bounds limit this search, not the architecture. The cap counts candidates,
    not scanned metadata. Unary-only ordering is unchanged. For several inputs,
    the leftmost deepest child is the pivot, avoiding duplicate tree generation.
    Branches are not shared at execution. Freeze models before evaluation.
    Repeated library entries remain distinct choices; semantic deduplication
    is not inferred from matching type identifiers or implementations.
    """
    if type(max_depth) is not int or max_depth < 0:
        raise ValueError("feature depth must be a nonnegative integer")
    if type(limit) is not int or limit < 1:
        raise ValueError("feature limit must be a positive integer")
    seeds, transforms = tuple(seeds), tuple(transforms)
    if seeds and any(replace(s.manifest.contract, output=seeds[0].manifest.contract.output)
                     != seeds[0].manifest.contract for s in seeds):
        raise ValueError("feature seeds must share external inputs, slots and relevance")
    frontier = list(seeds[:limit])
    result = frontier.copy()
    levels = [0] * len(result)
    for depth in range(1, max_depth + 1):
        if len(result) == limit or not frontier:
            break
        known = tuple(zip(result, levels, strict=True))
        following = []
        for pivot in frontier:
            for transform in transforms:
                head = transform.manifest.contract
                if head.polymorphic or head.slots or not head.inputs:
                    continue
                for position, required in enumerate(head.inputs):
                    if required != pivot.manifest.contract.output:
                        continue
                    choices = [([pivot] if i == position else [
                        feature for feature, level in known
                        if feature.manifest.contract.output == type_id
                        and (i > position or level < depth - 1)])
                        for i, type_id in enumerate(head.inputs)]
                    for args in product(*choices):
                        candidate = (Decoded(args[0], transform, replace(
                            args[0].manifest.contract, output=head.output)) if len(args) == 1
                            else AppliedFeature(transform, args))
                        result.append(candidate)
                        levels.append(depth)
                        following.append(candidate)
                        if len(result) == limit:
                            return result
        frontier = following
    return result
