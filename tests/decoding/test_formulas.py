import itertools
from dataclasses import dataclass
from fractions import Fraction
from typing import Any

import numpy as np
import pytest

torch = pytest.importorskip("torch")

from nca.abi import Contract, Manifest
from nca import decoding, prefix
from nca import shares as share_module
from nca.ladder import Decision, ladder, refine


def no_distribution(k: int, decision: Decision) -> torch.Tensor:
    raise AssertionError("not needed by this account")


@dataclass
class Constant:
    manifest: Manifest
    output: tuple[float, ...]

    def invoke(self, value: Any) -> tuple[float, ...]:
        return self.output


def test_refine_climbs_only_demanded_items() -> None:
    contract = Contract(("x",), "dist")
    rungs = ladder([Constant(Manifest("unsure", "1.0.0", contract, cost=1.0), (0.4, 0.6)),
                    Constant(Manifest("sure", "1.0.0", contract, cost=10.0), (0.01, 0.99))],
                   contract)
    result = refine([0, 0, 0], [rungs] * 3, delta=0.05,
                    certificate=lambda readings, risk, distribution: {0: risk(0, None)})
    assert result.cost == pytest.approx(3 * 1.0 + 10.0)
    assert result.bound == pytest.approx(0.01, abs=1e-6) and not result.abstained
    assert refine([0], [rungs], 0.05,
                  certificate=lambda readings, risk, distribution: None).abstained


@pytest.mark.parametrize("reference", [False, True])
def test_pair_risk_upper_avoids_cancellation_and_underflow(
        reference: bool, monkeypatch: pytest.MonkeyPatch) -> None:
    from nca import ladder as ladder_module

    if reference:
        monkeypatch.setattr(share_module, "_NATIVE", None)
        monkeypatch.setattr(share_module, "_STATS_NATIVE", None)
        monkeypatch.setattr(ladder_module, "_NATIVE", None)
    rng = np.random.default_rng(2331)
    samples = [[], [1.0, 1e-18], [1e-200, 1e-200], [0.8, 0.8, 0.8],
               *[rng.random(10).tolist() for _ in range(100)]]
    for risks in samples:
        values = [Fraction.from_float(float(r)) for r in risks]
        exact = min(Fraction(1), sum((a * b for a, b in itertools.combinations(values, 2)),
                                    Fraction()))
        bound = share_module.pair_risk_upper(risks)
        assert Fraction.from_float(bound) >= exact
        assert bound <= 1.0
    assert share_module.pair_risk_upper([1.0, 1e-18]) > 0.0
    assert share_module.pair_risk_upper([1e-200, 1e-200]) > 0.0
    assert np.isnan(share_module.pair_risk_upper([float("nan"), 0.2]))
    assert np.isnan(share_module.pair_risk_upper([-0.1, 0.2]))


@pytest.mark.parametrize("reference", [False, True])
@pytest.mark.parametrize("mixed", [False, True])
def test_combine_shares_preserves_precise_mixed_inputs(reference: bool, mixed: bool,
                                                      monkeypatch: pytest.MonkeyPatch) -> None:

    if reference:
        monkeypatch.setattr(share_module, "_NATIVE", None)
    additions = [np.float16(0.5), np.float32(0.25), np.float64(0.125), 0.0625]
    if mixed:
        additions.extend([Fraction(1, 3), 2**53 + 1])
    shares = [1e-18] * len(additions)
    combined = share_module._combine_shares(shares, additions)
    for actual, addition in zip(combined, additions, strict=True):
        exact = Fraction.from_float(float(addition)) if isinstance(addition, np.floating) else Fraction(addition)
        assert Fraction.from_float(actual) >= exact + Fraction.from_float(1e-18)


@pytest.mark.parametrize("reference", [False, True])
def test_changed_rows_matches_numpy_for_layouts_and_special_values(reference: bool, monkeypatch: pytest.MonkeyPatch) -> None:

    if reference:
        monkeypatch.setattr(prefix, "_NATIVE", None)
        monkeypatch.setattr(share_module, "_NATIVE", None)
    current = np.array([[0.0, -0.0, np.inf], [np.nan, 1.0, -np.inf],
                        [3.0, 4.0, 5.0], [6.0, 7.0, 8.0]])
    previous = current.copy()
    previous[2, 1] = 9.0
    for left, right in ((current, previous), (current[::2], previous[::2]),
                        (current.astype(np.float32), previous.astype(np.float32))):
        expected = tuple(int(k) for k in np.flatnonzero(np.any(left != right, axis=1)))
        assert prefix._changed_rows(left, right) == expected
    assert prefix._changed_rows(np.empty((0, 3)), np.empty((0, 3))) == ()


def test_native_prefix_validity_matches_general_parser() -> None:
    native = getattr(decoding._NATIVE, "valid_prefix", None)
    if native is None:
        pytest.skip("native prefix validation is not built")
    rng = np.random.default_rng(2034)
    samples = [[], [0], [1], [0, 0], [2, 0, 0], [3, 0, 0, 0], [-1], [2**63 - 1]]
    samples.extend(list(arities) for length in range(1, 7)
                   for arities in itertools.product(range(4), repeat=length))
    samples.extend(rng.integers(-1, 6, size=int(rng.integers(1, 20))).tolist()
                   for _ in range(3000))
    for arities in samples:
        assert native(np.asarray(arities, dtype=np.int64)) == (decoding.parse_reference(arities) is not None)
    assert not native(np.full(100_000, 2, dtype=np.int64))
    assert native(np.r_[np.ones(99_999, dtype=np.int64), np.zeros(1, dtype=np.int64)])


def test_native_grouped_argmax_preserves_first_class_ties() -> None:
    native = getattr(decoding._NATIVE, "grouped_argmax", None)
    if native is None:
        pytest.skip("native grouped argmax is not built")
    rng = np.random.default_rng(29)
    groups = np.array([7, 2, 7, 2, 9, 2], dtype=np.int64)
    decisions = rng.choice([2, 7, 9], size=100).astype(np.int64)
    for scores in (rng.normal(size=(100, 6)), np.zeros((100, 6)),
                   np.full((100, 6), -np.inf)):
        expected = [max((c for c, g in enumerate(groups) if g == d), key=row.__getitem__)
                    for row, d in zip(scores, decisions)]
        assert native(scores.reshape(-1), groups, decisions) == expected


def test_native_grouped_masses_handles_empty_and_reordered_groups() -> None:

    native = getattr(prefix._NATIVE, "grouped_masses", None)
    if native is None:
        pytest.skip("requires the native grouping kernel")
    groups = np.array([2, 0, 2, 3, 0, 2], dtype=np.int64)
    scores = np.arange(18, dtype=np.float64).reshape(3, 6)
    expected = [[sum(row[c] for c in range(6) if groups[c] == g) for g in range(5)]
                for row in scores]
    np.testing.assert_array_equal(np.array(native(scores.reshape(-1), groups, 5)).reshape(3, 5),
                                  expected)
    assert native(np.empty(0), groups, 5) == []
