"""The kernel's request resolver.

Mirrors ``NCA.resolve`` (``lean/NCA/Request.lean``): a request is planned with
the stable planner over the installed modules minus every module in the
request chain. Resolution is proved well-typed (``resolve_sound``), never
re-enters the chain (``resolve_avoids``), and nested request chains are no
longer than the number of installed modules (``RequestChain.length_le``).

``Kernel(recursive=True)`` excludes no one, so an expert may ask its own
question again. Termination then rests on the runtime's budgets, which
decrease with every invocation (``NCA.serve``); chain exclusion is the
default.

The library is fixed when the kernel is created. One planner index is kept per
set of excluded modules, so requests from the same chain reuse the plans found
for earlier ones. Each is derived from the index of the whole library, keeping
its results for the modules installed before the first excluded one.
"""

from __future__ import annotations

from collections.abc import Sequence

from nca.abi import Module, Request
from nca.index import ProducerIndex
from nca.planner import Plan, plan_stable_indexed


class Kernel:
    def __init__(self, modules: Sequence[Module], recursive: bool = False) -> None:
        self.modules = tuple(modules)
        self.recursive = recursive
        self.requests = 0
        self._indexes: dict[frozenset[str], ProducerIndex] = {}

    def resolve(self, request: Request, chain: tuple[str, ...]) -> Plan | None:
        self.requests += 1
        excluded = frozenset() if self.recursive else frozenset(chain)
        if excluded not in self._indexes:
            full = self._indexes.setdefault(frozenset(), ProducerIndex(self.modules))
            self._indexes[excluded] = full.without(
                [p for p, m in enumerate(self.modules) if m.manifest.module_id in excluded])
        return plan_stable_indexed(self._indexes[excluded], request.types,
                                   request.type_id)
