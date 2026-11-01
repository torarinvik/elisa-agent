import itertools
from collections.abc import Callable, Sequence
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


@pytest.mark.parametrize("alphabet, slack", [((), 1e-4), ((0, -1), 1e-4),
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


def test_native_off_reference_log_mass_matches_reference(monkeypatch: pytest.MonkeyPatch) -> None:
    if getattr(decoding._NATIVE, "off_reference_log_mass", None) is None:
        pytest.skip("native off-reference kernel is not built")
    rng = np.random.default_rng(239)
    rows = rng.choice([0.0, -40.0, -1000.0, -np.inf], size=(12, 5))
    reference = rng.integers(0, rows.shape[1], size=len(rows))
    actual = decoding._off_reference_log_mass(rows, reference)
    monkeypatch.setattr(decoding, "_NATIVE", None)
    expected = decoding._off_reference_log_mass(rows, reference)
    assert actual == pytest.approx(expected, abs=1e-12)

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


@pytest.mark.parametrize("alphabet", [(), (0, -1)])
@pytest.mark.parametrize("decoder", [decode, decode_reference])
def test_decode_rejects_empty_or_negative_arity_alphabet(decoder, alphabet) -> None:
    with pytest.raises(ValueError, match="nonnegative arities"):
        decoder(np.zeros((2, len(alphabet))), alphabet)


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
