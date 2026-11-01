import copy
import itertools
import pickle
from types import SimpleNamespace
from typing import Any

import numpy as np
import pytest

from nca import decoding, formulas, priors
from nca.formulas import (decode,
                          parse)


def test_prior_arrays_cannot_be_made_writeable() -> None:
    transitions = np.array([[0, 0]])
    weights = np.array([[0.0, -1.0]])
    final = np.array([0.0])
    prior = priors.ArityPrior((0, 1), transitions, weights, final)
    expected = prior.log_weight((0, 1))
    transitions[:] = -1
    weights[:] = 2
    final[:] = -np.inf
    for array in (prior.transitions, prior.log_weights, prior.log_final):
        with pytest.raises(ValueError):
            array.setflags(write=True)
        with pytest.raises(ValueError):
            array.flat[0] = 0
    assert prior.log_weight((0, 1)) == expected
    with pytest.raises(TypeError, match="initialized prior"):
        prior.__setstate__({"alphabet": (1,)})
    assert prior.log_weight((0, 1)) == expected


def test_native_alphabet_buffer_is_shared_without_becoming_writeable() -> None:
    first = priors._native_alphabet((2, 0, 1))
    assert first is priors._native_alphabet((2, 0, 1))
    assert first.tolist() == [2, 0, 1]
    assert priors._native_alphabet((0, 1, 2)).tolist() == [0, 1, 2]
    with pytest.raises(ValueError):
        first.setflags(write=True)


@pytest.mark.parametrize("reference", [False, True])
def test_decoded_risk_preserves_tiny_probabilities_and_rejects_nan(
        reference: bool, monkeypatch: pytest.MonkeyPatch) -> None:
    if reference:
        monkeypatch.setattr(priors, "_NATIVE", None)
    assert priors.risk_from_log_weight(-1e-18, 0.0) == pytest.approx(1e-18, rel=1e-15)
    assert priors.risk_from_log_weight(-np.inf, 0.0) == 1.0
    with pytest.raises(ValueError, match="sequence risk"):
        priors.risk_from_log_weight(np.nan, 0.0)


@pytest.mark.parametrize("reference", [False, True])
def test_prior_normalizer_preserves_tiny_alternative_probability(
        reference: bool, monkeypatch: pytest.MonkeyPatch) -> None:
    if reference:
        monkeypatch.setattr(priors, "_NATIVE", None)
    prior = priors.ArityPrior((0, 1), np.array([[0, 0]]), np.zeros((1, 2)), np.zeros(1))
    rows = np.array([[0.0, -40.0]])
    decoded = prior.decode(rows)
    assert decoded is not None and decoded.arities == (0,)
    expected = np.exp(-40.0) / (1.0 + np.exp(-40.0))
    assert decoded.risk(rows, prior.alphabet) == pytest.approx(expected, rel=1e-14)
    assert prior.log_normalizer(rows) == pytest.approx(np.log1p(np.exp(-40.0)), rel=1e-14)


@pytest.mark.parametrize("reference", [False, True])
def test_prior_partition_matches_exhaustive_paths(
        reference: bool, monkeypatch: pytest.MonkeyPatch) -> None:
    if reference:
        monkeypatch.setattr(priors, "_NATIVE", None)
    rng = np.random.default_rng(42)
    alphabet = (0, 1, 2)
    for _ in range(100):
        states, length = int(rng.integers(1, 5)), int(rng.integers(0, 5))
        transitions = rng.integers(-1, states, size=(states, 3))
        weights = rng.normal(size=(states, 3))
        final = rng.normal(size=states)
        rows = rng.normal(size=(length, 3))
        weights[rng.random(weights.shape) < .1] = -np.inf
        final[rng.random(final.shape) < .1] = -np.inf
        rows[rng.random(rows.shape) < .1] = -np.inf
        prior = priors.ArityPrior(alphabet, transitions, weights, final)
        chosen = tuple(rng.integers(0, 3, size=length))
        scores = [(seq, prior.log_weight(seq) + sum(rows[k, symbol] for k, symbol in enumerate(seq)))
                  for seq in itertools.product(alphabet, repeat=length)]
        selected = next(score for seq, score in scores if seq == chosen)
        other = float(np.logaddexp.reduce([score for seq, score in scores if seq != chosen], initial=-np.inf))
        np.testing.assert_allclose(prior.partition(rows, chosen), (selected, other), atol=1e-12)
        if not (selected == -np.inf and other == -np.inf):
            expected = 1.0 if selected == -np.inf else 0.0 if other == -np.inf else 1 / (1 + np.exp(selected - other))
            assert prior.sequence_risk(rows, chosen) == pytest.approx(expected, abs=1e-12)


@pytest.mark.parametrize("reference", [False, True])
@pytest.mark.parametrize("rows", [np.array([[0.0, -40.0]]), np.array([[-1.0, -41.0]]),
                                   np.array([[-41.0, -1.0]])])
def test_prior_risk_preserves_tiny_alternative_mass(
        reference: bool, rows: np.ndarray, monkeypatch: pytest.MonkeyPatch) -> None:
    if reference:
        monkeypatch.setattr(priors, "_NATIVE", None)
    prior = priors.ArityPrior((0, 1), np.array([[0, 0]]), np.zeros((1, 2)), np.zeros(1))
    decoded = prior.decode(rows)
    assert decoded is not None
    assert decoded.risk(rows, prior.alphabet) == pytest.approx(np.exp(-40), rel=1e-14)


@pytest.mark.parametrize("reference", [False, True])
def test_prior_partition_handles_missing_paths_and_overflow(
        reference: bool, monkeypatch: pytest.MonkeyPatch) -> None:
    if reference:
        monkeypatch.setattr(priors, "_NATIVE", None)
    prior = priors.ArityPrior((0,), np.array([[0]]), np.zeros((1, 1)), np.zeros(1))
    rows = np.zeros((1, 1))
    assert prior.partition(rows, (1,)) == (-np.inf, 0.0)
    assert prior.sequence_risk(rows, (1,)) == 1.0
    with pytest.raises(ValueError, match="match the number of rows"):
        prior.partition(rows, ())
    with pytest.raises(ValueError, match="positive total mass"):
        prior.sequence_risk(np.full((1, 1), -np.inf), (0,))
    extreme = priors.ArityPrior((0,), np.array([[0]]), np.array([[-1e308]]), np.zeros(1))
    with pytest.raises(ValueError, match="partition.*finite"):
        extreme.partition(np.zeros((2, 1)), (0, 0))


@pytest.mark.parametrize("reference", [False, True])
def test_partition_cursor_recomputes_from_first_changed_position(
        reference: bool, monkeypatch: pytest.MonkeyPatch) -> None:
    import nca.partition as incremental

    if reference:
        monkeypatch.setattr(incremental, "_NATIVE", None)
    rng = np.random.default_rng(441)
    prior = priors.height_prior(4)
    rows = np.log(rng.dirichlet(np.ones(3), size=15))
    selected = list(rng.integers(0, 3, size=len(rows)))
    cursor = incremental.PartitionCursor(prior)
    with pytest.raises(AttributeError):
        cursor.prior = priors.height_prior(3)
    np.testing.assert_allclose(cursor.partition(rows, tuple(selected)), prior.partition(rows, selected))
    for pos in (14, 8, 12, 0, 10, 4, 14):
        rows[pos] = np.log(rng.dirichlet(np.ones(3)))
        selected[pos] = (selected[pos] + 1) % 3
        actual = cursor.partition(rows, tuple(selected))
        np.testing.assert_allclose(actual, prior.partition(rows, selected), atol=1e-12)
        if incremental._NATIVE is not None:
            assert cursor.last_start == pos
            assert cursor.partition(rows, tuple(selected)) == actual
            assert cursor.last_start == len(rows)


def test_partition_cursor_tracks_independent_reading_and_selection_changes() -> None:
    import nca.partition as incremental

    if incremental._NATIVE is None:
        pytest.skip("incremental partition is not built")
    rng = np.random.default_rng(772)
    prior = priors.height_prior(4)
    rows = np.log(rng.dirichlet(np.ones(3), size=12))
    selected = [0] * len(rows)
    cursor = incremental.PartitionCursor(prior)
    cursor.partition(rows, tuple(selected))
    selected[6] = 1
    np.testing.assert_allclose(cursor.partition(rows, tuple(selected)),
                               prior.partition(rows, selected), atol=1e-12)
    assert cursor.last_start == 6
    rows[4] = np.log(rng.dirichlet(np.ones(3)))
    np.testing.assert_allclose(cursor.partition(rows, tuple(selected)),
                               prior.partition(rows, selected), atol=1e-12)
    assert cursor.last_start == 4
    selected[10] = 2
    rows[3] = np.log(rng.dirichlet(np.ones(3)))
    np.testing.assert_allclose(cursor.partition(rows, tuple(selected)),
                               prior.partition(rows, selected), atol=1e-12)
    assert cursor.last_start == 3


def test_partition_cursor_reuses_snapshot_after_out_of_alphabet_fallback() -> None:
    import nca.partition as incremental

    if incremental._NATIVE is None:
        pytest.skip("incremental partition is not built")
    prior = priors.height_prior(3)
    rows = np.zeros((12, 3))
    selected = (0,) * len(rows)
    cursor = incremental.PartitionCursor(prior)
    cursor.partition(rows, selected)
    invalid = (0,) * 11 + (7,)
    rows[10, 1] = -1.0
    np.testing.assert_allclose(cursor.partition(rows, invalid), prior.partition(rows, invalid))
    rows[11, 1] = -2.0
    np.testing.assert_allclose(cursor.partition(rows, selected), prior.partition(rows, selected))
    assert cursor.last_start == 10


def test_partition_first_change_matches_row_comparison() -> None:
    import nca.partition as incremental

    if incremental._NATIVE is None:
        pytest.skip("incremental partition is not built")
    rng = np.random.default_rng(192)
    for length in (0, 1, 37):
        old_rows = rng.normal(size=(length, 3))
        old_selected = rng.integers(0, 3, size=length, dtype=np.int64)
        for position in range(length + 1):
            rows, selected = old_rows.copy(), old_selected.copy()
            if position < length:
                if position % 2:
                    selected[position] = (selected[position] + 1) % 3
                else:
                    rows[position, position % 3] = -np.inf
            actual = incremental._NATIVE.first_change(rows.reshape(-1), old_rows.reshape(-1),
                                                      selected, old_selected, 3)
            assert actual == position


def test_partition_cursor_recovers_after_overflow() -> None:
    import nca.partition as incremental

    if incremental._NATIVE is None:
        pytest.skip("incremental partition is not built")
    prior = priors.ArityPrior((0,), np.array([[0]]), np.array([[-1e308]]), np.zeros(1))
    cursor = incremental.PartitionCursor(prior)
    valid = np.array([[1e308], [1e308]])
    assert cursor.partition(valid, (0, 0)) == (0.0, -np.inf)
    with pytest.raises(ValueError, match="partition.*finite"):
        cursor.partition(np.zeros((2, 1)), (0, 0))
    assert cursor.partition(valid, (0, 0)) == (0.0, -np.inf)
    assert cursor.last_start == 0


def test_partition_cursor_discards_mutated_cache_after_native_exception(
        monkeypatch: pytest.MonkeyPatch) -> None:
    import nca.partition as incremental

    native = incremental._NATIVE
    if native is None:
        pytest.skip("incremental partition is not built")
    prior = priors.height_prior(2)
    rows = np.log(np.full((3, 3), 1 / 3))
    selected = (2, 0, 0)
    cursor = incremental.PartitionCursor(prior)
    expected = cursor.partition(rows, selected)
    changed = rows.copy()
    changed[2] = np.log([0.5, 0.3, 0.2])
    def fail(*args: Any) -> None:
        args[6][:] = np.nan
        args[7][:] = 0
        raise RuntimeError("native failure")
    monkeypatch.setattr(incremental, "_NATIVE", SimpleNamespace(update=fail))
    with pytest.raises(RuntimeError, match="native failure"):
        cursor.partition(changed, selected)
    monkeypatch.setattr(incremental, "_NATIVE", native)
    assert cursor.partition(rows, selected) == expected
    assert cursor.last_start == 0


def test_partition_cursor_recovers_from_partial_resize_allocation(
        monkeypatch: pytest.MonkeyPatch) -> None:
    import nca.partition as incremental

    if incremental._NATIVE is None:
        pytest.skip("incremental partition is not built")
    prior = priors.height_prior(3)
    cursor = incremental.PartitionCursor(prior)
    rows = np.log(np.full((6, 3), 1 / 3))
    selected = (1, 1, 1, 1, 1, 0)
    cursor.partition(rows, selected)
    original = np.full
    calls = 0
    def failing_full(*args: Any, **kwargs: Any) -> np.ndarray:
        nonlocal calls
        calls += 1
        if calls == 2:
            raise MemoryError("injected allocation failure")
        return original(*args, **kwargs)
    monkeypatch.setattr(incremental.np, "full", failing_full)
    with pytest.raises(MemoryError, match="injected allocation failure"):
        cursor.partition(rows[:2], selected[:2])
    monkeypatch.setattr(incremental.np, "full", original)
    rows[-1] = np.log([0.5, 0.3, 0.2])
    np.testing.assert_allclose(cursor.partition(rows, selected), prior.partition(rows, selected))
    assert cursor.last_start == 0


def test_partition_cursor_matches_full_sparse_automata() -> None:
    from nca.partition import PartitionCursor

    rng = np.random.default_rng(2468)
    for _ in range(50):
        states, length = int(rng.integers(1, 12)), int(rng.integers(0, 16))
        transitions = rng.integers(-1, states, size=(states, 3))
        weights = rng.normal(size=(states, 3))
        final = rng.normal(size=states)
        rows = rng.normal(size=(length, 3))
        transitions[rng.random(transitions.shape) < .4] = -1
        weights[rng.random(weights.shape) < .1] = -np.inf
        final[rng.random(final.shape) < .1] = -np.inf
        selected = rng.integers(0, 3, size=length).tolist()
        prior = priors.ArityPrior((0, 1, 2), transitions, weights, final)
        cursor = PartitionCursor(prior)
        for _ in range(6):
            if length:
                k = int(rng.integers(length))
                rows[k] = rng.normal(size=3)
                selected[k] = int(rng.integers(3))
            np.testing.assert_allclose(cursor.partition(rows, tuple(selected)),
                                       prior.partition(rows, selected), atol=1e-12)


def test_partition_cursor_clears_old_gapped_envelopes() -> None:
    from nca.partition import PartitionCursor

    transitions = np.full((64, 3), -1, dtype=np.int64)
    transitions[0] = [1, 60, -1]
    transitions[1] = transitions[60] = [30, 30, -1]
    transitions[30] = [2, 61, -1]
    transitions[2] = transitions[61] = [0, 0, -1]
    prior = priors.ArityPrior((0, 1, 2), transitions, np.zeros((64, 3)), np.zeros(64))
    rows = np.zeros((12, 3))
    selected = (0,) * len(rows)
    cursor = PartitionCursor(prior)
    for position, symbol, value in ((0, 1, -np.inf), (4, 1, -np.inf), (0, 1, 0.0),
                                    (8, 0, -np.inf), (4, 1, 0.0), (8, 0, 0.0)):
        rows[position, symbol] = value
        np.testing.assert_allclose(cursor.partition(rows, selected),
                                   prior.partition(rows, selected), atol=1e-12)


def test_partition_cursor_bounds_cache_and_falls_back() -> None:
    import nca.partition as incremental

    prior = priors.ArityPrior((0,), np.array([[0]]), np.zeros((1, 1)), np.zeros(1))
    for invalid in (-1, True, 0.5):
        with pytest.raises(ValueError, match="max_cache_bytes"):
            incremental.PartitionCursor(prior, max_cache_bytes=invalid)
    cursor = incremental.PartitionCursor(prior, max_cache_bytes=128)
    with pytest.raises(AttributeError):
        cursor.max_cache_bytes = 0
    for n in (1, 100, 1):
        rows, selected = np.zeros((n, 1)), (0,) * n
        assert cursor.partition(rows, selected) == prior.partition(rows, selected)
        if n == 100:
            assert cursor._alternatives is None


def test_partition_cursor_fallback_does_not_copy_input_before_partition(
        monkeypatch: pytest.MonkeyPatch) -> None:
    import nca.partition as incremental

    prior = priors.height_prior(2)
    rows = np.zeros((12, 6))[:, ::2]
    selected = (0,) * len(rows)
    original = priors.ArityPrior.partition
    seen = []

    def recording_partition(self: priors.ArityPrior, weights: np.ndarray,
                            sequence: tuple[int, ...]) -> tuple[float, float]:
        seen.append(weights)
        return original(self, weights, sequence)

    monkeypatch.setattr(priors.ArityPrior, "partition", recording_partition)
    cursor = incremental.PartitionCursor(prior, max_cache_bytes=0)
    actual = cursor.partition(rows, selected)
    assert len(seen) == 1 and seen[0] is rows
    np.testing.assert_allclose(actual, original(prior, rows, selected))


@pytest.mark.parametrize("restore", [copy.copy, copy.deepcopy,
                                      lambda value: pickle.loads(pickle.dumps(value))])
def test_restored_prior_preserves_immutable_arrays(restore: Any) -> None:
    original = priors.height_prior(2)
    restored = restore(original)
    assert restored.log_weight((1, 0)) == original.log_weight((1, 0))
    for array in (restored.transitions, restored.log_weights, restored.log_final):
        with pytest.raises(ValueError):
            array.setflags(write=True)


@pytest.mark.parametrize("reference", [False, True])
def test_sequence_log_weight(reference: bool, monkeypatch: pytest.MonkeyPatch) -> None:
    if reference:
        monkeypatch.setattr(formulas, "_NATIVE", None)
        monkeypatch.setattr(priors, "_NATIVE", None)
        monkeypatch.setattr(decoding, "_NATIVE", None)
    rng = np.random.default_rng(31)
    alphabet = (7, 2, 9)
    rows = np.log(rng.dirichlet(np.ones(3), size=575))
    selected = rng.choice(alphabet, size=575).tolist()
    expected = sum(rows[k, alphabet.index(a)] for k, a in enumerate(selected))
    assert formulas.sequence_log_weight(rows, alphabet, selected) == expected
    assert formulas.sequence_log_weight(np.empty((0, 3)), alphabet, []) == 0.0
    assert formulas.sequence_log_weight(np.zeros((1, 3)), alphabet, [99]) == -np.inf
    rows[0] = -np.inf
    assert formulas.sequence_log_weight(rows, alphabet, selected) == -np.inf
    with pytest.raises(ValueError):
        formulas.sequence_log_weight(rows, alphabet, selected[:-1])

@pytest.mark.parametrize("reference", [False, True])
def test_weighted_prior_decode_matches_exhaustive_sequences(
        reference: bool, monkeypatch: pytest.MonkeyPatch) -> None:
    if reference:
        monkeypatch.setattr(formulas, "_NATIVE", None)
        monkeypatch.setattr(priors, "_NATIVE", None)
        monkeypatch.setattr(decoding, "_NATIVE", None)
    rng = np.random.default_rng(53)
    alphabet = (2, 0, 1)
    transitions = rng.integers(-1, 4, size=(4, 3))
    weights = rng.normal(size=(4, 3))
    final = rng.normal(size=4)
    final[1] = -np.inf
    prior = formulas.ArityPrior(alphabet, transitions, weights, final, start=2)
    # The prior owns a stable copy, even if the expert reuses its source arrays.
    transitions[:] = -1
    weights[:] = 99
    final[:] = -np.inf
    for size in range(1, 7):
        rows = rng.normal(size=(size, 3)) - 1000
        candidates = list(itertools.product(alphabet, repeat=size))
        scores = np.array([sum(rows[k, alphabet.index(a)] for k, a in enumerate(selected))
                           + prior.log_weight(selected) for selected in candidates])
        posterior = prior.decode(rows)
        log_z = float(np.logaddexp.reduce(scores))
        if not np.isfinite(log_z):
            assert posterior is None
            continue
        assert posterior is not None
        assert posterior.log_z == pytest.approx(log_z, abs=1e-10)
        assert prior.log_normalizer(rows) == posterior.log_z
        assert prior.best(rows) == posterior.arities
        assert posterior.arities == candidates[int(np.argmax(scores))]
        probabilities = np.exp(scores - log_z)
        expected = np.array([[sum(p for selected, p in zip(candidates, probabilities)
                                 if selected[k] == a) for a in alphabet] for k in range(size)])
        np.testing.assert_allclose(posterior.marginals, expected, atol=1e-10)
        assert posterior.risk(rows, alphabet) == pytest.approx(
            -np.expm1(scores.max() - log_z), abs=1e-10)
        for selected, score in zip(candidates, scores):
            assert posterior.risk(rows, alphabet, selected) == pytest.approx(
                -np.expm1(score - log_z), abs=1e-10)
    with pytest.raises(ValueError):
        prior.transitions[0, 0] = 0

@pytest.mark.parametrize("reference", [False, True])
def test_weighted_prior_empty_support_and_validation(
        reference: bool, monkeypatch: pytest.MonkeyPatch) -> None:
    if reference:
        monkeypatch.setattr(formulas, "_NATIVE", None)
        monkeypatch.setattr(priors, "_NATIVE", None)
        monkeypatch.setattr(decoding, "_NATIVE", None)
    prior = formulas.ArityPrior((0,), np.array([[0]]), np.zeros((1, 1)), np.array([-np.inf]))
    assert prior.decode(np.zeros((3, 1))) is None
    assert prior.decode(np.empty((0, 1))) is None
    assert prior.log_weight((2,)) == -np.inf
    for rows in (np.zeros((3, 2)), np.array([[np.nan]]), np.array([[np.inf]])):
        with pytest.raises(ValueError):
            prior.decode(rows)
    for transitions, weights, final in (([[1]], [[0]], [0]),
                                        ([[0.5]], [[0]], [0]),
                                        ([[0]], [[np.nan]], [0]),
                                        ([[0]], [[0]], [np.inf])):
        with pytest.raises(ValueError):
            formulas.ArityPrior((0,), np.array(transitions), np.array(weights), np.array(final))


@pytest.mark.parametrize("reference", [False, True])
@pytest.mark.parametrize("final", [-np.inf, -2.0, 0.0, 1.5])
def test_weighted_prior_empty_sequence(
        reference: bool, final: float, monkeypatch: pytest.MonkeyPatch) -> None:
    if reference:
        monkeypatch.setattr(priors, "_NATIVE", None)
    prior = priors.ArityPrior((0, 1), np.array([[0, 0]]), np.zeros((1, 2)), np.array([final]))
    rows = np.empty((0, 2))
    assert prior.log_weight(()) == final
    assert prior.log_normalizer(rows) == final
    decoded = prior.decode(rows)
    if final == -np.inf:
        assert decoded is None and prior.best(rows) is None
    else:
        assert decoded is not None and decoded.arities == prior.best(rows) == ()
        assert decoded.log_z == final and decoded.marginals.shape == (0, 2)
        assert decoded.risk(rows, prior.alphabet) == 0.0


def test_native_empty_sequence_uses_start_final_weight() -> None:
    native = priors._NATIVE
    if native is None:
        pytest.skip("native prior decoder is not built")
    args = (np.empty(0, dtype=np.float64), np.array([0], dtype=np.int64),
            np.array([0], dtype=np.int64), np.array([0.0]), np.array([-2.0]), 0)
    assert native.prior_normalizer(*args) == -2.0
    decoded = native.decode_prior(*args)
    assert decoded == {"log_z": -2.0, "arities": [], "marginals": []}

@pytest.mark.parametrize("reference", [False, True])
def test_counter_prior_matches_format_decoder(reference: bool,
                                              monkeypatch: pytest.MonkeyPatch) -> None:
    if reference:
        monkeypatch.setattr(formulas, "_NATIVE", None)
        monkeypatch.setattr(priors, "_NATIVE", None)
        monkeypatch.setattr(decoding, "_NATIVE", None)
    rng = np.random.default_rng(59)
    alphabet = (2, 0, 1)
    for size in (1, 3, 9, 35):
        states = size + 2
        transitions = np.full((states, 3), -1, dtype=np.int64)
        for state in range(1, states):
            for j, a in enumerate(alphabet):
                if state - 1 + a < states:
                    transitions[state, j] = state - 1 + a
        final = np.full(states, -np.inf)
        final[0] = 0.0
        prior = formulas.ArityPrior(alphabet, transitions, np.zeros_like(transitions), final, 1)
        rows = np.log(rng.dirichlet(np.ones(3), size=size))
        actual = prior.decode(rows)
        expected = decode(rows, alphabet)
        assert actual is not None and expected is not None
        assert actual.log_z == pytest.approx(expected.log_z, abs=1e-12)
        assert actual.arities == expected.arities
        np.testing.assert_allclose(actual.marginals, expected.marginals, atol=1e-12)
        assert actual.risk(rows, alphabet) == pytest.approx(expected.risk(rows, alphabet))
        with pytest.raises(ValueError, match="alphabet"):
            actual.risk(rows, (0, 1, 2))

def complete_shapes(depth: int) -> list[tuple[int, ...]]:
    if not depth:
        return [(0,), (1, 0)]
    smaller = complete_shapes(depth - 1)
    return [(2, *left, *right) for left in smaller for right in smaller]

def test_complete_prior_accepts_exactly_complete_shapes() -> None:
    expected = set(complete_shapes(0) + complete_shapes(1) + complete_shapes(2))
    for size in range(1, 9):
        prior = formulas.complete_prior(size)
        for selected in itertools.product(range(3), repeat=size):
            accepted = prior is not None and prior.log_weight(selected) == 0.0
            assert accepted == (selected in expected)
    for depth in range(4):
        for selected in complete_shapes(depth):
            prior = formulas.complete_prior(len(selected))
            assert prior is not None and prior.log_weight(selected) == 0.0
            assert parse(selected) is not None
    for invalid in (0, -1, 1.5):
        with pytest.raises(ValueError):
            formulas.complete_prior(invalid)
    assert formulas.complete_prior(6) is None
    assert formulas.complete_prior(12) is None

@pytest.mark.parametrize("reference", [False, True])
def test_complete_prior_posterior_matches_enumerated_shapes(
        reference: bool, monkeypatch: pytest.MonkeyPatch) -> None:
    if reference:
        monkeypatch.setattr(formulas, "_NATIVE", None)
        monkeypatch.setattr(priors, "_NATIVE", None)
        monkeypatch.setattr(decoding, "_NATIVE", None)
    rng = np.random.default_rng(67)
    for depth in range(4):
        shapes = complete_shapes(depth)
        for size in sorted({len(shape) for shape in shapes}):
            prior = formulas.complete_prior(size)
            assert prior is not None
            rows = np.log(rng.dirichlet(np.ones(3), size=size))
            candidates = [shape for shape in shapes if len(shape) == size]
            scores = np.array([sum(rows[k, a] for k, a in enumerate(shape))
                               for shape in candidates])
            expected_z = np.logaddexp.reduce(scores)
            posterior = prior.decode(rows)
            assert posterior is not None
            assert posterior.arities == candidates[int(np.argmax(scores))]
            assert posterior.log_z == pytest.approx(expected_z, abs=1e-12)
            assert posterior.risk(rows, (0, 1, 2)) == pytest.approx(
                -np.expm1(scores.max() - expected_z), abs=1e-12)

@pytest.mark.parametrize("reference", [False, True])
def test_unreachable_prior_states_do_not_change_posteriors(
        reference: bool, monkeypatch: pytest.MonkeyPatch) -> None:
    if reference:
        monkeypatch.setattr(formulas, "_NATIVE", None)
        monkeypatch.setattr(priors, "_NATIVE", None)
        monkeypatch.setattr(decoding, "_NATIVE", None)
    transitions = np.array([[0, 1, -1], [1, -1, 0]])
    base = formulas.ArityPrior((0, 1, 2), transitions, np.zeros((2, 3)),
                              np.array([0.0, -np.inf]))
    enlarged = formulas.ArityPrior((0, 1, 2),
        np.vstack([transitions, [[2, 3, 4], [3, 4, 2], [4, 2, 3]]]),
        np.vstack([np.zeros((2, 3)), np.full((3, 3), 1e6)]),
        np.array([0.0, -np.inf, 1e6, 1e6, 1e6]))
    rows = np.log(np.random.default_rng(79).dirichlet(np.ones(3), size=7))
    rows[3, 0] = -np.inf
    expected, actual = base.decode(rows), enlarged.decode(rows)
    assert expected is not None and actual is not None
    assert actual.arities == expected.arities
    assert actual.log_z == pytest.approx(expected.log_z, abs=1e-12)
    np.testing.assert_allclose(actual.marginals, expected.marginals, atol=1e-12)

def test_native_prior_log_weight_matches_reference_for_all_short_sequences(
        monkeypatch: pytest.MonkeyPatch) -> None:
    if getattr(priors._NATIVE, "prior_log_weight", None) is None:
        pytest.skip("native prior scoring kernel is not built")
    native = formulas._NATIVE
    prior = formulas.ArityPrior((2, 0, 1), np.array([[1, 0, -1], [0, -1, 1]]),
        np.array([[0.3, -0.7, 0.0], [-np.inf, 0.8, 1.2]]), np.array([-0.2, -np.inf]))
    for size in range(6):
        for selected in itertools.product((-1, 0, 1, 2, 3), repeat=size):
            monkeypatch.setattr(formulas, "_NATIVE", None)
            monkeypatch.setattr(priors, "_NATIVE", None)
            monkeypatch.setattr(decoding, "_NATIVE", None)
            expected = prior.log_weight(selected)
            monkeypatch.setattr(formulas, "_NATIVE", native)
            monkeypatch.setattr(priors, "_NATIVE", native)
            monkeypatch.setattr(decoding, "_NATIVE", native)
            assert prior.log_weight(selected) == expected
    # Empty input retains the initial state's final weight; source arrays are read-only.
    assert prior.log_weight(()) == -0.2

def bounded_shapes(height: int) -> set[tuple[int, ...]]:
    if not height:
        return {(0,)}
    smaller = bounded_shapes(height - 1)
    return {(0,)} | {(1, *child) for child in smaller} | {
        (2, *left, *right) for left in smaller for right in smaller}

def test_height_prior_accepts_exactly_bounded_shapes() -> None:
    for height in range(3):
        prior = formulas.height_prior(height)
        expected = bounded_shapes(height)
        for size in range(1, 8):
            for selected in itertools.product(range(3), repeat=size):
                assert (prior.log_weight(selected) == 0.0) == (selected in expected)
    for depth in range(4):
        prior = formulas.height_prior(depth + 1)
        for selected in complete_shapes(depth):
            assert prior.log_weight(selected) == 0.0
    for invalid in (-1, 1.5):
        with pytest.raises(ValueError):
            formulas.height_prior(invalid)

@pytest.mark.parametrize("reference", [False, True])
def test_height_prior_posterior_matches_enumerated_shapes(
        reference: bool, monkeypatch: pytest.MonkeyPatch) -> None:
    if reference:
        monkeypatch.setattr(formulas, "_NATIVE", None)
        monkeypatch.setattr(priors, "_NATIVE", None)
        monkeypatch.setattr(decoding, "_NATIVE", None)
    rng = np.random.default_rng(89)
    prior = formulas.height_prior(2)
    shapes = bounded_shapes(2)
    for size in range(1, 8):
        rows = np.log(rng.dirichlet(np.ones(3), size=size))
        candidates = sorted(shape for shape in shapes if len(shape) == size)
        scores = np.array([sum(rows[k, a] for k, a in enumerate(shape)) for shape in candidates])
        posterior = prior.decode(rows)
        assert posterior is not None
        assert posterior.arities == candidates[int(np.argmax(scores))]
        assert posterior.log_z == pytest.approx(np.logaddexp.reduce(scores), abs=1e-12)
        assert parse(posterior.arities) is not None
    assert prior.decode(np.zeros((8, 3))) is None

@pytest.mark.parametrize("reference", [False, True])
def test_prior_best_matches_full_decoder_ties_and_zero_support(
        reference: bool, monkeypatch: pytest.MonkeyPatch) -> None:
    if reference:
        monkeypatch.setattr(formulas, "_NATIVE", None)
        monkeypatch.setattr(priors, "_NATIVE", None)
        monkeypatch.setattr(decoding, "_NATIVE", None)
    prior = formulas.ArityPrior((2, 0, 1), np.array([[0, 1, -1], [1, 0, 2], [2, 2, 1]]),
                                np.zeros((3, 3)), np.zeros(3))
    for size in (1, 2, 5, 31):
        rows = np.zeros((size, 3))
        posterior = prior.decode(rows)
        assert posterior is not None
        assert prior.best(rows) == posterior.arities
    assert prior.best(np.empty((0, 3))) == ()
    assert prior.best(np.full((3, 3), -np.inf)) is None
    with pytest.raises(ValueError):
        prior.best(np.ones((3, 2)))

def test_native_prior_best_does_not_compute_unused_posteriors(
        monkeypatch: pytest.MonkeyPatch) -> None:
    if getattr(priors._NATIVE, "prior_best", None) is None:
        pytest.skip("native prior maximum is not built")

    def no_decode(*args: Any) -> Any:
        raise AssertionError("maximum-only selection must not compute sums or marginals")

    monkeypatch.setattr(formulas.ArityPrior, "decode", no_decode)
    prior = formulas.complete_prior(3)
    assert prior is not None
    assert prior.best(np.zeros((3, 3))) == (2, 0, 0)


def test_normalizer_matches_full_decoder_for_sparse_weighted_automata() -> None:
    rng = np.random.default_rng(42)
    for _ in range(100):
        states = int(rng.integers(1, 9))
        transitions = rng.integers(-1, states, size=(states, 3))
        weights = rng.normal(size=(states, 3))
        final = rng.normal(size=states)
        rows = rng.normal(size=(int(rng.integers(1, 16)), 3))
        weights[rng.random(weights.shape) < .2] = -np.inf
        final[rng.random(final.shape) < .2] = -np.inf
        rows[rng.random(rows.shape) < .2] = -np.inf
        prior = priors.ArityPrior((0, 1, 2), transitions, weights, final)
        decoded = prior.decode(rows)
        expected = -np.inf if decoded is None else decoded.log_z
        assert prior.log_normalizer(rows) == pytest.approx(expected, abs=1e-12)


@pytest.mark.parametrize("reference", [False, True])
@pytest.mark.parametrize("location", ["edge", "sequence", "final"])
def test_normalizer_rejects_finite_negative_overflow(
        reference: bool, location: str, monkeypatch: pytest.MonkeyPatch) -> None:
    if reference:
        monkeypatch.setattr(priors, "_NATIVE", None)
    weight = -1e308 if location in ("edge", "sequence") else 0.0
    final = -1e308 if location == "final" else 0.0
    rows = np.full((2 if location == "sequence" else 1, 1),
                   -1e308 if location == "edge" else 0.0)
    if location == "final":
        rows[0, 0] = -1e308
    prior = priors.ArityPrior((0,), np.array([[0]]), np.array([[weight]]), np.array([final]))
    with pytest.raises(ValueError, match="normalizer.*finite"):
        prior.log_normalizer(rows)
    assert prior.log_normalizer(np.full_like(rows, -np.inf)) == -np.inf
    for operation in (prior.decode, prior.best):
        with pytest.raises(ValueError, match="normalizer.*finite"):
            operation(rows)
        assert operation(np.full_like(rows, -np.inf)) is None


def test_older_native_decoder_without_normalizer_can_return_no_result(
        monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setattr(priors, "_NATIVE", SimpleNamespace(
        prior_best=lambda *args: [], decode_prior=lambda *args: None))
    prior = priors.ArityPrior((0,), np.array([[0]]), np.zeros((1, 1)), np.zeros(1))
    rows = np.full((1, 1), -np.inf)
    assert prior.best(rows) is None and prior.decode(rows) is None


@pytest.mark.parametrize("reference", [False, True])
def test_prior_decoders_reject_overflow_even_when_other_paths_exist(
        reference: bool, monkeypatch: pytest.MonkeyPatch) -> None:
    if reference:
        monkeypatch.setattr(priors, "_NATIVE", None)
    prior = priors.ArityPrior((0, 1), np.array([[0, 0]]),
                              np.array([[1e308, 0.0]]), np.zeros(1))
    for operation in (prior.best, prior.decode):
        with pytest.raises(ValueError, match="normalizer.*finite"):
            operation(np.zeros((2, 2)))


@pytest.mark.parametrize("reference", [False, True])
def test_prior_decoder_rejects_overflowing_backward_sums(
        reference: bool, monkeypatch: pytest.MonkeyPatch) -> None:
    if reference:
        monkeypatch.setattr(priors, "_NATIVE", None)
    prior = priors.ArityPrior((0,), np.array([[1], [2], [2]]),
                              np.array([[-1e308], [1e308], [1e308]]), np.zeros(3))
    rows = np.zeros((3, 1))
    with pytest.raises(ValueError, match="(decoder|decoding).*(finite|unavailable)"):
        prior.decode(rows)


def test_prior_passes_reuse_shrinking_and_gapped_state_ranges() -> None:
    # Successive supports alternate between a wide range with holes and one cell.
    # The two reusable rows must clear their old, sometimes wider envelopes.
    transitions = np.full((257, 3), -1, dtype=np.int64)
    transitions[128] = [1, 255, 128]
    transitions[1] = [127, 127, 127]
    transitions[255] = [127, 127, 127]
    transitions[127] = [2, 254, 127]
    transitions[2] = [128, 128, 128]
    transitions[254] = [128, 128, 128]
    weights = np.zeros((257, 3))
    weights[128, 2] = weights[127, 2] = -np.inf
    final = np.full(257, -np.inf)
    final[[1, 2, 127, 128, 254, 255]] = [0, -2, -1, 0, -3, 1]
    prior = priors.ArityPrior((2, 0, 1), transitions, weights, final, start=128)
    rng = np.random.default_rng(73)
    rows = np.log(rng.dirichlet(np.ones(3), size=17))
    for size in range(1, len(rows) + 1):
        full = prior.decode(rows[:size])
        assert full is not None
        assert prior.log_normalizer(rows[:size]) == full.log_z
        assert prior.best(rows[:size]) == full.arities
    # Once all prefixes die, stale values from either row must never reappear.
    rows[8] = -np.inf
    for size in range(9, len(rows) + 1):
        assert prior.decode(rows[:size]) is None
        assert prior.log_normalizer(rows[:size]) == -np.inf
        assert prior.best(rows[:size]) is None


def test_prior_partition_handles_shrinking_gapped_envelopes(
        monkeypatch: pytest.MonkeyPatch) -> None:
    if getattr(priors._NATIVE, "prior_partition", None) is None:
        pytest.skip("native partition is not built")
    transitions = np.full((257, 3), -1, dtype=np.int64)
    transitions[128] = [1, 255, 128]
    transitions[1] = transitions[255] = [127, 127, 127]
    transitions[127] = [2, 254, 127]
    transitions[2] = transitions[254] = [128, 128, 128]
    final = np.full(257, -np.inf)
    final[[1, 2, 127, 128, 254, 255]] = 0
    prior = priors.ArityPrior((2, 0, 1), transitions, np.zeros((257, 3)), final, start=128)
    rows = np.log(np.random.default_rng(73).dirichlet(np.ones(3), size=17))
    selected = (2, 0, 1, 2, 0, 1, 2, 0, 1, 2, 0, 1, 2, 0, 1, 2, 0)
    actual = [prior.partition(rows[:n], selected[:n]) for n in range(18)]
    monkeypatch.setattr(priors, "_NATIVE", None)
    expected = [prior.partition(rows[:n], selected[:n]) for n in range(18)]
    np.testing.assert_allclose(actual, expected, atol=1e-12)


@pytest.mark.parametrize("reference", [False, True])
def test_symbol_tilts_preserve_support_and_weighted_decoding(
        reference: bool, monkeypatch: pytest.MonkeyPatch) -> None:
    if reference:
        monkeypatch.setattr(priors, "_NATIVE", None)
    rng = np.random.default_rng(1705)
    prior = priors.ArityPrior((2, 0, 1), np.array([[1, 0, -1], [0, 1, 2], [2, 0, 1]]),
                              np.array([[0., -1, 0], [1, 0, -np.inf], [-1, 1, 0]]),
                              np.array([0., -np.inf, 1]), start=2)
    factors = np.log([.5, 2, 4])
    tilted = priors.tilt_prior(prior, factors)
    for size in range(6):
        for selected in itertools.product(prior.alphabet, repeat=size):
            original = prior.log_weight(selected)
            expected = original + sum(factors[prior.alphabet.index(a)] for a in selected)
            assert tilted.log_weight(selected) == pytest.approx(expected)
            assert np.isfinite(tilted.log_weight(selected)) == np.isfinite(original)
        if size:
            rows = rng.normal(size=(size, 3))
            actual, shifted = tilted.decode(rows), prior.decode(rows + factors)
            assert actual is not None and shifted is not None
            assert actual.arities == shifted.arities
            assert actual.log_z == pytest.approx(shifted.log_z)
            np.testing.assert_allclose(actual.marginals, shifted.marginals, atol=1e-12)
    factors[:] = 100
    assert tilted.log_weights[0, 0] == np.log(.5)
    assert not tilted.log_weights.flags.writeable
    assert not np.shares_memory(tilted.transitions, prior.transitions)


def test_symbol_tilt_validation_and_identity() -> None:
    prior = priors.height_prior(2)
    identity = priors.tilt_prior(prior, [0, 0, 0])
    np.testing.assert_array_equal(identity.log_weights, prior.log_weights)
    for bad in ([0, 0], [0, np.inf, 0], [0, -np.inf, 0], [0, np.nan, 0]):
        with pytest.raises(ValueError, match="finite log factor"):
            priors.tilt_prior(prior, bad)
    for weight, factor in ((1e308, 1e308), (-1e308, -1e308)):
        extreme = priors.ArityPrior((0,), np.array([[0]]), np.array([[weight]]), np.zeros(1))
        with pytest.raises(ValueError, match="overflow"):
            priors.tilt_prior(extreme, [factor])


def test_complete_prior_unary_tilts_cancel_at_fixed_length() -> None:
    rng = np.random.default_rng(1706)
    for size in (7, 9, 11):
        model = priors.complete_prior(size)
        assert model is not None
        rows = np.log(rng.dirichlet(np.ones(3), size=size))
        base = np.log(np.full((size, 3), 1 / 3))
        original = model.decode(rows)
        assert original is not None
        for factor in (.25, 4):
            tilted = priors.tilt_prior(model, [0, np.log(factor), 0])
            result = tilted.decode(rows)
            assert result is not None
            assert result.arities == original.arities
            assert result.log_z == pytest.approx(original.log_z + (size - 7) * np.log(factor))
            np.testing.assert_allclose(result.marginals, original.marginals, atol=1e-12)
            assert tilted.log_evidence(rows, base) == pytest.approx(model.log_evidence(rows, base))


def test_native_prior_decode_returns_owned_typed_record() -> None:
    import copy
    import gc

    native = getattr(priors._NATIVE, "decode_prior", None)
    if native is None:
        pytest.skip("requires native prior decoding")
    model = priors.complete_prior(3)
    assert model is not None
    rows = np.log(np.array([[.1, .2, .7], [.8, .1, .1], [.6, .2, .2]]))
    args = (np.array(model.alphabet, dtype=np.int64), model.transitions.reshape(-1),
            model.log_weights.reshape(-1), model.log_final, model.start)
    result = native(rows.reshape(-1), *args)
    assert set(result) == {"log_z", "arities", "marginals"}
    assert result["arities"] == [2, 0, 0]
    assert all(type(a) is int for a in result["arities"])
    assert len(result["marginals"]) == 3
    assert all(len(row) == 3 for row in result["marginals"])
    np.testing.assert_allclose(np.sum(result["marginals"], axis=1), 1, atol=1e-12)
    saved = copy.deepcopy(result)
    for _ in range(30):
        other = native(rows.reshape(-1), *args)
        other["arities"][0] = 99
        other["marginals"][0][0] = 99
    gc.collect()
    assert result == saved
    decoded = model.decode(rows)
    assert decoded is not None
    assert decoded.arities == tuple(result["arities"])
    np.testing.assert_array_equal(decoded.marginals, result["marginals"])
    assert native(np.empty(0), *args) is None
    assert native(np.full(9, -np.inf), *args) is None


def test_native_prior_passes_accept_unaligned_readonly_weights() -> None:
    if getattr(priors._NATIVE, "decode_prior", None) is None:
        pytest.skip("requires native prior decoding")
    storage = bytearray(1 + 9 * np.dtype(np.float64).itemsize)
    rows = np.ndarray((3, 3), dtype=np.float64, buffer=storage, offset=1)
    rows[:] = np.log([[.1, .2, .7], [.8, .1, .1], [.6, .2, .2]])
    rows.setflags(write=False)
    assert rows.flags.c_contiguous and not rows.flags.aligned
    # Contiguity conversion alone does not align the data; the FFI must handle it.
    assert np.ascontiguousarray(rows) is rows
    model = priors.complete_prior(3)
    assert model is not None
    aligned = rows.copy()
    expected = model.decode(aligned)
    actual = model.decode(rows)
    assert expected is not None and actual is not None
    assert actual.arities == expected.arities
    assert actual.log_z == expected.log_z
    np.testing.assert_array_equal(actual.marginals, expected.marginals)
    assert model.best(rows) == expected.arities
    assert model.log_normalizer(rows) == expected.log_z
    np.testing.assert_array_equal(rows, aligned)


@pytest.mark.parametrize("reference", [False, True])
def test_leaf_and_binary_tilts_have_identical_bounded_posteriors(
        reference: bool, monkeypatch: pytest.MonkeyPatch) -> None:
    if reference:
        monkeypatch.setattr(priors, "_NATIVE", None)
    rng = np.random.default_rng(2714)
    prior = priors.height_prior(4)
    for size in range(1, 12):
        rows = np.log(rng.dirichlet(np.ones(3), size=size))
        base = np.log(np.full((size, 3), 1 / 3))
        for log_factor in (-2.0, 0.0, 1.5):
            leaf = priors.tilt_prior(prior, [log_factor, 0, 0])
            binary = priors.tilt_prior(prior, [0, 0, log_factor])
            left, right = leaf.decode(rows), binary.decode(rows)
            assert left is not None and right is not None
            assert left.arities == right.arities
            assert left.log_z == pytest.approx(right.log_z + log_factor, abs=1e-11)
            np.testing.assert_allclose(left.marginals, right.marginals, atol=1e-11)
            assert leaf.log_evidence(rows, base) == pytest.approx(binary.log_evidence(rows, base), abs=1e-11)


def test_sequence_risk_preserves_finite_underflowed_alternative() -> None:
    import math
    from nca.priors import risk_from_partition

    assert risk_from_partition(0.0, -1000.0) == math.nextafter(0.0, 1.0)
    assert risk_from_partition(0.0, -math.inf) == 0.0
