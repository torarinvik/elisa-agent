"""Certified acquisition of learned connectors (THEORY §20.9).

An acquirer for ``planner.gaps.repair`` built from any fitter and a source of
paired cases. For each requested contract it fits on training cases, then
draws fresh cases and admits the result only if it agrees on all of them. The
``k``-th request is tested at level ``decision_level(confidence, k)`` with
``required_cases`` fresh cases, so across all requests the probability of
admitting any connector whose error rate exceeds ``tolerance`` is at most
``confidence`` (``NCA.zeroLoss_miss``, ``NCA.acquisition_sound``), assuming
the fresh cases are independent draws from the distribution of use. Fresh
cases are drawn in doubling batches and the test stops at the first
disagreement: it admits exactly when the full test would and never draws more
(``NCA.earlyTest_admits``, ``NCA.earlyTest_reads``), so a rejection costs at
most about twice the cases read up to the first error. Each
admitted connector carries ``tolerance`` as its certified rate, for
``evidence.route_risk``. What generalizes is the fitter's concern; the test
only measures it.
"""

from __future__ import annotations

from collections.abc import Callable, Hashable, Sequence
from typing import Any

from nca.abi import Contract, Module
from nca.retention.sampled import decision_level, required_cases

Fitter = Callable[[Contract, Sequence[Hashable], Sequence[Hashable]], Module | None]
"""Fits a unary expert from keys and labels, or ``None`` if it cannot."""
Sampler = Callable[[Contract, int], Sequence[tuple[Any, Any]] | None]
"""Up to the given number of fresh (input, output) cases for a contract, or
``None`` if none exist."""


def _equal(output: Any, label: Any) -> bool:
    return bool(output == label)


class CertifiedAcquirer:
    """Admits a learned connector only after zero errors on fresh cases."""

    def __init__(self, fit: Fitter, sample: Sampler, *, train: int, tolerance: float,
                 confidence: float, agree: Callable[[Any, Any], bool] = _equal) -> None:
        if train < 1:
            raise ValueError("training needs at least one case")
        required_cases(tolerance, confidence)
        self.fit, self.sample, self.train, self.agree = fit, sample, train, agree
        self.tolerance, self.confidence = tolerance, confidence
        self.decisions = 0
        self.labels = 0
        self.certified: dict[str, float] = {}

    def __call__(self, contract: Contract) -> Module | None:
        level = decision_level(self.confidence, self.decisions)
        self.decisions += 1
        fresh = required_cases(self.tolerance, level)
        training = self.sample(contract, self.train)
        if training is None or len(training) < self.train:
            return None
        self.labels += len(training)
        module = self.fit(contract, [k for k, _ in training], [v for _, v in training])
        if module is None:
            return None
        tested, batch = 0, 1
        while tested < fresh:
            held = self.sample(contract, min(batch, fresh - tested))
            if held is None or len(held) < min(batch, fresh - tested):
                return None
            self.labels += len(held)
            if not all(self.agree(module.invoke(k), v) for k, v in held):
                return None
            tested, batch = tested + len(held), 2 * batch
        self.certified[module.manifest.module_id] = self.tolerance
        return module

    def rate(self, module: Module) -> float | None:
        """The certified error rate of an expert this acquirer admitted."""
        return self.certified.get(module.manifest.module_id)
