"""Certified acquisition of learned connectors (§20.9)."""

import random
from collections.abc import Hashable, Sequence
from functools import partial
from typing import Any

import pytest

from nca.abi import Contract, Manifest, Module
from nca.evidence import route_risk
from nca.learning.affine import fit_affine
from nca.learning.discovery import fit_decoder
from nca.planner import Apply, Given
from nca.planner.gaps import repair
from nca.retention.acquisition import CertifiedAcquirer
from nca.retention.sampled import decision_level, required_cases


def linear(contract: Contract, count: int) -> list[tuple[Any, Any]]:
    rng = random.Random(count)
    return [(float(v), 3.0 * v + 7.0) for v in (rng.randrange(10 ** 6) for _ in range(count))]


def close(output: Any, label: Any) -> bool:
    return abs(output - label) < 0.5


@pytest.mark.parametrize("limit", [None, 1, 3])
def test_a_generalizing_fitter_is_admitted_with_its_certified_rate(limit: int | None) -> None:
    draws: list[int] = []

    def sample(contract: Contract, count: int) -> list[tuple[Any, Any]]:
        draws.append(count)
        return linear(contract, count)

    acquirer = CertifiedAcquirer(partial(fit_affine, cost=1.0), sample, train=8,
                                 tolerance=0.05, confidence=0.05, agree=close, batch_limit=limit)
    module = acquirer(Contract(("a",), "b"))
    assert module is not None and acquirer.rate(module) == 0.05
    assert acquirer.labels == 8 + required_cases(0.05, decision_level(0.05, 0))
    route = Apply(module, (Given("a"),))
    assert route_risk(route, acquirer.rate) == pytest.approx(0.05)
    assert draws[0] == 8  # Training remains independent of the certification cap.
    if limit is not None:
        assert max(draws[1:]) <= limit


@pytest.mark.parametrize("limit", [True, False, 0, -2, 2.5])
def test_invalid_certification_cap_does_not_fit_or_sample(limit: Any) -> None:
    with pytest.raises(ValueError, match="batch limit"):
        CertifiedAcquirer(partial(fit_affine, cost=1.0), linear, train=8,
                          tolerance=0.05, confidence=0.05, batch_limit=limit)


def test_a_memorizing_fitter_is_refused_on_fresh_values() -> None:
    acquirer = CertifiedAcquirer(partial(fit_decoder, cost=1.0), linear, train=256,
                                 tolerance=0.05, confidence=0.05, agree=close)
    assert acquirer(Contract(("a",), "b")) is None and acquirer.certified == {}


def test_admissions_read_every_case_and_rejections_stop_early() -> None:
    """``NCA.earlyTest_reads``: an admission draws all its fresh cases, later
    requests more of them; a memorized table is rejected after a few."""
    def sample(contract: Contract, count: int) -> list[tuple[Any, Any]] | None:
        return None if contract.output == "none" else linear(contract, count)

    acquirer = CertifiedAcquirer(partial(fit_affine, cost=1.0), sample, train=8,
                                 tolerance=0.1, confidence=0.1, agree=close)
    assert acquirer(Contract(("a",), "none")) is None and acquirer.labels == 0
    assert acquirer(Contract(("a",), "b")) is not None
    assert acquirer.labels == 8 + required_cases(0.1, decision_level(0.1, 1))
    assert required_cases(0.1, decision_level(0.1, 1)) > required_cases(0.1, decision_level(0.1, 0))
    table = CertifiedAcquirer(partial(fit_decoder, cost=1.0), linear, train=256,
                              tolerance=0.01, confidence=0.01, agree=close)
    assert table(Contract(("a",), "b")) is None
    assert table.labels == 256 + 1 < 256 + required_cases(0.01, decision_level(0.01, 0))


class Flaky:
    """Correct except on a fraction ``loss`` of inputs."""

    def __init__(self, contract: Contract, loss: float) -> None:
        self.loss = loss
        self.manifest = Manifest(f"flaky/{loss}", "1", contract, effects=frozenset())

    def invoke(self, value: Any) -> Any:
        wrong = random.Random(int(value)).random() < self.loss
        return 3.0 * value + 7.0 + (1.0 if wrong else 0.0)


def test_false_admissions_stay_within_the_confidence_budget() -> None:
    """``NCA.acquisition_sound``: an expert erring at twice the tolerance is
    admitted in at most ``confidence`` of runs over all their requests."""
    def flaky(contract: Contract, keys: Sequence[Hashable], labels: Sequence[Hashable]
              ) -> Module:
        return Flaky(contract, 0.2)

    runs, admitted = 200, 0
    for seed in range(runs):
        rng = random.Random(seed)

        def sample(contract: Contract, count: int) -> list[tuple[Any, Any]]:
            return [(float(v), 3.0 * v + 7.0)
                    for v in (rng.randrange(10 ** 6) for _ in range(count))]

        acquirer = CertifiedAcquirer(flaky, sample, train=1, tolerance=0.1, confidence=0.2,
                                     agree=close)
        admitted += any(acquirer(Contract(("a",), f"b{k}")) is not None for k in range(10))
    assert admitted / runs <= 0.2


def test_repair_through_a_certified_acquirer() -> None:
    acquirer = CertifiedAcquirer(partial(fit_affine, cost=1.0), linear, train=8,
                                 tolerance=0.05, confidence=0.05, agree=close)
    repaired = repair([], ("a",), "b", acquirer, attempts=5)
    assert repaired is not None and route_risk(repaired.route, acquirer.rate) == 0.05
