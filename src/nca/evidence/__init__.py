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

from collections.abc import Callable, Mapping, Sequence
from dataclasses import dataclass
from typing import Any

from nca.abi import NOTHING, Demand, Message, Module, SequenceDemand, TypeId
from nca.cache import ResultCache, value_digest
from nca.compile import compile_route
from nca.objects import Attestation, Ref, Store
from nca.packages import Export, Requirement, Upcast, charge
from nca.optimize import slot_calls
from nca.planner import Apply, Given, Map, Plan
from nca.router import sign_test
from nca.runtime import Invocation, Resolver, RiskLedger, execute
from nca.stats import clopper_pearson_upper, family_audit_alpha, poisson_binomial_upper_bound
from nca.workspace import Workspace
from nca.evidence.attestations import (
    EVALUATION as EVALUATION,
    PURITY as PURITY,
    EXACT as EXACT,
    Issuers as Issuers,
    trusted as trusted,
    benchmark as benchmark,
    evaluation as evaluation,
    outcomes as outcomes,
    purity as purity,
    refuted as refuted,
    exact as exact,
    _attested_exact as _attested_exact,
)


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
        promotions.append(_promotion(incumbent, library[j], base, found, p_value, level))
        library[i], library[j] = library[j], library[i]
    return library, promotions


def _promotion(incumbent: Module, challenger: Module, base: Sequence[bool],
               found: Sequence[bool], p_value: float, level: float) -> Promotion:
    return Promotion(incumbent, challenger, sum(c and not o for o, c in zip(base, found)),
                     sum(o and not c for o, c in zip(base, found)), p_value, level)


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


def refine_batch(plan: Plan, available: Sequence[TypeId], rows: Sequence[tuple[Any, ...]],
                 delta: float, exact: Callable[[Module], bool] | None = None,
                 cache: ResultCache | None = None) -> tuple[list[Any], list[RiskLedger], int]:
    """``refine_within`` for a batch of rows on the compiled route (§34.4).

    Each round evaluates the undecided rows together; each row over
    ``delta`` raises its charged invocation with the largest report whose
    expert can climb, a climb shared by several rows being made once per
    round. Returns the answers (``None`` for abstentions), each row's final
    ledger and the number of rounds."""
    compiled = compile_route(plan, available)
    answers: list[Any] = [None] * len(rows)
    ledgers: list[RiskLedger] = [RiskLedger() for _ in rows]
    pending = list(range(len(rows)))
    rounds = 0
    while pending:
        rounds += 1
        fresh = [RiskLedger() if exact is None else RiskLedger(exact) for _ in pending]
        outputs = compiled([rows[j] for j in pending], cache=cache, ledgers=fresh)
        climbed: set[tuple[int, str | None]] = set()
        undecided = []
        for j, output, ledger in zip(pending, outputs, fresh, strict=True):
            ledgers[j] = ledger
            if not ledger.certified:
                continue
            if ledger.charge <= delta:
                answers[j] = output
                continue
            for module, values, _ in sorted(ledger.entries, key=lambda e: -e[2]):
                climb = getattr(module, "refine", None)
                if climb is None:
                    continue
                key = (id(module), value_digest(list(values)))
                if key in climbed or climb(*values):
                    climbed.add(key)
                    undecided.append(j)
                    break
        pending = undecided
    return answers, ledgers, rounds


@dataclass(frozen=True)
class Audit:
    """Reports compared with failures on audited invocations of one expert (§35.1)."""

    invocations: int
    reported: float
    failures: int
    p_value: float
    """A bound on the probability of at least ``failures`` failures if the
    reports are calibrated."""

    def refutes(self, alpha: float) -> bool:
        """Whether the audit refutes calibration at level ``alpha``."""
        return self.p_value <= alpha


def audit(reports: Sequence[float], failures: Sequence[bool], independent: bool = True) -> Audit:
    """Audit reports against failures (Theorems 35.1–35.2). With
    ``independent`` the failures must be conditionally independent given
    the observations; otherwise the weaker bound ``R / F`` is used."""
    if len(reports) != len(failures):
        raise ValueError("an audit needs one failure flag per report")
    if any(not 0.0 <= r <= 1.0 for r in reports):
        raise ValueError("reports must be probabilities")
    failed = sum(bool(f) for f in failures)
    reported = float(sum(reports))
    if independent:
        p_value = poisson_binomial_upper_bound(failed, list(reports))
    else:
        p_value = 1.0 if failed == 0 else min(1.0, reported / failed)
    return Audit(len(reports), reported, failed, p_value)


def recalibrate(rung: Any, values: Sequence[Any], labels: Sequence[int], subject: Ref,
                issuer: str, alpha: float, independent: bool = True
                ) -> tuple[Attestation | None, Audit]:
    """Refit ``rung``'s expert on the first half of an audit's labeled values
    and audit the refit on the second half (§35.2). Returns a calibration
    attestation about ``subject`` if that audit does not refute the refit at
    ``alpha``, and the audit."""
    import torch

    from nca.ladder import Calibrated, Rung, calibration

    half = len(values) // 2
    if half == 0 or len(labels) != len(values):
        raise ValueError("recalibration needs at least two labeled values")
    refit = Rung(rung.module)
    refit.calibrate(list(values[:half]), torch.tensor(list(labels[:half])))
    reader = Calibrated(refit)
    outputs = [reader.invoke(value) for value in values[half:]]
    result = audit([reader.risk(output) for output in outputs],
                   [max(range(len(o)), key=o.__getitem__) != label
                    for o, label in zip(outputs, labels[half:], strict=True)], independent)
    return (None if result.refutes(alpha) else calibration(refit, subject, issuer=issuer)), result


def hotspots(ledgers: Sequence[RiskLedger]) -> list[tuple[Module, float]]:
    """Each charged expert with its total report over ``ledgers``, largest
    first: where a better expert lowers the route's risk most (§36.1)."""
    totals: dict[int, list[Any]] = {}
    for ledger in ledgers:
        for module, _, report in ledger.entries:
            totals.setdefault(id(module), [module, 0.0])[1] += report
    return sorted(((m, t) for m, t in totals.values()), key=lambda entry: -entry[1])


@dataclass(frozen=True)
class Acquisition:
    challenger: Module
    incumbent_outcomes: tuple[bool, ...]
    challenger_outcomes: tuple[bool, ...]
    """Each expert's correctness on the evaluation part, in order, which a
    caller may attest with ``evaluation`` for experts that are stored objects."""
    promotion: Promotion | None
    """The promotion made, or ``None`` if the evidence did not support one."""


def acquire(incumbent: Module, train: Callable[[Sequence[Any], Sequence[Any]], Module],
            values: Sequence[Any], labels: Sequence[Any],
            correct: Callable[[Any, Any], bool], alpha: float = 0.05) -> Acquisition:
    """Train a challenger for ``incumbent``'s contract on the first half of
    the labeled ``values`` and promote it if the paired sign test of
    ``promote`` on the second half supports it at ``alpha`` (Theorem 36.1).
    ``correct(output, label)`` scores an output."""
    half = len(values) // 2
    if half == 0 or len(labels) != len(values):
        raise ValueError("acquisition needs at least two labeled values")
    challenger = train(values[:half], labels[:half])
    if challenger.manifest.contract != incumbent.manifest.contract:
        raise ValueError("the challenger must have the incumbent's contract")
    held = list(zip(values[half:], labels[half:], strict=True))
    base = tuple(correct(incumbent.invoke(v), y) for v, y in held)
    found = tuple(correct(challenger.invoke(v), y) for v, y in held)
    accepted, p_value = sign_test(base, found, alpha)
    promotion = _promotion(incumbent, challenger, base, found, p_value, alpha) if accepted else None
    return Acquisition(challenger, base, found, promotion)


def sample_invocations(ledgers: Sequence[RiskLedger], rate: float, seed: int = 0,
                       select: Callable[[Module], bool] | None = None) -> list[Invocation]:
    """Keep each charged invocation of a selected expert in ``ledgers`` with
    probability ``rate``, by coins independent of everything else: an
    in-situ audit sample (Theorem 38.1)."""
    import random

    if not 0.0 <= rate <= 1.0:
        raise ValueError("the sampling rate must be a probability")
    coins = random.Random(seed)
    return [invocation for ledger in ledgers for invocation in ledger.invocations
            if (select is None or select(invocation.expert)) and coins.random() < rate]


def audit_invocations(invocations: Sequence[Invocation], labels: Sequence[Any],
                      correct: Callable[[Any, Any], bool], independent: bool = True) -> Audit:
    """``audit`` of sampled invocations, given a label for each."""
    if len(labels) != len(invocations):
        raise ValueError("an audit needs one label per invocation")
    return audit([i.report for i in invocations],
                 [not correct(i.output, label) for i, label in zip(invocations, labels)],
                 independent)


def cross_audit(invocations: Sequence[Invocation], reference: Module,
                same: Callable[[Any, Any], bool], independent: bool = True) -> Audit:
    """Audit sampled invocations against a reference expert with the same
    contract instead of labels (Theorem 40.1): the reference is invoked on
    each invocation's inputs, ``same`` compares the two decisions, and the
    disagreements are audited against the sums of both reports. A refutation
    means at least one of the two is miscalibrated."""
    reports, disagreements = [], []
    for invocation in invocations:
        if invocation.expert.manifest.contract != reference.manifest.contract:
            raise ValueError("the reference must have the audited expert's contract")
        output = reference.invoke(*invocation.values)
        report = getattr(reference, "risk", None)
        second = None if report is None else report(output, *invocation.values)
        if second is None:
            raise ValueError(f"{reference.manifest.ref} reports no risk")
        reports.append(min(1.0, invocation.report + second))
        disagreements.append(not same(invocation.output, output))
    return audit(reports, disagreements, independent)
