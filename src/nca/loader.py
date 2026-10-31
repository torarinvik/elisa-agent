"""Lazy experts and a memory-budgeted expert store.

A ``LazyExpert`` carries its manifest (always resident, as planning reads
only manifests) and a loader for its implementation. The implementation is
materialized on first invocation and kept in an ``ExpertStore``, which holds
at most ``budget`` bytes and evicts the least recently used experts first.
``NCA.WellTyped.contracts_subset`` and ``NCA.route_contracts_append`` state
what this relies on: executing a route loads only the experts in it, and
installing experts never adds to an existing route's working set.
"""

from __future__ import annotations

import time
from collections import OrderedDict
from dataclasses import dataclass, field
from typing import Any, Callable

from nca.abi import Manifest


@dataclass
class StoreStats:
    loads: int = 0
    evictions: int = 0
    load_seconds: float = 0.0
    peak_bytes: int = 0
    loaded_ids: set[str] = field(default_factory=set)


class ExpertStore:
    def __init__(self, budget: int | None = None) -> None:
        self.budget = budget
        self.resident: OrderedDict[str, tuple[Any, int]] = OrderedDict()
        self.stats = StoreStats()

    @property
    def resident_bytes(self) -> int:
        return sum(size for _, size in self.resident.values())

    def acquire(self, expert: LazyExpert) -> Any:
        key = expert.manifest.ref
        if key in self.resident:
            self.resident.move_to_end(key)
            return self.resident[key][0]
        if self.budget is not None and expert.size > self.budget:
            raise MemoryError(f"{key} ({expert.size} B) exceeds the store budget")
        while self.budget is not None and self.resident_bytes + expert.size > self.budget:
            self.resident.popitem(last=False)
            self.stats.evictions += 1
        start = time.perf_counter()
        implementation = expert.load()
        self.stats.load_seconds += time.perf_counter() - start
        self.stats.loads += 1
        self.stats.loaded_ids.add(expert.manifest.module_id)
        self.resident[key] = (implementation, expert.size)
        self.stats.peak_bytes = max(self.stats.peak_bytes, self.resident_bytes)
        return implementation


class LazyExpert:
    """A module whose implementation is loaded from ``load`` on first use."""

    def __init__(self, manifest: Manifest, load: Callable[[], Any], size: int,
                 store: ExpertStore) -> None:
        self.manifest = manifest
        self.load = load
        self.size = size
        self.store = store

    def invoke(self, *inputs: Any) -> Any:
        return self.store.acquire(self).invoke(*inputs)
