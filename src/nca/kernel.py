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

Otherwise the library is fixed when the kernel is created. One planner index is kept per
set of excluded modules, so requests from the same chain reuse the plans found
for earlier ones. Each is derived from the index of the whole library, keeping
its results for the modules installed before the first excluded one.
"""

from __future__ import annotations

from collections.abc import Sequence

from nca.abi import Module, Request, TypeId
from nca.index import ProducerIndex
from nca.planner import Plan, plan_stable_indexed
from nca.planner.gaps import Acquire, repair


class Kernel:
    def __init__(self, modules: Sequence[Module], recursive: bool = False,
                 index: ProducerIndex | None = None, acquire: Acquire | None = None,
                 attempts: int = 8, missing: int = 1,
                 media: Sequence[TypeId] | None = None) -> None:
        """``index``, if given, must index exactly ``modules``; it is shared.
        ``acquire`` is asked at most ``attempts`` times per request, for
        routes needing at most ``missing`` new connectors, inventing media
        grown over the types in ``media`` if given."""
        self.modules = tuple(modules)
        self.acquire, self.attempts, self.missing = acquire, attempts, missing
        self.media = media
        self.acquired: list[Module] = []
        self.recursive = recursive
        self.requests = 0
        self._indexes: dict[frozenset[str], ProducerIndex] = (
            {} if index is None else {frozenset(): index})

    def resolve(self, request: Request, chain: tuple[str, ...]) -> Plan | None:
        self.requests += 1
        excluded = frozenset() if self.recursive else frozenset(chain)
        if excluded not in self._indexes:
            full = self._indexes.setdefault(frozenset(), ProducerIndex(self.modules))
            self._indexes[excluded] = full.without(
                [p for p, m in enumerate(self.modules) if m.manifest.module_id in excluded])
        route = plan_stable_indexed(self._indexes[excluded], request.types, request.type_id)
        if route is not None or self.acquire is None:
            return route
        usable = [m for m in self.modules if m.manifest.module_id not in excluded]
        repaired = repair(usable, request.types, request.type_id, self.acquire, self.attempts,
                          self.missing, media=self.media)
        if repaired is None:
            return None
        self.modules += repaired.acquired
        self.acquired += repaired.acquired
        self._indexes.clear()
        return repaired.route
