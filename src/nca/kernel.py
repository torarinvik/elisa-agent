"""The kernel's request resolver.

Mirrors ``NCA.resolve`` (``lean/NCA/Execution/Request.lean``): a request is planned with
the stable planner over the installed modules minus every module in the
request chain. Resolution is proved well-typed (``resolve_sound``), never
re-enters the chain (``resolve_avoids``), and nested request chains are no
longer than the number of installed modules (``RequestChain.length_le``).

``Kernel(recursive=True)`` excludes no one, so an expert may ask its own
question again. Termination then rests on the runtime's budgets, which
decrease with every invocation (``NCA.serve``); chain exclusion is the
default.

With an ``acquire`` hook, a request no installed expert can serve becomes a
typed sub-goal: the kernel asks the hook for the fewest missing connectors
through ``planner.gaps.repair`` (``NCA.Repair``), installs what it supplies and
serves the request through them. Acquired experts are appended, so every route found
before remains (Theorem 3.3).

A host may also append installed modules between requests. One planner index is kept per
set of excluded modules, so requests from the same chain reuse the plans found
for earlier ones. Each is derived from the index of the whole library, keeping
its results for the modules installed before the first excluded one.
"""

from __future__ import annotations

from collections.abc import Callable, Sequence

from nca.abi import Contract, Module, Request, TypeId
from nca.index import ProducerIndex
from nca.planner import Plan, plan_stable_indexed
from nca.planner.gaps import Acquire, repair
from nca.planner.requests import RequestTemplates, bound_route


class Kernel:
    def __init__(self, modules: Sequence[Module], recursive: bool = False,
                 index: ProducerIndex | None = None, acquire: Acquire | None = None,
                 attempts: int = 8, missing: int = 1,
                 media: Sequence[TypeId] | None = None, *, arity: int = 1,
                 priority: Callable[[Contract], float] | None = None, fuel: int = 8) -> None:
        """``index``, if given, must index exactly ``modules``; it is shared.
        ``acquire`` is asked at most ``attempts`` times per request, for
        routes needing at most ``missing`` new connectors, inventing media
        grown over the types in ``media`` if given. ``arity`` bounds acquired
        input counts and ``priority`` scores valid single-gap candidates.
        ``fuel`` bounds planning depth, separately from runtime execution budgets."""
        self.modules = tuple(modules)
        self._providers: dict[str, Module | None] | None = None
        self._templates: RequestTemplates | None = None
        self.acquire, self.attempts, self.missing = acquire, attempts, missing
        self.media = media
        self.arity, self.priority = arity, priority
        self.fuel = fuel
        self.acquired: list[Module] = []
        self.recursive = recursive
        self.requests = 0
        self._borrowed_index = index is not None
        self._indexes: dict[frozenset[str], ProducerIndex] = (
            {} if index is None else {frozenset(): index})

    @property
    def templates(self) -> RequestTemplates:
        """Manifest-derived proposals, built when first used and maintained on installation."""
        if self._templates is None:
            self._templates = RequestTemplates(self.modules)
        return self._templates

    def install(self, modules: Sequence[Module]) -> None:
        """Append providers between decisions; an existing resolved route keeps its priority."""
        added = tuple(modules)
        if not added:
            return
        self.modules += added
        if self._borrowed_index:
            # Detach from the caller's library snapshot before extending our own.
            self._indexes.pop(frozenset(), None)
            self._borrowed_index = False
        for excluded, index in self._indexes.items():
            for module in added:
                if module.manifest.module_id not in excluded:
                    index.append(module)
        if self._providers is not None:
            self._index_providers(added)
        if self._templates is not None:
            for module in added:
                self._templates.add(module)

    def _index_providers(self, modules: Sequence[Module]) -> None:
        if self._providers is None:
            self._providers = {}
        for module in modules:
            ref = module.manifest.ref
            self._providers[ref] = None if ref in self._providers else module

    def _planning_index(self, excluded: frozenset[str]) -> ProducerIndex:
        if excluded not in self._indexes:
            full = self._indexes.get(frozenset())
            if full is None:
                full = self._indexes[frozenset()] = ProducerIndex(self.modules)
            if excluded:
                self._indexes[excluded] = full.without(
                    [p for p, m in enumerate(self.modules) if m.manifest.module_id in excluded])
        return self._indexes[excluded]

    def plan(self, request: Request, chain: tuple[str, ...] = ()) -> Plan | None:
        """Plan with installed manifests, without acquiring or running an expert."""
        excluded = frozenset() if self.recursive else frozenset(chain)
        if request.provider is not None:
            if self._providers is None:
                self._index_providers(self.modules)
            selected = self._providers.get(request.provider)
            if selected is None or selected.manifest.module_id in excluded:
                return None
            index = self._planning_index(excluded) if selected.manifest.contract.slots else None
            return bound_route(selected, request.types, request.type_id, index, self.fuel)
        return plan_stable_indexed(self._planning_index(excluded), request.types, request.type_id, self.fuel,
                                   request.required)

    def resolve(self, request: Request, chain: tuple[str, ...]) -> Plan | None:
        self.requests += 1
        route = self.plan(request, chain)
        if route is not None or self.acquire is None or request.provider is not None:
            return route
        excluded = frozenset() if self.recursive else frozenset(chain)
        usable = [m for m in self.modules if m.manifest.module_id not in excluded]
        repaired = repair(usable, request.types, request.type_id, self.acquire, self.attempts,
                          self.missing, fuel=self.fuel, media=self.media, arity=self.arity,
                          priority=self.priority, required=request.required)
        if repaired is None:
            return None
        self.install(repaired.acquired)
        self.acquired += repaired.acquired
        return repaired.route
