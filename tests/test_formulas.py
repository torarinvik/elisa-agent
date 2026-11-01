import itertools
from dataclasses import dataclass
from typing import Any

import numpy as np
import pytest

torch = pytest.importorskip("torch")

from nca.abi import Contract, Manifest
from nca import decoding, formulas, priors
from nca.formulas import (ARITY, VOCABULARY, FormulaDataset, corrupt, decode,
                          evaluate, formula, parse)
from nca.ladder import Decision, Rung, ladder, refine, risk
from nca.modules.symbols import BOOLEAN
from nca.modules.words import (ARITY_DECISION, ARITY_ORDER, FORMULA_TEXT, READER, EditReader,
                               FormulaEvaluator, Tokenizer, edit_distance)
from nca.planner import plan_stable
from nca.selective import build_ladders, solve


def one_hot(words: list[str]) -> list[tuple[float, ...]]:
    return [tuple(float(w == v) for v in VOCABULARY) for w in words]


def no_distribution(k: int, decision: Decision) -> torch.Tensor:
    raise AssertionError("not needed by this account")


def test_channel_and_prefix_parsing() -> None:
    rng = np.random.default_rng(0)
    assert corrupt("false", 0.0, rng) == "false"
    assert all(corrupt("or", 1.0, rng) for _ in range(200))
    assert evaluate("and or true false not false".split()) is True
    assert evaluate("xor true true".split()) is False
    assert evaluate("and true".split()) is None
    assert evaluate("not true false".split()) is None
    assert parse([2, 0, 1, 0]) == [[1, 2], [], [3], []]
    words = formula(3, rng)
    assert len(words) >= 15 and evaluate(words) is not None
    sample = FormulaDataset("test", 1, 3, 0.1).sample(0)
    assert len(sample.text.split(" ")) == len(sample.words)


def test_edit_distance_counts_transpositions() -> None:
    assert edit_distance("ture", "true") == 1
    assert edit_distance("", "and") == 3
    assert edit_distance("xor", "or") == 1


def test_grouped_risk_takes_the_group_of_the_most_probable_class() -> None:
    reading = torch.tensor([0.4, 0.05, 0.0, 0.35, 0.2, 0.0])
    # "true" is most probable; its arity group {true, false} holds 0.45.
    assert risk(reading, ARITY_DECISION) == pytest.approx(0.55)
    assert risk(reading, ARITY_DECISION) <= risk(reading) + 1e-9
    assert risk(reading, [(3, 4), 0]) == pytest.approx(1 - 0.4 / 0.95)


def test_grouped_decision_gets_its_own_temperature() -> None:
    rung = Rung(EditReader())
    words = ["and", "anf", "or", "nto", "true", "fals"] * 5
    labels = torch.tensor([3, 3, 4, 2, 0, 1] * 5)
    rung.calibrate(words, labels)
    assert 0.0 <= rung.risk(rung.observe("ot"), ARITY_DECISION) <= 1.0
    assert set(rung.temperatures) == {None, ((0, 1), (2,), (3, 4, 5))}


def random_formula(rng: np.random.Generator, depth: int) -> list[str]:
    return formula(depth, rng, xor=0.3, negation=0.3)


def test_certificate_is_sound() -> None:
    """Changing skipped words within their arity group never changes the value."""
    rng = np.random.default_rng(1)
    groups = {c: g for g in ARITY_DECISION for c in g}
    for _ in range(300):
        words = random_formula(rng, int(rng.integers(1, 5)))
        full, shape = rng.random(len(words)), rng.random(len(words))
        children = parse([ARITY[VOCABULARY.index(w)] for w in words])
        assert children is not None
        kept = FormulaEvaluator.evaluated(words, children, full, shape)
        changed = [w if k in kept else VOCABULARY[rng.choice(groups[VOCABULARY.index(w)])]
                   for k, w in enumerate(words)]
        assert evaluate(changed) == evaluate(words)


def certificates(words: list[str], k: int, children: list[list[int]]) -> list[set[int]]:
    """Every valid certificate of the subtree at ``k``, as its evaluated words."""
    kids = children[k]
    if not kids:
        return [{k}]
    if len(kids) == 1:
        return [{k} | c for c in certificates(words, kids[0], children)]
    a, b = kids
    found = [{k} | x | y for x, y in itertools.product(certificates(words, a, children),
                                                       certificates(words, b, children))]
    absorbing = {"and": False, "or": True}.get(words[k])
    for kept in kids:
        if evaluate_at(words, kept, children) == absorbing:
            found += [{k} | c for c in certificates(words, kept, children)]
    return found


def evaluate_at(words: list[str], k: int, children: list[list[int]]) -> bool:
    from nca.formulas import apply

    return apply(words[k], [evaluate_at(words, c, children) for c in children[k]])


def test_certificate_is_least_risk() -> None:
    rng = np.random.default_rng(2)
    for _ in range(100):
        words = random_formula(rng, 3)
        children = parse([ARITY[VOCABULARY.index(w)] for w in words])
        assert children is not None
        full, shape = rng.random(len(words)), rng.random(len(words)) * 0.2

        def weight(k: int, decision: Decision) -> float:
            return float(full[k] if decision is None else shape[k])

        account = FormulaEvaluator().certificate(one_hot(words), weight, no_distribution)
        assert account is not None
        chosen = sum(account.values())
        best = min(sum(full[k] if k in c else shape[k] for k in range(len(words)))
                   for c in certificates(words, 0, children))
        assert chosen == pytest.approx(best)
        static = FormulaEvaluator(short_circuit=False).certificate(one_hot(words), weight,
                                                                  no_distribution)
        assert static is not None
        assert chosen <= sum(static.values()) + 1e-9


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


def test_solve_short_circuits_noisy_formulas() -> None:
    modules = [Tokenizer(), EditReader(), FormulaEvaluator()]
    route = plan_stable(modules, (FORMULA_TEXT,), BOOLEAN)
    assert route is not None
    words = ["and", "or", "true", "false"] * 10
    ladders = build_ladders(modules, route, {READER.output: (words, torch.tensor(
        [VOCABULARY.index(w) for w in words]))})
    text = "and flse or xro true true tru"
    static = plan_stable([Tokenizer(), EditReader(), FormulaEvaluator(short_circuit=False)],
                         (FORMULA_TEXT,), BOOLEAN)
    assert static is not None
    answer = solve(route, ladders, text, delta=1.0)
    assert answer.value is False
    assert answer.bound < solve(static, ladders, text, delta=1.0).bound


def test_one_wrong_arity_never_parses() -> None:
    """``NCA.code_no_single_change``: a single wrong arity is always detected."""
    rng = np.random.default_rng(3)
    for _ in range(300):
        words = random_formula(rng, int(rng.integers(1, 5)))
        k = int(rng.integers(len(words)))
        others = [w for w in VOCABULARY if ARITY[VOCABULARY.index(w)] !=
                  ARITY[VOCABULARY.index(words[k])]]
        assert evaluate([*words[:k], str(rng.choice(others)), *words[k + 1:]]) is None


def test_detection_accounts() -> None:
    words = "and or true false not false".split()
    arity = [0.01, 0.02, 0.0, 0.03, 0.04, 0.0]
    within = [0.1, 0.2, 0.3, 0.4, 0.0, 0.5]

    def risk(k: int, decision: Decision) -> float:
        return arity[k] if decision == ARITY_DECISION else within[k]

    total = sum(arity)
    markov = FormulaEvaluator(detection="markov").certificate(one_hot(words), risk,
                                                              no_distribution)
    pairs = FormulaEvaluator(detection="pairs").certificate(one_hot(words), risk,
                                                            no_distribution)
    assert markov is not None and pairs is not None
    # "and" is true, so both children are evaluated; "or" reads true and keeps
    # its cheaper absorbing child, "true" (within risk 0.3 against 0.4).
    evaluated = within[0] + within[1] + within[2] + within[4] + within[5]
    assert sum(markov.values()) == pytest.approx(evaluated + total / 2)
    e2 = sum(a * b for a, b in itertools.combinations(arity, 2))
    assert sum(pairs.values()) == pytest.approx(evaluated + e2)


def test_floors_bound_every_account() -> None:
    """``FormulaEvaluator.floor`` never exceeds the account it bounds (§22.3),
    whatever the risks of the open words."""
    rng = np.random.default_rng(4)
    for _ in range(200):
        words = random_formula(rng, int(rng.integers(1, 4)))
        n = len(words)
        full, arity = rng.random(n) * 0.2, rng.random(n) * 0.1
        within = rng.random(n) * 0.1
        fixed = frozenset(int(k) for k in np.flatnonzero(rng.random(n) < 0.5))

        def risk(k: int, decision: Decision) -> float:
            if decision is None:
                return float(full[k])
            return float(arity[k] if decision == ARITY_DECISION else within[k])

        for short_circuit, detection in ((False, "none"), (True, "none"), (True, "markov"),
                                         (True, "pairs")):
            evaluator = FormulaEvaluator(short_circuit, detection)
            account = evaluator.certificate(one_hot(words), risk, no_distribution)
            assert account is not None
            assert evaluator.floor(one_hot(words), risk, fixed) <= sum(account.values()) + 1e-12


def test_decoding_agrees_with_parseable_readings() -> None:
    rng = np.random.default_rng(5)
    for _ in range(100):
        words = random_formula(rng, int(rng.integers(1, 4)))
        readings = [tuple(r) for r in rng.dirichlet(np.full(len(VOCABULARY), 0.3), size=len(words))]
        readings = [tuple(0.5 * np.array(r) + 0.5 * np.array(h)) for r, h in
                    zip(readings, one_hot(words))]
        masses = [[sum(r[c] for c in g) for g in ARITY_DECISION] for r in readings]
        per_word = [ARITY_ORDER[int(np.argmax(m))] for m in masses]
        if parse(per_word) is None:
            continue
        decoded = FormulaEvaluator(decode=True).words(readings)
        assert [ARITY[VOCABULARY.index(w)] for w in decoded] == per_word
        assert FormulaEvaluator(decode=True).invoke(readings) == FormulaEvaluator().invoke(readings)


def test_decoding_corrects_a_single_wrong_arity() -> None:
    words = "and or true false not false".split()
    readings = one_hot(words)
    wrong = list(readings[4])
    wrong[VOCABULARY.index("not")], wrong[VOCABULARY.index("or")] = 0.4, 0.6
    readings[4] = tuple(wrong)
    assert FormulaEvaluator().invoke(readings) is None
    assert FormulaEvaluator(decode=True).invoke(readings) == evaluate(words)


def test_correction_account() -> None:
    rng = np.random.default_rng(6)
    words = "and or true false not false".split()
    readings = [tuple(0.6 * np.array(h) + 0.4 * np.array(r)) for h, r in
                zip(one_hot(words), rng.dirichlet(np.ones(len(VOCABULARY)), size=len(words)))]
    within = rng.random(len(words)) * 0.1

    def masses(k: int, decision: Decision) -> torch.Tensor:
        assert decision == ARITY_DECISION
        return torch.tensor([sum(readings[k][c] for c in g) for g in ARITY_DECISION])

    def risk(k: int, decision: Decision) -> float:
        return float(within[k])

    evaluator = FormulaEvaluator(decode=True)
    account = evaluator.certificate(readings, risk, masses)
    assert account is not None
    decoded = evaluator.words(readings)
    log_probs = np.log(np.array([masses(k, ARITY_DECISION).tolist() for k in range(len(words))]))
    posterior = decode(log_probs, ARITY_ORDER)
    assert posterior is not None
    sequence_risk = posterior.risk(log_probs, ARITY_ORDER,
                                   [ARITY[VOCABULARY.index(w)] for w in decoded])
    children = parse([ARITY[VOCABULARY.index(w)] for w in decoded])
    assert children is not None
    kept = FormulaEvaluator.evaluated(decoded, children, within, [0.0] * len(words))
    assert sum(account.values()) == pytest.approx(sequence_risk + sum(within[k] for k in kept))


def test_correction_session_matches_fresh_bound() -> None:
    rng = np.random.default_rng(23)
    words = formula(3, rng)
    readings = np.array(one_hot(words)) * 0.7 + rng.dirichlet(
        np.ones(len(VOCABULARY)), size=len(words)) * 0.3
    evaluator = FormulaEvaluator(decode=True)
    session = evaluator.certificate_session()

    def masses(k: int, decision: Decision) -> torch.Tensor:
        return torch.tensor([sum(readings[k][c] for c in g) for g in ARITY_DECISION])

    def risk(k: int, decision: Decision) -> float:
        return 0.001

    for _ in range(30):
        k = int(rng.integers(len(words)))
        readings[k] = rng.dirichlet(np.ones(len(VOCABULARY)))
        fresh = evaluator.certificate(readings, risk, masses)
        cached = session(readings, risk, masses)
        assert fresh is not None and cached is not None
        assert sum(cached.values()) == pytest.approx(sum(fresh.values()), abs=1e-12)
    # A separate solve must start with a fresh cursor and fresh priorities.
    other = evaluator.certificate_session()(readings, risk, masses)
    assert other == pytest.approx(evaluator.certificate(readings, risk, masses))


def test_correction_revisions_invalidate_calibration_with_equal_scores() -> None:
    from nca.ladder import Distribution

    words = "and true false".split()
    readings = np.array(one_hot(words)) * 0.9 + 0.1 / len(VOCABULARY)
    versions = [0, 0, 0]
    seen: list[int] = []

    def masses(k: int, decision: Decision) -> torch.Tensor:
        seen.append(k)
        row = torch.tensor([sum(readings[k][c] for c in g) for g in ARITY_DECISION])
        return row * 0.7 + 0.1 if versions[k] else row

    def risk(k: int, decision: Decision) -> float:
        return 0.01 if versions[k] else 0.001

    distribution = Distribution(masses, versions.__getitem__)
    evaluator = FormulaEvaluator(decode=True)
    session = evaluator.certificate_session()
    session(readings, risk, distribution)
    assert seen == [0, 1, 2]
    seen.clear()
    session(readings, risk, distribution)
    assert seen == []
    versions[1] += 1
    cached = session(readings, risk, distribution)
    assert seen == [1]
    fresh = evaluator.certificate(readings, risk, distribution)
    assert cached is not None and fresh is not None
    assert sum(cached.values()) == pytest.approx(sum(fresh.values()), abs=1e-12)


@pytest.mark.parametrize("reference", [False, True])
def test_answer_cursor_matches_fresh_words(reference: bool, monkeypatch: pytest.MonkeyPatch) -> None:
    from nca.modules.words import CorrectionState

    if reference:
        monkeypatch.setattr(formulas, "_NATIVE", None)
        monkeypatch.setattr(priors, "_NATIVE", None)
        monkeypatch.setattr(decoding, "_NATIVE", None)
    rng = np.random.default_rng(25)
    evaluator = FormulaEvaluator(decode=True)
    state = CorrectionState()
    readings = rng.dirichlet(np.ones(len(VOCABULARY)), size=35)
    for _ in range(30):
        k = int(rng.integers(len(readings)))
        readings[k] = rng.dirichlet(np.ones(len(VOCABULARY)))
        assert evaluator.words(readings, state) == evaluator.words(readings)


def test_native_certificate_matches_reference_including_ties() -> None:
    from nca.modules import words as word_module

    if getattr(word_module._NATIVE, "certificate", None) is None:
        pytest.skip("native certificate kernel is not built")
    rng = np.random.default_rng(26)
    for depth in range(1, 7):
        for _ in range(20):
            words = formula(depth, rng, xor=0.3)
            kids = parse([ARITY[VOCABULARY.index(w)] for w in words])
            assert kids is not None
            for full, shape in ((rng.random(len(words)), rng.random(len(words))),
                                (np.zeros(len(words)), np.zeros(len(words)))):
                assert FormulaEvaluator.evaluated(words, kids, full, shape) == (
                    FormulaEvaluator.evaluated_reference(words, kids, full, shape))


def test_fused_native_certificate() -> None:
    native = getattr(formulas._NATIVE, "certificate_words", None)
    if native is None:
        pytest.skip("fused certificate kernel is not built")
    rng = np.random.default_rng(28)
    for depth in range(1, 7):
        words = formula(depth, rng, xor=0.3)
        ops = np.array([VOCABULARY.index(w) for w in words], dtype=np.int64)
        children = formulas.parse_reference([ARITY[c] for c in ops])
        assert children is not None
        for full, shape in ((rng.random(len(words)), rng.random(len(words))),
                            (np.zeros(len(words)), np.zeros(len(words)))):
            flags = native(ops, full, shape)
            assert {k for k, flag in enumerate(flags) if flag} == (
                FormulaEvaluator.evaluated_reference(words, children, full, shape))
    for ops in ([], [3, 0], [0, 0]):
        assert native(np.array(ops, dtype=np.int64), np.zeros(len(ops)),
                      np.zeros(len(ops))) == []


def test_native_grouped_argmax_preserves_first_class_ties() -> None:
    native = getattr(formulas._NATIVE, "grouped_argmax", None)
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


@pytest.mark.parametrize("reference", [False, True])
def test_banded_answer_session_matches_exact_words(reference: bool,
                                                   monkeypatch: pytest.MonkeyPatch) -> None:
    from nca.modules.words import CorrectionState

    if reference:
        monkeypatch.setattr(formulas, "_NATIVE", None)
        monkeypatch.setattr(priors, "_NATIVE", None)
        monkeypatch.setattr(decoding, "_NATIVE", None)
    rng = np.random.default_rng(34)
    readings = rng.dirichlet(np.ones(len(VOCABULARY)), size=35)
    evaluator = FormulaEvaluator(decode=True, band_slack=1e-4)
    state = CorrectionState()
    for _ in range(20):
        k = int(rng.integers(len(readings)))
        readings[k] = rng.dirichlet(np.ones(len(VOCABULARY)))
        assert evaluator.words(readings, state) == FormulaEvaluator(decode=True).words(readings)
    assert state.answer_band is not None
    assert state.answer_band_result is not None and state.answer_band_result.exact
    assert evaluator.words(np.zeros_like(readings), state) == [VOCABULARY[0]] * len(readings)


@pytest.mark.parametrize("reference", [False, True])
def test_banded_correction_charges_selected_answer_conservatively(
        reference: bool, monkeypatch: pytest.MonkeyPatch) -> None:
    from nca.ladder import Distribution
    from nca.modules.words import CorrectionState

    if reference:
        monkeypatch.setattr(formulas, "_NATIVE", None)
        monkeypatch.setattr(priors, "_NATIVE", None)
        monkeypatch.setattr(decoding, "_NATIVE", None)
    rng = np.random.default_rng(41)
    words = "and or true false not false".split()
    readings = np.array(one_hot(words)) * 0.99 + 0.01 / len(VOCABULARY)
    calibrated = rng.dirichlet(np.ones(3), size=len(words))
    versions = [0] * len(words)
    seen: list[int] = []

    def masses(k: int, decision: Decision) -> torch.Tensor:
        seen.append(k)
        return torch.tensor(calibrated[k])

    distribution = Distribution(masses, versions.__getitem__)
    exact = FormulaEvaluator(decode=True)
    banded = FormulaEvaluator(decode=True, band_slack=1e-4)
    state = CorrectionState()
    for step in range(20):
        if step:
            k = int(rng.integers(len(words)))
            calibrated[k] = rng.dirichlet(np.ones(3))
            versions[k] += 1
        seen.clear()
        account = banded.certificate(readings, lambda k, d: 0.001, distribution, state)
        assert seen == (list(range(len(words))) if not step else [k])
        baseline = exact.certificate(readings, lambda k, d: 0.001, distribution)
        assert account is not None and baseline is not None
        assert sum(baseline.values()) - 1e-12 <= sum(account.values())
        assert sum(account.values()) <= sum(baseline.values()) + 1e-4 + 1e-12
        assert state.risk_band is not None
        seen.clear()
        repeated = banded.certificate(readings, lambda k, d: 0.001, distribution, state)
        assert seen == []
        assert repeated is not None
        # A scheduled marginal refresh can redistribute the same total charge.
        assert sum(repeated.values()) == pytest.approx(sum(account.values()), abs=1e-12)


def test_early_leaf_structural_shift_is_valid_and_reproducible() -> None:
    dataset = FormulaDataset("test", 100, 4, 0.2, 806, early_leaf=0.2)
    replica = FormulaDataset("test", 100, 4, 0.2, 806, early_leaf=0.2)
    height = formulas.height_prior(5)
    outside_complete = unsupported_length = False
    for i in range(len(dataset)):
        sample = dataset.sample(i)
        assert sample == replica.sample(i)
        assert evaluate(sample.words) == sample.value
        assert len(sample.text.split()) == len(sample.words)
        arities = tuple(ARITY[VOCABULARY.index(word)] for word in sample.words)
        assert height.log_weight(arities) == 0.0
        complete = formulas.complete_prior(len(arities))
        unsupported_length |= complete is None
        outside_complete |= complete is not None and complete.log_weight(arities) == -np.inf
    assert outside_complete and unsupported_length
    for i in range(10):
        stopped = FormulaDataset("test", 10, 6, 0.0, 806, early_leaf=1).sample(i)
        assert len(stopped.words) <= 2 and evaluate(stopped.words) == stopped.value
    for invalid in (-0.1, 1.1, np.nan):
        with pytest.raises(ValueError):
            FormulaDataset("test", 1, 4, 0, early_leaf=invalid)
        with pytest.raises(ValueError):
            formula(4, np.random.default_rng(0), early_leaf=invalid)


def test_zero_early_leaf_preserves_existing_generator_stream() -> None:
    first = np.random.default_rng(809)
    second = np.random.default_rng(809)
    assert formula(4, first) == formula(4, second, early_leaf=0.0)
    assert first.random() == second.random()
    default = FormulaDataset("test", 10, 3, 0.1, 809)
    explicit = FormulaDataset("test", 10, 3, 0.1, 809, early_leaf=0.0)
    assert [default.sample(i) for i in range(10)] == [explicit.sample(i) for i in range(10)]
