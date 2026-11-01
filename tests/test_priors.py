import itertools
from typing import Any

import numpy as np
import pytest

from nca import decoding, formulas, priors
from nca.formulas import (decode,
                          parse)


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
    assert prior.best(np.empty((0, 3))) is None
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
