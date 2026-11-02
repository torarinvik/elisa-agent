from typing import Any
from fractions import Fraction

import numpy as np
import pytest

torch = pytest.importorskip("torch")

from nca import decoding, formulas, priors
from nca.formulas import (ARITY, VOCABULARY, evaluate)
from nca.ladder import Decision
from nca.modules.symbols import BOOLEAN
from nca.modules.words import (ARITY_ORDER, FORMULA_TEXT, EditReader,
                               FormulaEvaluator, Tokenizer)
from nca.planner import plan_stable
from nca.selective import build_ladders, solve


def one_hot(words: list[str]) -> list[tuple[float, ...]]:
    return [tuple(float(w == v) for v in VOCABULARY) for w in words]

@pytest.mark.parametrize("reference", [False, True])
def test_prior_evaluator_selection_and_account_use_same_structural_prior(
        reference: bool, monkeypatch: pytest.MonkeyPatch) -> None:
    if reference:
        monkeypatch.setattr(formulas, "_NATIVE", None)
        monkeypatch.setattr(priors, "_NATIVE", None)
        monkeypatch.setattr(decoding, "_NATIVE", None)
    rng = np.random.default_rng(71)
    evaluator = FormulaEvaluator(decode=True, short_circuit=False, prior=formulas.complete_prior)
    session = evaluator.certificate_session()
    readings = rng.dirichlet(np.ones(len(VOCABULARY)), size=9)
    calibrated = rng.dirichlet(np.ones(3), size=9)
    prior = formulas.complete_prior(9)
    assert prior is not None

    def distribution(k: int, decision: Decision) -> torch.Tensor:
        return torch.tensor(calibrated[k])

    for _ in range(10):
        readings[int(rng.integers(9))] = rng.dirichlet(np.ones(len(VOCABULARY)))
        calibrated[int(rng.integers(9))] = rng.dirichlet(np.ones(3))
        words = evaluator.words(readings)
        selected = tuple(ARITY[VOCABULARY.index(w)] for w in words)
        assert prior.log_weight(selected) == 0.0
        posterior = prior.decode(np.log(calibrated))
        assert posterior is not None
        expected = posterior.risk(np.log(calibrated), ARITY_ORDER, selected) + 0.009
        account = session(readings, lambda k, d: 0.001, distribution)
        fresh = evaluator.certificate(readings, lambda k, d: 0.001, distribution)
        assert account is not None and fresh is not None
        assert sum(account.values()) == pytest.approx(expected, abs=1e-12)
        assert account == pytest.approx(fresh)
        assert evaluator.invoke(readings) == evaluate(words)
    assert evaluator.invoke(readings[:6]) is None
    assert evaluator.certificate(readings[:6], lambda k, d: 0.001, distribution) is None
    with pytest.raises(ValueError):
        FormulaEvaluator(prior=formulas.complete_prior)
    with pytest.raises(ValueError):
        FormulaEvaluator(decode=True, band_slack=1e-4, prior=formulas.complete_prior)


@pytest.mark.parametrize("reference", [False, True])
@pytest.mark.parametrize("scale", [1.0, np.exp(-1.0)])
def test_prior_evaluator_retains_tiny_risk_with_and_without_session(
        reference: bool, scale: float, monkeypatch: pytest.MonkeyPatch) -> None:
    if reference:
        monkeypatch.setattr(priors, "_NATIVE", None)
    prior = priors.ArityPrior((0, 1, 2), np.array([[0, 0, 0]]),
                              np.zeros((1, 3)), np.zeros(1))
    evaluator = FormulaEvaluator(decode=True, short_circuit=False, prior=lambda length: prior)
    readings = one_hot(["true"])
    def distribution(k: int, decision: Decision) -> torch.Tensor:
        return torch.tensor([scale, scale * np.exp(-40.0), 0.0], dtype=torch.float64)
    expected = np.exp(-40.0)
    fresh = evaluator.certificate(readings, lambda k, d: 0.0, distribution)
    session = evaluator.certificate_session()
    first = session(readings, lambda k, d: 0.0, distribution)
    again = session(readings, lambda k, d: 0.0, distribution)
    for account in (fresh, first, again):
        assert account is not None
        assert sum(account.values()) == pytest.approx(expected, rel=1e-14)


@pytest.mark.parametrize("reference", [False, True])
def test_format_evaluator_retains_tiny_risk_with_and_without_session(
        reference: bool, monkeypatch: pytest.MonkeyPatch) -> None:
    if reference:
        monkeypatch.setattr(priors, "_NATIVE", None)
        monkeypatch.setattr(decoding, "_NATIVE", None)
    evaluator = FormulaEvaluator(decode=True, short_circuit=False)
    readings = one_hot(["and", "true", "true"])
    masses = np.array([[0.0, np.exp(-40.0), 1.0], [1.0, 1.0, 0.0],
                       [np.exp(-1.0), 0.0, 0.0]])
    def distribution(k: int, decision: Decision) -> torch.Tensor:
        return torch.tensor(masses[k], dtype=torch.float64)
    fresh = evaluator.certificate(readings, lambda k, d: 0.0, distribution)
    session = evaluator.certificate_session()
    cached = session(readings, lambda k, d: 0.0, distribution)
    for account in (fresh, cached):
        assert account is not None
        assert sum(account.values()) == pytest.approx(np.exp(-40.0), rel=1e-14)


@pytest.mark.parametrize("reference", [False, True])
@pytest.mark.parametrize("use_state", [False, True])
def test_corrected_account_retains_tiny_sequence_risk_with_larger_within_risk(
        reference, use_state, monkeypatch) -> None:
    from nca import ladder as ladder_module
    from nca.modules import words as word_module
    from nca.modules.words import CorrectionState

    if reference:
        monkeypatch.setattr(priors, "_NATIVE", None)
        monkeypatch.setattr(decoding, "_NATIVE", None)
        monkeypatch.setattr(ladder_module, "_NATIVE", None)
        monkeypatch.setattr(word_module, "_NATIVE", None)
    logs = np.array([[-np.inf, 0.0, -40.0], [np.log(0.5), np.log(0.5), -np.inf],
                     [0.0, -np.inf, -np.inf]])
    probabilities = torch.tensor(np.exp(logs), dtype=torch.float64)
    actual_logs = probabilities.log().numpy()
    sequence_risk = priors.format_sequence_risk(actual_logs, (0, 1, 2), (1, 1, 0))
    evaluator = FormulaEvaluator(decode=True, short_circuit=False)
    account = evaluator.corrected(["not", "not", "true"], [[1], [2], []],
                                  lambda k, d: 0.5, lambda k, d: probabilities[k],
                                  CorrectionState() if use_state else None)
    assert account is not None and sequence_risk > 0
    excess = sum(Fraction.from_float(value) - Fraction(1, 2) for value in account.values())
    assert excess >= Fraction.from_float(sequence_risk)


@pytest.mark.parametrize("use_prior", [False, True])
def test_partition_cache_tracks_readings_selected_arities_and_prior(
        use_prior: bool, monkeypatch: pytest.MonkeyPatch) -> None:
    from nca.ladder import Distribution
    from nca.modules.words import CorrectionState
    from nca.partition import PartitionCursor

    rng = np.random.default_rng(557)
    readings = rng.dirichlet(np.ones(len(VOCABULARY)), size=3)
    masses = rng.dirichlet(np.ones(3), size=3)
    versions = [0, 0, 0]
    distribution = Distribution(lambda k, d: torch.tensor(masses[k]), versions.__getitem__)
    evaluator = FormulaEvaluator(decode=True, prior=formulas.format_prior if use_prior else None)
    state = CorrectionState()
    original = PartitionCursor.partition
    calls = 0
    def partition(cursor: PartitionCursor, rows: np.ndarray, selected: tuple[int, ...]) -> tuple[float, float]:
        nonlocal calls
        calls += 1
        return original(cursor, rows, selected)
    monkeypatch.setattr(PartitionCursor, "partition", partition)
    def risk(k: int, d: Decision) -> float:
        return 0.0
    first = evaluator.certificate(readings, risk, distribution, state)
    assert first is not None and calls == 1
    cached_rows = state.prior_log_probs
    assert evaluator.certificate(readings, risk, distribution, state) == first and calls == 1
    if use_prior:
        assert state.prior_log_probs is cached_rows
    masses[0] = rng.dirichlet(np.ones(3))
    versions[0] += 1
    assert evaluator.certificate(readings, risk, distribution, state) is not None and calls == 2
    if use_prior:
        assert state.prior_log_probs is not cached_rows
    # The cache also depends on the selected sequence and prior identity.
    selected = state.risk_arities
    assert selected is not None
    changed = tuple((a + 1) % 3 for a in selected)
    state.cached_risk(state.risk_prior, changed, lambda: 0.25)
    assert state.cached_risk(state.risk_prior, changed, lambda: 0.5) == 0.25
    assert state.cached_risk(priors.format_prior(1), changed, lambda: 0.5) == 0.5
    def unversioned(k: int, d: Decision) -> torch.Tensor:
        return torch.tensor(masses[k])
    state = CorrectionState()
    before = calls
    assert evaluator.certificate(readings, risk, unversioned, state) is not None
    assert evaluator.certificate(readings, risk, unversioned, state) is not None
    assert calls == before + 2


def test_format_session_reuses_unchanged_normalizer_check(monkeypatch: pytest.MonkeyPatch) -> None:
    from nca.ladder import Distribution
    from nca.modules.words import CorrectionState

    original = decoding.Split.scores
    state = CorrectionState()
    calls = 0

    def scores(split: decoding.Split, k: int, row: np.ndarray) -> tuple[float, float]:
        nonlocal calls
        if split is state.cursor:
            calls += 1
        return original(split, k, row)

    monkeypatch.setattr(decoding.Split, "scores", scores)
    readings = one_hot(["and", "true", "true"])
    masses = np.array([[.1, .3, .6], [.5, .4, .1], [.8, .1, .1]])
    versions = [0, 0, 0]
    distribution = Distribution(lambda k, d: torch.tensor(masses[k]), versions.__getitem__)
    evaluator = FormulaEvaluator(decode=True, short_circuit=False)
    risk = lambda k, d: 0.0
    first = evaluator.certificate(readings, risk, distribution, state)
    assert first is not None
    before = calls
    assert evaluator.certificate(readings, risk, distribution, state) == first
    assert calls == before
    masses[1] = [.4, .5, .1]
    versions[1] += 1
    updated = evaluator.certificate(readings, risk, distribution, state)
    assert updated is not None and calls > before
    fresh = evaluator.certificate(readings, risk, distribution)
    assert fresh is not None
    assert sum(updated.values()) == pytest.approx(sum(fresh.values()))


@pytest.mark.parametrize("use_prior", [False, True])
def test_correction_session_invalidates_when_distribution_source_changes(use_prior: bool) -> None:
    from nca.ladder import Distribution
    from nca.modules.words import CorrectionState

    evaluator = FormulaEvaluator(decode=True, short_circuit=False,
                                 prior=formulas.format_prior if use_prior else None)
    readings = one_hot(["and", "true", "true"])
    first = np.array([[.1, .3, .6], [.5, .4, .1], [.8, .1, .1]])
    second = np.array([[.3, .1, .6], [.2, .7, .1], [.5, .2, .3]])
    old = Distribution(lambda k, d: torch.tensor(first[k]), lambda k: 0)
    new = Distribution(lambda k, d: torch.tensor(second[k]), lambda k: 0)
    def risk(k: int, d: Decision) -> float:
        return 0.0
    state = CorrectionState()
    old_account = evaluator.certificate(readings, risk, old, state)
    switched = evaluator.certificate(readings, risk, new, state)
    fresh = evaluator.certificate(readings, risk, new)
    assert old_account is not None and switched is not None and fresh is not None
    assert sum(old_account.values()) != pytest.approx(sum(fresh.values()))
    assert switched == pytest.approx(fresh)


@pytest.mark.parametrize("use_prior", [False, True])
def test_correction_session_invalidates_when_risk_callback_changes(use_prior: bool) -> None:
    from nca.ladder import Distribution
    from nca.modules.words import CorrectionState

    evaluator = FormulaEvaluator(decode=True, short_circuit=False,
                                 prior=formulas.format_prior if use_prior else None)
    readings = one_hot(["and", "true", "false"])
    masses = np.tile([0.6, 0.25, 0.15], (3, 1))
    distribution = Distribution(lambda k, d: torch.tensor(masses[k]), lambda k: 0)
    def low(k: int, d: Decision) -> float:
        return 0.01
    def high(k: int, d: Decision) -> float:
        return 0.2
    state = CorrectionState()
    first = evaluator.certificate(readings, low, distribution, state)
    switched = evaluator.certificate(readings, high, distribution, state)
    fresh = evaluator.certificate(readings, high, distribution)
    assert first is not None and switched is not None and fresh is not None
    assert sum(first.values()) < sum(fresh.values())
    assert switched == pytest.approx(fresh)


@pytest.mark.parametrize("mode", ["format", "prior", "banded"])
def test_correction_state_resets_when_formula_length_changes(mode: str) -> None:
    from nca.ladder import Distribution
    from nca.modules.words import CorrectionState

    evaluator = FormulaEvaluator(decode=True, short_circuit=False,
                                 prior=formulas.format_prior if mode == "prior" else None,
                                 band_slack=0.01 if mode == "banded" else None)
    masses = np.tile([0.6, 0.25, 0.15], (5, 1))
    distribution = Distribution(lambda k, d: torch.tensor(masses[k]), lambda k: 0)
    def risk(k: int, d: Decision) -> float:
        return 0.0
    state = CorrectionState()
    for words in (["and", "true", "false"], ["and", "not", "true", "not", "false"],
                  ["true"], ["and", "true", "false"]):
        readings = one_hot(words)
        actual = evaluator.certificate(readings, risk, distribution, state)
        expected = evaluator.certificate(readings, risk, distribution, CorrectionState())
        assert actual is not None and expected is not None
        assert actual == pytest.approx(expected)
        assert state.length == len(words)

def test_complete_tree_prior_expert_is_planned_and_executed_independently() -> None:
    from nca.abi import Message
    from nca.modules.words import ARITY_PRIOR, FORMULA_LENGTH, CompleteTreePrior
    from nca.runtime import execute
    from nca.workspace import Workspace

    expert = CompleteTreePrior()
    evaluator = FormulaEvaluator(decode=True, prior=expert.invoke)
    unsupported = one_hot("and or true false not false".split())
    assert evaluator.invoke(unsupported) is None
    assert plan_stable([], (FORMULA_LENGTH,), ARITY_PRIOR) is None
    route = plan_stable([expert], (FORMULA_LENGTH,), ARITY_PRIOR)
    assert route is not None
    assert plan_stable([expert], (FORMULA_TEXT,), ARITY_PRIOR) is None
    for size in (1, 3, 9, 6, 12):
        workspace = Workspace()
        result = execute(route, {FORMULA_LENGTH: Message(FORMULA_LENGTH, size, "input")},
                         workspace, budget=1)
        assert result.type_id == ARITY_PRIOR
        assert isinstance(result.payload, formulas.ArityPrior)
        assert workspace.spent == expert.manifest.cost
        if size in (6, 12):
            assert result.payload.decode(np.zeros((size, 3))) is None
        else:
            assert result.payload is formulas.complete_prior(size)

def test_typed_prior_slot_matches_provider_in_runtime_and_refinement() -> None:
    from nca.abi import Message, seq_type
    from nca.modules.words import (CompleteTreePrior, PriorFormulaEvaluator,
                                   WORD_DISTRIBUTION)
    from nca.runtime import execute
    from nca.selective import solve_many
    from nca.workspace import Workspace

    class CountingPrior(CompleteTreePrior):
        calls = 0

        def invoke(self, length: int) -> formulas.ArityPrior:
            self.calls += 1
            return super().invoke(length)

    prior = CountingPrior()
    consumer = PriorFormulaEvaluator()
    assert plan_stable([consumer], (seq_type(WORD_DISTRIBUTION),), BOOLEAN) is None
    direct = plan_stable([prior, consumer], (seq_type(WORD_DISTRIBUTION),), BOOLEAN)
    assert direct is not None
    from nca.planner import Apply
    from nca.selective import bind_consumer

    class UnboundConsumer:
        manifest = consumer.manifest

    assert isinstance(direct, Apply)
    with pytest.raises(ValueError, match="bind_slots"):
        bind_consumer(Apply(UnboundConsumer(), direct.args, direct.slots))
    readings = one_hot("and true not false".split())
    result = execute(direct, {seq_type(WORD_DISTRIBUTION): Message(
        seq_type(WORD_DISTRIBUTION), readings, "input")}, Workspace(), budget=2)
    assert result.payload is True and prior.calls == 1
    modules = [Tokenizer(), EditReader(), prior, consumer]
    route = plan_stable(modules, (FORMULA_TEXT,), BOOLEAN)
    provider = plan_stable([Tokenizer(), EditReader(), FormulaEvaluator(
        decode=True, prior=formulas.complete_prior)], (FORMULA_TEXT,), BOOLEAN)
    assert route is not None and provider is not None
    words = list(VOCABULARY) * 10
    ladders = build_ladders(modules, route, {WORD_DISTRIBUTION: (
        words, torch.tensor([VOCABULARY.index(w) for w in words]))})
    for text in ("and true not flse", "and tru flse", "and or true false not false"):
        prior.calls = 0
        typed_trace, provider_trace = [], []
        typed = solve(route, ladders, text, 0.05, trace=typed_trace)
        expected = solve(provider, ladders, text, 0.05, trace=provider_trace)
        assert typed == expected and typed_trace == provider_trace
        assert prior.calls == 1
        prior.calls = 0
        assert solve_many(route, ladders, text, [0.05, 0.01]) == solve_many(
            provider, ladders, text, [0.05, 0.01])
        assert prior.calls == 1


def test_selective_solve_pins_prior_for_certificate_and_answer() -> None:
    from nca.modules.words import WORD_DISTRIBUTION

    calls = []
    def provider(length: int) -> priors.ArityPrior:
        calls.append(length)
        return priors.height_prior(3) if len(calls) % 2 else priors.format_prior(length)

    evaluator = FormulaEvaluator(decode=True, prior=provider)
    modules = [Tokenizer(), EditReader(), evaluator]
    route = plan_stable(modules, (FORMULA_TEXT,), BOOLEAN)
    assert route is not None
    words = list(VOCABULARY) * 10
    ladders = build_ladders(modules, route, {WORD_DISTRIBUTION: (
        words, torch.tensor([VOCABULARY.index(w) for w in words]))})
    solve(route, ladders, "and true false", 1.0)
    assert calls == [3]
    solve(route, ladders, "and true false", 1.0)
    assert calls == [3, 3]

def test_height_expert_fills_evaluator_slot_with_relaxed_support() -> None:
    from nca.abi import Message, seq_type
    from nca.modules.words import HeightBoundedPrior, PriorFormulaEvaluator, WORD_DISTRIBUTION
    from nca.runtime import execute
    from nca.workspace import Workspace

    expert = HeightBoundedPrior(2)
    assert expert.manifest.module_id != HeightBoundedPrior(1).manifest.module_id
    route = plan_stable([expert, PriorFormulaEvaluator()],
                        (seq_type(WORD_DISTRIBUTION),), BOOLEAN)
    assert route is not None
    readings = one_hot("not not true".split())
    result = execute(route, {seq_type(WORD_DISTRIBUTION): Message(
        seq_type(WORD_DISTRIBUTION), readings, "input")}, Workspace(), budget=2)
    assert result.payload is True
    assert expert.invoke(3).log_weight((1, 1, 0)) == 0.0
    assert formulas.complete_prior(3).log_weight((1, 1, 0)) == -np.inf
    assert expert.invoke(8).decode(np.zeros((8, 3))) is None
    assert HeightBoundedPrior(0).invoke(1).log_weight((0,)) == 0.0
    for invalid in (0, -1, 1.5):
        with pytest.raises(ValueError):
            expert.invoke(invalid)

@pytest.mark.parametrize("reference", [False, True])
def test_prior_calibration_cache_tracks_revisions_and_unversioned_calls(
        reference: bool, monkeypatch: pytest.MonkeyPatch) -> None:
    from nca.ladder import Distribution
    from nca.modules.words import CorrectionState

    if reference:
        monkeypatch.setattr(formulas, "_NATIVE", None)
        monkeypatch.setattr(priors, "_NATIVE", None)
        monkeypatch.setattr(decoding, "_NATIVE", None)
    rng = np.random.default_rng(1103)
    readings = rng.dirichlet(np.ones(6), size=9)
    calibrated = rng.dirichlet(np.ones(3), size=9)
    versions = [0] * 9
    seen: list[int] = []

    def masses(k: int, decision: Decision) -> torch.Tensor:
        seen.append(k)
        return torch.tensor(calibrated[k])

    evaluator = FormulaEvaluator(decode=True, prior=formulas.complete_prior)
    distribution = Distribution(masses, versions.__getitem__)
    state = CorrectionState()
    expected_calls = list(range(9))
    previous = None
    for step in range(20):
        if step:
            k = int(rng.integers(9))
            calibrated[k] = rng.dirichlet(np.ones(3))
            versions[k] += 1
            expected_calls = [k]
        seen.clear()
        account = evaluator.certificate(readings, lambda k, d: 0.001, distribution, state)
        assert seen == expected_calls
        fresh = evaluator.certificate(readings, lambda k, d: 0.001, distribution)
        assert account is not None and fresh is not None
        assert sum(account.values()) == pytest.approx(sum(fresh.values()), abs=1e-12)
        assert all(charge >= 0 for charge in account.values())
        if previous is not None:
            assert not np.shares_memory(state.prior_log_probs, previous)
        previous = state.prior_log_probs
        seen.clear()
        assert evaluator.certificate(readings, lambda k, d: 0.001, distribution, state) == account
        assert seen == []
    # An unversioned refresh must not leave a revision-tagged cache reusable.
    calibrated[:] = rng.dirichlet(np.ones(3), size=9)
    seen.clear()
    plain = evaluator.certificate(readings, lambda k, d: 0.001, masses, state)
    assert seen == list(range(9))
    assert plain == pytest.approx(evaluator.certificate(readings, lambda k, d: 0.001, masses))
    calibrated[0] = rng.dirichlet(np.ones(3))
    seen.clear()
    restored = evaluator.certificate(readings, lambda k, d: 0.001, distribution, state)
    assert seen == list(range(9))
    assert restored == pytest.approx(evaluator.certificate(
        readings, lambda k, d: 0.001, distribution))

@pytest.mark.parametrize("reference", [False, True])
def test_prior_account_uses_current_risk_between_marginal_refreshes(
        reference: bool, monkeypatch: pytest.MonkeyPatch) -> None:
    from nca.ladder import Distribution
    from nca.modules.words import CorrectionState

    if reference:
        monkeypatch.setattr(formulas, "_NATIVE", None)
        monkeypatch.setattr(priors, "_NATIVE", None)
        monkeypatch.setattr(decoding, "_NATIVE", None)
    original_decode = formulas.ArityPrior.decode
    calls = 0

    def decode(prior: formulas.ArityPrior, rows: np.ndarray) -> Any:
        nonlocal calls
        calls += 1
        return original_decode(prior, rows)

    monkeypatch.setattr(formulas.ArityPrior, "decode", decode)
    rng = np.random.default_rng(1203)
    readings = rng.dirichlet(np.ones(6), size=9)
    calibrated = rng.dirichlet(np.ones(3), size=9)
    versions = [0] * 9
    distribution = Distribution(lambda k, d: torch.tensor(calibrated[k]), versions.__getitem__)
    evaluator = FormulaEvaluator(decode=True, prior=formulas.complete_prior)
    state = CorrectionState()
    selected = tuple(ARITY[VOCABULARY.index(w)] for w in evaluator.words(readings))
    calls = 0
    original_priorities = None
    for step in range(4):
        if step:
            calibrated[step - 1] = rng.dirichlet(np.ones(3))
            versions[step - 1] += 1
        before = calls
        account = evaluator.certificate(readings, lambda k, d: 0.0, distribution, state)
        assert account is not None
        native_best = getattr(priors._NATIVE, "prior_best", None) is not None
        assert calls - before == int(not native_best) + int(step in (0, 3))
        if step == 0:
            original_priorities = state.priorities
        elif step < 3:
            assert state.priorities is original_priorities
        else:
            assert state.priorities is not original_priorities
        oracle = original_decode(formulas.complete_prior(9), np.log(calibrated))
        assert oracle is not None
        assert sum(account.values()) == pytest.approx(
            oracle.risk(np.log(calibrated), ARITY_ORDER, selected), abs=1e-12)


def test_prior_change_refreshes_allocation_priorities() -> None:
    from nca.ladder import Distribution
    from nca.modules.words import CorrectionState

    rng = np.random.default_rng(1620)
    readings = rng.dirichlet(np.ones(len(VOCABULARY)), size=9)
    calibrated = rng.dirichlet(np.ones(3), size=9)
    distribution = Distribution(lambda k, d: torch.tensor(calibrated[k]), lambda k: 0)
    current = [priors.height_prior(4)]
    evaluator = FormulaEvaluator(decode=True, short_circuit=False, prior=lambda n: current[0])
    state = CorrectionState()
    def risk(k: int, d: Decision) -> float:
        return 0.0
    assert evaluator.certificate(readings, risk, distribution, state) is not None
    previous_priorities = state.priorities
    current[0] = priors.format_prior(9)
    actual = evaluator.certificate(readings, risk, distribution, state)
    fresh = evaluator.certificate(readings, risk, distribution)
    assert actual is not None and fresh is not None
    assert state.priorities is not previous_priorities
    assert actual == pytest.approx(fresh)


@pytest.mark.parametrize("with_state", [False, True])
def test_prior_provider_is_resolved_once_per_certificate(with_state: bool) -> None:
    from nca.modules.words import CorrectionState

    rng = np.random.default_rng(506)
    readings = rng.dirichlet(np.ones(len(VOCABULARY)), size=9)
    calibrated = rng.dirichlet(np.ones(3), size=9)
    first, second = priors.height_prior(4), priors.format_prior(9)
    calls = []
    def provider(length: int) -> priors.ArityPrior:
        calls.append(length)
        return first if len(calls) == 1 else second
    def distribution(k: int, d: Decision) -> torch.Tensor:
        return torch.tensor(calibrated[k])
    def risk(k: int, d: Decision) -> float:
        return 0.0
    evaluator = FormulaEvaluator(decode=True, short_circuit=False, prior=provider)
    expected = FormulaEvaluator(decode=True, short_circuit=False, prior=lambda n: first)
    actual = evaluator.certificate(readings, risk, distribution,
                                   CorrectionState() if with_state else None)
    assert actual is not None
    assert actual == pytest.approx(expected.certificate(readings, risk, distribution))
    assert calls == [9]
    calls.clear()
    assert evaluator.invoke(readings) == expected.invoke(readings)
    assert calls == [9]


def test_priorities_track_prior_when_partition_fails(monkeypatch: pytest.MonkeyPatch) -> None:
    from nca.ladder import Distribution
    from nca.modules.words import CorrectionState
    from nca.partition import PartitionCursor

    rng = np.random.default_rng(2311)
    readings = rng.dirichlet(np.ones(len(VOCABULARY)), size=9)
    calibrated = rng.dirichlet(np.ones(3), size=9)
    distribution = Distribution(lambda k, d: torch.tensor(calibrated[k]), lambda k: 0)
    first_prior = priors.height_prior(4)
    second_prior = priors.format_prior(9)
    current = [first_prior]
    evaluator = FormulaEvaluator(decode=True, short_circuit=False, prior=lambda n: current[0])
    state = CorrectionState()
    def risk(k: int, d: Decision) -> float:
        return 0.0
    first = evaluator.certificate(readings, risk, distribution, state)
    assert first is not None
    original = PartitionCursor.partition
    def partition(cursor: PartitionCursor, rows: np.ndarray,
                  selected: tuple[int, ...]) -> tuple[float, float]:
        if cursor.prior is second_prior:
            raise ValueError("simulated partition failure")
        return original(cursor, rows, selected)
    monkeypatch.setattr(PartitionCursor, "partition", partition)
    current[0] = second_prior
    with pytest.raises(ValueError, match="simulated partition failure"):
        evaluator.certificate(readings, risk, distribution, state)
    assert state.priorities_prior is second_prior and state.risk_prior is first_prior
    current[0] = first_prior
    restored = evaluator.certificate(readings, risk, distribution, state)
    assert state.priorities_prior is first_prior
    assert restored == pytest.approx(first)
