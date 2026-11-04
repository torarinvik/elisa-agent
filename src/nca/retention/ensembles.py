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
from nca.retention.certification import zero_loss_test
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


class EnsembleSearch:
    """Request routes until a declared vote size passes fresh certification.

    ``counts`` declares tested sizes before any cases are seen. Each receives
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
    """

    def __init__(self, *, counts: Sequence[int], tolerance: float, confidence: float,
                 budget: int, history: AcquisitionHistory | None = None,
                 resolver: Resolver | None = None) -> None:
        sizes = tuple(counts)
        if (not sizes or any(isinstance(n, bool) or not isinstance(n, int) or n < 1 for n in sizes)
                or any(a >= b for a, b in zip(sizes, sizes[1:]))):
            raise ValueError("ensemble counts must be positive and strictly increasing")
        if isinstance(budget, bool) or not isinstance(budget, int) or budget < 1:
            raise ValueError("per-route evaluation budget must be positive")
        required_cases(tolerance, confidence)
        self.counts, self.tolerance, self.confidence = sizes, tolerance, confidence
        self.budget, self.history = budget, history
        self.resolver = resolver
        self.decisions = self.requests = self.labels = self.evaluations = self.tests = 0

    def __call__(self, contract: Contract,
                 acquire: Callable[[tuple[Plan, ...]], Plan | None],
                 sample: Callable[[int], Sequence[VoteCase] | None], *,
                 agree: Callable[[Any, Any], bool] = _equal,
                 feedback: Callable[[VoteFailure], None] | None = None) -> CertifiedVote | None:
        index = self.decisions
        if self.history is not None:
            key = self.history.key(contract, self.tolerance, self.confidence, None)
            index, _ = self.history.reserve(key)
        self.decisions += 1
        level = family_audit_alpha(decision_level(self.confidence, index), len(self.counts))
        routes: list[Plan] = []

        def draw(count: int) -> Sequence[VoteCase] | None:
            cases = sample(count)
            if cases is not None:
                self.labels += len(cases)
            return cases

        for count in self.counts:
            while len(routes) < count:
                self.requests += 1
                route = acquire(tuple(routes))
                if route is None:
                    return None
                if output_type(route) != contract.output:
                    raise ValueError("acquired route has the wrong output type")
                routes.append(route)
            frozen = tuple(routes)
            failure: tuple[VoteCase, Vote] | None = None

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
                if not accepted:
                    failure = case, result
                return accepted

            fresh = required_cases(self.tolerance, level)
            self.tests += 1
            result = zero_loss_test(draw, correct, cases=fresh)
            if result.passed is None:
                return None
            if result.passed:
                return CertifiedVote(frozen, self.tolerance, level, fresh)
            if feedback is not None:
                assert failure is not None
                feedback(VoteFailure(frozen, failure[0], failure[1], level, result.drawn))
        return None
