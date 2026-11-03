"""Evaluation, purity and exactness claims under supplied issuer policies."""
from __future__ import annotations

from collections.abc import Collection, Sequence
from typing import Any

from nca.cache import Checks, value_digest
from nca.objects import Attestation, Json, Ref, Store
from nca.trust import Trust


EVALUATION = "evaluation"


Issuers = Collection[str] | Trust


"""Whose evaluations to read: a ``Trust`` of keys whose signatures must
verify (§32), or plain issuer names, which nothing authenticates."""


def trusted(attestation: Attestation, issuers: Issuers) -> bool:
    """Whether an attestation is accepted by the supplied issuer/trust policy."""
    if isinstance(issuers, Trust):
        return issuers.accepts(attestation)
    if isinstance(issuers, (str, bytes)):
        raise TypeError("issuer policy must be a collection of names, not one string")
    return attestation.issuer in issuers


def benchmark(samples: Sequence[Any]) -> Ref:
    """The identity of a benchmark: the digest of its samples, in order."""
    found = value_digest(list(samples))
    if found is None:
        raise ValueError("benchmark samples have no canonical encoding")
    return found


def evaluation(identity: str, bench: Ref, outcomes: Sequence[bool],
               issuer: str = "", *, records: Sequence[Ref] | None = None) -> Attestation:
    """An attestation that the expert ``identity`` was right (``True``) or
    wrong on each sample of ``bench``. Its subject is the stored object the
    identity names: the expert, or the composite an export belongs to.
    Optional ``records`` bind an ordered durable-memory benchmark; payload
    interpretation and truthful correctness remain the issuer's claim."""
    subject = identity.partition("#")[0]
    claim: dict[str, Json] = {"identity": identity, "benchmark": bench,
             "outcomes": "".join("1" if o else "0" for o in outcomes)}
    if records is not None:
        records = tuple(records)
        if (not records or len(records) != len(outcomes)
                or any(not isinstance(ref, str) for ref in records)
                or any(type(outcome) is not bool for outcome in outcomes)
                or len(set(records)) != len(records)
                or benchmark(records) != bench):
            raise ValueError("retained evaluation needs distinct aligned benchmark records")
        claim["records"] = list(records)
    return Attestation(subject, EVALUATION, claim, issuer)


def outcomes(store: Store, identity: str, bench: Ref,
             issuers: Issuers) -> tuple[bool, ...] | None:
    """The outcomes of ``identity`` on ``bench`` that ``issuers`` attest, or
    ``None`` if none do; trusted evaluations that disagree are an error."""
    found = {a.claim["outcomes"] for a in store.attestations(identity.partition("#")[0], EVALUATION)
             if trusted(a, issuers) and a.claim.get("identity") == identity
             and a.claim.get("benchmark") == bench}
    if len(found) > 1:
        raise ValueError(f"trusted evaluations of {identity} on {bench} disagree")
    return tuple(c == "1" for c in found.pop()) if found else None


PURITY = "purity"


def purity(identity: str, checks: Checks, issuer: str = "") -> Attestation:
    """An attestation of the spot checks of ``identity``'s cached outputs
    (§32.3): how many were recomputed and how many did not match."""
    claim = {"identity": identity, "checked": checks.checked, "mismatches": checks.mismatches}
    return Attestation(identity.partition("#")[0], PURITY, claim, issuer)


def refuted(store: Store, identity: str, issuers: Issuers) -> bool:
    """Whether an accepted purity attestation reports a mismatch for
    ``identity``: one mismatch refutes a purity declaration."""
    return any(trusted(a, issuers) and a.claim.get("identity") == identity
               and a.claim.get("mismatches", 0) > 0
               for a in store.attestations(identity.partition("#")[0], PURITY))


EXACT = "exact"


def exact(identity: str, reason: str, issuer: str = "") -> Attestation:
    """An attestation that ``identity`` never fails on correct inputs, by
    ``reason`` (a proof or construction), so it is charged rate 0 (§31.5)."""
    return Attestation(identity.partition("#")[0], EXACT,
                       {"identity": identity, "reason": reason}, issuer)


def _attested_exact(store: Store, identity: str, issuers: Issuers) -> bool:
    return any(trusted(a, issuers) and a.claim.get("identity") == identity
               for a in store.attestations(identity.partition("#")[0], EXACT))
