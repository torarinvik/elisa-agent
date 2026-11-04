"""Acquire and freshly certify a vote against an error target (§31.9).

Route errors may be arbitrarily dependent. The fresh cases must instead be
IID from the joint operating distribution, conditional on past observations.
Candidate plans and expert behavior must stay fixed during certification and
subsequent use; sampling and evaluation semantics are host responsibilities.
"""

from __future__ import annotations

from collections.abc import Callable, Mapping, Sequence
from dataclasses import dataclass
from typing import Any

from nca.abi import Contract, Message, TypeId
from nca.evidence.redundancy import Vote, vote
from nca.planner import Plan, output_type
from nca.runtime import Resolver
from nca.retention.certification import (loss_test, validate_batch_limit,
                                        validate_validation_cases, validation_plan)
from nca.retention.history import AcquisitionHistory
from nca.retention.sampled import decision_level, required_cases
from nca.stats import family_audit_alpha

VoteInputs = Mapping[TypeId, Message] | Sequence[Message]
VoteCase = tuple[VoteInputs, Any]


def _equal(answer: Any, target: Any) -> bool:
    return bool(answer == target)


@dataclass(frozen=True)
class CertifiedVote:
    routes: tuple[Plan, ...]
    tolerance: float
    level: float
    cases: int


@dataclass(frozen=True)
class VoteFailure:
    """First scored failure, delivered only after its candidate test closes.

    This observation may train later candidates; later tests need new draws,
    even when values coincide. Payloads and plan implementations follow the host's
    immutability/retention policy, just as ordinary runtime inputs do.
    """

    routes: tuple[Plan, ...]
    case: VoteCase
    vote: Vote
    level: float
    drawn: int
    controls: tuple[VoteCase, ...] = ()
    training: tuple[VoteCase, ...] = ()
    """Bounded drawn prefix, possibly including unscored final-batch cases.

    May overlap controls and case; consumers choose a source or deduplicate.
    Neither this selected prefix nor controls is an independent audit sample.
    """


class EnsembleSearch:
    """Request routes until a declared vote size passes fresh certification.

    ``counts`` declares tested sizes (revision caps for ``revise``) before
    any cases are seen. Counts may repeat for same-size revisions. Each receives
    a share of this search's confidence level. ``budget`` is per route per
    evaluation, not a global compute bound. Route acquisition has its own
    training/compute budget supplied by the caller. Abstention counts as error,
    even if the target payload is None. No route independence is assumed.
    Optional history persists spending positions; it caches no refusals here.
    Calls on one object are serialized. Without history, constructing a new
    object starts a new confidence budget. Resolver behavior is part of the
    candidate's fixed evaluation semantics.
    Optional ``feedback`` receives one observed failure after each rejected
    test, including the last. It may inform later proposals or later searches;
    it must not mutate published experts or reuse that draw for certification.
    Callback errors propagate after already drawn labels have been charged.
    ``retain_controls`` bounds the scored successful prefix exposed alongside
    a rejection. These selected training controls are not fresh audit data;
    subsequent proposals still require independently drawn certification cases.
    ``retain_training`` additionally retains a bounded drawn prefix, including
    unscored cases in the rejected batch. It makes no extra label requests and
    exposes nothing from an admitted or incomplete test.
    ``batch_limit`` optionally caps certification draws, reducing unscored
    labels on rejection at the cost of more sampler calls.
    Optional ``validation_cases`` fixes a held-out size with a conservative
    binomial error cutoff chosen before proposal or sampling (§20.22). None
    retains zero-error admission. Observed errors of admitted votes generate
    no rejection feedback. Successful controls still precede the first error.
    """

    def __init__(self, *, counts: Sequence[int], tolerance: float, confidence: float,
                 budget: int, history: AcquisitionHistory | None = None,
                 resolver: Resolver | None = None, retain_controls: int = 0,
                 retain_training: int = 0, batch_limit: int | None = None,
                 validation_cases: int | None = None) -> None:
        sizes = tuple(counts)
        if (not sizes or any(isinstance(n, bool) or not isinstance(n, int) or n < 1 for n in sizes)
                or any(a > b for a, b in zip(sizes, sizes[1:]))):
            raise ValueError("ensemble counts must be positive and nondecreasing")
        if isinstance(budget, bool) or not isinstance(budget, int) or budget < 1:
            raise ValueError("per-route evaluation budget must be positive")
        if (isinstance(retain_controls, bool) or not isinstance(retain_controls, int)
                or retain_controls < 0):
            raise ValueError("retained control capacity must be nonnegative")
        if type(retain_training) is not int or retain_training < 0:
            raise ValueError("retained training capacity must be nonnegative")
        validate_batch_limit(batch_limit)
        validate_validation_cases(validation_cases)
        required_cases(tolerance, confidence)
        self.counts, self.tolerance, self.confidence = sizes, tolerance, confidence
        self.budget, self.history = budget, history
        self.resolver = resolver
        self.retain_controls = retain_controls
        self.retain_training = retain_training
        self.batch_limit = batch_limit
        self.validation_cases = validation_cases
        self.decisions = self.requests = self.labels = self.evaluations = self.tests = 0

    def __call__(self, contract: Contract,
                 acquire: Callable[[tuple[Plan, ...]], Plan | None],
                 sample: Callable[[int], Sequence[VoteCase] | None], *,
                 agree: Callable[[Any, Any], bool] = _equal,
                 feedback: Callable[[VoteFailure], None] | None = None) -> CertifiedVote | None:
        routes: list[Plan] = []

        def propose(count: int) -> tuple[Plan, ...] | None:
            while len(routes) < count:
                self.requests += 1
                route = acquire(tuple(routes))
                if route is None:
                    return None
                if output_type(route) != contract.output:
                    raise ValueError("acquired route has the wrong output type")
                routes.append(route)
            return tuple(routes)

        return self._search(contract, propose, sample, agree, feedback)

    def revise(self, contract: Contract,
               propose: Callable[[int, tuple[VoteFailure, ...]], Sequence[Plan] | None],
               sample: Callable[[int], Sequence[VoteCase] | None], *,
               agree: Callable[[Any, Any], bool] = _equal,
               feedback: Callable[[VoteFailure], None] | None = None) -> CertifiedVote | None:
        """Replace the whole candidate using earlier closed-test failures.

        Each call asks for a nonempty frozen family of at most the stage's
        declared count. Old plans are not changed or installed. The curriculum
        contains at most one counterexample per earlier stage of this search.
        ``requests`` counts family-proposal calls here, route calls in growing
        mode; the proposer owns and reports its training/resource costs.
        """
        failures: list[VoteFailure] = []

        def candidate(cap: int) -> tuple[Plan, ...] | None:
            self.requests += 1
            proposed = propose(cap, tuple(failures))
            if proposed is None:
                return None
            frozen = tuple(proposed)
            if not frozen or len(frozen) > cap:
                raise ValueError("revision must contain between one and its declared cap routes")
            return frozen

        def observe(failure: VoteFailure) -> None:
            failures.append(failure)
            if feedback is not None:
                feedback(failure)

        return self._search(contract, candidate, sample, agree, observe)

    def _search(self, contract: Contract, propose: Callable[[int], Sequence[Plan] | None],
                sample: Callable[[int], Sequence[VoteCase] | None],
                agree: Callable[[Any, Any], bool],
                feedback: Callable[[VoteFailure], None] | None) -> CertifiedVote | None:
        index = self.decisions
        if self.history is not None:
            key = self.history.key(contract, self.tolerance, self.confidence, None)
            index, _ = self.history.reserve(key)
        self.decisions += 1
        level = family_audit_alpha(decision_level(self.confidence, index), len(self.counts))
        fresh, allowance = validation_plan(self.tolerance, level, self.validation_cases)
        if allowance < 0:
            return None

        def draw(count: int) -> Sequence[VoteCase] | None:
            cases = sample(count)
            if cases is not None:
                self.labels += len(cases)
            return cases

        for count in self.counts:
            proposed = propose(count)
            if proposed is None:
                return None
            frozen = tuple(proposed)
            if any(output_type(route) != contract.output for route in frozen):
                raise ValueError("acquired route has the wrong output type")
            failure: tuple[VoteCase, Vote] | None = None
            controls: list[VoteCase] = []

            def correct(case: VoteCase) -> bool:
                nonlocal failure
                self.evaluations += 1
                inputs, label = case
                if isinstance(inputs, Mapping):
                    valid_inputs = (len(inputs) == len(contract.inputs)
                                    and set(inputs) == set(contract.inputs)
                                    and all(key == message.type_id for key, message in inputs.items()))
                else:
                    valid_inputs = tuple(message.type_id for message in inputs) == contract.inputs
                if not valid_inputs:
                    raise ValueError("certification inputs do not match the requested contract")
                result = vote(frozen, inputs, self.budget, self.resolver)
                accepted = result.agreeing > 0 and bool(agree(result.answer, label))
                if not accepted and failure is None:
                    failure = case, result
                elif accepted and failure is None and len(controls) < self.retain_controls:
                    controls.append(case)
                return accepted

            self.tests += 1
            result = loss_test(draw, correct, cases=fresh, max_errors=allowance,
                               retain=self.retain_training, batch_limit=self.batch_limit)
            if result.passed is None:
                return None
            if result.passed:
                return CertifiedVote(frozen, self.tolerance, level, fresh)
            if feedback is not None:
                assert failure is not None
                feedback(VoteFailure(frozen, failure[0], failure[1], level, result.drawn,
                                     tuple(controls), result.retained))
        return None
