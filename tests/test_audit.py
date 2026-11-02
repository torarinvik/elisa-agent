"""Calibration audits and recalibration (§35)."""

import random
from typing import Any

import pytest

from nca.abi import Contract, Manifest
from nca.evidence import audit, recalibrate


def test_audits_refute_overconfident_reports_only() -> None:
    rng = random.Random(0)
    honest = [rng.random() < 0.1 for _ in range(1000)]
    assert not audit([0.1] * 1000, honest).refutes(0.01)
    overconfident = audit([0.01] * 1000, honest)
    assert overconfident.refutes(1e-6) and overconfident.failures == sum(honest)
    assert overconfident.reported == pytest.approx(10.0)
    # Without independence the bound is R / F: weaker, still refuting here.
    markov = audit([0.01] * 1000, honest, independent=False)
    assert markov.p_value == pytest.approx(10.0 / sum(honest)) and markov.refutes(0.2)
    assert audit([0.5], [False]).p_value == 1.0
    with pytest.raises(ValueError, match="one failure flag"):
        audit([0.1], [])
    with pytest.raises(ValueError, match="probabilities"):
        audit([1.5], [True])


class Overconfident:
    """Says its reading with probability 0.99, but reads right only 70% of the time."""

    manifest = Manifest("reader", "1", Contract(("glyph.v1",), "dist.v1"))

    def invoke(self, value: tuple[int, int]) -> tuple[float, ...]:
        label, noise = value
        read = label if noise < 70 else (label + 1) % 3
        return tuple(0.99 if k == read else 0.005 for k in range(3))


def test_recalibration_refits_and_attests_an_overconfident_expert() -> None:
    torch = pytest.importorskip("torch")
    from nca.ladder import Calibrated, Rung, attested

    rng = random.Random(1)
    values = [(rng.randrange(3), rng.randrange(100)) for _ in range(2000)]
    labels = [label for label, _ in values]
    expert: Any = Overconfident()
    stale = Rung(expert, {None: 1.0})
    reader = Calibrated(stale)
    outputs = [reader.invoke(v) for v in values]
    before = audit([reader.risk(o) for o in outputs],
                   [max(range(3), key=o.__getitem__) != y for o, y in zip(outputs, labels)])
    assert before.refutes(1e-6)
    attestation, after = recalibrate(stale, values, labels, "reader-ref", "auditor", 0.01)
    assert attestation is not None and not after.refutes(0.01)
    assert after.reported == pytest.approx(after.failures, rel=0.25)
    refit = attested(expert, attestation)
    assert refit.temperature() > 1.0  # Softened.
    assert torch.is_tensor(refit.observe(values[0]))


class Guesser:
    """Right on a value when its noise is below ``skill`` percent."""

    def __init__(self, skill: int, name: str = "guesser") -> None:
        self.manifest = Manifest("reader", "1", Contract(("glyph.v1",), "label.v1"))
        self.skill, self.name = skill, name

    def invoke(self, value: tuple[int, int]) -> int:
        label, noise = value
        return label if noise < self.skill else label + 1


def labeled(n: int) -> tuple[list[tuple[int, int]], list[int]]:
    rng = random.Random(2)
    values = [(rng.randrange(3), rng.randrange(100)) for _ in range(n)]
    return values, [label for label, _ in values]


def test_acquisition_promotes_only_a_better_trained_challenger() -> None:
    from nca.evidence import acquire

    values, labels = labeled(400)
    seen: list[int] = []

    def trainer(skill: int) -> Any:
        def train(train_values: list, train_labels: list) -> Guesser:
            seen.append(len(train_values))
            return Guesser(skill, "challenger")
        return train

    def correct(output: int, label: int) -> bool:
        return output == label

    incumbent = Guesser(60)
    better = acquire(incumbent, trainer(95), values, labels, correct)
    assert seen == [200]  # Trained on the first half only.
    assert better.promotion is not None and better.promotion.challenger is better.challenger
    assert better.promotion.losses == 0 and better.promotion.wins > 50
    assert sum(better.challenger_outcomes) > sum(better.incumbent_outcomes)
    same = acquire(incumbent, trainer(60), values, labels, correct)
    assert same.promotion is None
    other = Guesser(90)
    other.manifest = Manifest("reader", "1", Contract(("glyph.v1",), "other.v1"))
    with pytest.raises(ValueError, match="contract"):
        acquire(incumbent, lambda v, y: other, values, labels, correct)


def test_hotspots_rank_experts_by_charged_risk() -> None:
    from nca.evidence import hotspots
    from nca.runtime import RiskLedger

    a, b = Guesser(10, "a"), Guesser(20, "b")
    first, second = RiskLedger(), RiskLedger()
    first.entries += [(a, (1,), 0.1), (b, (1,), 0.3)]
    second.entries += [(a, (2,), 0.4)]
    assert [(m, pytest.approx(t)) for m, t in hotspots([first, second])] == [(a, 0.5), (b, 0.3)]
