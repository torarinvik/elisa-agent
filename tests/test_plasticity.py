"""Self-regulating plasticity over (piece, region) keys (§43.8)."""

import json
import random
import shutil
import subprocess
from fractions import Fraction
from numbers import Real
from pathlib import Path

import pytest

from nca.retention.plasticity import PlasticityField, Smoothing


def test_surprise_opens_and_stability_damps() -> None:
    field = PlasticityField(Smoothing(0.5))
    for _ in range(3):
        field.observe(("piece", "left"), 1.0, 0.0)
        field.observe(("piece", "right"), 1.0, 0.9)
    assert field.is_open(("piece", "left")) and not field.is_open(("piece", "right"))
    assert field.plasticity(("piece", "left")) > field.plasticity(("piece", "right"))
    assert not field.is_open(("piece", "unseen")) and field.plasticity("unseen") == 0


def test_plasticity_stays_bounded_and_moves_at_most_its_rate() -> None:
    """``NCA.smooth_unit`` and ``NCA.smooth_step``."""
    rng = random.Random(11)
    for rate in (0.05, 0.3, 1.0):
        field = PlasticityField(Smoothing(rate))
        previous = 0.0
        for _ in range(500):
            value = field.observe("key", rng.random(), rng.random())
            assert 0 <= value <= 1 and abs(value - previous) <= rate + 1e-12
            previous = value


def test_hysteresis_prevents_flapping() -> None:
    """``NCA.hysteresis_gap``: reversals need at least (open - close) / rate steps."""
    rng = random.Random(5)
    rate, open_at, close_at = 0.1, 0.6, 0.3
    field = PlasticityField(Smoothing(rate), open_at=open_at, close_at=close_at)
    switches, state = [], False
    for step in range(5000):
        field.observe("key", float(rng.random() < 0.5), 0.0)
        if field.is_open("key") != state:
            state = not state
            switches.append(step)
    assert switches
    gaps = [later - earlier for earlier, later in zip(switches, switches[1:])]
    assert min(gaps) * rate >= open_at - close_at - 1e-12


def test_regulators_are_pluggable_but_must_stay_in_unit_range() -> None:
    def jump(plasticity: Real, surprise: Real, stability: Real) -> Real:
        return surprise

    field = PlasticityField(jump)
    assert field.observe("key", 0.7, 0.0) == 0.7 and field.is_open("key")

    def escape(plasticity: Real, surprise: Real, stability: Real) -> Real:
        return 1.5

    with pytest.raises(ValueError, match="regulated plasticity"):
        PlasticityField(escape).observe("key", 0.5, 0.5)
    with pytest.raises(ValueError, match="surprise"):
        field.observe("key", 1.2, 0.0)
    with pytest.raises(ValueError, match="thresholds"):
        PlasticityField(open_at=0.3, close_at=0.6)


def test_allocation_follows_plasticity_over_open_keys() -> None:
    field = PlasticityField(lambda p, s, w: s * (1 - w))
    field.observe("a", 0.9, 0.0)
    field.observe("b", 0.6, 0.0)
    field.observe("closed", 0.2, 0.0)
    granted = field.allocate(10)
    assert set(granted) == {"a", "b"} and sum(granted.values()) == 10
    assert granted["a"] == 6 and granted["b"] == 4
    assert field.allocate(0) == {"a": 0, "b": 0}
    assert PlasticityField().allocate(5) == {}


def test_field_matches_the_lean_model_exactly_over_rationals() -> None:
    lake = shutil.which("lake")
    if lake is None:
        pytest.skip("Lean differential checks require the development toolchain")
    rng = random.Random(29)
    fixtures, expected = [], []

    def text(value: Fraction) -> str:
        return f"{value.numerator}/{value.denominator}"

    for _ in range(64):
        rate = Fraction(rng.randrange(1, 10), 10)
        lo = Fraction(rng.randrange(0, 5), 10)
        hi = lo + Fraction(rng.randrange(1, 11 - int(lo * 10)), 10)
        steps = [(Fraction(rng.randrange(0, 5), 4), Fraction(rng.randrange(0, 5), 4))
                 for _ in range(rng.randrange(1, 12))]
        field = PlasticityField(Smoothing(rate), open_at=hi, close_at=lo)
        rows = []
        for surprise, stability in steps:
            value = field.observe("key", surprise, stability)
            rows.append([text(Fraction(value)), field.is_open("key")])
        fixtures.append({"rate": text(rate), "lo": text(lo), "hi": text(hi),
                         "steps": [[text(s), text(w)] for s, w in steps]})
        expected.append(rows)
    lean = Path(__file__).resolve().parents[1] / "lean"
    subprocess.run([lake, "build", "NCA.Reliability.Plasticity"], cwd=lean,
                   capture_output=True, text=True, check=True, timeout=300)
    result = subprocess.run(
        [lake, "env", "lean", "--run", "NCA/Reliability/PlasticityReplay.lean"],
        cwd=lean, input=json.dumps(fixtures), capture_output=True, text=True,
        check=True, timeout=300,
    )
    assert json.loads(result.stdout) == expected


def test_settling_closes_a_key_until_fresh_surprise_reopens_it() -> None:
    """``NCA.reopen_after_settle``."""
    rate, open_at, close_at = 0.25, 0.6, 0.3
    field = PlasticityField(Smoothing(rate), open_at=open_at, close_at=close_at)
    while not field.is_open("key"):
        field.observe("key", 1.0, 0.0)
    field.settle("key")
    assert not field.is_open("key") and field.plasticity("key") == 0
    observations = 0
    while not field.is_open("key"):
        field.observe("key", 1.0, 0.0)
        observations += 1
    assert observations * rate >= open_at - close_at
    with pytest.raises(ValueError, match="initial"):
        PlasticityField(initial=0.5, close_at=0.3)
