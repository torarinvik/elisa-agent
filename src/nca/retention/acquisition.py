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
from nca.retention.screening import FeasibilityScreen

Fitter = Callable[[Contract, Sequence[Hashable], Sequence[Hashable]], Module | None]
"""Fits an expert from input keys and labels, or ``None`` if it cannot."""
Sampler = Callable[[Contract, int], Sequence[tuple[Any, Any]] | None]
"""Up to the given number of fresh (input, output) cases for a contract, or
``None`` if none exist; for several inputs, the input is their tuple."""


def _equal(output: Any, label: Any) -> bool:
    return bool(output == label)


def _invoke(module: Module, contract: Contract, key: Any) -> Any:
    return module.invoke(key) if len(contract.inputs) == 1 else module.invoke(*key)


class CertifiedAcquirer:
    """Admit after zero fresh errors, optionally screening before full fitting.

    A screen has a separate false-discard budget and requires separation sound
    for this instance's ``agree`` predicate. Its passing prefix is training
    data, never held-out evidence. See ``FeasibilityScreen`` for assumptions.
    """

    def __init__(self, fit: Fitter, sample: Sampler, *, train: int, tolerance: float,
                 confidence: float, agree: Callable[[Any, Any], bool] = _equal,
                 screen: FeasibilityScreen | None = None) -> None:
        if train < 1:
            raise ValueError("training needs at least one case")
        required_cases(tolerance, confidence)
        self.fit, self.sample, self.train, self.agree = fit, sample, train, agree
        self.tolerance, self.confidence = tolerance, confidence
        self.screen = screen
        self.decisions = 0
        self.labels = 0
        self.certified: dict[str, float] = {}

    def __call__(self, contract: Contract) -> Module | None:
        level = decision_level(self.confidence, self.decisions)
        self.decisions += 1
        fresh = required_cases(self.tolerance, level)
        training: list[tuple[Any, Any]] = []
        prefix = min(self.screen.cases, self.train) if self.screen is not None else 0
        if prefix >= 2:
            drawn = self.sample(contract, prefix)
            if drawn is not None:
                self.labels += len(drawn)
                training.extend(drawn)
            if len(training) != prefix:
                return None
            if self.screen is not None and self.screen.reject(training, self.tolerance):
                return None
        remaining = self.train - len(training)
        if remaining:
            drawn = self.sample(contract, remaining)
            if drawn is not None:
                self.labels += len(drawn)
                training.extend(drawn)
            if len(training) != self.train:
                return None
        module = self.fit(contract, [k for k, _ in training], [v for _, v in training])
        if module is None:
            return None
        tested, batch = 0, 1
        while tested < fresh:
            held = self.sample(contract, min(batch, fresh - tested))
            if held is not None:
                self.labels += len(held)
            if held is None or len(held) < min(batch, fresh - tested):
                return None
            if not all(self.agree(_invoke(module, contract, k), v) for k, v in held):
                return None
            tested, batch = tested + len(held), 2 * batch
        self.certified[module.manifest.module_id] = self.tolerance
        return module

    def rate(self, module: Module) -> float | None:
        """The certified error rate of an expert this acquirer admitted."""
        return self.certified.get(module.manifest.module_id)
