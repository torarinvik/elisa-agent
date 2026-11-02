"""Selection among substitutes by attested evaluations (THEORY §30).

An *evaluation* is an attestation that an expert, identified by its content
identity, was right or wrong on each sample of a benchmark, a labeled
sample sequence identified by its digest. ``promote`` reads the
evaluations of trusted issuers and, for each contract, tests every
substitute with evidence against the incumbent (the first expert with that
contract) by the exact sign test of §8 at level ``α / k``; the challenger
with the smallest p-value among those accepted exchanges places with the
incumbent. Planning commutes with that exchange (``NCA.planShallowStable_rename``),
so every route through the incumbent then uses the challenger and no other
route changes.

``error_bound`` turns an evaluation into an upper confidence bound on an
expert's failure rate, and ``route_risk`` charges each invocation of a route
its expert's rate, through maps, slots and packages, which bounds the
probability of a wrong answer (§31).
"""

from __future__ import annotations

from collections.abc import Callable, Collection, Sequence
from dataclasses import dataclass
from typing import Any

from nca.abi import Module
from nca.cache import value_digest
from nca.objects import Attestation, Ref, Store
from nca.packages import Export, Requirement, Upcast, charge
from nca.planner import Plan
from nca.router import sign_test
from nca.stats import clopper_pearson_upper, family_audit_alpha

EVALUATION = "evaluation"


def benchmark(samples: Sequence[Any]) -> Ref:
    """The identity of a benchmark: the digest of its samples, in order."""
    found = value_digest(list(samples))
    if found is None:
        raise ValueError("benchmark samples have no canonical encoding")
    return found


def evaluation(identity: str, bench: Ref, outcomes: Sequence[bool],
               issuer: str = "") -> Attestation:
    """An attestation that the expert ``identity`` was right (``True``) or
    wrong on each sample of ``bench``. Its subject is the stored object the
    identity names: the expert, or the composite an export belongs to."""
    subject = identity.partition("#")[0]
    claim = {"identity": identity, "benchmark": bench,
             "outcomes": "".join("1" if o else "0" for o in outcomes)}
    return Attestation(subject, EVALUATION, claim, issuer)


def outcomes(store: Store, identity: str, bench: Ref,
             issuers: Collection[str]) -> tuple[bool, ...] | None:
    """The outcomes of ``identity`` on ``bench`` that ``issuers`` attest, or
    ``None`` if none do; trusted evaluations that disagree are an error."""
    found = {a.claim["outcomes"] for a in store.attestations(identity.partition("#")[0], EVALUATION)
             if a.issuer in issuers and a.claim.get("identity") == identity
             and a.claim.get("benchmark") == bench}
    if len(found) > 1:
        raise ValueError(f"trusted evaluations of {identity} on {bench} disagree")
    return tuple(c == "1" for c in found.pop()) if found else None


@dataclass(frozen=True)
class Promotion:
    incumbent: Module
    challenger: Module
    wins: int
    """Samples only the challenger got right."""
    losses: int
    """Samples only the incumbent got right."""
    p_value: float
    level: float
    """The level the test was run at: ``α`` over the number of challengers."""


def promote(modules: Sequence[Module], store: Store, bench: Ref, issuers: Collection[str],
            alpha: float = 0.05) -> tuple[list[Module], list[Promotion]]:
    """``modules`` with each contract's incumbent exchanged for the best
    challenger the evidence supports, and the promotions made. Experts
    without an identity or without a trusted evaluation on ``bench`` are
    neither tested nor tested against."""
    library = list(modules)
    promotions: list[Promotion] = []
    decided = set()
    for i, incumbent in enumerate(library):
        contract = incumbent.manifest.contract
        if contract in decided:
            continue
        decided.add(contract)
        base = _outcomes(incumbent, store, bench, issuers)
        if base is None:
            continue
        challengers = [(j, m, found) for j, m in enumerate(library[i + 1:], i + 1)
                       if m.manifest.contract == contract
                       and (found := _outcomes(m, store, bench, issuers)) is not None]
        if any(len(found) != len(base) for _, _, found in challengers):
            raise ValueError(f"evaluations on {bench} have different lengths")
        if not challengers:
            continue
        level = family_audit_alpha(alpha, len(challengers))
        best: tuple[float, int, tuple[bool, ...]] | None = None
        for j, _, found in challengers:
            accepted, p_value = sign_test(base, found, level)
            if accepted and (best is None or p_value < best[0]):
                best = (p_value, j, found)
        if best is None:
            continue
        p_value, j, found = best
        promotions.append(Promotion(
            incumbent, library[j], sum(c and not o for o, c in zip(base, found)),
            sum(o and not c for o, c in zip(base, found)), p_value, level))
        library[i], library[j] = library[j], library[i]
    return library, promotions


def _outcomes(module: Module, store: Store, bench: Ref,
              issuers: Collection[str]) -> tuple[bool, ...] | None:
    identity = getattr(module, "identity", None)
    return None if identity is None else outcomes(store, identity, bench, issuers)


def error_bound(store: Store, identity: str, bench: Ref, issuers: Collection[str],
                beta: float) -> float | None:
    """An upper bound, holding with probability at least ``1 - beta``, on the
    failure rate of ``identity`` on ``bench``'s distribution (Clopper–Pearson),
    or ``None`` without a trusted evaluation. It is the in-situ rate of §31
    only if ``bench`` samples the inputs the expert receives in the route."""
    found = outcomes(store, identity, bench, issuers)
    if found is None:
        return None
    return clopper_pearson_upper(found.count(False), len(found), beta)


class _Unknown(Exception):
    pass


def route_risk(plan: Plan, rate: Callable[[Module], float | None], length: int = 1) -> float | None:
    """The total charge of ``plan`` when each invocation of an expert costs its
    failure rate ``rate(expert)`` (§31.2): an upper bound on the probability
    of a wrong answer when the rates are in situ, ``length`` bounds every
    mapped sequence and failures propagate (Theorems 31.1, 31.2).

    An export is charged its own route, with its requirements charged
    through the slots that fill them; an upcast returns its input and never
    fails. ``None`` if some invoked expert has no rate, or an expert with
    slots declares no call counts, since then nothing bounds the risk.
    """
    def unit(module: Module) -> float:
        if isinstance(module, Export):
            return charge(module.route, length, unit, strict=True)
        if isinstance(module, (Upcast, Requirement)):
            return 0.0
        found = rate(module)
        if found is None:
            raise _Unknown
        return found

    try:
        return charge(plan, length, unit, strict=True)
    except (_Unknown, ValueError):
        return None
