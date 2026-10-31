"""Lazy experts and a memory-budgeted expert store.

A ``LazyExpert`` carries its manifest (always resident, as planning reads
only manifests) and a loader for its implementation. The implementation is
materialized on first invocation and kept in an ``ExpertStore``, which holds
at most ``budget`` bytes and evicts the least recently used experts first.

Before executing a route the kernel may call ``ExpertStore.prepare``: experts
outside the route are evicted (least recently used first) until the route's
missing experts fit, those are loaded, and the route's experts are pinned
until the next ``prepare``. Every transition that serves a route loads at
least its missing experts, and this one loads exactly those
(``NCA.routeAware_optimal``), so experts shared by consecutive routes are
never reloaded.
``NCA.WellTyped.contracts_subset`` and ``NCA.route_contracts_append`` state
what this relies on: executing a route loads only the experts in it, and
installing experts never adds to an existing route's working set.
"""

from __future__ import annotations

import time
from collections import OrderedDict
from collections.abc import Iterator
from dataclasses import dataclass, field
from typing import Any, Callable

from nca.abi import Manifest
from nca.planner import Apply, Map, Plan


@dataclass
class StoreStats:
    loads: int = 0
    evictions: int = 0
    loaded_bytes: int = 0
    load_seconds: float = 0.0
    peak_bytes: int = 0
    loaded_ids: set[str] = field(default_factory=set)


class ExpertStore:
    def __init__(self, budget: int | None = None) -> None:
        self.budget = budget
        self.resident: OrderedDict[str, tuple[Any, int]] = OrderedDict()
        self.pinned: frozenset[str] = frozenset()
        self.stats = StoreStats()

    @property
    def resident_bytes(self) -> int:
        return sum(size for _, size in self.resident.values())

    def prepare(self, route: Plan) -> None:
        """Make ``route``'s experts resident, evicting only experts outside it."""
        experts = {e.manifest.ref: e for e in route_experts(route)}
        self.pinned = frozenset(experts)
        missing = [e for key, e in experts.items() if key not in self.resident]
        self._make_room(sum(e.size for e in missing))
        for expert in missing:
            self.acquire(expert)

    def _make_room(self, size: int) -> None:
        if self.budget is None:
            return
        victims = (key for key in list(self.resident) if key not in self.pinned)
        while self.resident_bytes + size > self.budget:
            victim = next(victims, None)
            if victim is None:
                raise MemoryError(f"pinned experts leave no room for {size} B")
            del self.resident[victim]
            self.stats.evictions += 1

    def acquire(self, expert: LazyExpert) -> Any:
        key = expert.manifest.ref
        if key in self.resident:
            self.resident.move_to_end(key)
            return self.resident[key][0]
        if self.budget is not None and expert.size > self.budget:
            raise MemoryError(f"{key} ({expert.size} B) exceeds the store budget")
        self._make_room(expert.size)
        start = time.perf_counter()
        implementation = expert.load()
        self.stats.load_seconds += time.perf_counter() - start
        self.stats.loads += 1
        self.stats.loaded_bytes += expert.size
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


def route_experts(route: Plan) -> Iterator[LazyExpert]:
    """The lazy experts a route invokes."""
    if isinstance(route, Apply):
        if isinstance(route.module, LazyExpert):
            yield route.module
        for arg in route.args:
            yield from route_experts(arg)
    elif isinstance(route, Map):
        yield from route_experts(route.source)
        yield from route_experts(route.body)
