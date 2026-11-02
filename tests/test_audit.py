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


class Shifting:
    """Overconfident on shifted inputs (second field 1) only."""

    manifest = Manifest("reader", "1", Contract(("glyph.v1",), "dist.v1"))

    def invoke(self, value: tuple[int, int, int]) -> tuple[float, ...]:
        label, shifted, noise = value
        read = label if noise < (60 if shifted else 97) else (label + 1) % 3
        return tuple(0.98 if k == read else 0.01 for k in range(3))


def test_grouped_calibration_holds_in_each_group_and_any_mixture() -> None:
    pytest.importorskip("torch")
    from nca.grouped import Grouped, fit_groups
    from nca.ladder import Calibrated, Rung

    rng = random.Random(3)

    def draw(n: int, shifted: int) -> list[tuple[int, int, int]]:
        return [(rng.randrange(3), shifted, rng.randrange(100)) for _ in range(n)]

    def group(value: tuple[int, int, int]) -> int:
        return value[1]

    expert: Any = Shifting()
    pool = draw(5000, 0) + draw(5000, 1)
    rungs = fit_groups(expert, group, pool, [v[0] for v in pool])
    grouped = Grouped(expert, group, rungs)
    pooled = Rung(expert)
    pooled.calibrate(pool, __import__("torch").tensor([v[0] for v in pool]))
    one = Calibrated(pooled)

    def audited(reader: Any, values: list) -> Any:
        outputs = [reader.invoke(v) for v in values]
        return audit([reader.risk(o, v) for o, v in zip(outputs, values)],
                     [max(range(3), key=o.__getitem__) != v[0] for o, v in zip(outputs, values)])

    for shifted in (0, 1):
        assert not audited(grouped, draw(1000, shifted)).refutes(0.01)
    # One temperature for the pooled mixture is refuted on the shifted
    # inputs alone, and over-reports on the clean ones.
    assert audited(one, draw(1000, 1)).refutes(0.01)
    clean = audited(one, draw(1000, 0))
    assert clean.reported > 3 * clean.failures
    # An input of a group without a rung reports no risk.
    sparse = Grouped(expert, group, {0: rungs[0]})
    assert sparse.risk(sparse.invoke((0, 1, 5)), (0, 1, 5)) is None


def test_cross_audits_refute_by_disagreement_without_labels() -> None:
    from nca.evidence import cross_audit
    from nca.runtime import Invocation

    rng = random.Random(5)

    class Reader:
        def __init__(self, name: str, error: float, report: float) -> None:
            self.manifest = Manifest(name, "1", Contract(("glyph.v1",), "label.v1"))
            self.error, self.report = error, report

        def invoke(self, value: tuple[int, int]) -> int:
            label, noise = value
            return label if rng.random() >= self.error else label + 1 + rng.randrange(5)

        def risk(self, output: int, *inputs: Any) -> float:
            return self.report

    def sample(reader: Reader, n: int) -> list[Invocation]:
        values = [(rng.randrange(10), 0) for _ in range(n)]
        return [Invocation(reader, (v,), out := reader.invoke(v), reader.risk(out)) for v in values]

    def same(first: int, second: int) -> bool:
        return first == second

    honest, reference = Reader("a", 0.05, 0.05), Reader("b", 0.05, 0.05)
    assert not cross_audit(sample(honest, 1000), reference, same).refutes(0.01)
    overconfident = Reader("a", 0.2, 0.01)
    found = cross_audit(sample(overconfident, 1000), reference, same)
    assert found.refutes(1e-6) and found.reported == pytest.approx(60.0)
    silent = Reader("c", 0.0, 0.0)
    silent.manifest = Manifest("c", "1", Contract(("glyph.v1",), "other.v1"))
    with pytest.raises(ValueError, match="contract"):
        cross_audit(sample(honest, 3), silent, same)
