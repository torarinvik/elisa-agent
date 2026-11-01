import itertools
from collections.abc import Sequence
from dataclasses import dataclass
from typing import Any

import numpy as np
import pytest

torch = pytest.importorskip("torch")

from nca.abi import Contract, Manifest
from nca.formulas import (ARITY, VOCABULARY, FormulaDataset, corrupt, decode, evaluate, formula,
                          parse)
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


def parseable(m: int) -> list[tuple[int, ...]]:
    return [a for a in itertools.product(ARITY_ORDER, repeat=m) if parse(list(a)) is not None]


def test_decoder_matches_enumeration() -> None:
    """``NCA.dpSum_eq``, ``NCA.dpMax_ge`` and ``NCA.dpMax_attained`` against
    every arity sequence, with ``NCA.accepts_iff_codes`` as the language."""
    rng = np.random.default_rng(4)
    for m in range(1, 9):
        for _ in range(10):
            probs = rng.dirichlet(np.full(3, 0.5), size=m)
            decoded = decode(np.log(probs), ARITY_ORDER)
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
