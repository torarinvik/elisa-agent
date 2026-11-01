"""Lazy experts and a memory-budgeted expert store.

A ``LazyExpert`` carries its manifest (always resident, as planning reads
only manifests) and a loader for its implementation. The implementation is
materialized on first invocation and kept in an ``ExpertStore``, which holds
at most ``budget`` bytes and evicts the least recently used experts first.

Before executing a route the caller may call ``ExpertStore.prepare``: by
default it loads the route's missing experts, evicting least recently used
experts outside the route as needed. The route's experts stay pinned until
the next ``prepare``; callers may instead defer loading until invocation.
Distinct live wrappers with the same reference
are rejected while an implementation is resident, and conflicting wrappers
in one route are rejected before the store changes. Use distinct versions
for distinct implementations when provenance must distinguish them.
Each lazy expert in a prepared route must belong to the preparing store.
Loaders must not mutate or acquire experts from their own store while loading;
they may use other stores.
Every transition that makes a route resident loads at
least its missing experts, and eager preparation loads exactly those
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
from numbers import Integral
from types import MappingProxyType
from typing import Any, Callable, Mapping

from nca.abi import Demand, Manifest
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
        self._loading = False
        self._pin_owners: dict[str, LazyExpert] = {}
        self.budget = budget
        self._resident: OrderedDict[str, tuple[Any, int]] = OrderedDict()
        self._resident_bytes = 0
        self._owners: dict[str, LazyExpert] = {}
        self._pinned: frozenset[str] = frozenset()
        self.stats = StoreStats()

    @property
    def budget(self) -> int | None:
        return self._budget

    @budget.setter
    def budget(self, value: int | None) -> None:
        self._check_not_loading()
        if value is not None and (isinstance(value, bool) or not isinstance(value, Integral) or value < 0):
            raise ValueError("store budget must be a nonnegative integer or None")
        if value is not None and hasattr(self, "_resident") and self.resident_bytes > value:
            raise ValueError("store budget cannot be less than resident bytes")
        if value is not None and sum(expert.size for expert in self._pin_owners.values()) > value:
            raise ValueError("store budget cannot be less than the pinned route")
        self._budget = None if value is None else int(value)

    @property
    def resident(self) -> Mapping[str, tuple[Any, int]]:
        """Read-only view of currently loaded implementations and declared sizes."""
        return MappingProxyType(self._resident)

    @property
    def resident_bytes(self) -> int:
        return self._resident_bytes

    @property
    def pinned(self) -> frozenset[str]:
        return self._pinned

    def prepare(self, route: Plan, *, eager: bool = True) -> None:
        """Pin ``route``'s experts, optionally loading them immediately.

        With ``eager=False``, route experts load on invocation and remain pinned;
        the full route must still fit the budget. Existing non-route residents
        are evicted only when space is needed.

        On load failure, restore old pending pins and surviving resident pins
        where their references have not been claimed by another expert.
        Evictions and successful partial loads are not rolled back.
        """
        self._check_not_loading()
        experts: dict[str, LazyExpert] = {}
        for expert in route_experts(route):
            if expert.store is not self:
                raise ValueError("expert belongs to a different store")
            key = expert.manifest.ref
            if (key in experts and experts[key] is not expert) or (
                    key in self._owners and self._owners[key] is not expert):
                raise ValueError(f"conflicting expert definitions for {key}")
            experts[key] = expert
        required = sum(e.size for e in experts.values())
        if self.budget is not None and required > self.budget:
            raise MemoryError(f"route requires {required} B, exceeding the {self.budget} B store budget")
        previous_pins = self.pinned
        previous_owners = self._pin_owners
        previously_pending = previous_pins.difference(self._resident)
        self._pinned = frozenset(experts)
        self._pin_owners = experts
        if not eager:
            return
        try:
            missing = [e for key, e in experts.items() if key not in self._resident]
            self._make_room(sum(e.size for e in missing))
            for expert in missing:
                self.acquire(expert)
        except BaseException:
            # Evicted implementations cannot be restored without reloading them.
            self._pinned = frozenset(
                key for key in previous_pins
                if (key in self._resident and self._owners[key] is previous_owners[key])
                or (key in previously_pending and key not in self._resident))
            self._pin_owners = {key: previous_owners[key] for key in self.pinned}
            raise

    def _make_room(self, size: int) -> None:
        if self.budget is None or self.resident_bytes + size <= self.budget:
            return
        needed = self.resident_bytes + size - self.budget
        victims: list[str] = []
        released = 0
        for key, (_, resident_size) in self._resident.items():
            if key not in self.pinned:
                victims.append(key)
                released += resident_size
                if released >= needed:
                    break
        if released < needed:
            raise MemoryError(f"pinned experts leave no room for {size} B")
        for victim in victims:
            self._resident_bytes -= self._resident[victim][1]
            del self._resident[victim]
            del self._owners[victim]
            self.stats.evictions += 1

    def acquire(self, expert: LazyExpert) -> Any:
        self._check_not_loading()
        if expert.store is not self:
            raise ValueError("expert belongs to a different store")
        key = expert.manifest.ref
        if key in self._pin_owners and self._pin_owners[key] is not expert:
            raise ValueError(f"conflicting expert definitions for {key}")
        if key in self._resident:
            if self._owners[key] is not expert:
                raise ValueError(f"conflicting expert definitions for {key}")
            self._resident.move_to_end(key)
            return self._resident[key][0]
        if self.budget is not None and expert.size > self.budget:
            raise MemoryError(f"{key} ({expert.size} B) exceeds the store budget")
        self._make_room(expert.size)
        start = time.perf_counter()
        self._loading = True
        try:
            implementation = expert.load()
            if not callable(getattr(implementation, "invoke", None)):
                raise TypeError(f"loader for {key} must return an implementation with an invoke method")
        finally:
            self._loading = False
        self.stats.load_seconds += time.perf_counter() - start
        self.stats.loads += 1
        self.stats.loaded_bytes += expert.size
        self.stats.loaded_ids.add(expert.manifest.module_id)
        self._resident[key] = (implementation, expert.size)
        self._resident_bytes += expert.size
        self._owners[key] = expert
        self.stats.peak_bytes = max(self.stats.peak_bytes, self.resident_bytes)
        return implementation

    def _check_not_loading(self) -> None:
        if self._loading:
            raise RuntimeError("expert loaders cannot re-enter their own store")


class LazyExpert:
    """A module loaded on first use, with a fixed manifest and owning store.

    Optional demand and relevance rules are available before the implementation
    is loaded and must have the same semantics as its corresponding rules.
    """

    def __init__(self, manifest: Manifest, load: Callable[[], Any], size: int,
                 store: ExpertStore, *,
                 demand: Callable[[int, Demand], Demand] | None = None,
                 relevant: Callable[[int, list[Any]], bool] | None = None) -> None:
        if isinstance(size, bool) or not isinstance(size, Integral) or size < 0:
            raise ValueError("expert size must be a nonnegative integer")
        self._manifest = manifest
        self.load = load
        self._size = int(size)
        self._store = store
        self.demand = demand
        self.relevant = relevant

    @property
    def manifest(self) -> Manifest:
        return self._manifest

    @property
    def store(self) -> ExpertStore:
        return self._store

    @property
    def size(self) -> int:
        return self._size

    def invoke(self, *inputs: Any) -> Any:
        return self.store.acquire(self).invoke(*inputs)


def route_experts(route: Plan) -> Iterator[LazyExpert]:
    """The lazy experts a route invokes."""
    if isinstance(route, Apply):
        if isinstance(route.module, LazyExpert):
            yield route.module
        for arg in (*route.args, *route.slots):
            yield from route_experts(arg)
    elif isinstance(route, Map):
        yield from route_experts(route.source)
        yield from route_experts(route.body)
