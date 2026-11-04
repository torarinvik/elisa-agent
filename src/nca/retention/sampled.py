"""Sampled admission on fresh retained cases (§43.7, Theorem 43.1).

Each decision draws ``m`` unused cases from every affected route's retained
pool and accepts only if the proposal loses none of them. Decision ``k`` spends
``δ / ((k+1)(k+2))`` of the confidence budget, split evenly over its routes,
and ``m`` conservatively covers an outward estimate of ``-log(level)``
(``NCA.zeroLoss_log_upper``), so its cost depends on the tolerance, the confidence
and the decision count (logarithmically), never on how much evidence has been
retained. Cases are consumed once drawn, whatever the outcome, so no case
informs two decisions (``NCA.allocate_fresh``). If each route's pool is an
i.i.d. sample of its operating distribution, the probability that any
decision ever admits an update whose loss rate on an affected route exceeds
``ε`` is at most ``δ`` (``NCA.sampledGate_sound``).
"""

from __future__ import annotations

import math
import random
from collections.abc import Callable, Collection, Sequence
from dataclasses import dataclass

from nca.evidence import Issuers
from nca.memory import MemoryBackend, MemoryRecord
from nca.native import load
from nca.objects import Attestation, Ref
from nca.retention import baselines

_LOG_UPPER = getattr(load("stats"), "negative_log_upper", None)


def decision_level(confidence: float, index: int) -> float:
    """Decision ``index``'s share of the budget; all shares sum to below it."""
    return confidence / ((index + 1) * (index + 2))


def required_cases(tolerance: float, level: float) -> int:
    """Conservative count from an outward estimate of ``-log(level)``.

    Integer-ratio ceiling avoids overflow and downward rounding in division.
    The logarithm bound assumes libm error is within one adjacent binary64
    value; compiler/libm fidelity remains an explicit numerical boundary.
    """
    if not 0 < tolerance < 1 or not 0 < level < 1:
        raise ValueError("tolerance and level must lie in (0, 1)")
    need = (_LOG_UPPER(level) if _LOG_UPPER is not None
            else math.nextafter(-math.log(level), math.inf))
    numerator, denominator = need.as_integer_ratio()
    epsilon, scale = tolerance.as_integer_ratio()
    top, bottom = numerator * scale, denominator * epsilon
    return max(1, (top + bottom - 1) // bottom)


@dataclass(frozen=True)
class SampledRoute:
    identity: str
    records: tuple[Ref, ...]
    """The fresh cases drawn, baseline successes and failures alike."""
    losses: int
    """Drawn cases the proposal loses."""

    @property
    def accepted(self) -> bool:
        return self.losses == 0


@dataclass(frozen=True)
class SampledDecision:
    index: int | None
    """The decision's budget position, or ``None`` if nothing was drawn."""
    cases: int
    routes: tuple[SampledRoute, ...]
    insufficient: tuple[str, ...] = ()
    """Routes without ``cases`` unused records; their presence refuses."""

    @property
    def accepted(self) -> bool:
        return not self.insufficient and all(route.accepted for route in self.routes)


class SampledGate:
    """Sequential sampled admission over durable retained evaluations.

    Pools are shuffled once, before any proposal, with ``seed``; ``add`` appends
    newly retained cases behind every cursor. The caller supplies every affected
    route, and pools must be i.i.d. samples of each route's operating
    distribution for the probability bound to apply.
    """

    def __init__(self, memory: MemoryBackend, retained: Sequence[Attestation],
                 issuers: Issuers, *, tolerance: float, confidence: float, seed: int,
                 max_cases: int) -> None:
        if not 0 < tolerance < 1 or not 0 < confidence < 1:
            raise ValueError("tolerance and confidence must lie in (0, 1)")
        self.tolerance, self.confidence = tolerance, confidence
        self._memory, self._issuers, self._max_cases = memory, issuers, max_cases
        self._random = random.Random(seed)
        self._pools: dict[str, list[tuple[Ref, str]]] = {}
        self._cursors: dict[str, int] = {}
        self._decisions = 0
        self.add(retained)

    def add(self, retained: Sequence[Attestation]) -> None:
        """Append unseen trusted cases, shuffled, behind each route's cursor."""
        for identity, baseline in baselines(retained, self._issuers,
                                            max_cases=self._max_cases).items():
            pool = self._pools.setdefault(identity, [])
            known = dict(pool)
            fresh = []
            for reference, bit in baseline.items():
                if reference in known:
                    if known[reference] != bit:
                        raise ValueError("trusted retained outcomes disagree")
                else:
                    fresh.append((reference, bit))
            self._random.shuffle(fresh)
            pool.extend(fresh)
            self._cursors.setdefault(identity, 0)

    def knows(self, identity: str) -> bool:
        """Whether trusted retained cases were ever added for ``identity``."""
        return identity in self._pools

    @property
    def identities(self) -> tuple[str, ...]:
        return tuple(self._pools)

    def drawn(self, identity: str) -> tuple[Ref, ...]:
        """Cases of ``identity`` already drawn, in draw order: no decision will
        use them again, so they are the first candidates for eviction."""
        return tuple(reference for reference, _ in
                     self._pools.get(identity, ())[:self._cursors.get(identity, 0)])

    def withdraw(self, references: Collection[Ref]) -> dict[str, int]:
        """Remove cases from every pool, as forced deletion requires; returns
        the unused cases each route lost. Later draws come only from what
        remains unused (``NCA.withdraw_fresh``), so fewer cases can mean
        refusals for insufficient evidence, never acceptance without it."""
        gone = frozenset(references)
        lost: dict[str, int] = {}
        for identity, pool in self._pools.items():
            cursor = self._cursors[identity]
            drawn = [case for case in pool[:cursor] if case[0] not in gone]
            unused = [case for case in pool[cursor:] if case[0] not in gone]
            if len(drawn) + len(unused) != len(pool):
                if len(unused) != len(pool) - cursor:
                    lost[identity] = len(pool) - cursor - len(unused)
                self._pools[identity] = drawn + unused
                self._cursors[identity] = len(drawn)
        return lost

    def unused(self, identity: str) -> frozenset[Ref]:
        """Cases of ``identity`` no decision has drawn yet; proposals must not
        be trained on them (``NCA.allocate_skips_drawn``)."""
        pool = self._pools.get(identity, ())
        return frozenset(reference for reference, _ in pool[self._cursors.get(identity, 0):])

    def remaining(self, identity: str) -> int:
        return len(self._pools.get(identity, ())) - self._cursors.get(identity, 0)

    def decide(self, identities: Sequence[str],
               loss: Callable[[str, MemoryRecord, bool], bool]) -> SampledDecision:
        """Admit a proposal only if fresh cases show no loss on any route.

        Refusal for insufficient evidence draws nothing and spends no budget.
        Otherwise cases are consumed before evaluation, so an error still
        retires them. ``loss(identity, record, baseline)`` says whether the
        proposal loses the case, given whether the baseline succeeded on it;
        the usual loss is ``baseline and not correct``, and a caller may count
        further losses (Theorem 43.1 holds for any fixed per-case loss).
        """
        affected = tuple(dict.fromkeys(identities))
        if not affected:
            return SampledDecision(None, 0, ())
        index = self._decisions
        cases = required_cases(self.tolerance,
                               decision_level(self.confidence, index) / len(affected))
        short = tuple(identity for identity in affected if self.remaining(identity) < cases)
        if short:
            return SampledDecision(None, cases, (), short)
        self._decisions += 1
        drawn = {}
        for identity in affected:
            start = self._cursors[identity]
            drawn[identity] = self._pools[identity][start:start + cases]
            self._cursors[identity] = start + cases
        routes = []
        for identity in affected:
            losses = 0
            for reference, bit in drawn[identity]:
                lost = loss(identity, self._memory.get(reference), bit == "1")
                if type(lost) is not bool:
                    raise TypeError("sampled loss must be a boolean")
                losses += lost
            routes.append(SampledRoute(identity, tuple(ref for ref, _ in drawn[identity]),
                                       losses))
        return SampledDecision(index, cases, tuple(routes))
