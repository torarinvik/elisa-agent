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

from collections.abc import Callable, Collection, Mapping, Sequence
from dataclasses import dataclass
from typing import Any

from nca.abi import NOTHING, Demand, Message, Module, SequenceDemand
from nca.cache import Checks, value_digest
from nca.objects import Attestation, Ref, Store
from nca.packages import Export, Requirement, Upcast, charge
from nca.optimize import slot_calls
from nca.planner import Apply, Given, Map, Plan
from nca.router import sign_test
from nca.runtime import Resolver, RiskLedger, execute
from nca.stats import clopper_pearson_upper, family_audit_alpha
from nca.trust import Trust
from nca.workspace import Workspace

EVALUATION = "evaluation"

Issuers = Collection[str] | Trust
"""Whose evaluations to read: a ``Trust`` of keys whose signatures must
verify (§32), or plain issuer names, which nothing authenticates."""


def _trusted(attestation: Attestation, issuers: Issuers) -> bool:
    if isinstance(issuers, Trust):
        return issuers.accepts(attestation)
    return attestation.issuer in issuers


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
             issuers: Issuers) -> tuple[bool, ...] | None:
    """The outcomes of ``identity`` on ``bench`` that ``issuers`` attest, or
    ``None`` if none do; trusted evaluations that disagree are an error."""
    found = {a.claim["outcomes"] for a in store.attestations(identity.partition("#")[0], EVALUATION)
             if _trusted(a, issuers) and a.claim.get("identity") == identity
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


def promote(modules: Sequence[Module], store: Store, bench: Ref, issuers: Issuers,
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
              issuers: Issuers) -> tuple[bool, ...] | None:
    identity = getattr(module, "identity", None)
    return None if identity is None else outcomes(store, identity, bench, issuers)


def error_bound(store: Store, identity: str, bench: Ref, issuers: Issuers,
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


def route_risk(plan: Plan, rate: Callable[[Module], float | None], length: int = 1, *,
               relevant: bool = False) -> float | None:
    """The total charge of ``plan`` when each invocation of an expert costs its
    failure rate ``rate(expert)`` (§31.2): an upper bound on the probability
    of a wrong answer when the rates are in situ, ``length`` bounds every
    mapped sequence and failures propagate (Theorems 31.1, 31.2).

    An export is charged its own route, with its requirements charged
    through the slots that fill them; an upcast returns its input and never
    fails. ``None`` if some invoked expert has no rate, or an expert with
    slots declares no call counts, since then nothing bounds the risk.

    With ``relevant``, only relevant invocations are charged (§31.6): demand
    is propagated from the answer through each expert's ``decides`` rule, or
    its ``demand`` rule, a map's body is charged at each element's demand,
    and an invocation whose output has empty demand costs nothing.
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

    def relevant_charge(node: Plan, demand: Demand) -> float:
        if isinstance(node, Given) or demand == NOTHING:
            return 0.0
        if isinstance(node, Map):
            per = demand.element if isinstance(demand, SequenceDemand) else (lambda i, n: demand)
            return (relevant_charge(node.source, None)
                    + sum(relevant_charge(node.body, per(i, length)) for i in range(length)))
        module = node.module
        rule = getattr(module, "decides", None) or getattr(module, "demand", None)
        calls = slot_calls(module.manifest, length)
        if node.slots and not calls:
            raise ValueError(f"{module.manifest.module_id} declares no slot calls")
        own = (relevant_charge(module.route, None) if isinstance(module, Export) else unit(module))
        return (own + sum(relevant_charge(arg, None if rule is None else rule(i, demand))
                          for i, arg in enumerate(node.args))
                + sum(n * charge(sub, length, unit, strict=True)
                      for n, sub in zip(calls, node.slots)))

    try:
        if relevant:
            return relevant_charge(plan, None)
        return charge(plan, length, unit, strict=True)
    except (_Unknown, ValueError):
        return None


def rates(bounds: Mapping[str, float], length: int = 1) -> Callable[[Module], float | None]:
    """A per-invocation failure rate for every module: ``bounds`` by identity
    for experts, an export's own route charged by ``route_risk``, and 0 for
    upcasts and requirements; ``None`` where nothing bounds it. Passed to
    ``optimize.plan_pareto``, it plans by cost and risk through packages."""
    def rate(module: Module) -> float | None:
        if isinstance(module, Export):
            return route_risk(module.route, rate, length)
        if isinstance(module, (Upcast, Requirement)):
            return 0.0
        identity = getattr(module, "identity", None)
        return None if identity is None else bounds.get(identity)

    return rate


PURITY = "purity"


def purity(identity: str, checks: Checks, issuer: str = "") -> Attestation:
    """An attestation of the spot checks of ``identity``'s cached outputs
    (§32.3): how many were recomputed and how many did not match."""
    claim = {"identity": identity, "checked": checks.checked, "mismatches": checks.mismatches}
    return Attestation(identity.partition("#")[0], PURITY, claim, issuer)


def refuted(store: Store, identity: str, issuers: Issuers) -> bool:
    """Whether an accepted purity attestation reports a mismatch for
    ``identity``: one mismatch refutes a purity declaration."""
    return any(_trusted(a, issuers) and a.claim.get("identity") == identity
               and a.claim.get("mismatches", 0) > 0
               for a in store.attestations(identity.partition("#")[0], PURITY))


EXACT = "exact"


def exact(identity: str, reason: str, issuer: str = "") -> Attestation:
    """An attestation that ``identity`` never fails on correct inputs, by
    ``reason`` (a proof or construction), so it is charged rate 0 (§31.5)."""
    return Attestation(identity.partition("#")[0], EXACT,
                       {"identity": identity, "reason": reason}, issuer)


def _attested_exact(store: Store, identity: str, issuers: Issuers) -> bool:
    return any(_trusted(a, issuers) and a.claim.get("identity") == identity
               for a in store.attestations(identity.partition("#")[0], EXACT))


def _identities(plan: Plan) -> list[str]:
    """The identities of the experts ``plan`` may invoke, inside exports too."""
    found: list[str] = []

    def visit(node: Plan) -> None:
        if isinstance(node, Map):
            visit(node.source)
            visit(node.body)
        elif isinstance(node, Apply):
            module = node.module
            if isinstance(module, Export):
                visit(module.route)
            elif not isinstance(module, (Upcast, Requirement)):
                identity = getattr(module, "identity", None)
                if identity is not None and identity not in found:
                    found.append(identity)
            for child in (*node.args, *node.slots):
                visit(child)

    visit(plan)
    return found


def route_bound(plan: Plan, store: Store, benches: Mapping[str, Ref], issuers: Issuers,
                beta: float, length: int = 1) -> float | None:
    """A bound on ``plan``'s error holding with probability at least
    ``1 - beta`` (Theorem 31.4): experts attested exact are charged 0, and
    ``beta`` is split among the others in proportion to their invocation
    counts, a split fixed by the route before any outcome is read. Each
    expert's rate bound comes from its trusted evaluation on
    ``benches[identity]``, its in-situ benchmark. ``None`` if an expert
    lacks one."""
    identities = _identities(plan)
    audited = [i for i in identities if not _attested_exact(store, i, issuers)]
    counts = {i: route_risk(plan, lambda m, i=i: float(getattr(m, "identity", None) == i),
                            length) for i in audited}
    if any(c is None for c in counts.values()):
        return None
    total = sum(counts.values())
    bounds = {i: 0.0 for i in identities if i not in counts}
    for identity, count in counts.items():
        if not count:  # Never invoked: its rate is never charged.
            bounds[identity] = 0.0
            continue
        bound = (None if identity not in benches else
                 error_bound(store, identity, benches[identity], issuers, beta * count / total))
        if bound is None:
            return None
        bounds[identity] = bound
    return route_risk(plan, rates(bounds, length), length)


def exact_by(store: Store, issuers: Issuers) -> Callable[[Module], bool]:
    """Whether a module has an accepted ``exact`` attestation, for a
    ``RiskLedger``."""
    def exact_module(module: Module) -> bool:
        identity = getattr(module, "identity", None)
        return identity is not None and _attested_exact(store, identity, issuers)

    return exact_module


def answer_within(plan: Plan, inputs: Sequence[Message], delta: float,
                  exact: Callable[[Module], bool] | None = None, budget: int = 10_000,
                  resolver: Resolver | None = None) -> tuple[Any, RiskLedger]:
    """Execute ``plan`` on a risk ledger and give its answer only if every
    invoked expert reported its risk (or is ``exact``) and the total is at
    most ``delta``; otherwise ``None``, an abstention (Theorem 33.2)."""
    ledger = RiskLedger() if exact is None else RiskLedger(exact)
    answer = execute(plan, inputs, Workspace(), budget, resolver, ledger=ledger).payload
    return (answer if ledger.certified and ledger.charge <= delta else None), ledger


def refine_within(plan: Plan, inputs: Sequence[Message], delta: float,
                  exact: Callable[[Module], bool] | None = None, budget: int = 10_000,
                  resolver: Resolver | None = None) -> tuple[Any, RiskLedger, int]:
    """``answer_within`` with refinement (§33.3): while the ledger exceeds
    ``delta``, raise the charged invocation with the largest report whose
    expert can ``refine`` its inputs, and execute again. Returns the answer
    (``None`` if no climb is left), the final ledger and the number of
    executions, at most the bound of Theorem 33.3."""
    executions = 0
    while True:
        answer, ledger = answer_within(plan, inputs, delta, exact, budget, resolver)
        executions += 1
        if not ledger.certified or ledger.charge <= delta:
            return answer, ledger, executions
        for module, values, _ in sorted(ledger.entries, key=lambda e: -e[2]):
            climb = getattr(module, "refine", None)
            if climb is not None and climb(*values):
                break
        else:
            return None, ledger, executions
