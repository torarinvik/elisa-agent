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
