"""Replay trusted retained evaluations before committing proposed updates (§43.4).

The caller supplies all affected routes and the evaluator of proposed versions.
This checks finite retained cases; it neither installs updates nor certifies
population non-regression after adaptive reuse of those cases.
"""

from __future__ import annotations

from collections.abc import Callable, Sequence
from dataclasses import dataclass

from nca.evidence import EVALUATION, Issuers, benchmark, trusted
from nca.memory import MemoryBackend, MemoryRecord
from nca.objects import Attestation, Ref


@dataclass(frozen=True)
class ReplayResult:
    identity: str
    records: tuple[Ref, ...]
    outcomes: tuple[bool, ...]
    losses: int
    wins: int
    accepted: bool


@dataclass(frozen=True)
class ReplayGate:
    routes: tuple[ReplayResult, ...]

    @property
    def accepted(self) -> bool:
        return all(route.accepted for route in self.routes)


def baselines(retained: Sequence[Attestation], issuers: Issuers, *,
              max_cases: int) -> dict[str, dict[Ref, str]]:
    """Each route's trusted baseline bits by record, merged in first-seen order.

    Untrusted, malformed or conflicting assertions and more than ``max_cases``
    distinct route/record pairs are errors.
    """
    frozen: dict[str, dict[Ref, str]] = {}
    cases = 0
    for attestation in tuple(retained):
        if attestation.kind != EVALUATION or not trusted(attestation, issuers):
            raise ValueError("replay requires trusted evaluation attestations")
        claim = attestation.claim
        identity = claim.get("identity")
        records = claim.get("records")
        bits = claim.get("outcomes")
        if (
            not isinstance(identity, str)
            or not identity
            or identity.partition("#")[0] != attestation.subject
            or not isinstance(records, (list, tuple))
            or not records
            or any(not isinstance(ref, str) for ref in records)
            or len(set(records)) != len(records)
            or not isinstance(bits, str)
            or len(bits) != len(records)
            or any(bit not in "01" for bit in bits)
            or benchmark(records) != claim.get("benchmark")
        ):
            raise ValueError("invalid retained evaluation")
        baseline = frozen.setdefault(identity, {})
        for reference, bit in zip(records, bits, strict=True):
            if reference in baseline:
                if baseline[reference] != bit:
                    raise ValueError("trusted retained outcomes disagree")
                continue
            baseline[reference] = bit
            cases += 1
            if cases > max_cases:
                raise ValueError("retained replay exceeds case budget")
    return frozen


def replay_gate(
    memory: MemoryBackend,
    retained: Sequence[Attestation],
    issuers: Issuers,
    evaluate: Callable[[str, MemoryRecord], bool],
    *,
    max_cases: int,
    max_losses: int = 0,
) -> ReplayGate:
    """Score proposed versions against each trusted baseline's durable records.

    Freeze/validate attestation metadata before callbacks; load records as scored.
    ``max_cases`` bounds distinct route/record pairs, not callback work, I/O
    bytes or runtime invocation cost. The
    evaluator must enforce its own resources/permissions and version selection.
    Callbacks must not install updates or repeat irreversible actions. Read
    permission is needed for memory access. Any error prevents a result;
    there is no partially accepted update. Empty families cover no old routes.
    """
    for value in (max_cases, max_losses):
        if isinstance(value, bool) or not isinstance(value, int) or value < 0:
            raise ValueError("replay budgets must be nonnegative integers")
    frozen = baselines(retained, issuers, max_cases=max_cases)
    results = []
    for identity, baseline in frozen.items():
        references, bits = tuple(baseline), tuple(baseline.values())
        outcomes = []
        for reference in references:
            answer = evaluate(identity, memory.get(reference))
            if type(answer) is not bool:
                raise TypeError("replay evaluator must return a correctness boolean")
            outcomes.append(answer)
        losses = sum(old == "1" and not new for old, new in zip(bits, outcomes, strict=True))
        wins = sum(old == "0" and new for old, new in zip(bits, outcomes, strict=True))
        results.append(
            ReplayResult(identity, references, tuple(outcomes), losses, wins, losses <= max_losses)
        )
    return ReplayGate(tuple(results))
