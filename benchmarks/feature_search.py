"""Feature-search metadata scaling; full-scan reference versus type indices.

The reference reproduces the pre-index search for differential verification
and timing only. Production has one implementation, in learning.features.
"""

from __future__ import annotations

import json
import tracemalloc
from collections.abc import Sequence
from dataclasses import replace
from itertools import product
from time import process_time
from typing import Any

from nca.abi import Contract, Manifest, Module
from nca.learning.discovery import Decoded
from nca.learning.features import AppliedFeature, compose_features


def compose_unindexed(seeds: Sequence[Module], transforms: Sequence[Module], *,
                       max_depth: int, limit: int) -> list[Module]:
    """Previous full-scan implementation, including snapshots and validation."""
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


def signature(module: Module) -> Any:
    if type(module) is Decoded:
        return signature(module.decoder), (signature(module.feature),)
    if type(module) is AppliedFeature:
        return signature(module.transform), tuple(signature(f) for f in module.features)
    return module.manifest.ref, id(module)


class Part:
    def __init__(self, name: str, contract: Contract) -> None:
        self._manifest = Manifest(name, "1", contract, effects=frozenset())
        self.reads = self.calls = 0

    @property
    def manifest(self) -> Manifest:
        self.reads += 1
        return self._manifest

    def invoke(self, *inputs: Any) -> Any:
        self.calls += 1
        raise AssertionError("metadata search must not invoke experts")


def trial(size: int, cap: int) -> dict[str, Any]:
    seeds = [Part(f"seed.{t}", Contract(("source",), t)) for t in ("a", "b")]
    rules = [Part("first", Contract(("a",), "b")),
             Part("second", Contract(("a", "b"), "a"))]
    rules.extend(Part(f"unused.{i}", Contract((f"missing{i}",), f"missing{i}"))
                 for i in range(size - len(rules)))
    parts = [*seeds, *rules]
    outputs: dict[str, Any] = {"size": size, "cap": cap,
                               "labels": 0, "acquisition_requests": 0}
    expected = None
    for name, search in (("scan", compose_unindexed), ("indexed", compose_features)):
        search(seeds, rules, max_depth=4, limit=cap)
        for part in parts:
            part.reads = part.calls = 0
        started = process_time()
        for _ in range(10):
            result = search(seeds, rules, max_depth=4, limit=cap)
        outputs[f"{name}_cpu"] = (process_time() - started) / 10
        outputs[f"{name}_reads"] = sum(p.reads for p in parts) / 10
        outputs[f"{name}_calls"] = sum(p.calls for p in parts)
        current = [signature(m) for m in result]
        if expected is None:
            expected = current
        else:
            assert current == expected
        tracemalloc.start()
        search(seeds, rules, max_depth=4, limit=cap)
        outputs[f"{name}_peak_bytes"] = tracemalloc.get_traced_memory()[1]
        tracemalloc.stop()
        outputs["candidates"] = len(result)
    return outputs


if __name__ == "__main__":
    for size, cap in ((128, 64), (1024, 64), (8192, 64), (8192, 3)):
        print(json.dumps(trial(size, cap)), flush=True)
