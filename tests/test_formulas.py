import itertools
from collections.abc import Callable, Sequence
from dataclasses import dataclass
from typing import Any

import numpy as np
import pytest

torch = pytest.importorskip("torch")

from nca.abi import Contract, Manifest
from nca import formulas
from nca.formulas import (ARITY, VOCABULARY, Decoded, FormulaDataset, corrupt, decode,
                          Split, decode_banded, decode_reference, evaluate, formula, parse)
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


def parseable(m: int) -> list[tuple[int, ...]]:
    return [a for a in itertools.product(ARITY_ORDER, repeat=m) if parse(list(a)) is not None]


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
def test_sequence_log_weight(reference: bool, monkeypatch: pytest.MonkeyPatch) -> None:
    if reference:
        monkeypatch.setattr(formulas, "_NATIVE", None)
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
def test_certified_cursor_preserves_risk_bounds(reference: bool,
                                                monkeypatch: pytest.MonkeyPatch) -> None:
    if reference:
        monkeypatch.setattr(formulas, "_NATIVE", None)
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


@pytest.mark.parametrize("reference", [False, True])
def test_banded_answer_session_matches_exact_words(reference: bool,
                                                   monkeypatch: pytest.MonkeyPatch) -> None:
    from nca.modules.words import CorrectionState

    if reference:
        monkeypatch.setattr(formulas, "_NATIVE", None)
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
