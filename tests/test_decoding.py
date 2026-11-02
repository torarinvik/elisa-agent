import itertools
import math
import subprocess
import sys
from collections.abc import Callable, Sequence
from decimal import Decimal, localcontext
from typing import Any

import numpy as np
import pytest

torch = pytest.importorskip("torch")

from nca import decoding, formulas, priors
from nca.formulas import (Decoded, decode,
                          Split, decode_banded, decode_reference, parse)
from nca.modules.words import (ARITY_ORDER)


def parseable(m: int) -> list[tuple[int, ...]]:
    return [a for a in itertools.product(ARITY_ORDER, repeat=m) if parse(list(a)) is not None]


@pytest.mark.parametrize("reference", [False, True])
@pytest.mark.parametrize("alphabet", [(0, 1, 2), (2, 0, 1), (2, 1, 0)])
def test_format_risk_preserves_tiny_alternative_and_excludes_invalid_sequences(
        reference: bool, alphabet: tuple[int, ...], monkeypatch: pytest.MonkeyPatch) -> None:
    if reference:
        monkeypatch.setattr(priors, "_NATIVE", None)
        monkeypatch.setattr(decoding, "_NATIVE", None)
    canonical = np.array([[-np.inf, -40.0, 0.0], [0.0, 0.0, -np.inf],
                          [-1.0, -np.inf, -np.inf]])
    rows = canonical[:, alphabet]
    decoded = decode(rows, alphabet)
    assert decoded is not None and decoded.arities == (2, 0, 0)
    assert decoded.risk(rows, alphabet) == pytest.approx(np.exp(-40.0), rel=1e-14)
    assert decoded.risk(rows, alphabet, (2, 1, 0)) == 1.0


def test_format_risk_accepts_a_reduced_alphabet() -> None:
    rows = np.array([[0.0, 0.0], [0.0, 0.0]])
    result = decode(rows, (1, 0))
    assert result is not None and result.arities == (1, 0)
    assert result.risk(rows, (1, 0)) == 0.0

@pytest.mark.parametrize("decoder", [decode_reference, decode])
def test_decoder_matches_enumeration(decoder: Callable[..., Decoded | None]) -> None:
    """``NCA.dpSum_eq``, ``NCA.dpMax_ge`` and ``NCA.dpMax_attained`` against
    every arity sequence, with ``NCA.accepts_iff_codes`` as the language."""
    rng = np.random.default_rng(4)
    for m in range(1, 9):
        for _ in range(10):
            probs = rng.dirichlet(np.full(3, 0.5), size=m)
            decoded = decoder(np.log(probs), ARITY_ORDER)
            weights = {a: float(np.prod([probs[k, a_k] for k, a_k in enumerate(a)]))
                       for a in parseable(m)}
            if not weights:
                assert decoded is None
                continue
            assert decoded is not None and parse(list(decoded.arities)) is not None
            z = sum(weights.values())
            assert decoded.log_z == pytest.approx(np.log(z))
            assert weights[decoded.arities] == pytest.approx(max(weights.values()))
            marginals = np.zeros((m, 3))
            for a, w in weights.items():
                marginals[np.arange(m), list(a)] += w / z
            np.testing.assert_allclose(decoded.marginals, marginals, atol=1e-9)
            union = sum(1 - probs[k, a] for k, a in enumerate(decoded.arities))
            assert decoded.risk(np.log(probs), ARITY_ORDER) <= union + 1e-9

@pytest.mark.parametrize("slack", [1e-1, 1e-4])
def test_banded_decoder_is_certified(slack: float) -> None:
    """``NCA.banded_risk_le`` and ``NCA.banded_risk_slack``: the banded risk
    bounds the exact risk of the banded answer from above, within ``slack``,
    and the exactness certificate implies the exact answer."""
    rng = np.random.default_rng(5)
    for m in range(1, 9):
        for _ in range(20):
            probs = rng.dirichlet(np.full(3, 0.5), size=m)
            exact = decode_reference(np.log(probs), ARITY_ORDER)
            banded = decode_banded(np.log(probs), ARITY_ORDER, slack)
            if banded is None:
                assert exact is None
                continue
            assert exact is not None and parse(list(banded.arities)) is not None
            exact_risk = exact.risk(np.log(probs), ARITY_ORDER, banded.arities)
            assert exact_risk <= banded.risk + 1e-9
            assert banded.risk <= exact_risk + slack + 1e-9
            if banded.exact:
                assert banded.arities == exact.arities


@pytest.mark.parametrize("alphabet", [(0, 1, 3), (0, 3), (0, 1, 3, 2**63 - 1)])
def test_banded_decoder_supports_general_arities(alphabet) -> None:
    rng = np.random.default_rng(238)
    for m in range(1, 9):
        for _ in range(10):
            rows = np.log(rng.dirichlet(np.ones(len(alphabet)), size=m))
            exact, banded = decode_reference(rows, alphabet), decode_banded(rows, alphabet)
            assert (exact is None) == (banded is None)
            if exact is not None and banded is not None:
                exact_risk = exact.risk(rows, alphabet, banded.arities)
                assert exact_risk <= banded.risk + 1e-12
                assert banded.risk <= exact_risk + 1e-4 + 1e-12
                if banded.exact:
                    assert banded.arities == exact.arities


@pytest.mark.parametrize("alphabet, slack", [((), 1e-4), ((0, -1), 1e-4), ((0, 0), 1e-4),
                                              ((0, 1), 0.0), ((0, 1), 1.0)])
def test_banded_decoder_rejects_invalid_parameters(alphabet, slack) -> None:
    with pytest.raises(ValueError):
        decode_banded(np.zeros((1, len(alphabet))), alphabet, slack)


@pytest.mark.parametrize("rows", [np.array([[np.inf, -np.inf]]),
                                  np.array([[np.nan, -np.inf]]),
                                  np.array([[0.0, 0.0]])])
def test_banded_decoder_rejects_invalid_probability_rows(rows) -> None:
    with pytest.raises(ValueError, match="log probabilities"):
        decode_banded(rows, (0, 1))
    with pytest.raises(ValueError, match="log-probability"):
        decoding.band_changes(rows, [0], 1e-4)


@pytest.mark.parametrize("log_mass", [-40.0, -1000.0])
@pytest.mark.parametrize("reference_only", [False, True])
def test_banded_decoder_keeps_tiny_off_reference_mass(
        log_mass: float, reference_only: bool, monkeypatch: pytest.MonkeyPatch) -> None:
    if reference_only:
        monkeypatch.setattr(decoding, "_NATIVE", None)
    rows = np.array([[-np.inf, 0.0, log_mass], [0.0, -np.inf, -np.inf],
                     [0.0, -np.inf, -np.inf]])
    result = decode_banded(rows)
    assert result is not None and result.arities == (2, 0, 0)
    assert result.exact
    changes, tail = decoding.band_changes(rows, np.argmax(rows, axis=1), 1e-4)
    assert changes == 1 and tail > 0


def test_native_tail_mass_summary_matches_reference(monkeypatch: pytest.MonkeyPatch) -> None:
    if getattr(decoding._NATIVE, "tail_mass_summary", None) is None:
        pytest.skip("native tail mass kernel is not built")
    rng = np.random.default_rng(239)
    rows = rng.choice([0.0, -40.0, -1000.0, -np.inf], size=(12, 5))
    reference = rng.integers(0, rows.shape[1], size=len(rows))
    actual = decoding._tail_mass_summary(rows, reference)
    monkeypatch.setattr(decoding, "_NATIVE", None)
    expected = decoding._tail_mass_summary(rows, reference)
    np.testing.assert_allclose(actual, expected, atol=1e-12)


@pytest.mark.parametrize("block_size", [1, 3, 16, 100])
def test_native_tail_blocks_match_fresh_summary_after_updates(block_size: int) -> None:
    native = getattr(decoding._NATIVE, "tail_block_summary", None)
    if native is None:
        pytest.skip("native tail block kernel is not built")
    rng = np.random.default_rng(269)
    m = 31
    rows = np.log(rng.dirichlet(np.ones(4), size=m))
    reference = rng.integers(0, 4, size=m, dtype=np.int64)
    blocks = np.empty(2 * ((m - 1) // block_size + 1), dtype=np.float64)
    actual = native(rows.reshape(-1), reference, blocks, block_size, -1)
    np.testing.assert_allclose(actual, decoding._NATIVE.tail_mass_summary(rows.reshape(-1), reference),
                               atol=1e-13)
    for k in (0, 1, 15, 30, 15):
        rows[k] = np.log(rng.dirichlet(np.ones(4)))
        actual = native(rows.reshape(-1), reference, blocks, block_size, k)
        np.testing.assert_allclose(actual, decoding._NATIVE.tail_mass_summary(rows.reshape(-1), reference),
                                   atol=1e-13)
    rows[15] = [-np.inf] * 4
    actual = native(rows.reshape(-1), reference, blocks, block_size, 15)
    np.testing.assert_allclose(actual, decoding._NATIVE.tail_mass_summary(rows.reshape(-1), reference),
                               atol=1e-13)


def test_native_tail_blocks_reject_invalid_shapes() -> None:
    native = getattr(decoding._NATIVE, "tail_block_summary", None)
    if native is None:
        pytest.skip("native tail block kernel is not built")
    rows = np.array([0.0, -np.inf, 0.0, -np.inf])
    reference = np.array([0, 0], dtype=np.int64)
    blocks = np.zeros(2)
    assert not native(rows, reference, blocks, 0, -1)
    assert not native(rows, reference, blocks, 2, 2)
    assert not native(rows[:-1], reference, blocks, 2, -1)
    assert not native(rows, reference, np.zeros(1), 2, -1)
    assert not native(rows, np.array([0, 2], dtype=np.int64), blocks, 2, -1)


def test_native_tail_blocks_preserve_tiny_and_tolerated_mass() -> None:
    native = getattr(decoding._NATIVE, "tail_block_summary", None)
    if native is None:
        pytest.skip("native tail block kernel is not built")
    rows = np.tile([0.0, math.log(5e-13)], (1000, 1))
    reference = np.zeros(len(rows), dtype=np.int64)
    block_size = 32
    blocks = np.empty(2 * ((len(rows) - 1) // block_size + 1))
    off, factor = native(rows.reshape(-1), reference, blocks, block_size, -1)
    with localcontext() as context:
        context.prec = 80
        epsilon = Decimal.from_float(float(rows[0, 1])).exp()
        true_tail = (Decimal(1) + epsilon) ** len(rows) - 1
        bound = math.exp(decoding._band_log_tail(off, 1, factor))
        assert Decimal.from_float(bound) >= true_tail
    rows[0] = [0.0, -1000.0]
    off, factor = native(rows.reshape(-1), reference, blocks, block_size, 0)
    fresh = decoding._NATIVE.tail_mass_summary(rows.reshape(-1), reference)
    np.testing.assert_allclose([off, factor], fresh, atol=1e-13)


def test_native_tail_blocks_recombine_reference_and_off_mass() -> None:
    native = getattr(decoding._NATIVE, "tail_block_summary", None)
    if native is None:
        pytest.skip("native tail block kernel is not built")
    rows = np.array([[0.0, -40.0, -1000.0],
                     [-1001.0, -np.inf, 0.0],
                     [-np.inf, -1000.0, -1001.0],
                     [-np.inf, -np.inf, -np.inf]])
    reference = np.array([0, 1, 2, 0], dtype=np.int64)
    blocks = np.empty(4)
    off, factor = native(rows.reshape(-1), reference, blocks, 2, -1)
    with localcontext() as context:
        context.prec = 80
        weights = [[Decimal(0) if x == -np.inf else Decimal.from_float(float(x)).exp()
                    for x in row] for row in rows]
        exact_off = sum((w for row, r in zip(weights, reference)
                         for j, w in enumerate(row) if j != r), Decimal(0))
        exact_factor = sum((max(Decimal(0), sum(row).ln()) for row in weights if sum(row)),
                           Decimal(0))
        assert off == pytest.approx(float(exact_off.ln()), abs=1e-14)
        assert factor == pytest.approx(float(exact_factor), rel=1e-14, abs=1e-25)


@pytest.mark.parametrize("reference", [0, 1, 2])
@pytest.mark.parametrize("log_mass", [-40.0, -100.0, -700.0])
def test_native_tail_blocks_keep_tiny_excess_for_any_reference_order(
        reference: int, log_mass: float) -> None:
    native = getattr(decoding._NATIVE, "tail_block_summary", None)
    if native is None:
        pytest.skip("native tail block kernel is not built")
    rows = np.full((1, 3), -np.inf)
    rows[0, reference] = 0.0
    rows[0, (reference + 1) % 3] = log_mass
    blocks = np.empty(2)
    off, factor = native(rows.reshape(-1), np.array([reference], dtype=np.int64), blocks, 1, -1)
    with localcontext() as context:
        context.prec = 400
        exact_factor = (Decimal(1) + Decimal.from_float(log_mass).exp()).ln()
        assert off == log_mass
        assert factor == pytest.approx(float(exact_factor), rel=1e-14, abs=0.0)


@pytest.mark.parametrize("width", [3, 16, 64, 256])
def test_native_tail_blocks_wide_rows_against_high_precision(width: int) -> None:
    native = getattr(decoding._NATIVE, "tail_block_summary", None)
    if native is None:
        pytest.skip("native tail block kernel is not built")
    rng = np.random.default_rng(280 + width)
    probabilities = rng.dirichlet(np.full(width, 0.2), size=12) * (1 + 5e-13)
    rows = np.log(probabilities)
    reference = np.argmin(rows, axis=1).astype(np.int64)
    blocks = np.empty(2 * len(rows))
    off, factor = native(rows.reshape(-1), reference, blocks, 1, -1)
    with localcontext() as context:
        context.prec = 80
        weights = [[Decimal.from_float(float(x)).exp() for x in row] for row in rows]
        exact_off = sum((w for row, r in zip(weights, reference)
                         for j, w in enumerate(row) if j != r), Decimal(0))
        exact_factors = [max(Decimal(0), sum(row).ln()) for row in weights]
        assert off == pytest.approx(float(exact_off.ln()), abs=2e-14)
        assert factor == pytest.approx(float(sum(exact_factors)), abs=3e-15)
        for actual, expected in zip(blocks[1::2], exact_factors):
            assert actual == pytest.approx(float(expected), abs=1e-15)


def test_native_tail_blocks_remain_stable_across_many_updates() -> None:
    native = getattr(decoding._NATIVE, "tail_block_summary", None)
    if native is None:
        pytest.skip("native tail block kernel is not built")
    rng = np.random.default_rng(271)
    m, block_size = 137, 9
    choices = np.array([[0.0, -40.0, -1000.0, -np.inf],
                        [0.0, math.log(5e-13), -np.inf, -np.inf],
                        [-np.inf] * 4,
                        np.log([0.7, 0.2, 0.1, 1e-20])])
    rows = np.tile(choices[0], (m, 1))
    reference = np.zeros(m, dtype=np.int64)
    blocks = np.empty(2 * ((m - 1) // block_size + 1))
    native(rows.reshape(-1), reference, blocks, block_size, -1)
    for _ in range(3000):
        k = int(rng.integers(m))
        rows[k] = choices[int(rng.integers(len(choices)))]
        actual = native(rows.reshape(-1), reference, blocks, block_size, k)
        expected = decoding._NATIVE.tail_mass_summary(rows.reshape(-1), reference)
        np.testing.assert_allclose(actual, expected, rtol=0.0, atol=1e-13)


def test_native_tail_blocks_track_sparse_anchor_transitions() -> None:
    native = getattr(decoding._NATIVE, "tail_block_summary", None)
    if native is None:
        pytest.skip("native tail block kernel is not built")
    m, width, block_size = 17, 8, 4
    reference = np.arange(m, dtype=np.int64) % width
    rows = np.full((m, width), -np.inf)
    rows[np.arange(m), reference] = 0.0
    blocks = np.empty(2 * ((m - 1) // block_size + 1))
    assert native(rows.reshape(-1), reference, blocks, block_size, -1) == [-math.inf, 0.0]
    for k, log_weights in [(0, [-40.0]), (8, [-700.0, -701.0]),
                           (16, [-1000.0]), (0, []), (8, []), (16, [])]:
        rows[k, :] = -np.inf
        rows[k, reference[k]] = 0.0
        for j, log_weight in enumerate(log_weights, 1):
            rows[k, (reference[k] + j) % width] = log_weight
        off, factor = native(rows.reshape(-1), reference, blocks, block_size, k)
        with localcontext() as context:
            context.prec = 500
            weights = [[Decimal(0) if x == -np.inf else Decimal.from_float(float(x)).exp()
                        for x in row] for row in rows]
            exact_off = sum((w for row, r in zip(weights, reference)
                             for j, w in enumerate(row) if j != r), Decimal(0))
            exact_factor = sum((sum(row).ln() for row in weights), Decimal(0))
            if exact_off:
                assert off == pytest.approx(float(exact_off.ln()), abs=1e-12)
            else:
                assert off == -math.inf
            assert factor == pytest.approx(float(exact_factor), rel=1e-13, abs=0.0)


def test_native_tail_blocks_preserve_mass_when_zero_weights_move() -> None:
    native = getattr(decoding._NATIVE, "tail_block_summary", None)
    if native is None:
        pytest.skip("native tail block kernel is not built")
    rng = np.random.default_rng(282)
    finite = np.log(rng.dirichlet(np.full(32, 0.4)) * (1 + 5e-13))
    row = np.concatenate((finite, np.full(96, -np.inf)))
    reference = 0
    baseline = native(row, np.array([reference], dtype=np.int64), np.empty(2), 1, -1)
    for _ in range(20):
        order = rng.permutation(len(row))
        moved_reference = int(np.flatnonzero(order == reference)[0])
        actual = native(row[order], np.array([moved_reference], dtype=np.int64), np.empty(2), 1, -1)
        np.testing.assert_allclose(actual, baseline, rtol=0.0, atol=2e-15)


@pytest.mark.parametrize("shift", [0.0, -40.0])
@pytest.mark.parametrize("reference_only", [False, True])
def test_banded_risk_retains_tiny_accepted_alternative(
        shift: float, reference_only: bool, monkeypatch: pytest.MonkeyPatch) -> None:
    if reference_only:
        monkeypatch.setattr(decoding, "_NATIVE", None)
    rows = np.array([[-np.inf, -40.0, 0.0], [0.0, -40.0, -np.inf],
                     [0.0, -np.inf, -np.inf]])
    rows[0] += shift
    exact = decode_reference(rows)
    banded = decode_banded(rows)
    cursor = decoding.CertifiedSplit(rows)
    result = cursor.result()
    assert exact is not None and banded is not None and result is not None
    expected = exact.risk(rows, (0, 1, 2))
    assert expected == pytest.approx(np.exp(-80), rel=1e-12)
    assert banded.risk >= expected * (1 - 1e-12)
    assert result.risk >= expected * (1 - 1e-12)
    assert cursor.sequence_risk(result.arities) >= expected * (1 - 1e-12)


@pytest.mark.parametrize("reference_only", [False, True])
def test_banded_risk_retains_alternative_below_float_range(
        reference_only: bool, monkeypatch: pytest.MonkeyPatch) -> None:
    if reference_only:
        monkeypatch.setattr(decoding, "_NATIVE", None)
    rows = np.array([[-np.inf, -1000.0, 0.0], [0.0, -1000.0, -np.inf],
                     [0.0, -np.inf, -np.inf]])
    result = decode_banded(rows)
    assert result is not None and result.risk == np.nextafter(0.0, 1.0)


@pytest.mark.parametrize("alphabet", [(0, 1, 2), (2, 0, 1), (0, 1, 3), (0, 1, 3, 2**63 - 1)])
def test_native_format_partition_matches_reference(alphabet, monkeypatch: pytest.MonkeyPatch) -> None:
    if getattr(decoding._NATIVE, "format_partition", None) is None:
        pytest.skip("native format partition is not built")
    rng = np.random.default_rng(240)
    for m in range(1, 8):
        for _ in range(15):
            rows = np.log(rng.dirichlet(np.ones(len(alphabet)), size=m))
            chosen = decode_reference(rows, alphabet)
            if chosen is None:
                continue
            actual = decoding._format_sequence_risk(rows, alphabet, chosen.arities)
            with monkeypatch.context() as patch:
                patch.setattr(priors, "_NATIVE", None)
                expected = decoding._format_sequence_risk(rows, alphabet, chosen.arities)
            assert actual == pytest.approx(expected, rel=1e-12, abs=1e-15)


@pytest.mark.parametrize("alphabet", [(0, 1, 2), (0, 1, 3)])
def test_format_partition_matches_enumerated_paths(alphabet) -> None:
    rng = np.random.default_rng(241)
    for m in range(1, 7):
        rows = np.log(rng.dirichlet(np.ones(len(alphabet)), size=m))
        paths = [path for path in itertools.product(alphabet, repeat=m) if parse(path) is not None]
        if not paths:
            continue
        weights = np.array([np.exp(sum(rows[k, alphabet.index(a)] for k, a in enumerate(path)))
                            for path in paths])
        for index, path in enumerate(paths):
            expected = np.delete(weights, index).sum() / weights.sum()
            actual = decoding._format_sequence_risk(rows, alphabet, path)
            assert actual == pytest.approx(expected, rel=1e-12, abs=1e-15)


@pytest.mark.parametrize("reference_only", [False, True])
@pytest.mark.parametrize("shift", [0.0, -40.0])
def test_generic_decoded_risk_survives_log_weight_shift(
        reference_only: bool, shift: float, monkeypatch: pytest.MonkeyPatch) -> None:
    if reference_only:
        monkeypatch.setattr(priors, "_NATIVE", None)
    rows = np.array([[-np.inf, 0.0, -40.0], [-40.0, 0.0, -np.inf],
                     [-40.0, 0.0, -np.inf], [0.0, -np.inf, -np.inf]])
    rows[0] += shift
    result = decode_reference(rows, (0, 1, 3))
    assert result is not None and result.arities == (1, 1, 1, 0)
    assert result.risk(rows, (0, 1, 3)) == pytest.approx(np.exp(-120), rel=1e-12)


@pytest.mark.parametrize("alphabet", [(0, 1, 3), (3, 0, 1, 2**63 - 1)])
def test_generic_decoded_risk_is_stable_under_row_shifts(alphabet) -> None:
    rng = np.random.default_rng(248)
    for m in range(1, 8):
        for _ in range(10):
            rows = np.log(rng.dirichlet(np.ones(len(alphabet)), size=m))
            selected = decode_reference(rows, alphabet)
            if selected is None:
                continue
            shifted = rows - rng.uniform(0.0, 100.0, size=(m, 1))
            assert selected.risk(shifted, alphabet) == pytest.approx(
                selected.risk(rows, alphabet), rel=1e-12, abs=1e-14)


@pytest.mark.parametrize("reference_only", [False, True])
@pytest.mark.parametrize("rows, alphabet, selected", [
    (np.array([[-np.inf, 0.0, -1e308], [-1e308, 0.0, -np.inf],
               [0.0, 0.0, -np.inf], [0.0, -np.inf, -np.inf]]),
     (0, 1, 3), (1, 1, 1, 0)),
    (np.array([[-np.inf, 1e308, -np.inf], [1e308, -np.inf, -np.inf]]),
     (0, 1, 3), (1, 0)),
])
def test_generic_format_risk_rejects_log_arithmetic_overflow(
        reference_only: bool, rows, alphabet, selected, monkeypatch: pytest.MonkeyPatch) -> None:
    if reference_only:
        monkeypatch.setattr(priors, "_NATIVE", None)
    with pytest.raises(ValueError, match="format partition arithmetic is not finite"):
        priors.format_sequence_risk(rows, alphabet, selected)


@pytest.mark.parametrize("decoder", [decode, decode_reference])
@pytest.mark.parametrize("value", [-1e308, 1e308])
def test_format_decoder_rejects_finite_log_weight_overflow(decoder, value) -> None:
    rows = np.array([[-np.inf, value, -np.inf], [value, -np.inf, -np.inf]])
    with pytest.raises(ValueError, match="format decoding arithmetic is not finite"):
        decoder(rows)


def test_format_decoder_handles_large_positive_log_weights() -> None:
    rows = np.array([[-np.inf, 1000.0, -np.inf], [1000.0, -np.inf, -np.inf]])
    actual, expected = decode(rows), decode_reference(rows)
    assert actual is not None and expected is not None
    assert actual.arities == expected.arities == (1, 0)
    assert actual.log_z == expected.log_z == 2000.0
    np.testing.assert_allclose(actual.marginals, expected.marginals)


def test_banded_decoder_rejects_finite_log_weight_overflow() -> None:
    rows = np.array([[-np.inf, -1e308, -np.inf], [-1e308, -np.inf, -np.inf]])
    with pytest.raises(ValueError, match="format decoding arithmetic is not finite"):
        decode_banded(rows)


@pytest.mark.parametrize("value", [-1e307, -2e307])
def test_banded_pass_retains_large_representable_log_sums(value: float) -> None:
    rows = np.array([[-np.inf, value, -np.inf], [value, -np.inf, -np.inf]])
    result = decoding._banded_passes(rows, (0, 1, 2), (1, 1, 0), 0)
    assert result == (2 * value, 2 * value, (1, 0))


def test_banded_pass_ignores_overflow_outside_its_band() -> None:
    rows = np.array([[-np.inf, -1e308, -np.inf], [-1e308, 0.0, -np.inf],
                     [0.0, -np.inf, -np.inf]])
    result = decoding._banded_passes(rows, (0, 1, 2), (1, 1, 1, 0), 0)
    assert result == (-1e308, -1e308, (1, 1, 0))


@pytest.mark.parametrize("reference_only", [False, True])
def test_banded_pass_ignores_overflow_when_final_state_is_outside_band(
        reference_only: bool, monkeypatch: pytest.MonkeyPatch) -> None:
    if reference_only:
        monkeypatch.setattr(decoding, "_NATIVE", None)
    rows = np.array([[-np.inf, -1e308, -np.inf], [-np.inf, -1e308, -np.inf],
                     [0.0, -np.inf, -np.inf]])
    assert decoding._banded_passes(rows, (0, 1, 2), (1, 1, 1, 1), 0) is None


@pytest.mark.parametrize("reference_only", [False, True])
@pytest.mark.parametrize("extreme", [2**63 - 1, -(2**63)])
def test_banded_pass_handles_extreme_numpy_centres(
        reference_only: bool, extreme: int, monkeypatch: pytest.MonkeyPatch) -> None:
    if reference_only:
        monkeypatch.setattr(decoding, "_NATIVE", None)
    rows = np.array([[-np.inf, 0.0, -np.inf], [0.0, -np.inf, -np.inf]])
    centre = np.array([1, extreme, 0], dtype=np.int64)
    with np.errstate(over="raise"):
        assert decoding._banded_passes(rows, (0, 1, 2), centre, 1) is None


@pytest.mark.parametrize("alphabet", [(0, 1, 2), (0, 3)])
@pytest.mark.parametrize("reference_only", [False, True])
def test_banded_pass_matches_enumeration_with_arbitrary_bands(
        alphabet, reference_only: bool, monkeypatch: pytest.MonkeyPatch) -> None:
    if reference_only:
        monkeypatch.setattr(decoding, "_NATIVE", None)
    rng = np.random.default_rng(253)
    for m in range(1, 6):
        for _ in range(20):
            rows = rng.choice([-np.inf, -3.0, -1.0, 0.0], size=(m, len(alphabet)))
            centre = rng.integers(-2, m + 3, size=m + 1).tolist()
            half = int(rng.integers(0, m + 2))
            accepted = []
            for path in itertools.product(alphabet, repeat=m):
                pending = 1
                states = [pending]
                for a in path:
                    if pending < 1:
                        break
                    pending += a - 1
                    states.append(pending)
                if (len(states) != m + 1 or pending != 0
                        or any(abs(state - c) > half for state, c in zip(states, centre, strict=True))):
                    continue
                score = sum(rows[k, alphabet.index(a)] for k, a in enumerate(path))
                if np.isfinite(score):
                    accepted.append((path, score))
            result = decoding._banded_passes(rows, alphabet, centre, half)
            if not accepted:
                assert result is None
            else:
                assert result is not None
                log_z, log_x, path = result
                scores = [score for _, score in accepted]
                assert log_z == pytest.approx(np.logaddexp.reduce(scores), abs=1e-12)
                assert log_x == pytest.approx(max(scores), abs=1e-12)
                assert (path, log_x) in accepted


@pytest.mark.parametrize("alphabet", [(0, 1, 2), (0, 1, 3), (0, 3, 2**63 - 1)])
def test_native_banded_pass_matches_reference(alphabet, monkeypatch: pytest.MonkeyPatch) -> None:
    if getattr(decoding._NATIVE, "banded_format", None) is None:
        pytest.skip("native banded decoder is not built")
    rng = np.random.default_rng(255)
    for m in range(1, 13):
        for _ in range(10):
            rows = np.log(rng.dirichlet(np.ones(len(alphabet)), size=m))
            centre = rng.integers(-m, m * 2 + 1, size=m + 1).tolist()
            half = int(rng.integers(0, m * 2 + 1))
            actual = decoding._banded_passes(rows, alphabet, centre, half)
            with monkeypatch.context() as patch:
                patch.setattr(decoding, "_NATIVE", None)
                expected = decoding._banded_passes(rows, alphabet, centre, half)
            assert (actual is None) == (expected is None)
            if actual is not None and expected is not None:
                assert actual[0] == pytest.approx(expected[0], abs=1e-12)
                assert actual[1] == pytest.approx(expected[1], abs=1e-12)
                assert actual[2] == expected[2]


@pytest.mark.parametrize("alphabet", [(0, 1, 2), (2, 0, 1), (0, 1, 3)])
def test_native_banded_pass_matches_sparse_ties(alphabet, monkeypatch: pytest.MonkeyPatch) -> None:
    if getattr(decoding._NATIVE, "banded_format", None) is None:
        pytest.skip("native banded decoder is not built")
    rng = np.random.default_rng(258)
    for m in range(1, 10):
        for _ in range(30):
            rows = rng.choice([-np.inf, -1000.0, -3.0, -1.0, 0.0], size=(m, len(alphabet)))
            centre = [1] * m + [0]
            half = int(rng.integers(0, m + 2))
            actual = decoding._banded_passes(rows, alphabet, centre, half)
            with monkeypatch.context() as patch:
                patch.setattr(decoding, "_NATIVE", None)
                expected = decoding._banded_passes(rows, alphabet, centre, half)
            assert (actual is None) == (expected is None)
            if actual is not None and expected is not None:
                np.testing.assert_allclose(actual[:2], expected[:2], rtol=0, atol=1e-10)
                assert actual[2] == expected[2]


def test_finite_band_tail_overflow_is_not_treated_as_absent_mass() -> None:
    with pytest.raises(ValueError, match="band tail arithmetic is not finite"):
        decoding._band_log_tail(-1e308, 2)
    assert decoding._band_log_tail(-np.inf, 2) == -np.inf


@pytest.mark.parametrize("reference_only", [False, True])
def test_band_tail_is_zero_beyond_number_of_words(
        reference_only: bool, monkeypatch: pytest.MonkeyPatch) -> None:
    if reference_only:
        monkeypatch.setattr(decoding, "_NATIVE", None)
    rows = np.log(np.full((3, 3), 1 / 3))
    changes, tail = decoding.band_changes(rows, np.zeros(3, dtype=np.int64), 1e-4)
    assert changes == 4 and tail == 0.0
    exact = decode_reference(rows)
    banded = decode_banded(rows)
    cursor = decoding.CertifiedSplit(rows).result()
    assert exact is not None and banded is not None and cursor is not None
    assert banded.exact and cursor.exact
    assert banded.risk == pytest.approx(exact.risk(rows, (0, 1, 2)), abs=1e-12)
    assert cursor.risk == pytest.approx(exact.risk(rows, (0, 1, 2)), abs=1e-12)


def test_band_tail_for_empty_input_is_zero() -> None:
    assert decoding.band_changes(np.empty((0, 3)), [], 1e-4) == (1, 0.0)


@pytest.mark.parametrize("reference_only", [False, True])
def test_full_band_cursor_does_not_rescan_tail(
        reference_only: bool, monkeypatch: pytest.MonkeyPatch) -> None:
    if reference_only:
        monkeypatch.setattr(decoding, "_NATIVE", None)
    rows = np.log(np.full((3, 3), 1 / 3))
    cursor = decoding.CertifiedSplit(rows)
    assert cursor.arity_bound * (cursor.changes - 1) >= cursor.cover_half
    expected = decoding.decode_reference(rows)
    assert expected is not None

    def unexpected_scan(*args: object) -> tuple[float, float]:
        raise AssertionError("a full band has no outside tail")

    monkeypatch.setattr(decoding, "_tail_mass_summary", unexpected_scan)
    assert cursor.normalizer() == pytest.approx(expected.log_z)
    updated = np.log(np.array([0.6, 0.3, 0.1]))
    rows[1] = updated
    expected = decoding.decode_reference(rows)
    assert expected is not None
    assert cursor.climb_normalizer(1, updated) == pytest.approx(expected.log_z)


@pytest.mark.parametrize("reference_only", [False, True])
def test_banded_cursor_reuses_tail_summary_until_row_update(
        reference_only: bool, monkeypatch: pytest.MonkeyPatch) -> None:
    if reference_only:
        monkeypatch.setattr(decoding, "_NATIVE", None)
    rows = np.log(np.tile([0.00001, 0.99998, 0.00001], (15, 1)))
    rows[-1] = np.log([0.99998, 0.00001, 0.00001])
    original = decoding._tail_mass_summary
    calls = 0

    def counted_summary(log_probs: np.ndarray, reference: Sequence[int]) -> tuple[float, float]:
        nonlocal calls
        calls += 1
        return original(log_probs, reference)

    monkeypatch.setattr(decoding, "_tail_mass_summary", counted_summary)
    cursor = decoding.CertifiedSplit(rows)
    assert cursor.arity_bound * (cursor.changes - 1) < cursor.cover_half
    initial_calls = 1 if cursor._tail_blocks is None else 0
    assert calls == initial_calls
    assert cursor.normalizer() is not None
    assert cursor.normalizer() is not None
    assert calls == initial_calls
    updated = np.log(np.array([0.00002, 0.99996, 0.00002]))
    rows[2] = updated
    upper = cursor.climb_normalizer(2, updated)
    expected_calls = initial_calls + (1 if cursor._tail_blocks is None else 0)
    assert upper is not None and calls == expected_calls
    exact = decoding.decode_reference(rows)
    assert exact is not None and upper >= exact.log_z - 1e-12
    assert cursor.normalizer() == pytest.approx(upper)
    assert calls == expected_calls


@pytest.mark.parametrize("reference_only", [False, True])
def test_initial_cursor_band_matches_standalone_near_thresholds(
        reference_only: bool, monkeypatch: pytest.MonkeyPatch) -> None:
    if reference_only:
        monkeypatch.setattr(decoding, "_NATIVE", None)
    rows = np.log(np.tile([0.02, 0.97, 0.01], (12, 1)))
    rows[-1] = np.log([0.97, 0.02, 0.01])
    reference = np.argmax(rows, axis=1)
    log_off, log_factor = decoding._tail_mass_summary(rows, reference)
    for changes in range(1, 8):
        threshold = math.exp(decoding._band_log_tail(log_off, changes, log_factor))
        for slack in (math.nextafter(threshold, 0.0), threshold,
                      math.nextafter(threshold, 1.0)):
            if 0 < slack < 1:
                expected, _ = decoding.band_changes(rows, reference, slack)
                assert decoding.CertifiedSplit(rows, slack=slack).changes == expected


def test_tail_summary_uses_older_native_fallback(monkeypatch: pytest.MonkeyPatch) -> None:
    native = getattr(decoding._NATIVE, "tail_mass_summary", None)
    if native is None:
        pytest.skip("native tail summary kernel is not built")

    class OlderNative:
        tail_mass_summary = staticmethod(native)

    monkeypatch.setattr(decoding, "_NATIVE", OlderNative())
    rows = np.log(np.array([[0.2, 0.8], [0.7, 0.3]]))
    reference = np.array([1, 0], dtype=np.int64)
    assert decoding._tail_mass_blocks(rows, reference) is None
    assert decoding._tail_mass_summary(rows, reference) == pytest.approx(
        native(rows.reshape(-1), reference))


@pytest.mark.parametrize("reference_only", [False, True])
def test_band_changes_accepts_strided_reference_indices(
        reference_only: bool, monkeypatch: pytest.MonkeyPatch) -> None:
    if reference_only:
        monkeypatch.setattr(decoding, "_NATIVE", None)
    rows = np.log(np.tile([0.8, 0.2], (6, 1)))
    reference = np.array([0, 1, 1, 1, 0, 1, 0, 1, 0, 1, 1, 1], dtype=np.int64)[::2]
    assert not reference.flags.c_contiguous
    assert decoding._tail_mass_summary(rows, reference) == pytest.approx(
        decoding._tail_mass_summary(rows, reference.copy()))
    assert decoding.band_changes(rows, reference, 0.01) == pytest.approx(
        decoding.band_changes(rows, reference.copy(), 0.01))


def test_banded_cursor_recovers_if_block_update_fails() -> None:
    if getattr(decoding._NATIVE, "tail_block_summary", None) is None:
        pytest.skip("native tail block kernel is not built")
    rows = np.log(np.tile([0.00001, 0.99998, 0.00001], (15, 1)))
    rows[-1] = np.log([0.99998, 0.00001, 0.00001])
    cursor = decoding.CertifiedSplit(rows)
    assert cursor._tail_blocks is not None
    assert cursor.normalizer() is not None

    def failed_update(*args: object) -> list[float]:
        raise RuntimeError("block update failed")

    cursor._tail_block_kernel = failed_update
    rows[2] = np.log([0.00002, 0.99996, 0.00002])
    with pytest.raises(RuntimeError, match="block update failed"):
        cursor.climb_normalizer(2, rows[2])
    assert cursor._tail_blocks is None and cursor.log_upper is None
    upper = cursor.normalizer()
    exact = decoding.decode_reference(rows)
    assert upper is not None and exact is not None
    assert upper >= exact.log_z - 1e-12


@pytest.mark.parametrize("reference_only", [False, True])
def test_certified_cursor_validates_before_committing_row(
        reference_only: bool, monkeypatch: pytest.MonkeyPatch) -> None:
    if reference_only:
        monkeypatch.setattr(decoding, "_NATIVE", None)
    rows = np.log(np.tile([0.1, 0.8, 0.1], (5, 1)))
    cursor = decoding.CertifiedSplit(rows)
    original = cursor.normalizer()
    assert original is not None
    for row in (np.array([np.nan, -np.inf, -np.inf]),
                np.array([np.inf, -np.inf, -np.inf]),
                np.array([0.0, 0.0, -np.inf]), np.array([0.0])):
        with pytest.raises(ValueError):
            cursor.climb_normalizer(2, row)
        np.testing.assert_array_equal(cursor.log_probs, rows)
        np.testing.assert_array_equal(cursor.split.log_probs, rows)
        assert cursor.log_upper == original
    for index in (-1, len(rows), 1.5):
        with pytest.raises(IndexError):
            cursor.climb_normalizer(index, rows[0])
        np.testing.assert_array_equal(cursor.log_probs, rows)
        assert cursor.log_upper == original


def test_banded_cursor_releases_blocks_after_widening_to_full_band() -> None:
    if getattr(decoding._NATIVE, "tail_block_summary", None) is None:
        pytest.skip("native tail block kernel is not built")
    rows = np.log(np.tile([0.00001, 0.99998, 0.00001], (7, 1)))
    rows[-1] = np.log([0.99998, 0.00001, 0.00001])
    cursor = decoding.CertifiedSplit(rows)
    assert cursor._tail_blocks is not None
    assert cursor.normalizer() is not None
    rows[3] = np.log([0.99998, 0.00001, 0.00001])
    upper = cursor.climb_normalizer(3, rows[3])
    exact = decoding.decode_reference(rows)
    assert cursor.rebuilds > 0
    assert cursor.arity_bound * (cursor.changes - 1) >= cursor.cover_half
    assert cursor._tail_blocks is None and cursor._tail_summary is None
    assert upper is not None and exact is not None
    assert upper == pytest.approx(exact.log_z, abs=1e-12)

    rows[1] = np.log([0.00002, 0.99996, 0.00002])
    upper = cursor.climb_normalizer(1, rows[1])
    exact = decoding.decode_reference(rows)
    assert upper is not None and exact is not None
    assert upper == pytest.approx(exact.log_z, abs=1e-12)
    assert cursor._tail_blocks is None and cursor._tail_summary is None


@pytest.mark.parametrize("reference_only", [False, True])
def test_band_tail_accounts_for_tolerated_row_excess(
        reference_only: bool, monkeypatch: pytest.MonkeyPatch) -> None:
    if reference_only:
        monkeypatch.setattr(decoding, "_NATIVE", None)
    m = 1000
    log_epsilon = float(np.log(5e-13))
    rows = np.tile(np.array([0.0, log_epsilon]), (m, 1))
    changes, bound = decoding.band_changes(rows, np.zeros(m, dtype=np.int64), 0.1)
    with localcontext() as context:
        context.prec = 80
        epsilon = Decimal.from_float(log_epsilon).exp()
        true_tail = (Decimal(1) + epsilon) ** m - 1
        assert changes == 1
        assert Decimal.from_float(bound) >= true_tail


@pytest.mark.parametrize("reference_only", [False, True])
@pytest.mark.parametrize("weights", [
    [[0.7, 0.2, 0.1000000000004], [0.3, 0.6000000000004, 0.1],
     [0.2000000000004, 0.3, 0.5], [0.4, 0.4, 0.2000000000004]],
    [[0.7, 0.6, 0.3], [0.3, 0.6, 0.5], [0.2, 0.8, 0.5], [0.4, 0.7, 0.6]],
])
def test_scaled_tail_bound_against_enumerated_sequences(
        reference_only: bool, weights: list[list[float]], monkeypatch: pytest.MonkeyPatch) -> None:
    if reference_only:
        monkeypatch.setattr(decoding, "_NATIVE", None)
    rows = np.log(np.array(weights))
    reference = [0, 1, 2, 0]
    log_off, log_factor = decoding._tail_mass_summary(rows, reference)
    assert log_factor > 0
    with localcontext() as context:
        context.prec = 80
        weights = [[Decimal.from_float(float(x)).exp() for x in row] for row in rows]
        for changes in range(1, len(reference) + 1):
            tail = sum((math.prod(weights[k][a] for k, a in enumerate(sequence))
                        for sequence in itertools.product(range(3), repeat=len(reference))
                        if sum(a != r for a, r in zip(sequence, reference)) >= changes),
                       Decimal(0))
            bound = math.exp(decoding._band_log_tail(log_off, changes, log_factor))
            assert Decimal.from_float(bound) >= tail * Decimal("0.99999999999999")


@pytest.mark.parametrize("reference_only", [False, True])
def test_band_tail_accounts_for_excess_after_cursor_update(
        reference_only: bool, monkeypatch: pytest.MonkeyPatch) -> None:
    if reference_only:
        monkeypatch.setattr(decoding, "_NATIVE", None)
    rows = np.log(np.array([[0.2, 0.8], [0.8, 0.2], [0.8, 0.2]]))
    cursor = decoding.CertifiedSplit(rows, (0, 1))
    assert cursor.normalizer() is not None
    update = np.array([0.0, np.log(5e-13)])
    assert cursor.climb_normalizer(0, update) is not None
    rows[0] = update
    log_off, log_factor = decoding._tail_mass_summary(rows, cursor.reference)
    assert log_factor > 0
    assert cursor.sequence_risk((1, 1, 0)) >= decoding.decode_reference(rows, (0, 1)).risk(
        rows, (0, 1), (1, 1, 0)) - 1e-12


@pytest.mark.parametrize("reference_only", [False, True])
@pytest.mark.parametrize("reference", [[0.5, 1], [0.0, 1.0], [-1, 1], [0, 2],
                                        [0, 10**100], np.array([[0], [1]])])
def test_band_changes_rejects_invalid_reference_indices(
        reference_only: bool, reference, monkeypatch: pytest.MonkeyPatch) -> None:
    if reference_only:
        monkeypatch.setattr(decoding, "_NATIVE", None)
    rows = np.log(np.array([[0.8, 0.2], [0.6, 0.4]]))
    with pytest.raises(ValueError, match="reference must index"):
        decoding.band_changes(rows, reference, 0.1)


@pytest.mark.parametrize("dtype", [np.int32, np.int64, np.uint64])
def test_band_changes_accepts_integer_reference_arrays(dtype) -> None:
    rows = np.log(np.array([[0.8, 0.2], [0.6, 0.4]]))
    assert decoding.band_changes(rows, np.array([0, 1], dtype=dtype), 0.1) == \
        decoding.band_changes(rows, [0, 1], 0.1)


@pytest.mark.parametrize("log_factor", [0.0, 0.1, 1e-8])
def test_native_tail_search_matches_reference_at_rounding_boundaries(
        log_factor: float,
        monkeypatch: pytest.MonkeyPatch) -> None:
    if getattr(decoding._NATIVE, "initial_band_changes_scaled", None) is None:
        pytest.skip("native band tail search is not built")
    for length in (2, 3, 10, 50):
        for total in (0.1, 0.5, 1.0, 3.0, 10.0):
            log_off = math.log(total)
            for changes in range(1, min(length, 30) + 1):
                log_tail = decoding._band_log_tail(log_off, changes, log_factor)
                if not -740 < log_tail < 0:
                    continue
                threshold = math.exp(log_tail)
                for slack in (math.nextafter(threshold, 0.0), threshold,
                              math.nextafter(threshold, 1.0)):
                    if not 0 < slack < 1:
                        continue
                    actual = decoding._initial_band_changes(log_off, slack, length, log_factor)
                    with monkeypatch.context() as patch:
                        patch.setattr(decoding, "_NATIVE", None)
                        expected = decoding._initial_band_changes(log_off, slack, length, log_factor)
                    assert actual == expected


def test_native_tail_search_matches_linear_reference(monkeypatch: pytest.MonkeyPatch) -> None:
    if getattr(decoding._NATIVE, "initial_band_changes_scaled", None) is None:
        pytest.skip("native band tail search is not built")
    rng = np.random.default_rng(267)
    for _ in range(500):
        length = int(rng.integers(0, 500))
        log_off = float(rng.uniform(-20, math.log(600)))
        log_factor = float(rng.uniform(0, 1))
        slack = math.exp(float(rng.uniform(-40, -0.001)))
        actual = decoding._initial_band_changes(log_off, slack, length, log_factor)
        with monkeypatch.context() as patch:
            patch.setattr(decoding, "_NATIVE", None)
            expected = decoding._initial_band_changes(log_off, slack, length, log_factor)
        assert actual == expected


@pytest.mark.parametrize(("total", "slack", "length", "expected"), [
    (0.01, 0.1, 5, 1),
    (1.0, 0.01, 5, 5),
    (1.0, 0.001, 5, 6),
    (10.0, 0.1, 0, 1),
])
@pytest.mark.parametrize("reference_only", [False, True])
def test_tail_search_stops_at_first_or_last_possible_change(
        total: float, slack: float, length: int, expected: int,
        reference_only: bool, monkeypatch: pytest.MonkeyPatch) -> None:
    if reference_only:
        monkeypatch.setattr(decoding, "_NATIVE", None)
    assert decoding._initial_band_changes(math.log(total), slack, length) == expected


def test_native_tail_search_handles_integer_length_limits() -> None:
    if getattr(decoding._NATIVE, "initial_band_changes_scaled", None) is None:
        pytest.skip("native band tail search is not built")
    # Isolate the call: a regression in the sentinel calculation can trap.
    code = (
        "from nca.native.decoding import initial_band_changes_scaled as f; "
        "print(f(0.0, 0.0, -1.0, 2**63 - 1), f(0.0, 0.0, -1.0, -1))"
    )
    result = subprocess.run([sys.executable, "-c", code], capture_output=True, text=True)
    assert result.returncode == 0, result.stderr
    assert result.stdout.strip() == "-1 -1"

    log_off, slack = math.log(1e9), 1e-4
    changes = decoding._initial_band_changes(log_off, slack, 2**63 - 2)
    assert decoding._band_log_tail(log_off, changes) <= math.log(slack)
    assert decoding._band_log_tail(log_off, changes - 1) > math.log(slack)


def test_native_log_decoder_signals_finite_log_weight_overflow() -> None:
    native = getattr(decoding._NATIVE, "decode_log", None)
    if native is None:
        pytest.skip("native log decoder is not built")
    rows = np.array([[-np.inf, -1e308, -np.inf], [-1e308, -np.inf, -np.inf]])
    result = native(rows.reshape(-1), np.asarray((0, 1, 2), dtype=np.int64))
    assert len(result) == 1 and np.isnan(result[0])

def test_split_matches_full_decoding() -> None:
    """``NCA.dpSum_append`` and ``NCA.dpMax_append``: after changing one
    word's weights, the cached vectors give the full programs' results."""
    rng = np.random.default_rng(6)
    for m in range(1, 12):
        for _ in range(10):
            probs = rng.dirichlet(np.full(3, 0.5), size=m)
            split = Split(np.log(probs), ARITY_ORDER)
            k = int(rng.integers(m))
            probs[k] = rng.dirichlet(np.full(3, 0.5))
            full = decode_reference(np.log(probs), ARITY_ORDER)
            log_z, log_x = split.scores(k, np.log(probs[k]))
            if full is None:
                assert log_z == -np.inf
                continue
            assert log_z == pytest.approx(full.log_z)
            assert log_x == pytest.approx(full.log_weight(np.log(probs), ARITY_ORDER,
                                                          full.arities))


@pytest.mark.parametrize("reference_only", [False, True])
@pytest.mark.parametrize("alphabet", [(0, 1, 2), (0, 1, 3), (0, 1, 3, 2**63 - 1)])
def test_split_reachable_bounds_preserve_general_arity_updates(
        reference_only: bool, alphabet, monkeypatch: pytest.MonkeyPatch) -> None:
    if reference_only:
        monkeypatch.setattr(decoding, "_NATIVE", None)
    rng = np.random.default_rng(251)
    m = 9
    rows = np.log(rng.dirichlet(np.ones(len(alphabet)), size=m))
    cursor = Split(rows, alphabet)
    growth = max(0, max(alphabet) - 1)
    assert cursor.high.tolist() == [min(m - k, 1 + k * growth) for k in range(m + 1)]
    for _ in range(12):
        k = int(rng.integers(m))
        rows[k] = np.log(rng.dirichlet(np.ones(len(alphabet))))
        score, _ = cursor.climb(k, rows[k])
        exact = decode_reference(rows, alphabet)
        assert exact is not None
        assert score == pytest.approx(exact.log_z, abs=1e-12)


@pytest.mark.parametrize("reference_only", [False, True])
def test_split_retains_underflowed_paths_through_climbs(
        reference_only: bool, monkeypatch: pytest.MonkeyPatch) -> None:
    if reference_only:
        monkeypatch.setattr(decoding, "_NATIVE", None)
    rows = np.array([[-np.inf, 0.0, -1000.0], [0.0, -np.inf, -np.inf],
                     [0.0, -np.inf, -np.inf]])
    split = Split(rows)
    for k, replacement in ((1, rows[1]), (0, np.array([-np.inf, -2.0, -900.0])),
                           (2, np.array([-1.0, -np.inf, -np.inf]))):
        rows[k] = replacement
        expected = decode_reference(rows)
        assert expected is not None
        log_z, log_x = split.climb(k, replacement)
        assert log_z == pytest.approx(expected.log_z, abs=1e-12)
        assert log_x == pytest.approx(expected.log_z, abs=1e-12)
    result = decoding.CertifiedSplit(rows).result()
    assert result is not None and result.arities == (2, 0, 0)


@pytest.mark.parametrize("reference_only", [False, True])
def test_split_retains_underflowed_products(reference_only: bool, monkeypatch: pytest.MonkeyPatch) -> None:
    if reference_only:
        monkeypatch.setattr(decoding, "_NATIVE", None)
    rows = np.array([[-np.inf, 0.0, -400.0], [-400.0, -400.0, -np.inf],
                     [0.0, -np.inf, -np.inf]])
    split = Split(rows)
    expected = decode_reference(rows)
    assert expected is not None
    for k in range(len(rows)):
        log_z, _ = split.scores(k, rows[k])
        assert log_z == pytest.approx(expected.log_z, abs=1e-12)


@pytest.mark.parametrize("reference_only", [False, True])
@pytest.mark.parametrize("value", [-1e308, 1e308])
def test_split_rejects_finite_log_overflow_during_construction(
        reference_only: bool, value: float, monkeypatch: pytest.MonkeyPatch) -> None:
    if reference_only:
        monkeypatch.setattr(decoding, "_NATIVE", None)
    rows = np.array([[-np.inf, value, -np.inf], [value, -np.inf, -np.inf]])
    with pytest.raises(ValueError, match="format decoding arithmetic is not finite"):
        Split(rows)


@pytest.mark.parametrize("reference_only", [False, True])
@pytest.mark.parametrize("value", [-1e308, 1e308])
def test_split_rejects_overflowing_climb_without_mutation(
        reference_only: bool, value: float, monkeypatch: pytest.MonkeyPatch) -> None:
    if reference_only:
        monkeypatch.setattr(decoding, "_NATIVE", None)
    rows = np.array([[-np.inf, value, -np.inf], [0.0, -np.inf, -np.inf]])
    cursor = Split(rows)
    with pytest.raises(ValueError, match="format decoding arithmetic is not finite"):
        cursor.climb(1, np.array([value, -np.inf, -np.inf]))
    np.testing.assert_array_equal(cursor.log_probs, rows)
    assert cursor.best(1) == (value, (1, 0))
    assert cursor.climb(1, rows[1])[0] == value


@pytest.mark.parametrize("reference_only", [False, True])
def test_split_ignores_overflow_on_path_without_a_suffix(
        reference_only: bool, monkeypatch: pytest.MonkeyPatch) -> None:
    if reference_only:
        monkeypatch.setattr(decoding, "_NATIVE", None)
    rows = np.array([[-np.inf, -1e308, -np.inf], [0.0, 0.0, -np.inf],
                     [0.0, -np.inf, -np.inf]])
    cursor = Split(rows)
    replacement = np.array([-1e308, 0.0, -np.inf])
    assert cursor.scores(1, replacement) == (-1e308, -1e308)


@pytest.mark.parametrize("reference_only", [False, True])
def test_split_best_reports_absent_path_and_recovers_after_climb(
        reference_only: bool, monkeypatch: pytest.MonkeyPatch) -> None:
    if reference_only:
        monkeypatch.setattr(decoding, "_NATIVE", None)
    rows = np.array([[-np.inf, 0.0, -np.inf], [-np.inf, 0.0, -np.inf],
                     [-np.inf, 0.0, -np.inf]])
    split = Split(rows)
    for k in range(len(rows)):
        assert split.best(k) == (-np.inf, ())
    replacement = np.array([0.0, -np.inf, -np.inf])
    split.climb(2, replacement)
    for k in range(len(rows)):
        assert split.best(k) == (0.0, (1, 1, 0))


@pytest.mark.parametrize("reference_only", [False, True])
def test_split_best_ignores_unreachable_large_numpy_arity(
        reference_only: bool, monkeypatch: pytest.MonkeyPatch) -> None:
    if reference_only:
        monkeypatch.setattr(decoding, "_NATIVE", None)
    alphabet = np.array([0, 1, 2, 2**63 - 1], dtype=np.int64)
    rows = np.log(np.tile([0.3, 0.1, 0.5, 0.1], (5, 1)))
    split = Split(rows, alphabet)
    full = decode_reference(rows, alphabet)
    assert full is not None
    for k in range(len(rows)):
        score, path = split.best(k)
        assert parse(path) is not None
        assert score == pytest.approx(full.log_weight(rows, alphabet, full.arities))


@pytest.mark.parametrize("reference_only", [False, True])
def test_split_rejects_invalid_rows_and_indices_before_native_calls(
        reference_only: bool, monkeypatch: pytest.MonkeyPatch) -> None:
    if reference_only:
        monkeypatch.setattr(decoding, "_NATIVE", None)
    split = Split(np.zeros((3, 3)))
    for row in (np.zeros(1), np.zeros(4), np.array([0.0, np.nan, 0.0]),
                np.array([0.0, np.inf, 0.0])):
        with pytest.raises(ValueError, match="row must"):
            split.scores(0, row)
        with pytest.raises(ValueError, match="row must"):
            split.climb(0, row)
    for k in (-1, 3):
        with pytest.raises(IndexError, match="out of range"):
            split.scores(k, np.zeros(3))
        with pytest.raises(IndexError, match="out of range"):
            split.best(k)


@pytest.mark.parametrize("rows, alphabet", [(np.zeros(3), (0, 1, 2)),
                                             (np.zeros((2, 1)), (0, 1)),
                                             (np.zeros((2, 1)), (-1,)),
                                             (np.full((2, 1), np.nan), (0,))])
def test_split_rejects_invalid_construction(rows, alphabet) -> None:
    with pytest.raises(ValueError, match="requires rows"):
        Split(rows, alphabet)


@pytest.mark.parametrize("centre, half", [(None, 1), (np.zeros(4, dtype=int), None),
                                           (np.zeros(3, dtype=int), 1),
                                           (np.zeros(4), 1), (np.zeros(4, dtype=int), -1)])
def test_split_rejects_invalid_band(centre, half) -> None:
    with pytest.raises(ValueError, match="band requires"):
        Split(np.zeros((3, 3)), centre=centre, half=half)


@pytest.mark.parametrize("reference_only", [False, True])
@pytest.mark.parametrize("centre", [2**63 - 1, -(2**63)])
def test_split_handles_out_of_range_band_centres(
        reference_only: bool, centre: int, monkeypatch: pytest.MonkeyPatch) -> None:
    if reference_only:
        monkeypatch.setattr(decoding, "_NATIVE", None)
    split = Split(np.zeros((3, 3)), centre=np.full(4, centre, dtype=np.int64), half=0)
    assert split.scores(1, np.zeros(3)) == (-np.inf, -np.inf)
    assert split.best(1) == (-np.inf, ())


def test_native_split_scores_sparse_extreme_rows(monkeypatch: pytest.MonkeyPatch) -> None:
    if getattr(decoding._NATIVE, "advance_ragged_log", None) is None:
        pytest.skip("native log cursor is not built")
    rng = np.random.default_rng(245)
    for m in range(1, 9):
        for _ in range(10):
            rows = rng.choice([-np.inf, -1000.0, -40.0, 0.0], size=(m, 3))
            native = Split(rows)
            with monkeypatch.context() as patch:
                patch.setattr(decoding, "_NATIVE", None)
                reference = Split(rows)
            for k in range(m):
                actual, expected = native.scores(k, rows[k]), reference.scores(k, rows[k])
                np.testing.assert_allclose(actual, expected, rtol=0, atol=1e-12)

def test_split_cursor_follows_climbs() -> None:
    """A sequence of climbs at random words, each rescored after the vectors
    were moved to it, matches a full decode after every climb."""
    rng = np.random.default_rng(7)
    for m in (5, 17, 40):
        probs = rng.dirichlet(np.full(3, 0.5), size=m)
        split = Split(np.log(probs), ARITY_ORDER)
        for _ in range(15):
            k = int(rng.integers(m))
            probs[k] = rng.dirichlet(np.full(3, 0.5))
            log_z, log_x = split.climb(k, np.log(probs[k]))
            full = decode_reference(np.log(probs), ARITY_ORDER)
            assert full is not None
            assert log_z == pytest.approx(full.log_z)
            assert log_x == pytest.approx(full.log_weight(np.log(probs), ARITY_ORDER,
                                                          full.arities))

@pytest.mark.parametrize("native", [True, False])
def test_split_traces_best_sequence(native: bool, monkeypatch: pytest.MonkeyPatch) -> None:
    """After each climb, the sequence traced from the vectors around the
    climbed word parses and attains the best weight (Theorem 23.10)."""
    if not native:
        monkeypatch.setattr(formulas, "_NATIVE", None)
        monkeypatch.setattr(priors, "_NATIVE", None)
        monkeypatch.setattr(decoding, "_NATIVE", None)
    elif formulas._NATIVE is None:
        pytest.skip("native kernel not built")
    rng = np.random.default_rng(9)
    for m in (1, 5, 17, 40):
        probs = rng.dirichlet(np.full(3, 0.5), size=m)
        split = Split(np.log(probs), ARITY_ORDER)
        for _ in range(10):
            k = int(rng.integers(m))
            probs[k] = rng.dirichlet(np.full(3, 0.5))
            split.climb(k, np.log(probs[k]))
            log_x, arities = split.best(k)
            full = decode_reference(np.log(probs), ARITY_ORDER)
            assert full is not None
            assert parse(list(arities)) is not None
            assert log_x == pytest.approx(full.log_weight(np.log(probs), ARITY_ORDER, full.arities))
            assert full.log_weight(np.log(probs), ARITY_ORDER, arities) == pytest.approx(log_x)

def test_banded_split_matches_banded_passes() -> None:
    """With the band fixed, climbs rescored by the cursor match the banded
    programs run in full on the changed weights (Theorems 23.7 and 23.8
    applied to the position-restricted automaton)."""
    rng = np.random.default_rng(8)
    for m in (6, 20, 45):
        probs = rng.dirichlet(np.full(3, 0.5), size=m)
        reference = np.argmax(probs, axis=1)
        centre = 1 + np.concatenate(([0], np.cumsum(np.asarray(ARITY_ORDER)[reference] - 1)))
        split = Split(np.log(probs), ARITY_ORDER, centre, 4)
        for _ in range(12):
            k = int(rng.integers(m))
            probs[k] = rng.dirichlet(np.full(3, 0.5))
            log_z, log_x = split.climb(k, np.log(probs[k]))
            full = formulas._banded_passes(np.log(probs), ARITY_ORDER, centre, 4)
            if full is None:
                assert log_z == -np.inf
                continue
            assert log_z == pytest.approx(full[0])
            assert log_x == pytest.approx(full[1])


@pytest.mark.parametrize("reference_only", [False, True])
def test_banded_split_limits_storage_to_largest_row_interval(
        reference_only: bool, monkeypatch: pytest.MonkeyPatch) -> None:
    if reference_only:
        monkeypatch.setattr(decoding, "_NATIVE", None)
    m = 50
    rows = np.log(np.tile([0.1, 0.8, 0.1], (m, 1)))
    centre = [1] * m + [0]
    split = decoding.Split(rows, (0, 1, 2), centre, 2)
    assert split.width == max(1, int((split.high - split.low + 1).max())) == 4
    assert split.forward.size == int(np.maximum(0, split.high - split.low + 1).sum())
    expected = decoding._banded_passes(rows, (0, 1, 2), centre, 2)
    assert expected is not None
    for k in (0, m // 2, m - 1):
        log_z, log_x = split.scores(k, rows[k])
        assert log_z == pytest.approx(expected[0])
        assert log_x == pytest.approx(expected[1])
        weight, arities = split.best(k)
        assert weight == pytest.approx(expected[1])
        assert parse(arities) is not None


@pytest.mark.parametrize("reference_only", [False, True])
def test_ragged_split_sparse_generic_alphabet_after_many_updates(
        reference_only: bool, monkeypatch: pytest.MonkeyPatch) -> None:
    if reference_only:
        monkeypatch.setattr(decoding, "_NATIVE", None)
    rng = np.random.default_rng(284)
    m = 35
    alphabet = (0, 1, 2, 3, 5, 8, 13, 21, 34)
    rows = np.full((m, len(alphabet)), -np.inf)
    rows[:, 1] = 0.0
    rows[-1, 0] = 0.0
    centre = [1] * m + [0]
    cursor = decoding.Split(rows, alphabet, centre, 5)
    for _ in range(45):
        k = int(rng.integers(m))
        row = np.full(len(alphabet), -np.inf)
        row[1] = -float(rng.uniform(0.0, 2.0))
        if k == m - 1:
            row[0] = -float(rng.uniform(0.0, 2.0))
        for j in rng.choice(len(alphabet), size=3, replace=False):
            row[j] = -float(rng.uniform(0.0, 20.0))
        rows[k] = row
        actual = cursor.climb(k, row)
        expected = decoding._banded_passes(rows, alphabet, centre, 5)
        assert expected is not None
        assert actual == pytest.approx(expected[:2])
        best, arities = cursor.best(k)
        assert best == pytest.approx(expected[1])
        assert parse(arities) is not None


@pytest.mark.parametrize("reference_only", [False, True])
@pytest.mark.parametrize("alphabet", [
    (0, 1, 2, 3, 4, 8, 16, 32, 64, 10**100),
    (64, 3, 10**100, 0, 8, 1, 32, 2, 16, 4),
])
def test_ragged_sweeps_handle_ordered_and_permuted_large_arities(
        reference_only: bool, alphabet: tuple[int, ...], monkeypatch: pytest.MonkeyPatch) -> None:
    if reference_only:
        monkeypatch.setattr(decoding, "_NATIVE", None)
    rng = np.random.default_rng(289)
    m = 15
    rows = np.log(rng.dirichlet(np.ones(len(alphabet)), size=m))
    centre = [1] * m + [0]
    cursor = decoding.Split(rows, alphabet, centre, 3)
    for k in (0, m - 1, m // 2, 1, m - 2):
        rows[k] = np.log(rng.dirichlet(np.ones(len(alphabet))))
        actual = cursor.climb(k, rows[k])
        expected = decoding._banded_passes(rows, alphabet, centre, 3)
        assert expected is not None
        assert actual == pytest.approx(expected[:2])
        best, arities = cursor.best(k)
        assert best == pytest.approx(expected[1])
        assert parse(arities) is not None


@pytest.mark.parametrize("reference_only", [False, True])
def test_ragged_split_recovers_support_after_empty_row(
        reference_only: bool, monkeypatch: pytest.MonkeyPatch) -> None:
    if reference_only:
        monkeypatch.setattr(decoding, "_NATIVE", None)
    rng = np.random.default_rng(285)
    m, alphabet = 19, (0, 1, 2, 4)
    rows = np.log(rng.dirichlet(np.ones(len(alphabet)), size=m))
    cursor = decoding.Split(rows, alphabet)
    for k in (m // 2, 0, m - 1, m // 3):
        original = rows[k].copy()
        rows[k] = -np.inf
        assert cursor.climb(k, rows[k]) == (-math.inf, -math.inf)
        assert cursor.best(k) == (-math.inf, ())
        other = (k + m // 2) % m
        assert cursor.scores(other, rows[other]) == (-math.inf, -math.inf)
        rows[k] = original
        actual = cursor.climb(k, original)
        expected = decoding.decode_reference(rows, alphabet)
        assert expected is not None
        assert actual[0] == pytest.approx(expected.log_z)
        assert cursor.best(k)[0] == pytest.approx(expected.log_weight(rows, alphabet, expected.arities))


@pytest.mark.parametrize("reference_only", [False, True])
def test_ragged_split_scores_with_holes_in_support(
        reference_only: bool, monkeypatch: pytest.MonkeyPatch) -> None:
    if reference_only:
        monkeypatch.setattr(decoding, "_NATIVE", None)
    alphabet = (0, 2)
    rows = np.log(np.tile([0.55, 0.45], (9, 1)))
    cursor = decoding.Split(rows, alphabet)
    middle = cursor._row(cursor.forward, 4)
    finite = np.flatnonzero(np.isfinite(middle))
    assert len(finite) > 1 and np.any(~np.isfinite(middle[finite[0]:finite[-1] + 1]))
    for k, row in ((4, np.array([-1000.0, -0.1])),
                   (1, np.array([-0.3, -1000.0])),
                   (7, np.array([-0.9, -0.2]))):
        rows[k] = row
        actual = cursor.climb(k, row)
        expected = decoding.decode_reference(rows, alphabet)
        assert expected is not None
        assert actual[0] == pytest.approx(expected.log_z, abs=1e-12)
        weight, arities = cursor.best(k)
        assert weight == pytest.approx(expected.log_weight(rows, alphabet, expected.arities), abs=1e-12)
        assert parse(arities) is not None


@pytest.mark.parametrize("reference_only", [False, True])
@pytest.mark.parametrize("alphabet", [(0, 2), (2, 0)])
def test_ragged_split_trace_preserves_junction_tie_order(
        reference_only: bool, alphabet: tuple[int, ...], monkeypatch: pytest.MonkeyPatch) -> None:
    if reference_only:
        monkeypatch.setattr(decoding, "_NATIVE", None)
    m = 7
    rows = np.zeros((m, len(alphabet)))
    cursor = decoding.Split(rows, alphabet)
    paths = [path for path in itertools.product(alphabet, repeat=m) if parse(path) is not None]
    assert paths
    for k in range(m):
        def rank(path: tuple[int, ...]) -> tuple[int, int]:
            state = 1 + sum(a - 1 for a in path[:k])
            return alphabet.index(path[k]), state

        weight, path = cursor.best(k)
        assert weight == 0.0 and path in paths
        assert rank(path) == min(map(rank, paths))


@pytest.mark.parametrize("alphabet", [(0, 1, 3, 10**100), (10**100, 3, 0, 1)])
@pytest.mark.parametrize("reference_only", [False, True])
def test_ragged_trace_handles_sorted_and_permuted_generic_arities(
        alphabet: tuple[int, ...], reference_only: bool, monkeypatch: pytest.MonkeyPatch) -> None:
    if reference_only:
        monkeypatch.setattr(decoding, "_NATIVE", None)
    rng = np.random.default_rng(288)
    for _ in range(25):
        m = int(rng.integers(1, 10))
        rows = rng.choice([-np.inf, -1000.0, -5.0, 0.0], size=(m, len(alphabet)))
        cursor = decoding.Split(rows, alphabet)
        expected = decoding.decode_reference(rows, alphabet)
        for k in {0, m // 2, m - 1}:
            actual_z, best = cursor.scores(k, rows[k])
            weight, path = cursor.best(k)
            if expected is None:
                assert actual_z == best == weight == -math.inf and path == ()
            else:
                assert actual_z == pytest.approx(expected.log_z, abs=1e-12)
                assert weight == pytest.approx(best, abs=1e-12)
                assert parse(path) is not None
                assert expected.log_weight(rows, alphabet, path) == pytest.approx(weight, abs=1e-12)


@pytest.mark.parametrize("reference_only", [False, True])
def test_banded_split_packs_rows_around_nonzero_states(
        reference_only: bool, monkeypatch: pytest.MonkeyPatch) -> None:
    if reference_only:
        monkeypatch.setattr(decoding, "_NATIVE", None)
    rng = np.random.default_rng(273)
    m = 21
    rows = np.log(rng.dirichlet(np.ones(3), size=m))
    path = [2] * 10 + [0] * 11
    centre = [1]
    for arity in path:
        centre.append(centre[-1] - 1 + arity)
    split = decoding.Split(rows, (0, 1, 2), centre, 1)
    assert split.width == 2
    assert int(split.high.max()) > split.width
    for k in (0, 5, 10, 15, 20):
        rows[k] = np.log(rng.dirichlet(np.ones(3)))
        actual = split.climb(k, rows[k])
        expected = decoding._banded_passes(rows, (0, 1, 2), centre, 1)
        assert expected is not None
        assert actual == pytest.approx(expected[:2])
        weight, arities = split.best(k)
        assert weight == pytest.approx(expected[1])
        assert parse(arities) is not None


@pytest.mark.parametrize("reference_only", [False, True])
def test_ragged_split_alternates_updates_across_empty_and_live_paths(
        reference_only: bool, monkeypatch: pytest.MonkeyPatch) -> None:
    if reference_only:
        monkeypatch.setattr(decoding, "_NATIVE", None)
    rng = np.random.default_rng(277)
    m = 11
    rows = np.log(rng.dirichlet(np.ones(3), size=m))
    centre = [1]
    for arity in [2] * 5 + [0] * 6:
        centre.append(centre[-1] + arity - 1)
    split = decoding.Split(rows, (0, 1, 2), centre, 0)
    for step in range(80):
        k = (0, m - 1, int(rng.integers(m)))[step % 3]
        rows[k] = np.log(rng.dirichlet(np.ones(3)))
        if step % 4 == 0:
            rows[k, :] = -np.inf
        actual = split.climb(k, rows[k])
        expected = decoding._banded_passes(rows, (0, 1, 2), centre, 0)
        if expected is None:
            assert actual == (-math.inf, -math.inf)
            assert split.best(k) == (-math.inf, ())
        else:
            assert actual == pytest.approx(expected[:2])
            weight, arities = split.best(k)
            assert weight == pytest.approx(expected[1])
            assert parse(arities) is not None


@pytest.mark.parametrize("reference_only", [False, True])
@pytest.mark.parametrize("alphabet", [(0, 1, 2), (0, 1, 3)])
def test_packed_split_matches_independently_enumerated_bands(
        reference_only: bool, alphabet: tuple[int, ...], monkeypatch: pytest.MonkeyPatch) -> None:
    if reference_only:
        monkeypatch.setattr(decoding, "_NATIVE", None)
    rng = np.random.default_rng(274)
    for m in range(1, 7):
        for trial in range(8):
            rows = np.log(rng.dirichlet(np.ones(len(alphabet)), size=m))
            if trial < 4:
                path = ([alphabet[-1]] + [1] * (m - alphabet[-1] - 1) +
                        [0] * alphabet[-1]) if m > alphabet[-1] else [1] * (m - 1) + [0]
                centre = [1]
                for arity in path:
                    centre.append(centre[-1] + arity - 1)
            else:
                centre = rng.integers(-1, m + 2, size=m + 1).tolist()
            half = int(rng.integers(0, 4))
            split = decoding.Split(rows, alphabet, centre, half)
            lengths = np.maximum(0, split.high - split.low + 1)
            np.testing.assert_array_equal(np.diff(split.offsets), lengths)
            assert split.forward.size == int(lengths.sum())
            k = int(rng.integers(m))
            rows[k] = np.log(rng.dirichlet(np.ones(len(alphabet))))
            actual_z, actual_best = split.climb(k, rows[k])
            weights: dict[tuple[int, ...], float] = {}
            for path in itertools.product(alphabet, repeat=m):
                state = 1
                valid = split.low[0] <= state <= split.high[0]
                for i, arity in enumerate(path):
                    if state < 1:
                        valid = False
                        break
                    state += arity - 1
                    if not split.low[i + 1] <= state <= split.high[i + 1]:
                        valid = False
                        break
                if valid and state == 0:
                    weights[path] = math.exp(sum(rows[i, alphabet.index(a)]
                                                  for i, a in enumerate(path)))
            if not weights:
                assert actual_z == actual_best == -math.inf
                assert split.best(k) == (-math.inf, ())
            else:
                assert actual_z == pytest.approx(math.log(math.fsum(weights.values())))
                assert actual_best == pytest.approx(math.log(max(weights.values())))
                traced_weight, traced = split.best(k)
                assert traced in weights
                assert traced_weight == pytest.approx(math.log(weights[traced]))
                assert traced_weight == pytest.approx(actual_best)


def test_banded_split_falls_back_with_older_native_kernel(monkeypatch: pytest.MonkeyPatch) -> None:
    rows = np.log(np.tile([0.1, 0.8, 0.1], (5, 1)))
    expected = decoding._banded_passes(rows, (0, 1, 2), [1] * 5 + [0], 1)
    monkeypatch.setattr(decoding, "_NATIVE", object())
    split = decoding.Split(rows, (0, 1, 2), [1] * 5 + [0], 1)
    assert split._native is None
    assert expected is not None
    assert split.scores(2, rows[2]) == pytest.approx(expected[:2])


@pytest.mark.parametrize("alphabet", [(0, 1, 3, 10**100), (10**100, 3, 0, 1)])
def test_split_cached_order_matches_legacy_native_kernels(alphabet: tuple[int, ...]) -> None:
    native = decoding._NATIVE
    if (getattr(native, "scores_ragged_with_order", None) is None
            or getattr(native, "trace_ragged_with_order", None) is None):
        pytest.skip("native cached-order kernels are not built")

    class OlderNative:
        def __getattr__(self, name: str) -> Any:
            if name in ("scores_ragged_with_order", "trace_ragged_with_order", "trace_ragged_indexed"):
                raise AttributeError(name)
            return getattr(native, name)

    rng = np.random.default_rng(291)
    rows = np.log(rng.dirichlet(np.ones(len(alphabet)), size=13))
    cursor = decoding.Split(rows, alphabet)
    assert not cursor.arities.flags.writeable
    assert cursor._arities_ordered == (alphabet[0] == 0)
    with pytest.raises(ValueError):
        cursor.arities[0] = 0
    for k in (0, 6, 12):
        rows[k] = np.log(rng.dirichlet(np.ones(len(alphabet))))
        cursor.climb(k, rows[k])
        actual = cursor.scores(k, rows[k])
        actual_best = cursor.best(k)
        cursor._native = OlderNative()
        expected = cursor.scores(k, rows[k])
        expected_best = cursor.best(k)
        cursor._native = native
        assert actual == pytest.approx(expected)
        assert actual_best == expected_best


def test_indexed_trace_preserves_full_legacy_path_on_ties() -> None:
    native = decoding._NATIVE
    if getattr(native, "trace_ragged_indexed", None) is None:
        pytest.skip("native indexed traceback is not built")
    rng = np.random.default_rng(294)
    for alphabet in itertools.permutations((0, 1, 2, 3)):
        if list(alphabet) == sorted(alphabet):
            continue
        for m in range(1, 9):
            for _ in range(3):
                rows = rng.choice([-np.inf, -1000.0, -2.0, 0.0], size=(m, len(alphabet)))
                cursor = decoding.Split(rows, alphabet)
                for k in {0, m // 2, m - 1}:
                    actual = cursor.best(k)
                    expected = native.trace_ragged_with_order(
                        cursor.forward_max, cursor.backward_max, cursor.log_probs.reshape(-1),
                        cursor.arities, cursor.low, cursor.high, cursor.offsets, k, False)
                    assert actual == (float(expected[0]), tuple(int(a) for a in expected[1:]))


def test_indexed_trace_builds_order_lazily_and_reuses_it_after_updates() -> None:
    if getattr(decoding._NATIVE, "trace_ragged_indexed", None) is None:
        pytest.skip("native indexed traceback is not built")
    alphabet = (10**100, 2, 0, 1, 10**99)
    rows = np.log(np.full((7, len(alphabet)), 1 / len(alphabet)))
    cursor = decoding.Split(rows, alphabet)
    assert cursor._trace_indices is None
    cursor.scores(3, rows[3])
    assert cursor._trace_indices is None
    cursor.best(3)
    order = cursor._trace_indices
    assert order is not None and not order.flags.writeable
    assert np.all(cursor.arities[order][:-1] <= cursor.arities[order][1:])
    updated = np.log(np.array([0.1, 0.3, 0.1, 0.4, 0.1]))
    cursor.climb(3, updated)
    cursor.best(3)
    assert cursor._trace_indices is order


def test_certified_cursor_reuses_trace_order_after_band_rebuild() -> None:
    if getattr(decoding._NATIVE, "trace_ragged_indexed", None) is None:
        pytest.skip("native indexed traceback is not built")
    m, width = 15, 32
    alphabet = tuple(reversed(range(width)))
    probabilities = np.full((m, width), 1e-8)
    probabilities[:, alphabet.index(1)] = 1 - (width - 1) * 1e-8
    probabilities[-1, alphabet.index(1)] = 1e-8
    probabilities[-1, alphabet.index(0)] = 1 - (width - 1) * 1e-8
    rows = np.log(probabilities)
    cursor = decoding.CertifiedSplit(rows, alphabet)
    assert cursor.changes == 1
    assert cursor.result() is not None
    previous_split = cursor.split
    order = previous_split._trace_indices
    assert order is not None

    replacement = np.full(width, 1e-8)
    replacement[alphabet.index(1)] = 0.2
    replacement[alphabet.index(0)] = 0.8 - (width - 2) * 1e-8
    rows[5] = np.log(replacement)
    actual = cursor.climb(5, rows[5])
    expected = decoding.decode_reference(rows, alphabet)
    assert actual is not None and expected is not None and cursor.rebuilds > 0
    assert cursor.split is not previous_split
    assert cursor.split._trace_indices is order
    assert expected.log_weight(rows, alphabet, actual.arities) == pytest.approx(
        expected.log_weight(rows, alphabet, expected.arities))


@pytest.mark.parametrize("reference_only", [False, True])
def test_cursors_copy_fortran_input_to_contiguous_private_rows(
        reference_only: bool, monkeypatch: pytest.MonkeyPatch) -> None:
    if reference_only:
        monkeypatch.setattr(decoding, "_NATIVE", None)
    rows = np.asfortranarray(np.log(np.tile([0.00001, 0.99998, 0.00001], (15, 1))))
    rows[-1] = np.log([0.99998, 0.00001, 0.00001])
    assert rows.flags.f_contiguous and not rows.flags.c_contiguous
    split = decoding.Split(rows)
    cursor = decoding.CertifiedSplit(rows)
    for owned in (split.log_probs, cursor.log_probs, cursor.split.log_probs):
        assert owned.flags.c_contiguous
        assert np.shares_memory(owned, owned.reshape(-1))
        assert not np.shares_memory(owned, rows)
    update = np.log([0.00002, 0.99996, 0.00002])
    rows[3] = update
    actual_z, _ = split.climb(3, update)
    upper = cursor.climb_normalizer(3, update)
    expected = decoding.decode_reference(rows)
    assert expected is not None and upper is not None
    assert actual_z == pytest.approx(expected.log_z)
    assert upper >= expected.log_z - 1e-12


@pytest.mark.skipif(formulas._NATIVE is None, reason="native decoding kernel not built")
def test_native_decoder_matches_reference() -> None:
    """The native kernel against NumPy at formula sizes up to depth 9, with
    impossible arities (probability 0) and inputs that admit no formula."""
    rng = np.random.default_rng(7)
    for trial in range(60):
        m = int(rng.integers(1, 1200))
        probs = rng.dirichlet(np.full(3, 0.4), size=m)
        probs[rng.random((m, 3)) < 0.05] = 0.0
        if trial % 10 == 0:
            probs[:, 0] = 0.0
        with np.errstate(divide="ignore"):
            log_probs = np.log(probs)
        native, reference = decode(log_probs, ARITY_ORDER), decode_reference(log_probs, ARITY_ORDER)
        assert (native is None) == (reference is None)
        if native is None or reference is None:
            continue
        assert native.arities == reference.arities
        assert native.log_z == pytest.approx(reference.log_z, rel=1e-9)
        np.testing.assert_allclose(native.marginals, reference.marginals, atol=1e-9)

def accepted(arities: Sequence[int]) -> bool:
    """The counter automaton of ``NCA.await`` from one awaited subformula."""
    state: int | None = 1
    for a in arities:
        state = state - 1 + a if state is not None and state >= 1 else None
    return state == 0

def test_parse_accepts_exactly_the_automaton_language() -> None:
    """``NCA.accepts_iff_codes``: parseable arity sequences are the counter
    automaton's words, and the decoder searches exactly these."""
    for m in range(1, 9):
        assert {a for a in itertools.product(ARITY_ORDER, repeat=m) if accepted(a)} == \
            set(parseable(m))

def test_native_parser_matches_reference() -> None:
    if getattr(formulas._NATIVE, "parse_tree", None) is None:
        pytest.skip("native parser is not built")
    for size in range(8):
        for arities in itertools.product(range(3), repeat=size):
            assert parse(arities) == formulas.parse_reference(arities)
    # A deep valid unary chain exceeds Python's recursive parser's stack.
    result = parse([1] * 2000 + [0])
    assert result is not None and len(result) == 2001
    assert result[0] == [1] and result[-1] == []

@pytest.mark.parametrize("reference", [False, True])
def test_certified_cursor_preserves_risk_bounds(reference: bool,
                                                monkeypatch: pytest.MonkeyPatch) -> None:
    if reference:
        monkeypatch.setattr(formulas, "_NATIVE", None)
        monkeypatch.setattr(priors, "_NATIVE", None)
        monkeypatch.setattr(decoding, "_NATIVE", None)
    rng = np.random.default_rng(32)
    weights = np.log(rng.dirichlet(np.full(3, 0.3), size=35))
    cursor = formulas.CertifiedSplit(weights, slack=1e-4)
    for step in range(20):
        if step:
            k = int(rng.integers(len(weights)))
            weights[k] = np.log(rng.dirichlet(np.full(3, 0.3)))
            banded = cursor.climb(k, weights[k])
        else:
            banded = cursor.result()
        exact = decode(weights)
        assert banded is not None and exact is not None and banded.exact
        risk = exact.risk(weights, (0, 1, 2), banded.arities)
        assert risk - 1e-12 <= banded.risk <= risk + 1e-4 + 1e-12
        selected = formulas.sequence_log_weight(weights, (0, 1, 2), banded.arities)
        best = formulas.sequence_log_weight(weights, (0, 1, 2), exact.arities)
        assert selected == pytest.approx(best, abs=1e-12)
        # A valid answer may differ from the maximum and lie outside its band.
        alternate = (1,) * (len(weights) - 1) + (0,)
        alternate_risk = exact.risk(weights, (0, 1, 2), alternate)
        assert alternate_risk - 1e-12 <= cursor.sequence_risk(alternate)
        assert cursor.sequence_risk(alternate) <= alternate_risk + 1e-4 + 1e-12
        assert cursor.sequence_risk(banded.arities) == pytest.approx(banded.risk, abs=1e-12)

def test_certified_cursor_rejects_invalid_weights_and_handles_zero_mass() -> None:
    with pytest.raises(ValueError):
        formulas.CertifiedSplit(np.zeros((2, 3)))  # Row mass is three, not at most one.
    with pytest.raises(ValueError):
        formulas.CertifiedSplit(np.log(np.full((2, 3), 1 / 3)), slack=0.0)
    with pytest.raises(ValueError):
        formulas.CertifiedSplit(np.empty((0, 3)))
    cursor = formulas.CertifiedSplit(np.full((3, 3), -np.inf))
    assert cursor.result() is None


@pytest.mark.parametrize("reference_only", [False, True])
@pytest.mark.parametrize("alphabet", [(0,), (1,), (0, 3), (0, 1, 3),
                                      (0, 1, 3, 2**63 - 1)])
def test_certified_cursor_supports_general_arities(
        reference_only: bool, alphabet, monkeypatch: pytest.MonkeyPatch) -> None:
    if reference_only:
        monkeypatch.setattr(decoding, "_NATIVE", None)
    rng = np.random.default_rng(247)
    for m in range(1, 9):
        rows = np.log(rng.dirichlet(np.ones(len(alphabet)), size=m))
        cursor = decoding.CertifiedSplit(rows, alphabet)
        for step in range(4):
            if step:
                k = int(rng.integers(m))
                rows[k] = np.log(rng.dirichlet(np.ones(len(alphabet))))
                result = cursor.climb(k, rows[k])
            else:
                result = cursor.result()
            exact = decode_reference(rows, alphabet)
            assert (result is None) == (exact is None)
            if result is not None and exact is not None:
                weight = exact.log_weight(rows, alphabet, result.arities)
                assert weight == pytest.approx(exact.log_weight(rows, alphabet, exact.arities), abs=1e-12)
                risk = exact.risk(rows, alphabet, result.arities)
                assert risk - 1e-12 <= result.risk <= risk + 1e-4 + 1e-12
                assert risk - 1e-12 <= cursor.sequence_risk(result.arities) <= risk + 1e-4 + 1e-12


@pytest.mark.parametrize("reference_only", [False, True])
def test_certified_cursor_scores_ternary_alternative(
        reference_only: bool, monkeypatch: pytest.MonkeyPatch) -> None:
    if reference_only:
        monkeypatch.setattr(decoding, "_NATIVE", None)
    alphabet = (0, 1, 3, 2**63 - 1)
    rows = np.log(np.tile([0.4, 0.3, 0.2, 0.1], (4, 1)))
    cursor = decoding.CertifiedSplit(rows, alphabet)
    assert cursor.normalizer() is not None
    exact = decode_reference(rows, alphabet)
    assert exact is not None
    alternative = (3, 0, 0, 0)
    expected = exact.risk(rows, alphabet, alternative)
    assert expected - 1e-12 <= cursor.sequence_risk(alternative) <= expected + 1e-4 + 1e-12
    with pytest.raises(ValueError):
        cursor.sequence_risk((2**63 - 1, 0, 0, 0))


@pytest.mark.parametrize("reference_only", [False, True])
def test_format_interfaces_support_arities_beyond_native_integer_range(
        reference_only: bool, monkeypatch: pytest.MonkeyPatch) -> None:
    if reference_only:
        monkeypatch.setattr(decoding, "_NATIVE", None)
        monkeypatch.setattr(priors, "_NATIVE", None)
    big = 10**100
    alphabet = (0, 1, 3, big, big + 1)
    rows = np.log(np.tile([0.15, 0.2, 0.25, 0.3, 0.1], (4, 1)))
    exact = decode_reference(rows, alphabet)
    actual = decode(rows, alphabet)
    banded = decode_banded(rows, alphabet)
    cursor = decoding.CertifiedSplit(rows, alphabet)
    result = cursor.result()
    assert exact is not None and actual is not None and banded is not None and result is not None
    assert exact.arities == actual.arities == banded.arities == result.arities == (1, 1, 1, 0)
    assert actual.log_z == pytest.approx(exact.log_z, abs=1e-12)
    np.testing.assert_allclose(actual.marginals, exact.marginals, atol=1e-12)
    risk = exact.risk(rows, alphabet)
    assert banded.risk == pytest.approx(risk, abs=1e-12)
    assert result.risk == pytest.approx(risk, abs=1e-12)
    assert cursor.sequence_risk(exact.arities) == pytest.approx(risk, abs=1e-12)
    with pytest.raises(ValueError):
        cursor.sequence_risk((big, 0, 0, 0))


@pytest.mark.parametrize("reference_only", [False, True])
def test_large_arity_sentinel_preserves_underflowed_valid_path(
        reference_only: bool, monkeypatch: pytest.MonkeyPatch) -> None:
    if reference_only:
        monkeypatch.setattr(decoding, "_NATIVE", None)
        monkeypatch.setattr(priors, "_NATIVE", None)
    alphabet = (0, 1, 3, 10**100, 10**100 + 1)
    rows = np.array([[-np.inf, 0.0, -1000.0, -np.inf, -np.inf],
                     [0.0, -1000.0, -np.inf, -np.inf, -np.inf],
                     [0.0, -np.inf, -np.inf, -np.inf, -np.inf],
                     [0.0, -np.inf, -np.inf, -np.inf, -np.inf]])
    exact = decode(rows, alphabet)
    banded = decode_banded(rows, alphabet)
    cursor = decoding.CertifiedSplit(rows, alphabet).result()
    assert exact is not None and banded is not None and cursor is not None
    assert exact.arities == banded.arities == cursor.arities == (3, 0, 0, 0)
    assert exact.log_z == pytest.approx(-1000.0)
    assert exact.risk(rows, alphabet) == banded.risk == cursor.risk == 0.0

def test_certified_sequence_risk_requires_current_normalizer_and_valid_answer() -> None:
    cursor = formulas.CertifiedSplit(np.log(np.full((3, 3), 1 / 3)))
    with pytest.raises(ValueError, match="successful result"):
        cursor.sequence_risk((2, 0, 0))
    assert cursor.result() is not None
    for invalid in ((0,), (0, 0, 0), (2, 0, 9)):
        with pytest.raises(ValueError):
            cursor.sequence_risk(invalid)
    assert cursor.climb(0, np.full(3, -np.inf)) is None
    with pytest.raises(ValueError, match="successful result"):
        cursor.sequence_risk((2, 0, 0))

def test_certified_sequence_risk_scores_answer_outside_band() -> None:
    weights = np.full((9, 3), 1e-9)
    weights[:8, 1] = 1 - 2e-9
    weights[8, 0] = 1 - 2e-9
    cursor = formulas.CertifiedSplit(np.log(weights))
    result = cursor.result()
    assert result is not None and result.width == 1
    alternate = (2, 2, 2, 2, 0, 0, 0, 0, 0)
    assert 1 + alternate[0] - 1 > cursor.split.high[1]
    exact = decode(np.log(weights))
    assert exact is not None
    risk = exact.risk(np.log(weights), (0, 1, 2), alternate)
    assert risk - 1e-12 <= cursor.sequence_risk(alternate) <= risk + 1e-4 + 1e-12

@pytest.mark.parametrize("reference", [False, True])
def test_normalizer_only_updates_bound_risk_without_tracing(
        reference: bool, monkeypatch: pytest.MonkeyPatch) -> None:
    if reference:
        monkeypatch.setattr(formulas, "_NATIVE", None)
        monkeypatch.setattr(priors, "_NATIVE", None)
        monkeypatch.setattr(decoding, "_NATIVE", None)

    def no_trace(*args: Any) -> Any:
        raise AssertionError("normalizer computation must not trace an answer")

    rng = np.random.default_rng(43)
    weights = np.log(rng.dirichlet(np.full(3, 0.3), size=35))
    cursor = formulas.CertifiedSplit(weights)
    selected = (1,) * 34 + (0,)
    with monkeypatch.context() as patch:
        patch.setattr(Split, "best", no_trace)
        for step in range(20):
            if step:
                k = int(rng.integers(len(weights)))
                weights[k] = np.log(rng.dirichlet(np.full(3, 0.3)))
                upper = cursor.climb_normalizer(k, weights[k])
            else:
                upper = cursor.normalizer()
            exact = decode(weights)
            assert exact is not None and upper is not None
            risk = exact.risk(weights, (0, 1, 2), selected)
            assert risk - 1e-12 <= cursor.sequence_risk(selected) <= risk + 1e-4 + 1e-12
    # The same cursor can later request the stronger maximum certificate.
    assert cursor.result() is not None
    assert cursor.climb_normalizer(0, np.full(3, -np.inf)) is None
    with pytest.raises(ValueError, match="successful result"):
        cursor.sequence_risk(selected)

def test_native_accepted_log_weight_matches_prefix_parser() -> None:
    native = getattr(formulas._NATIVE, "accepted_log_weight", None)
    if native is None:
        pytest.skip("native accepted sequence weight is not built")
    rng = np.random.default_rng(47)
    alphabet = np.array([2, 0, 1], dtype=np.int64)
    for size in range(1, 8):
        rows = rng.normal(size=(size, 3))
        for selected in itertools.product(range(3), repeat=size):
            actual = native(rows.reshape(-1), alphabet, np.array(selected, dtype=np.int64))
            if formulas.parse_reference(selected) is None:
                assert actual == []
            else:
                expected = sum(rows[k, list(alphabet).index(a)] for k, a in enumerate(selected))
                assert actual == [expected]
    assert native(np.array([-np.inf]), np.array([0], dtype=np.int64),
                  np.array([0], dtype=np.int64)) == [-np.inf]
    for selected, alphabet_values, weights in (([], [0], []), ([0], [], []),
                                               ([0], [0], []), ([-1], [0], [0.0]),
                                               ([3], [3], [0.0]), ([1, 0], [0], [0.0, 0.0])):
        assert native(np.array(weights, dtype=np.float64),
                      np.array(alphabet_values, dtype=np.int64),
                      np.array(selected, dtype=np.int64)) == []


def test_native_decode_falls_back_when_accepted_mass_underflows() -> None:
    rows = np.array([[-1488.0, 0.0, -1151.0], [0.0, -1381.0, -1487.0],
                     [0.0, -1488.0, -1487.0]])
    result = decode(rows, ARITY_ORDER)
    reference = decode_reference(rows, ARITY_ORDER)
    assert result is not None and reference is not None
    assert result.arities == reference.arities == (2, 0, 0)
    assert result.log_z == pytest.approx(reference.log_z)
    np.testing.assert_allclose(result.marginals, reference.marginals)


def test_native_decode_preserves_partially_underflowed_paths() -> None:
    rows = np.array([[-np.inf, 0.0, -750.0], [0.0, -740.0, -np.inf],
                     [0.0, -np.inf, -np.inf]])
    result = decode(rows, ARITY_ORDER)
    reference = decode_reference(rows, ARITY_ORDER)
    assert result is not None and reference is not None
    assert result.arities == reference.arities
    assert result.log_z == pytest.approx(reference.log_z, abs=1e-12)
    np.testing.assert_allclose(result.marginals, reference.marginals, rtol=1e-12, atol=0)


def test_native_decode_ties_match_log_space_order() -> None:
    rows = np.array([[-np.inf, -1.0, 0.0], [-1.0, 0.0, -1.0],
                     [0.0, 0.0, 0.0]])
    result, reference = decode(rows, ARITY_ORDER), decode_reference(rows, ARITY_ORDER)
    assert result is not None and reference is not None
    assert result.arities == reference.arities == (2, 0, 0)


@pytest.mark.parametrize("alphabet", [(0, 2**63 - 1), (0, 1, 2, 2**63 - 1),
                                      np.array([0, 1, 2, 2**63 - 1], dtype=np.int64)])
def test_decode_accepts_arities_larger_than_any_possible_state(alphabet) -> None:
    rows = np.zeros((5, len(alphabet)))
    actual, expected = decode(rows, alphabet), decode_reference(rows, alphabet)
    assert (actual is None) == (expected is None)
    if actual is not None and expected is not None:
        assert actual.arities == expected.arities
        np.testing.assert_allclose(actual.marginals, expected.marginals, atol=1e-12)


@pytest.mark.parametrize("extra", [7, 8, 9, 15, 10**100])
def test_reference_decode_ignores_impossible_arity_near_table_width(extra: int) -> None:
    m = 4
    alphabet = (0, 1, extra)
    rows = np.log(np.tile([0.2, 0.5, 0.3], (m, 1)))
    actual = decoding.decode_reference(rows, alphabet)
    expected = decoding.decode_reference(rows[:, :2], alphabet[:2])
    assert actual is not None and expected is not None
    assert actual.arities == expected.arities
    assert actual.log_z == pytest.approx(expected.log_z)
    np.testing.assert_allclose(actual.marginals[:, :2], expected.marginals)
    np.testing.assert_array_equal(actual.marginals[:, 2], np.zeros(m))


def test_native_decode_keeps_ternary_paths_alongside_unary_paths() -> None:
    alphabet = (0, 1, 3)
    rows = np.full((4, 3), -np.log(3.0))
    result, reference = decode(rows, alphabet), decode_reference(rows, alphabet)
    assert result is not None and reference is not None
    assert result.log_z == pytest.approx(reference.log_z, abs=1e-12)
    np.testing.assert_allclose(result.marginals, reference.marginals, atol=1e-12)
    assert result.marginals[0, 2] == pytest.approx(0.5)


@pytest.mark.parametrize("alphabet", [(0, 1, 3), (3, 0, 1), (0, 2, 4),
                                      (0, 1, 2, 2**63 - 1)])
def test_native_decode_matches_reference_for_general_arities(alphabet) -> None:
    rng = np.random.default_rng(242)
    for m in range(1, 11):
        for _ in range(20):
            rows = np.log(rng.dirichlet(np.ones(len(alphabet)), size=m))
            actual, expected = decode(rows, alphabet), decode_reference(rows, alphabet)
            assert (actual is None) == (expected is None)
            if actual is not None and expected is not None:
                assert actual.arities == expected.arities
                assert actual.log_z == pytest.approx(expected.log_z, abs=1e-12)
                np.testing.assert_allclose(actual.marginals, expected.marginals, atol=1e-12)


@pytest.mark.parametrize("alphabet", [(), (0, -1), (0, 1.5), (0, 1.0), (0, 0)])
@pytest.mark.parametrize("decoder", [decode, decode_reference, decode_banded])
def test_decode_rejects_invalid_arity_alphabet(decoder, alphabet) -> None:
    with pytest.raises(ValueError, match="nonnegative arities"):
        decoder(np.zeros((2, len(alphabet))), alphabet)


@pytest.mark.parametrize("decoder", [decode, decode_reference, decode_banded])
@pytest.mark.parametrize("rows", [np.zeros(3), np.zeros((2, 2)), np.full((2, 3), np.nan),
                                  np.full((2, 3), np.inf)])
def test_decode_rejects_malformed_rows(decoder, rows) -> None:
    with pytest.raises(ValueError, match="rows must"):
        decoder(rows, (0, 1, 2))


@pytest.mark.parametrize("parser", [parse, decoding.parse_reference])
@pytest.mark.parametrize("arities", [(-1,), (0.0,), (1.5, 0), (1, -1)])
def test_parse_rejects_noninteger_or_negative_arities(parser, arities) -> None:
    assert parser(arities) is None


@pytest.mark.parametrize("parser", [parse, decoding.parse_reference])
def test_parse_handles_deep_general_arity_without_recursion(parser) -> None:
    depth = 1500
    arities = np.array([1] * depth + [3, 0, 0, 0], dtype=np.int64)
    children = parser(arities)
    assert children is not None
    assert children[0] == [1]
    assert children[depth] == [depth + 1, depth + 2, depth + 3]


def test_generic_native_parser_matches_reference_exhaustively() -> None:
    native = getattr(decoding._NATIVE, "parse_tree_generic", None)
    if native is None:
        pytest.skip("native generic parser is not built")
    for m in range(1, 7):
        for arities in itertools.product((0, 1, 2, 3), repeat=m):
            result = native(np.asarray(arities, dtype=np.int64))
            actual = ([result[m + 1 + result[k]:m + 1 + result[k + 1]]
                       for k in range(m)] if result else None)
            assert actual == decoding.parse_reference(arities)


@pytest.mark.parametrize("reference_only", [False, True])
def test_generic_parser_handles_unbounded_impossible_arity(
        reference_only: bool, monkeypatch: pytest.MonkeyPatch) -> None:
    if reference_only:
        monkeypatch.setattr(decoding, "_NATIVE", None)
    assert parse((10**100, 0)) is None


@pytest.mark.parametrize("alphabet", [(0, 1, 2), (2, 0, 1), (2, 1, 0)])
def test_native_decode_ties_match_reference_across_alphabet_orders(alphabet) -> None:
    rng = np.random.default_rng(920)
    for length in range(2, 9):
        for _ in range(100):
            rows = rng.choice([0.0, -1.0, -2.0, -np.inf], size=(length, 3))
            actual, expected = decode(rows, alphabet), decode_reference(rows, alphabet)
            assert (actual is None) == (expected is None)
            if actual is not None and expected is not None:
                assert actual.arities == expected.arities


def test_native_decode_retries_when_normal_weights_have_underflowing_product() -> None:
    native = getattr(decoding._NATIVE, "decode", None)
    if native is None:
        pytest.skip("native decoder is not built")
    rows = np.array([[-np.inf, 0.0, -400.0], [-400.0, -400.0, -np.inf],
                     [0.0, -np.inf, -np.inf]])
    assert native(rows.reshape(-1), np.asarray(ARITY_ORDER, dtype=np.int64))[0] <= -1e300
    actual, reference = decode(rows, ARITY_ORDER), decode_reference(rows, ARITY_ORDER)
    assert actual is not None and reference is not None
    assert actual.log_z == pytest.approx(reference.log_z, abs=1e-12)
    np.testing.assert_allclose(actual.marginals, reference.marginals, rtol=1e-12, atol=0)


@pytest.mark.parametrize("alphabet", [(0, 1, 2), (2, 0, 1), (2, 1, 0), (0, 3), (0, 2**63 - 1)])
def test_native_log_decoder_matches_reference_on_extreme_tied_rows(alphabet) -> None:
    native = getattr(decoding._NATIVE, "decode_log", None)
    if native is None:
        pytest.skip("native log decoder is not built")
    rng = np.random.default_rng(286)
    for length in range(1, 9):
        for _ in range(20):
            rows = rng.choice([0.0, -1000.0, -1500.0, -np.inf], size=(length, len(alphabet)))
            expected = decode_reference(rows, alphabet)
            actual = native(rows.reshape(-1), np.asarray(alphabet, dtype=np.int64))
            if expected is None:
                assert actual == []
            else:
                assert actual[0] == pytest.approx(expected.log_z, abs=1e-12)
                assert tuple(int(x) for x in actual[1:length + 1]) == expected.arities
                np.testing.assert_allclose(np.asarray(actual[1 + length:]).reshape(rows.shape),
                                           expected.marginals, atol=1e-12)
