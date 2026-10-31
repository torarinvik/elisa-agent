"""The kernel's request resolver.

Mirrors ``NCA.resolve`` (``lean/NCA/Request.lean``): a request is planned with
the stable planner over the installed modules minus every module in the
request chain. Resolution is proved well-typed (``resolve_sound``), never
re-enters the chain (``resolve_avoids``), and nested request chains are no
longer than the number of installed modules (``RequestChain.length_le``).
"""

from __future__ import annotations

from collections.abc import Sequence

from nca.abi import Request
from nca.planner import Plan, plan_stable
from nca.registry import Module


class Kernel:
    def __init__(self, modules: Sequence[Module]) -> None:
        self.modules = list(modules)
        self.requests = 0

    def resolve(self, request: Request, chain: tuple[str, ...]) -> Plan | None:
        self.requests += 1
        candidates = [m for m in self.modules if m.manifest.module_id not in chain]
        return plan_stable(candidates, tuple(request.inputs), request.type_id)
