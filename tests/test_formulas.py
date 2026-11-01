import itertools
from dataclasses import dataclass
from typing import Any

import numpy as np
import pytest

torch = pytest.importorskip("torch")

from nca.abi import Contract, Manifest
from nca.formulas import ARITY, VOCABULARY, FormulaDataset, corrupt, evaluate, formula, parse
from nca.ladder import Decision, Rung, ladder, refine, risk
from nca.modules.symbols import BOOLEAN
from nca.modules.words import (ARITY_DECISION, FORMULA_TEXT, READER, EditReader,
                               FormulaEvaluator, Tokenizer, edit_distance)
from nca.planner import plan_stable
from nca.selective import build_ladders, solve


def one_hot(words: list[str]) -> list[tuple[float, ...]]:
    return [tuple(float(w == v) for v in VOCABULARY) for w in words]


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

        account = FormulaEvaluator().certificate(one_hot(words), weight)
        assert account is not None
        chosen = sum(account.values())
        best = min(sum(full[k] if k in c else shape[k] for k in range(len(words)))
                   for c in certificates(words, 0, children))
        assert chosen == pytest.approx(best)
        static = FormulaEvaluator(short_circuit=False).certificate(one_hot(words), weight)
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
                    certificate=lambda readings, risk: {0: risk(0, None)})
    assert result.cost == pytest.approx(3 * 1.0 + 10.0)
    assert result.bound == pytest.approx(0.01, abs=1e-6) and not result.abstained
    assert refine([0], [rungs], 0.05, certificate=lambda readings, risk: None).abstained


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
    markov = FormulaEvaluator(detection="markov").certificate(one_hot(words), risk)
    pairs = FormulaEvaluator(detection="pairs").certificate(one_hot(words), risk)
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
            account = evaluator.certificate(one_hot(words), risk)
            assert account is not None
            assert evaluator.floor(one_hot(words), risk, fixed) <= sum(account.values()) + 1e-12
