"""Consolidation of corrected pieces into compact ones (§43.10).

A piece that has accumulated local corrections is replaced by a compact piece
a caller's distiller fits to the current piece's own behavior: each training
record is decoded and run through a route that uses the piece, recording
the piece's inputs and outputs, so consolidation needs no new labels. The
replacement is published only through the catalog's gate on every dependent
route (``NCA.published_only_if_admitted``). With a sampled gate, training
records must already have been drawn: training on cases the gate may still
draw would make the proposal depend on its own test cases, breaking Theorem
43.1 (``NCA.allocate_skips_drawn``). An admitted replacement leaves the old
piece with no protected dependents; it is reported as retirable, not deleted.
"""

from __future__ import annotations

from collections.abc import Callable, Sequence
from dataclasses import dataclass
from typing import Any

from nca.abi import Module
from nca.effects import invoke_scoped
from nca.evidence import Issuers
from nca.memory import MemoryBackend
from nca.objects import Ref
from nca.planner import Plan
from nca.retention.routes import GuardedUpdate, RouteCatalog, _rewrite
from nca.retention.sampled import SampledGate
from nca.runtime import RiskLedger, execute
from nca.workspace import Workspace

Example = tuple[tuple[Any, ...], Any]
"""One recorded invocation of the piece: its inputs and its output."""


class _Recorder:
    """Forwards to ``inner``, recording each invocation's inputs and output."""

    def __init__(self, inner: Module, examples: list[Example]) -> None:
        self._inner, self._examples = inner, examples

    def __getattr__(self, name: str) -> Any:
        return getattr(self._inner, name)

    def invoke(self, *values: Any) -> Any:
        output = invoke_scoped(self._inner, *values)
        self._examples.append((values, output))
        return output


@dataclass(frozen=True)
class Consolidation:
    update: GuardedUpdate
    candidate: Module
    examples: int
    """Recorded invocations the distiller was given."""
    retired: tuple[Module, ...]
    """Replaced pieces left without protected dependents."""

    @property
    def accepted(self) -> bool:
        return self.update.accepted


def record(catalog: RouteCatalog, piece: Module, training: Sequence[tuple[str, Ref]],
           memory: MemoryBackend, *, budget: int) -> list[Example]:
    """The piece's inputs and outputs when each ``(anchor, record)`` runs
    through that protected route's current plan."""
    examples: list[Example] = []
    recorder = _Recorder(piece, examples)
    plans: dict[str, Plan] = {}
    for anchor, reference in training:
        route = catalog.routes[anchor]
        if anchor not in catalog.dependents(piece):
            raise ValueError("training routes must use the consolidated piece")
        if anchor not in plans:
            plans[anchor] = _rewrite(route.plan, {id(piece): recorder}, {})
        messages, _ = route.decode(memory.get(reference))
        execute(plans[anchor], tuple(messages), Workspace(), budget, route.resolver,
                ledger=RiskLedger())
    return examples


def consolidate(catalog: RouteCatalog, piece: Module,
                distill: Callable[[Sequence[Example]], Module],
                training: Sequence[tuple[str, Ref]], memory: MemoryBackend,
                issuers: Issuers, *, budget: int, max_cases: int,
                sampler: SampledGate | None = None) -> Consolidation:
    """Distill ``piece`` from recorded behavior and publish it only if the gate
    admits it on every protected route that uses ``piece``."""
    training = tuple(training)
    if sampler is not None:
        affected = catalog.dependents(piece)
        unused = frozenset().union(*(sampler.unused(anchor) for anchor in affected))
        if any(reference in unused for _, reference in training):
            raise ValueError("consolidation must not train on cases the gate has not drawn")
    examples = record(catalog, piece, training, memory, budget=budget)
    candidate = distill(examples)
    if candidate.manifest.contract != piece.manifest.contract:
        raise ValueError("the consolidated piece must keep the replaced contract")
    update = catalog.replace(((piece, candidate),), memory, issuers, max_cases=max_cases,
                             budget=budget, sampler=sampler)
    retired = (piece,) if update.accepted and not update.catalog.dependents(piece) else ()
    return Consolidation(update, candidate, len(examples), retired)
