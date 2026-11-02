import itertools
import math
from typing import Any
from decimal import Decimal, localcontext

import numpy as np
import pytest

torch = pytest.importorskip("torch")

from nca import decoding, priors
from nca.domains.boolean.formulas import FormulaDataset
from nca.decoding import decode
from nca.ladder import Decision, Rung
from nca.domains.boolean.words import (ARITY_DECISION, EditReader)


@pytest.mark.parametrize("reference", [False, True])
@pytest.mark.parametrize("location", ["edge", "final"])
def test_prior_evidence_and_selection_ignore_large_common_weight(reference, location, monkeypatch) -> None:
    if reference:
        monkeypatch.setattr(priors, "_NATIVE", None)
    large = float(2**52)
    if location == "edge":
        prior = priors.ArityPrior((0, 1), np.array([[0, 0]]), np.array([[large, large - 2]]),
                                  np.zeros(1))
    else:
        prior = priors.ArityPrior((0, 1), np.array([[1, 2], [-1, -1], [-1, -1]]),
                                  np.zeros((3, 2)), np.array([-np.inf, large, large - 2]))
    competitor = priors.ArityPrior((0, 1), np.array([[0, 0]]), np.array([[0.0, -2.1]]),
                                   np.zeros(1))
    base = np.log([0.5, 0.5])
    posterior = np.log([[0.9, 0.1]])
    expected = math.log((0.9 + 0.1 * math.exp(-2)) / (0.5 + 0.5 * math.exp(-2)))
    assert prior.log_evidence(posterior, base[None, :]) == pytest.approx(expected, abs=1e-12)
    selected = priors.select_prior([lambda _: prior, lambda _: competitor], [posterior], base,
                                   alphabet=(0, 1))
    assert selected.index == 1
    assert selected.scores[0] == pytest.approx(expected, abs=1e-12)


@pytest.mark.parametrize("reference", [False, True])
def test_prior_evidence_ignores_forbidden_edge_weight_when_shifting(reference, monkeypatch) -> None:
    if reference:
        monkeypatch.setattr(priors, "_NATIVE", None)
    large = -float(2**52)
    prior = priors.ArityPrior((0, 1, 2), np.array([[0, 0, -1]]),
                              np.array([[large, large - 2, 0.0]]), np.zeros(1))
    base = np.log([[1 / 3, 1 / 3, 1 / 3]])
    posterior = np.log([[0.45, 0.05, 0.5]])
    expected = math.log((0.45 + 0.05 * math.exp(-2)) / ((1 + math.exp(-2)) / 3))
    assert prior.log_evidence(posterior, base) == pytest.approx(expected, abs=1e-12)


@pytest.mark.parametrize("reference", [False, True])
def test_prior_evidence_rejects_large_normalizers_hidden_by_unreachable_final(reference, monkeypatch) -> None:
    if reference:
        monkeypatch.setattr(priors, "_NATIVE", None)
    prior = priors.ArityPrior((0, 1), np.array([[0, 0], [-1, -1]]),
                              np.array([[0.0, -2.0], [0.0, 0.0]]),
                              np.array([-float(2**52), 0.0]))
    base = np.log([[0.5, 0.5]])
    posterior = np.log([[0.9, 0.1]])
    with pytest.raises(ValueError, match="normalizers are too large|normalizer arithmetic.*precision"):
        prior.log_evidence(posterior, base)
    with pytest.raises(ValueError, match="normalizers are too large|normalizer arithmetic.*precision"):
        priors.select_prior([lambda _: prior], [posterior], base[0], alphabet=(0, 1))
    # Identical readings need positive mass, never a precise normalizer.
    assert prior.log_evidence(base, base) == 0.0
    empty = priors.ArityPrior((0, 1), np.array([[0, 0], [-1, -1]]), np.zeros((2, 2)),
                              np.array([-np.inf, 0.0]))
    with pytest.raises(ValueError, match="zero mass"):
        empty.log_evidence(base, base)
    selected = priors.select_prior([lambda _: prior], [base], base[0], alphabet=(0, 1))
    assert selected.scores == (0.0,)


def test_support_matches_positive_normalizers() -> None:
    rng = np.random.default_rng(2211)
    for _ in range(300):
        states = int(rng.integers(1, 4))
        transitions = rng.integers(-1, states, size=(states, 3))
        weights = np.where(rng.random((states, 3)) < 0.2, -np.inf, rng.normal(size=(states, 3)))
        final = np.where(rng.random(states) < 0.3, -np.inf, rng.normal(size=states))
        prior = priors.ArityPrior((0, 1, 2), transitions, weights, final)
        rows = np.where(rng.random((int(rng.integers(0, 5)), 3)) < 0.2, -np.inf,
                        rng.normal(size=(1, 3)))
        assert prior.supports(rows) == (prior.log_normalizer(rows) > -np.inf)


@pytest.mark.parametrize("reference", [False, True])
def test_prior_evidence_rejects_unrepresentable_prior_shift(reference, monkeypatch) -> None:
    if reference:
        monkeypatch.setattr(priors, "_NATIVE", None)
    prior = priors.ArityPrior((0, 1), np.array([[0, 0]]), np.array([[1e308, -1e308]]),
                              np.zeros(1))
    base = np.log([[0.5, 0.5]])
    with pytest.raises(ValueError, match="normalizer.*(finite|precision)"):
        prior.log_evidence(base, base)
    with pytest.raises(ValueError, match="normalizer.*(finite|precision)"):
        priors.select_prior([lambda _: prior], [base], base[0], alphabet=(0, 1))


@pytest.mark.parametrize("reference", [False, True])
def test_prior_evidence_matches_enumerated_observation_likelihood(
        reference: bool, monkeypatch: pytest.MonkeyPatch) -> None:
    if reference:
        monkeypatch.setattr(priors, "_NATIVE", None)
        monkeypatch.setattr(decoding, "_NATIVE", None)
    base = np.array([[0.8, 0.2], [0.6, 0.4], [0.3, 0.7]])
    likelihood = np.array([[0.1, 0.9], [0.8, 0.2], [0.2, 0.8]])
    marginals = (base * likelihood).sum(axis=1)
    posterior = base * likelihood / marginals[:, None]
    for transitions, weights in (([[0, 0]], [[0.5, 1.7]]), ([[0, -1]], [[1.0, 1.0]])):
        prior = priors.ArityPrior((0, 1), np.array(transitions), np.log(weights), np.zeros(1))
        numerator = denominator = 0.0
        for selected in itertools.product(range(2), repeat=3):
            weight = np.exp(prior.log_weight(selected))
            mass = weight * np.prod([base[k, a] for k, a in enumerate(selected)])
            denominator += mass
            numerator += mass * np.prod([likelihood[k, a] for k, a in enumerate(selected)])
        expected = np.log(numerator / denominator) - np.log(marginals).sum()
        actual = prior.log_evidence(np.log(posterior), np.log(base))
        assert actual == pytest.approx(expected, abs=1e-12)
        scaled = priors.ArityPrior(prior.alphabet, prior.transitions,
                                     prior.log_weights + 2, prior.log_final + 3)
        assert scaled.log_evidence(np.log(posterior), np.log(base)) == pytest.approx(actual)

def test_prior_evidence_support_and_probability_validation() -> None:
    prior = priors.ArityPrior((0, 1), np.array([[0, -1]]), np.zeros((1, 2)), np.zeros(1))
    base = np.log(np.array([[0.5, 0.5]]))
    assert prior.log_evidence(np.array([[-np.inf, 0.0]]), base) == -np.inf
    with pytest.raises(ValueError, match="zero mass"):
        prior.log_evidence(np.array([[-np.inf, 0.0]]), np.array([[-np.inf, 0.0]]))
    with pytest.raises(ValueError, match="support"):
        prior.log_evidence(base, np.array([[0.0, -np.inf]]))
    for bad in (np.zeros((1, 2)), np.array([[np.nan, 0.0]]), np.empty((0, 2))):
        with pytest.raises(ValueError):
            prior.log_evidence(bad, base)


@pytest.mark.parametrize("reference", [False, True])
def test_evidence_and_selection_accept_empty_sequence(
        reference: bool, monkeypatch: pytest.MonkeyPatch) -> None:
    if reference:
        monkeypatch.setattr(priors, "_NATIVE", None)
    prior = priors.ArityPrior((0, 1), np.array([[0, 0]]), np.zeros((1, 2)), np.array([-2.0]))
    rows = np.empty((0, 2))
    assert prior.log_evidence(rows, rows) == 0.0
    seen: list[int] = []
    def provider(length: int) -> priors.ArityPrior:
        seen.append(length)
        return prior
    selection = priors.select_prior([provider], [rows, rows], np.log([0.5, 0.5]), alphabet=(0, 1))
    assert selection.index == 0 and selection.scores == (0.0,) and selection.samples == 2
    assert seen == [0]

@pytest.mark.parametrize("reference", [False, True])
def test_normalized_evidence_distinguishes_complete_and_unary_shapes(
        reference: bool, monkeypatch: pytest.MonkeyPatch) -> None:
    if reference:
        monkeypatch.setattr(priors, "_NATIVE", None)
        monkeypatch.setattr(decoding, "_NATIVE", None)
    complete = priors.complete_prior(3)
    broad = priors.height_prior(2)
    assert complete is not None
    base = np.log(np.full((3, 3), 1 / 3))
    for selected in ((2, 0, 0), (1, 1, 0)):
        rows = np.full((3, 3), -np.inf)
        for k, a in enumerate(selected):
            rows[k, a] = 0.0
        narrow_evidence = complete.log_evidence(rows, base)
        broad_evidence = broad.log_evidence(rows, base)
        if selected[0] == 2:
            # Same reading mass, but conditioning on the smaller support matters.
            assert narrow_evidence - broad_evidence == pytest.approx(np.log(2))
        else:
            assert narrow_evidence == -np.inf
            assert np.isfinite(broad_evidence)

def test_native_prior_evidence_does_not_decode_unused_outputs(
        monkeypatch: pytest.MonkeyPatch) -> None:
    if getattr(priors._NATIVE, "prior_normalizer", None) is None:
        pytest.skip("native prior normalizer is not built")
    prior = priors.height_prior(3)
    rng = np.random.default_rng(101)
    for size in (1, 2, 7, 8, 15, 16):
        rows = np.log(rng.dirichlet(np.ones(3), size=size))
        decoded = prior.decode(rows)
        expected = -np.inf if decoded is None else decoded.log_z
        assert prior.log_normalizer(rows) == expected
    assert prior.log_normalizer(np.empty((0, 3))) == -np.inf
    assert prior.log_normalizer(np.full((2, 3), -np.inf)) == -np.inf

    def no_decode(*args: Any) -> Any:
        raise AssertionError("evidence must not compute maxima or marginals")

    monkeypatch.setattr(priors.ArityPrior, "decode", no_decode)
    rows = np.log(np.full((3, 3), 1 / 3))
    assert prior.log_evidence(rows, rows) == 0.0

@pytest.mark.parametrize("reference", [False, True])
def test_unlabeled_prior_selection_changes_with_shape_family(
        reference: bool, monkeypatch: pytest.MonkeyPatch) -> None:
    if reference:
        monkeypatch.setattr(priors, "_NATIVE", None)
        monkeypatch.setattr(decoding, "_NATIVE", None)
    candidates = [priors.format_prior, lambda length: priors.height_prior(2),
                  priors.complete_prior]
    base = np.log(np.full(3, 1 / 3))
    for shape, winner in (((2, 0, 0), 2), ((1, 1, 0), 0)):
        rows = np.full((3, 3), -np.inf)
        for k, a in enumerate(shape):
            rows[k, a] = 0.0
        selected = priors.select_prior(candidates, iter([rows, rows]), base)
        assert selected.index == winner and selected.samples == 2
        assert selected.scores[0] == selected.scores[1]  # Exact ties keep declared order.
        for i, candidate in enumerate(candidates):
            expected = 2 * candidate(3).log_evidence(rows, np.broadcast_to(base, rows.shape))
            assert selected.scores[i] == expected
        parsed = decode(rows)
        prior = priors.format_prior(3).decode(rows)
        assert prior is not None and parsed is not None
        assert prior.log_z == parsed.log_z and prior.arities == parsed.arities

def test_prior_selection_rejects_missing_or_incompatible_evidence() -> None:
    rows = np.log(np.full((3, 3), 1 / 3))
    base = rows[0]
    for candidates, readings in (([], [rows]), ([priors.complete_prior], []),
                                  ([lambda length: None], [rows])):
        with pytest.raises(ValueError):
            priors.select_prior(candidates, readings, base)
    selected = priors.select_prior([lambda length: None, priors.format_prior], [rows], base)
    assert selected.index == 1 and selected.scores[0] == -np.inf
    with pytest.raises(ValueError):
        priors.select_prior([priors.format_prior], [np.zeros((3, 3))], base)
    wrong = priors.ArityPrior((2, 1, 0), np.zeros((1, 3), dtype=np.int64),
                                np.zeros((1, 3)), np.zeros(1))
    with pytest.raises(ValueError, match="alphabet"):
        priors.select_prior([lambda length: wrong], [rows], base)


@pytest.mark.parametrize("reference", [False, True])
def test_evidence_cancels_overflowed_base_normalizer(
        reference: bool, monkeypatch: pytest.MonkeyPatch) -> None:
    if reference:
        monkeypatch.setattr(priors, "_NATIVE", None)
    extreme = priors.ArityPrior((0, 1, 2), np.zeros((1, 3), dtype=np.int64),
                                np.full((1, 3), 1e308), np.zeros(1))
    rows = np.log(np.full((2, 3), 1 / 3))
    assert extreme.log_evidence(rows, rows) == pytest.approx(0.0)
    selection = priors.select_prior([lambda length: extreme], [rows], rows[0])
    assert selection.scores == pytest.approx((0.0,))
    with pytest.raises(ValueError, match="normalizer.*finite"):
        extreme.log_normalizer(rows)

def test_priority_score_comparison_handles_overflowing_gap() -> None:
    assert not priors._within_score_error(1e308, -1e308, 9e307)
    assert priors._within_score_error(1e308, -1e308, 1e308)
    assert not priors._within_score_error(1.0, -(2.0**-54), 0.5)
    assert priors._within_score_error(1.0, 2.0**-54, 0.5)


@pytest.mark.parametrize("reference", [False, True])
def test_prior_selection_distinguishes_subnormal_score_gaps(reference, monkeypatch) -> None:
    if reference:
        monkeypatch.setattr(priors, "_NATIVE", None)
    alphabet = (0, 1, 2)
    base = np.array([0.0, -745.0, -745.0])
    reading = np.array([[0.0, -743.5, -746.0]])
    weak = priors.ArityPrior(alphabet, np.array([[0, -1, 0]]), np.zeros((1, 3)), np.zeros(1))
    strong = priors.ArityPrior(alphabet, np.array([[0, 0, -1]]), np.zeros((1, 3)), np.zeros(1))
    least = math.nextafter(0.0, 1.0)
    result = priors.select_prior([lambda _: weak, lambda _: strong], [reading], base,
                                 alphabet=alphabet, score_error=least)
    assert result.scores == (-least, 2 * least)
    assert result.index == 1


@pytest.mark.parametrize("reference", [False, True])
def test_prior_selection_rejects_lost_evidence_contribution(reference, monkeypatch) -> None:
    if reference:
        monkeypatch.setattr(priors, "_NATIVE", None)
    prior = priors.ArityPrior((0, 1), np.array([[0, -1]]), np.zeros((1, 2)), np.zeros(1))
    base = np.array([-1e7, 0.0])
    large = np.array([[0.0, -np.inf]])
    small = np.array([[-1e7 + 1.5e-8, 0.0]])
    assert prior.log_evidence(small, base[None, :]) > 1.01e-8
    with pytest.raises(ValueError, match="summed evidence.*precision"):
        priors.select_prior([lambda _: prior], [large] * 30 + [small], base, alphabet=(0, 1))


@pytest.mark.parametrize("reference", [False, True])
def test_prior_selection_recovers_repeated_small_evidence(reference, monkeypatch) -> None:
    if reference:
        monkeypatch.setattr(priors, "_NATIVE", None)
    prior = priors.ArityPrior((0, 1), np.array([[0, -1]]), np.zeros((1, 2)), np.zeros(1))
    base = np.array([-1e7, 0.0])
    large = np.array([[0.0, -np.inf]])
    small = np.array([[-1e7 + 1.5e-8, 0.0]])
    contribution = prior.log_evidence(small, base[None, :])
    expected = math.fsum([1e7] * 30 + [contribution] * 4)
    selection = priors.select_prior([lambda _: prior], [large] * 30 + [small] * 4,
                                    base, alphabet=(0, 1))
    assert selection.scores == (expected,)
    assert selection.scores[0] > 3e8
    negative = np.array([[-1.5e7, 0.0]])
    cancelled = priors.select_prior([lambda _: prior],
                                    [large] * 30 + [small] * 4 + [negative] * 60,
                                    base, alphabet=(0, 1))
    assert cancelled.scores == (4 * contribution,)


@pytest.mark.parametrize("reference", [False, True])
def test_prior_selection_prefers_declared_priority_within_supplied_error(
        reference: bool, monkeypatch: pytest.MonkeyPatch) -> None:
    if reference:
        monkeypatch.setattr(priors, "_NATIVE", None)
        monkeypatch.setattr(decoding, "_NATIVE", None)
    rows = np.full((3, 3), -np.inf)
    rows[0, 2] = rows[1, 0] = rows[2, 0] = 0.0
    candidates = [lambda length: None, priors.format_prior, priors.complete_prior]
    base = np.log(np.full(3, 1 / 3))
    empirical = priors.select_prior(candidates, [rows, rows], base)
    assert empirical.index == 2 and empirical.score_error == 0.0
    boundary = empirical.scores[2] / 2 - empirical.scores[1] / 2
    narrow = priors.select_prior(candidates, [rows, rows], base,
                                  score_error=float(np.nextafter(boundary, 0)))
    broad = priors.select_prior(candidates, [rows, rows], base, score_error=boundary)
    assert narrow.index == 2 and broad.index == 1
    assert broad.scores == empirical.scores and broad.score_error == boundary
    assert empirical.scores[2] <= broad.scores[1] + 2 * boundary + 1e-12
    assert priors.select_prior(candidates, [rows], base, score_error=1e300).index == 1
    for invalid in (-1, np.nan, np.inf):
        with pytest.raises(ValueError, match="score_error"):
            priors.select_prior(candidates, [rows], base, score_error=invalid)

@pytest.mark.parametrize("reference", [False, True])
def test_clipped_prior_selection_derives_uniform_total_score_error(
        reference: bool, monkeypatch: pytest.MonkeyPatch) -> None:
    if reference:
        monkeypatch.setattr(priors, "_NATIVE", None)
        monkeypatch.setattr(decoding, "_NATIVE", None)
    rows = np.full((3, 3), -np.inf)
    rows[0, 1] = rows[1, 1] = rows[2, 0] = 0.0
    base = np.log(np.full(3, 1 / 3))
    candidates = [priors.format_prior, priors.complete_prior]
    small = priors.select_prior(candidates, [rows] * 2, base, score_clip=2, alpha=0.1)
    large = priors.select_prior(candidates, [rows] * 8, base, score_clip=2, alpha=0.1)
    assert small.scores == (4.0, -4.0)  # Zero model evidence is clipped, not undefined.
    assert large.scores == (16.0, -16.0)
    assert small.score_error == pytest.approx(2 * np.sqrt(4 * np.log(40)))
    assert large.score_error / 8 == pytest.approx(small.score_error / 2 / 2)
    assert small.index == large.index == 0
    assert small.score_clip == 2 and small.alpha == 0.1
    for options in ({"score_clip": 2}, {"alpha": 0.1},
                    {"score_clip": -1, "alpha": 0.1},
                    {"score_clip": np.inf, "alpha": 0.1},
                    {"score_clip": 2, "alpha": 0},
                    {"score_clip": 2, "alpha": 0.1, "score_error": 1}):
        with pytest.raises(ValueError):
            priors.select_prior(candidates, [rows], base, **options)
    unavailable = priors.select_prior([lambda length: None], [rows], base,
                                        score_clip=2, alpha=0.1)
    assert unavailable.scores == (-2.0,) and unavailable.index == 0

def test_clipped_prior_selection_bounds_subnormal_error_upward() -> None:
    least = math.nextafter(0.0, 1.0)
    rows = np.array([[0.0]])
    result = priors.select_prior([lambda _: None], [rows], np.array([0.0]),
                                 alphabet=(0,), score_clip=least, alpha=0.9)
    with localcontext() as context:
        context.prec = 100
        alpha = Decimal.from_float(0.9)
        expected = Decimal.from_float(least) * (2 * (Decimal(2) / alpha).ln()).sqrt()
    assert Decimal.from_float(result.score_error) >= expected
    assert result.score_error > least


@pytest.mark.parametrize("clip,alpha", [
    (math.nextafter(0.0, 1.0), math.nextafter(0.0, 1.0)),
    (1e-200, math.nextafter(1.0, 0.0)),
    (1e300, 1e-300),
    (1e-307, 1e-320),
])
def test_clipped_prior_error_bound_covers_high_precision_extremes(clip, alpha) -> None:
    result = priors.select_prior([lambda _: None], [np.array([[0.0]])], np.array([0.0]),
                                 alphabet=(0,), score_clip=clip, alpha=alpha)
    with localcontext() as context:
        context.prec = 120
        exact = Decimal.from_float(clip) * (2 * (Decimal(2) / Decimal.from_float(alpha)).ln()).sqrt()
    assert Decimal.from_float(result.score_error) >= exact


def test_clipped_prior_error_bound_rejects_unrepresentable_result() -> None:
    with pytest.raises(ValueError, match="derived score error overflow"):
        priors.select_prior([lambda _: None], [np.array([[0.0]])], np.array([0.0]),
                            alphabet=(0,), score_clip=1e308, alpha=0.1)


def test_logic_prior_fit_consumes_texts_with_separate_calibration_labels() -> None:
    from nca.domains.boolean.logic import choose_prior

    class Reader:
        seen: list[str] = []

        def observe(self, word: str) -> str:
            self.seen.append(word)
            return word

        def distribution(self, word: str, decision: Decision) -> torch.Tensor:
            assert decision == ARITY_DECISION
            return torch.tensor([0.0, 1.0, 0.0] if word == "not" else [1.0, 0.0, 0.0])

    reader = Reader()
    selected = choose_prior(reader, np.arange(6), iter(["not not true", "not not false"]),
                            height=2, score_clip=2, alpha=0.1)
    assert selected.index == 0 and selected.samples == 2
    assert selected.scores == (4.0, 4.0, -4.0)
    assert reader.seen == ["not", "not", "true", "not", "not", "false"]
    assert selected.score_clip == 2 and selected.alpha == 0.1

def test_auto_prior_is_fixed_before_deployment_audit(
        monkeypatch: pytest.MonkeyPatch) -> None:
    import sys
    from types import SimpleNamespace
    from nca.domains.boolean import logic

    phases: list[str] = []
    datasets: list[tuple[str, int, float]] = []
    original_dataset = logic.FormulaDataset

    def dataset(*args: Any, **kwargs: Any) -> FormulaDataset:
        result = original_dataset(*args, **kwargs)
        datasets.append((result.split, result.seed, result.early_leaf))
        return result

    monkeypatch.setattr(logic, "FormulaDataset", dataset)
    monkeypatch.setattr(sys, "argv", ["logic", "--prior", "auto", "--prior-height", "1",
        "--prior-fit", "2", "--calibration", "1", "--samples", "1", "--depths", "0",
        "--shift", "0.2", "--account", "correction", "--draws", "2", "--early-leaf", "0.25"])
    monkeypatch.setattr(logic, "library", lambda *args, **kwargs: [
        SimpleNamespace(prior=kwargs.get("prior"))])
    monkeypatch.setattr(logic, "plan_stable", lambda modules, available, target: modules[0])
    monkeypatch.setattr(logic, "build_ladders", lambda *args: {
        logic.WORD_DISTRIBUTION: [Rung(EditReader())]})

    def choose(rung: Rung, labels: np.ndarray, texts: Any, *args: Any) -> Any:
        phases.append("select")
        assert len(list(texts)) == 2 and len(labels) > 0
        return priors.PriorSelection(2, (0.0, 1.0, 2.0), 2, 1.0, 100.0, 0.1)

    def audit(route: Any, ladders: Any, args: Any) -> None:
        phases.append("audit")
        assert route.prior is priors.complete_prior
        assert args.draws == 2

    monkeypatch.setattr(logic, "choose_prior", choose)
    monkeypatch.setattr(logic, "shifted", audit)
    logic.main()
    assert phases == ["select", "audit"]
    assert datasets == [("validation", 0, 0.0), ("validation", 10000, 0.25),
                        ("test", 0, 0.25)]

@pytest.mark.parametrize("reference", [False, True])
def test_prior_selection_caches_fixed_base_normalizers_per_length(
        reference: bool, monkeypatch: pytest.MonkeyPatch) -> None:
    if reference:
        monkeypatch.setattr(priors, "_NATIVE", None)
        monkeypatch.setattr(decoding, "_NATIVE", None)
    base = np.log(np.full(3, 1 / 3))
    providers = [priors.format_prior, lambda length: priors.height_prior(2),
                 priors.complete_prior]
    observations = []
    for shape in ((1, 0), (2, 0, 0), (1, 0), (2, 0, 0)):
        rows = np.full((len(shape), 3), -np.inf)
        for k, a in enumerate(shape):
            rows[k, a] = 0.0
        observations.append(rows)
    expected = tuple(sum(provider(len(rows)).log_evidence(
        rows, np.broadcast_to(base, rows.shape)) for rows in observations) for provider in providers)
    calls = {"base": 0, "observed": 0}
    original = priors.ArityPrior.log_normalizer

    def counted(prior: priors.ArityPrior, rows: np.ndarray) -> float:
        calls["base" if np.all(rows == base) else "observed"] += 1
        return original(prior, rows)

    monkeypatch.setattr(priors.ArityPrior, "log_normalizer", counted)
    selected = priors.select_prior(providers, observations, base)
    assert selected.scores == expected
    assert calls == {"base": 6, "observed": 12}
    # Cache inputs are owned by the selection even if a producer reuses caller buffers.
    def stream() -> Any:
        yield observations[0]
        base[:] = np.log([0.2, 0.3, 0.5])
        providers.reverse()
        yield observations[0]

    original_base = np.log(np.full(3, 1 / 3))
    scores = tuple(2 * provider(2).log_evidence(
        observations[0], np.broadcast_to(original_base, (2, 3))) for provider in providers)
    assert priors.select_prior(providers, stream(), base).scores == scores


def test_native_row_validation_falls_back_at_normalization_boundary() -> None:
    native = getattr(priors._NATIVE, "normalized_rows_fast", None)
    if native is None:
        pytest.skip("native validation unavailable")
    base = np.array([np.log(0.5), np.log(0.5), -np.inf])
    valid = base.reshape(1, -1).copy()
    assert native(valid.reshape(-1), base)
    for delta in (0.0, 0.8e-12, 0.95e-12, 1.05e-12, 2e-12):
        with np.errstate(divide="ignore"):
            rows = np.log(np.array([[0.5, 0.5 - delta, 0.0]]))
        accepted = bool(np.allclose(np.exp(rows).sum(axis=1), 1.0, rtol=0, atol=1e-12))
        if not accepted:
            assert not native(rows.reshape(-1), base)
    unsupported = np.log(np.array([[0.4, 0.4, 0.2]]))
    assert not native(unsupported.reshape(-1), base)
    assert not native(np.array([np.nan, 0.0, -np.inf]), base)
    rng = np.random.default_rng(2715)
    for width in (1, 2, 3):
        shared_base = np.log(np.full(width, 1 / width))
        for _ in range(200):
            rows = np.log(rng.dirichlet(np.ones(width), size=5))
            assert native(rows.reshape(-1), shared_base)
            assert np.allclose(np.exp(rows).sum(axis=1), 1.0, rtol=0, atol=1e-12)


@pytest.mark.parametrize("reference", [False, True])
def test_selection_rejects_rows_outside_base_support(
        reference: bool, monkeypatch: pytest.MonkeyPatch) -> None:
    if reference:
        monkeypatch.setattr(priors, "_NATIVE", None)
    base = np.array([np.log(0.5), np.log(0.5), -np.inf])
    rows = np.tile(np.log([0.4, 0.4, 0.2]), (3, 1))
    with pytest.raises(ValueError, match="supported by the shared base"):
        priors.select_prior([priors.format_prior], [rows], base)


@pytest.mark.parametrize("reference", [False, True])
@pytest.mark.parametrize("layout", ["contiguous", "transposed", "strided"])
def test_prior_log_weight_validation_preserves_edge_cases(
        reference: bool, layout: str, monkeypatch: pytest.MonkeyPatch) -> None:
    if reference:
        monkeypatch.setattr(priors, "_NATIVE", None)
    prior = priors.height_prior(2)
    assert prior is not None
    values = np.array([[0.0, -np.inf, -1e300], [1e300, -0.0, -2.0]])
    def arrange(rows: np.ndarray) -> np.ndarray:
        if layout == "transposed":
            return np.array(rows.T, order="C").T
        if layout == "strided":
            expanded = np.repeat(rows, 2, axis=1)
            return expanded[:, ::2]
        return rows.copy()
    assert np.array_equal(prior._rows(arrange(values)), values)
    for bad in (np.nan, np.inf):
        invalid = values.copy()
        invalid[1, 2] = bad
        with pytest.raises(ValueError, match="finite or -inf"):
            prior._rows(arrange(invalid))

@pytest.mark.parametrize("reference", [False, True])
def test_bounded_selection_scores_unavailable_lengths_without_losing_the_batch(
        reference: bool, monkeypatch: pytest.MonkeyPatch) -> None:
    if reference:
        monkeypatch.setattr(priors, "_NATIVE", None)
        monkeypatch.setattr(decoding, "_NATIVE", None)
    seen: list[int] = []

    def partial(length: int) -> priors.ArityPrior | None:
        seen.append(length)
        return priors.complete_prior(length)

    shapes = [(2, 0, 0), (1, 1, 1, 1, 1, 0), (1, 1, 1, 1, 1, 0)]
    rows = []
    for shape in shapes:
        q = np.full((len(shape), 3), -np.inf)
        for k, a in enumerate(shape):
            q[k, a] = 0.0
        rows.append(q)
    base = np.log(np.full(3, 1 / 3))
    result = priors.select_prior([priors.format_prior, partial], rows, base,
                                   score_clip=4, alpha=0.1)
    first = priors.complete_prior(3).log_evidence(rows[0], np.broadcast_to(base, (3, 3)))
    assert result.scores[1] == pytest.approx(first - 8)
    assert seen == [3, 6]  # Cached absence, with a penalty for each absent observation.
    reversed_result = priors.select_prior([priors.format_prior, partial], reversed(rows), base,
                                            score_clip=4, alpha=0.1)
    assert reversed_result.scores == pytest.approx(result.scores)
    empty = priors.ArityPrior((0, 1, 2), np.full((1, 3), -1),
                                np.zeros((1, 3)), np.array([-np.inf]))
    with pytest.raises(ValueError, match="zero mass"):
        priors.select_prior([lambda length: empty], rows, base, score_clip=4, alpha=0.1)


@pytest.mark.parametrize("reference", [False, True])
def test_provider_mutation_cannot_change_the_current_reading(
        reference: bool, monkeypatch: pytest.MonkeyPatch) -> None:
    if reference:
        monkeypatch.setattr(priors, "_NATIVE", None)
    rows = np.log(np.full((3, 3), 1 / 3))
    base = np.log(np.full(3, 1 / 3))

    def provider(length: int) -> priors.ArityPrior:
        rows[0, 0] = np.nan
        return priors.height_prior(2)

    result = priors.select_prior([lambda length: priors.height_prior(2), provider], [rows], base)
    assert result.scores[0] == pytest.approx(result.scores[1])
    assert np.isnan(rows[0, 0])
