"""Bounded construction of feature chains from public typed experts (§36.59)."""

from collections.abc import Sequence
from dataclasses import replace

from nca.abi import Contract, Module
from nca.learning.discovery import Decoded


def compose_features(seeds: Sequence[Module], transforms: Sequence[Module], *,
                     max_depth: int, limit: int) -> list[Module]:
    """Enumerate seeds and compatible unary chains in breadth-first order.

    Depth counts transformations after a seed. All seeds share external inputs,
    slots and relevance. Only ground, unary, slot-free transformation contracts
    equal to the derived head contract participate; other library entries are
    inapplicable to this search fragment. Models are composed, never invoked or
    trained here. No value semantics, purity or useful representation is inferred.
    Caller-supplied bounds limit this search, not the architecture. Without
    truncation all such chains through max_depth occur, including repeated types
    and cycles. The limit counts returned candidates, not scanned metadata.
    Supplied order resolves ties. Freeze models before independent evaluation.
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
    for _ in range(max_depth):
        if len(result) == limit or not frontier:
            break
        following = []
        for feature in frontier:
            source = feature.manifest.contract
            for transform in transforms:
                head = transform.manifest.contract
                if head.polymorphic or head != Contract((source.output,), head.output):
                    continue
                candidate = Decoded(feature, transform, replace(source, output=head.output))
                result.append(candidate)
                following.append(candidate)
                if len(result) == limit:
                    return result
        frontier = following
    return result
