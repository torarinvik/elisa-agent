"""Evidence-preserving eviction of episodic records (§43.11).

Memory is bounded, so records must eventually be removed. A record is
*protected* while a gate may still rely on it: it is named by a retained
evaluation of a route catalog (exact replay scores every such record), or it is
a case a sampled gate has not drawn yet. Ordinary eviction never removes a
protected record (``NCA.evict_keeps_protected``). The preferred candidates are
cases sampled gates have already drawn, which no decision will use again,
then unprotected records oldest first. A forced removal, such as a deletion
request, removes protected records too, but withdraws them from the sampler
and reports the routes whose evidence shrank: their gates then refuse for
insufficient or missing evidence rather than accept without it
(``NCA.withdraw_fresh``). Records that other records name as parents are kept.
"""

from __future__ import annotations

from collections.abc import Collection, Mapping, Sequence
from dataclasses import dataclass, field

from nca.memory import MemoryBackend
from nca.objects import Ref
from nca.retention.routes import RouteCatalog
from nca.retention.sampled import SampledGate


@dataclass(frozen=True)
class Eviction:
    removed: tuple[Ref, ...]
    freed: int
    """Logical bytes released."""
    kept: tuple[Ref, ...]
    """Candidates left in place: protected (unless forced) or parents."""
    withdrawn: Mapping[str, int] = field(default_factory=dict)
    """Forced only: unused sampled cases each route lost."""
    unprotected: tuple[str, ...] = ()
    """Forced only: catalog anchors whose retained evaluations name a removed
    record; exact replay of those routes now fails rather than accepts."""


def protected(catalog: RouteCatalog | None = None, sampler: SampledGate | None = None,
              pending: Collection[Ref] = ()) -> frozenset[Ref]:
    """Records a gate may still rely on, plus ``pending`` records the caller
    has stored but not yet handed to a gate."""
    found: set[Ref] = set(pending)
    if catalog is not None:
        for attestation in catalog.retained:
            found.update(attestation.claim.get("records") or ())
    if sampler is not None:
        for identity in sampler.identities:
            found.update(sampler.unused(identity))
    return frozenset(found)


def candidates(memory: MemoryBackend, guard: frozenset[Ref],
               sampler: SampledGate | None = None, *, page: int = 1024) -> list[Ref]:
    """Eviction order: drawn sampled cases first, then other unprotected
    records in append order."""
    order: dict[Ref, None] = {}
    if sampler is not None:
        for identity in sampler.identities:
            order.update((ref, None) for ref in sampler.drawn(identity) if ref not in guard)
    after = 0
    while rows := memory.scan(after=after, limit=page):
        order.update((ref, None) for _, ref in rows if ref not in guard)
        after = rows[-1][0]
    return list(order)


def evict(memory: MemoryBackend, requested: Sequence[Ref], *,
          catalog: RouteCatalog | None = None, sampler: SampledGate | None = None,
          forced: bool = False, needed: int | None = None,
          pending: Collection[Ref] = ()) -> Eviction:
    """Remove ``requested`` records in order, stopping once ``needed`` bytes are
    freed if given. Without ``forced``, protected and pending records are kept."""
    guard = protected(catalog, sampler, pending)
    removed, kept, freed = [], [], 0
    for reference in dict.fromkeys(requested):
        if needed is not None and freed >= needed:
            break
        if reference in guard and not forced:
            kept.append(reference)
            continue
        try:
            freed += memory.remove(reference)
        except ValueError:
            kept.append(reference)
            continue
        removed.append(reference)
    withdrawn: dict[str, int] = {}
    unprotected: tuple[str, ...] = ()
    gone = frozenset(removed)
    if sampler is not None and gone:
        # Removed drawn cases leave the pools too; only unused ones count as lost.
        withdrawn = sampler.withdraw(gone)
    if forced and gone:
        if catalog is not None:
            unprotected = tuple(dict.fromkeys(
                attestation.claim["identity"] for attestation in catalog.retained
                if gone.intersection(attestation.claim.get("records") or ())))
    return Eviction(tuple(removed), freed, tuple(kept), withdrawn, unprotected)
