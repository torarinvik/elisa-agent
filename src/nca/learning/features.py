"""Bounded construction of feature trees from public typed experts (§36.59–60)."""

from collections import deque
from collections.abc import Callable, Iterator, Sequence
from array import array
from dataclasses import replace
from itertools import product
import math
from typing import Any

from nca.abi import Contract, Module, TypeId
from nca.effects import invoke_scoped
from nca.learning.discovery import Decoded, _total_calls
from nca.native import load

_NATIVE = load("records")


class AppliedFeature:
    """A slot-free transformation over ordered features of one external input.

    Branches are evaluated separately, even when an object is repeated. No
    purity, caching or shared execution is inferred. Graph retention preserves
    argument positions even when several positions name the same component.
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
        return invoke_scoped(self.transform, *(invoke_scoped(feature, *inputs) for feature in self.features))


def _target_library(seeds: tuple[Module, ...], transforms: tuple[Module, ...],
                    targets: frozenset[TypeId]) -> tuple[tuple[Module, ...], tuple[Module, ...]]:
    """Backward dependency cone; all alternatives and ordered inputs remain."""
    by_output: dict[TypeId, list[Contract]] = {}
    eligible = []
    for transform in transforms:
        head = transform.manifest.contract
        if not head.polymorphic and not head.slots and head.inputs:
            by_output.setdefault(head.output, []).append(head)
            eligible.append((transform, head))
    allowed = set(targets)
    pending = deque(targets)
    while pending:
        for head in by_output.get(pending.popleft(), ()):
            for type_id in head.inputs:
                if type_id not in allowed:
                    allowed.add(type_id)
                    pending.append(type_id)
    return (tuple(seed for seed in seeds if seed.manifest.contract.output in allowed),
            tuple(transform for transform, head in eligible if head.output in allowed))


def compose_features(seeds: Sequence[Module], transforms: Sequence[Module], *,
                     max_depth: int, limit: int, index_entries: int | None = None,
                     priority: Callable[[Module], float] | None = None,
                     targets: Sequence[TypeId] | None = None) -> list[Module]:
    """Enumerate seeds and compatible feature trees in breadth-first order.

    Depth is maximum transformations on a seed-to-root branch. Seeds share
    external inputs, slots and relevance. Transformations must have a ground,
    positive-arity, slot-free contract; other entries are inapplicable here.
    Construction itself invokes no models. Without truncation all such
    trees through max_depth occur, including cycles and repeated input types.
    Bounds limit this search, not the architecture. The cap counts candidates,
    not scanned metadata. Unary-only ordering is unchanged. For several inputs,
    the leftmost deepest child is the pivot, avoiding duplicate tree generation.
    Branches are not shared at execution. Freeze models before evaluation.
    Repeated library entries remain distinct choices; semantic deduplication
    is not inferred from matching type identifiers or implementations.
    Demand-built type indices preserve supplied order and bounded prefixes
    (§36.62–63), reading a rule only when its library position is reached.
    ``index_entries`` bounds prefetched rule-position entries for unqueried
    types. None retains the previous unbounded prefetch policy; zero builds
    only queried buckets. New types scan headers beyond the prefetched prefix.
    This trades repeated comparisons for fewer unused entries, not a byte cap
    on headers, queried buckets, native buffers or returned models.
    Available Elisa record scanning accelerates repeated unprefetched lookup;
    full identifier equality always verifies coarse hash matches (§36.64).
    Optional priority scores eligible transformations once, highest first,
    stably within ties (§36.65). Scoring inspects the eligible library before
    construction; its compute and training evidence belong to the caller.
    Scorers must not mutate models or use future certification draws. It changes
    bounded prefixes, never invents rules, and implies no semantic calibration.
    Optional ``targets`` returns only features of those output types, pruning
    seeds and rules outside their backward dependency cone (§36.67). Every
    retained intermediate still counts against ``limit``. This eager metadata
    pass preserves untruncated target trees, not completeness under a cap or
    semantic usefulness. It may cost more when the library is already relevant.
    """
    if type(max_depth) is not int or max_depth < 0:
        raise ValueError("feature depth must be a nonnegative integer")
    if type(limit) is not int or limit < 1:
        raise ValueError("feature limit must be a positive integer")
    if index_entries is not None and (type(index_entries) is not int or index_entries < 0):
        raise ValueError("index entry budget must be a nonnegative integer or None")
    seeds, transforms = tuple(seeds), tuple(transforms)
    if seeds and any(replace(s.manifest.contract, output=seeds[0].manifest.contract.output)
                     != seeds[0].manifest.contract for s in seeds):
        raise ValueError("feature seeds must share external inputs, slots and relevance")
    requested = None if targets is None else frozenset(targets)
    if requested is not None:
        if not requested:
            return []
        seeds, transforms = _target_library(seeds, transforms, requested)
    frontier = list(seeds[:limit])
    result = frontier.copy()

    def selected() -> list[Module]:
        return result if requested is None else [
            feature for feature in result if feature.manifest.contract.output in requested]

    if not max_depth or not frontier or len(result) == limit:
        return selected()
    if priority is not None:
        scored = []
        for transform in transforms:
            head = transform.manifest.contract
            if head.polymorphic or head.slots or not head.inputs:
                continue
            score = float(priority(transform))
            if not math.isfinite(score):
                raise ValueError("feature priorities must be finite")
            scored.append((score, transform))
        transforms = tuple(transform for _, transform in sorted(
            scored, key=lambda item: item[0], reverse=True))
    rules: dict[TypeId, list[tuple[Module, Contract, int]]] = {}
    prefetched: dict[TypeId, list[tuple[Module, Contract, int]]] = {}
    prefix = entries = 0
    prefetching = True
    headers: list[Contract | None] = []
    packed: array | None = None

    def indexed_rules(type_id: TypeId) -> Iterator[tuple[Module, Contract, int]]:
        nonlocal prefix, entries, prefetching, packed
        cached = rules.get(type_id)
        if cached is not None:
            yield from cached
            return
        matches = list(prefetched.get(type_id, ()))
        yield from matches
        start = prefix
        if _NATIVE is not None and len(headers) == len(transforms) and start < len(headers):
            if packed is None:
                packed = array("q")
                for index in range(start, len(headers)):
                    head = headers[index]
                    if head is not None:
                        for position, required in enumerate(head.inputs):
                            packed.extend((hash(required), index, position))
            for row in _NATIVE.select_equal(packed, 3, 0, hash(type_id)):
                index, position = packed[3 * row + 1], packed[3 * row + 2]
                head = headers[index]
                assert head is not None
                if head.inputs[position] == type_id:  # Hashes never define type equality.
                    entry = transforms[index], head, position
                    matches.append(entry)
                    yield entry
            rules[type_id] = matches
            return
        for index in range(start, len(transforms)):
            transform = transforms[index]
            if index == len(headers):
                head = transform.manifest.contract
                headers.append(head if not head.polymorphic and not head.slots and head.inputs else None)
                width = len(head.inputs) if headers[-1] is not None else 0
                if prefetching and (index_entries is None or entries + width <= index_entries):
                    if headers[-1] is not None:
                        for position, required in enumerate(head.inputs):
                            prefetched.setdefault(required, []).append((transform, head, position))
                    entries += width
                    prefix = index + 1
                else:
                    prefetching = False
            head = headers[index]
            if head is not None:
                for position, required in enumerate(head.inputs):
                    if required == type_id:
                        entry = transform, head, position
                        matches.append(entry)
                        yield entry
        rules[type_id] = matches  # Only a completed bucket may be reused.
    levels = [0] * len(result)
    for depth in range(1, max_depth + 1):
        if len(result) == limit or not frontier:
            break
        known: dict[TypeId, list[Module]] = {}
        older: dict[TypeId, list[Module]] = {}
        for feature, level in zip(result, levels, strict=True):
            type_id = feature.manifest.contract.output
            known.setdefault(type_id, []).append(feature)
            if level < depth - 1:
                older.setdefault(type_id, []).append(feature)
        following = []
        for pivot in frontier:
            for transform, head, position in indexed_rules(pivot.manifest.contract.output):
                choices = [([pivot] if i == position else
                            (older if i < position else known).get(type_id, ()))
                           for i, type_id in enumerate(head.inputs)]
                for args in product(*choices):
                    candidate = (Decoded(args[0], transform, replace(
                        args[0].manifest.contract, output=head.output)) if len(args) == 1
                        else AppliedFeature(transform, args))
                    result.append(candidate)
                    levels.append(depth)
                    following.append(candidate)
                    if len(result) == limit:
                        return selected()
        frontier = following
    return selected()
