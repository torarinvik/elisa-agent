from typing import Any

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


@pytest.mark.parametrize("use_prior", [False, True])
def test_partition_cache_tracks_readings_selected_arities_and_prior(
        use_prior: bool, monkeypatch: pytest.MonkeyPatch) -> None:
    from nca.ladder import Distribution
    from nca.modules.words import CorrectionState

    rng = np.random.default_rng(557)
    readings = rng.dirichlet(np.ones(len(VOCABULARY)), size=3)
    masses = rng.dirichlet(np.ones(3), size=3)
    versions = [0, 0, 0]
    distribution = Distribution(lambda k, d: torch.tensor(masses[k]), versions.__getitem__)
    evaluator = FormulaEvaluator(decode=True, prior=formulas.format_prior if use_prior else None)
    state = CorrectionState()
    original = priors.ArityPrior.partition
    calls = 0
    def partition(prior: priors.ArityPrior, rows: np.ndarray, selected: tuple[int, ...]) -> tuple[float, float]:
        nonlocal calls
        calls += 1
        return original(prior, rows, selected)
    monkeypatch.setattr(priors.ArityPrior, "partition", partition)
    def risk(k: int, d: Decision) -> float:
        return 0.0
    first = evaluator.certificate(readings, risk, distribution, state)
    assert first is not None and calls == 1
    assert evaluator.certificate(readings, risk, distribution, state) == first and calls == 1
    masses[0] = rng.dirichlet(np.ones(3))
    versions[0] += 1
    assert evaluator.certificate(readings, risk, distribution, state) is not None and calls == 2
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
