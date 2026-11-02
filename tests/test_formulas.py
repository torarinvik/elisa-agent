import itertools
from dataclasses import dataclass
from decimal import Decimal
from fractions import Fraction
from typing import Any

import numpy as np
import pytest

torch = pytest.importorskip("torch")

from nca.abi import Contract, Manifest
from nca import decoding, prefix, priors
from nca import shares as share_module
from nca.domains.boolean.formulas import ARITY, VOCABULARY, FormulaDataset, corrupt, evaluate, formula
from nca.decoding import decode, parse
from nca.ladder import Decision, Rung, ladder, refine, risk
from nca.domains.boolean.words import (BOOLEAN, ARITY_DECISION, ARITY_ORDER, FORMULA_TEXT, READER, EditReader,
                               FormulaEvaluator, Tokenizer)
from nca.modules.edit import edit_distance
from nca.planner import plan_stable
from nca.selective import build_ladders, solve


def one_hot(words: list[str]) -> list[tuple[float, ...]]:
    return [tuple(float(w == v) for v in VOCABULARY) for w in words]


def test_batched_word_argmax_matches_reference(monkeypatch: pytest.MonkeyPatch) -> None:
    import nca.domains.boolean.words as words

    native = getattr(prefix._NATIVE, "row_argmax", None)
    if native is None:
        pytest.skip("Elisa decoding kernel is not built")
    rng = np.random.default_rng(412)
    rows = rng.normal(size=(30, len(VOCABULARY)))
    rows[0] = 0.0  # Ties choose the first class.
    rows[1, 3] = np.nan
    rows[1, 4] = np.nan  # NumPy chooses the first NaN.
    rows[2] = -np.inf
    expected = [VOCABULARY[int(np.argmax(row))] for row in rows]
    assert prefix.most_likely(rows, words.FORMULA) == expected
    assert prefix.most_likely([], words.FORMULA) == []
    assert list(native(np.array([], dtype=np.float64), 0)) == []
    assert list(native(np.array([1.0], dtype=np.float64), 2)) == []
    monkeypatch.setattr(prefix, "_NATIVE", None)
    assert prefix.most_likely(rows, words.FORMULA) == expected


def test_word_argmax_preserves_higher_precision_inputs(monkeypatch: pytest.MonkeyPatch) -> None:
    import nca.domains.boolean.words as words

    decimal_row = [Decimal(0)] * len(VOCABULARY)
    decimal_row[:2] = [Decimal("0.5"), Decimal("0.50000000000000000001")]
    integer_row = [0] * len(VOCABULARY)
    integer_row[:2] = [2**53, 2**53 + 1]
    for row in (decimal_row, integer_row):
        assert prefix.most_likely([row], words.FORMULA) == [VOCABULARY[1]]
    assert prefix.most_likely([integer_row, [0.0] * len(VOCABULARY)], words.FORMULA) == [
        VOCABULARY[1], VOCABULARY[0]]
    monkeypatch.setattr(prefix, "_NATIVE", None)
    for row in (decimal_row, integer_row):
        assert prefix.most_likely([row], words.FORMULA) == [VOCABULARY[1]]


def test_premise_diagnostic_handles_zero_expected_pairs(monkeypatch: pytest.MonkeyPatch, capsys: pytest.CaptureFixture[str]) -> None:
    from types import SimpleNamespace
    import nca.domains.boolean.logic as logic

    class Dataset:
        def __init__(self, *args: Any, **kwargs: Any) -> None:
            pass

        def __len__(self) -> int:
            return 1

        def sample(self, index: Any) -> Any:
            return SimpleNamespace(text="true", words=["true"])

    class Reader:
        def observe(self, word: Any) -> Any:
            return None

        def reading(self, log: Any) -> Any:
            return torch.tensor(one_hot(["true"])[0])

        def distribution(self, log: Any, classes: Any) -> Any:
            return torch.tensor([1.0, 0.0, 0.0])

        def risk(self, log: Any, classes: Any) -> Any:
            return 0.0

    monkeypatch.setattr(logic, "FormulaDataset", Dataset)
    args = SimpleNamespace(noise=0.1, shift=None, depths=[0], samples=1, seed=0, xor=0.0,
                           early_leaf=0.0)
    logic.premises(Reader(), args)
    output = capsys.readouterr().out
    assert "distant joint failures: 0" in output
    assert "ratio n/a against marginal ratio² n/a" in output


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
    from nca.domains.boolean.formulas import apply

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


def test_shared_stopping_paths_match_formula_evaluator() -> None:
    from nca.selective import solve_stops

    reader = EditReader()
    route = plan_stable([Tokenizer(), reader, FormulaEvaluator()], (FORMULA_TEXT,), BOOLEAN)
    assert route is not None
    ladders = {READER.output: [Rung(reader), Rung(reader)]}
    policies = [None, lambda state: state.cost >= 2000, lambda state: True]
    for text in ("and flse or xro true true tru", "and true false", ""):
        shared = solve_stops(route, ladders, text, 0.05, policies, floors=True)
        separate = [solve(route, ladders, text, 0.05, floors=True, stop=policy)
                    for policy in policies]
        assert shared == separate


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


@pytest.mark.parametrize("reference", [False, True])
def test_pair_shares_preserve_tiny_risks(reference: bool, monkeypatch: pytest.MonkeyPatch) -> None:

    if reference:
        monkeypatch.setattr(share_module, "_NATIVE", None)
    rng = np.random.default_rng(932)
    samples = [[1.0, 1e-18, 0.0], [1.0, np.nextafter(0.0, 1.0)],
               *[rng.random(10).tolist() for _ in range(100)]]
    for risks in samples:
        shares = share_module._pair_shares(risks)
        exact = [Fraction.from_float(float(r)) for r in risks]
        for i, share in enumerate(shares):
            expected = exact[i] * sum((v for j, v in enumerate(exact) if i != j), Fraction()) / 2
            assert Fraction.from_float(share) >= expected

    arity = [1.0, 1e-18, 0.0]
    def risk(k: int, decision: Decision) -> float:
        return arity[k] if decision == ARITY_DECISION else 0.0
    evaluator = FormulaEvaluator(detection="pairs", short_circuit=False)
    account = evaluator.certificate(one_hot(["and", "true", "true"]), risk, no_distribution)
    assert account is not None
    assert sum(Fraction.from_float(float(v)) for v in account.values()) >= Fraction.from_float(1e-18)


@pytest.mark.parametrize("reference", [False, True])
def test_pair_risk_upper_avoids_cancellation_and_underflow(
        reference: bool, monkeypatch: pytest.MonkeyPatch) -> None:
    from nca import ladder as ladder_module

    if reference:
        monkeypatch.setattr(share_module, "_NATIVE", None)
        monkeypatch.setattr(share_module, "_STATS_NATIVE", None)
        monkeypatch.setattr(ladder_module, "_NATIVE", None)
    rng = np.random.default_rng(2331)
    samples = [[], [1.0, 1e-18], [1e-200, 1e-200], [0.8, 0.8, 0.8],
               *[rng.random(10).tolist() for _ in range(100)]]
    for risks in samples:
        values = [Fraction.from_float(float(r)) for r in risks]
        exact = min(Fraction(1), sum((a * b for a, b in itertools.combinations(values, 2)),
                                    Fraction()))
        bound = share_module.pair_risk_upper(risks)
        assert Fraction.from_float(bound) >= exact
        assert bound <= 1.0
    assert share_module.pair_risk_upper([1.0, 1e-18]) > 0.0
    assert share_module.pair_risk_upper([1e-200, 1e-200]) > 0.0
    assert np.isnan(share_module.pair_risk_upper([float("nan"), 0.2]))
    assert np.isnan(share_module.pair_risk_upper([-0.1, 0.2]))


@pytest.mark.parametrize("reference", [False, True])
def test_detection_shares_round_up_at_boundaries(reference: bool, monkeypatch: pytest.MonkeyPatch) -> None:

    if reference:
        monkeypatch.setattr(share_module, "_NATIVE", None)
    smallest = float(np.nextafter(0.0, 1.0))
    risks = [smallest, 1.0, 0.0]
    shares = share_module._markov_shares(risks)
    assert all(Fraction.from_float(share) >= Fraction.from_float(risk) / 2
               for share, risk in zip(shares, risks, strict=True))
    additions = [0.0, 1e-18, Fraction(1, 3)]
    combined = share_module._combine_shares(shares, additions)
    for actual, share, addition in zip(combined, shares, additions, strict=True):
        assert Fraction.from_float(actual) >= Fraction.from_float(share) + Fraction(addition)
    arity = [smallest, 1.0, 0.0]
    within = [0.0, 1e-18, 0.0]
    def risk(k: int, decision: Decision) -> float:
        return arity[k] if decision == ARITY_DECISION else within[k]
    evaluator = FormulaEvaluator(detection="markov", short_circuit=False)
    account = evaluator.certificate(one_hot(["and", "true", "true"]), risk, no_distribution)
    assert account is not None
    for i in range(3):
        exact = Fraction.from_float(arity[i]) / 2 + Fraction.from_float(within[i])
        assert Fraction.from_float(account[i]) >= exact


@pytest.mark.parametrize("reference", [False, True])
@pytest.mark.parametrize("mixed", [False, True])
def test_combine_shares_preserves_precise_mixed_inputs(reference: bool, mixed: bool,
                                                      monkeypatch: pytest.MonkeyPatch) -> None:

    if reference:
        monkeypatch.setattr(share_module, "_NATIVE", None)
    additions = [np.float16(0.5), np.float32(0.25), np.float64(0.125), 0.0625]
    if mixed:
        additions.extend([Fraction(1, 3), 2**53 + 1])
    shares = [1e-18] * len(additions)
    combined = share_module._combine_shares(shares, additions)
    for actual, addition in zip(combined, additions, strict=True):
        exact = Fraction.from_float(float(addition)) if isinstance(addition, np.floating) else Fraction(addition)
        assert Fraction.from_float(actual) >= exact + Fraction.from_float(1e-18)


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


@pytest.mark.parametrize("short_circuit", [False, True])
def test_unconstrained_formula_floor_rounds_down(short_circuit: bool) -> None:
    arity = [Fraction(1, 3), Fraction(1, 10 ** 400), Fraction(2, 7)]
    full = [Fraction(2, 3), Fraction(2, 10 ** 400), Fraction(3, 7)]
    def risk(k: int, decision: Decision) -> Fraction:
        return arity[k] if decision == ARITY_DECISION else full[k]
    evaluator = FormulaEvaluator(short_circuit=short_circuit)
    result = evaluator.floor(one_hot(["and", "true", "true"]), risk, frozenset(range(3)))
    exact = sum(arity if short_circuit else full, Fraction())
    assert Fraction.from_float(result) <= exact



@pytest.mark.parametrize("reference", [False, True])
def test_detection_floors_round_down(reference: bool, monkeypatch: pytest.MonkeyPatch) -> None:
    """Both detection floors bound their exact values from below, keeping tiny
    risks and inputs that need rounding to binary64."""

    if reference:
        monkeypatch.setattr(share_module, "_NATIVE", None)
    elif getattr(share_module._NATIVE, "detection_floors", None) is None:
        pytest.skip("native kernel not built")
    rng = np.random.default_rng(10)
    cases: list[list[float | Fraction]] = [[1.0, 1e-18], [float(np.nextafter(0.0, 1.0))] * 3,
                                           [Fraction(1, 3), Fraction(1, 10 ** 400), Fraction(2, 7)]]
    cases += [list(rng.random(int(rng.integers(1, 30))) * 10.0 ** rng.integers(-20, 1))
              for _ in range(300)]
    for risks in cases:
        markov, pairs = share_module._detection_floors(risks)
        exact = [Fraction(r) if isinstance(r, Fraction) else Fraction.from_float(r) for r in risks]
        total = sum(exact, Fraction())
        assert Fraction.from_float(markov) <= total / 2
        assert Fraction.from_float(pairs) <= (total * total - sum(r * r for r in exact)) / 2
        evaluator = FormulaEvaluator(detection="pairs")
        def risk(k: int, decision: Decision) -> float | Fraction:
            return risks[k]
        floor = evaluator.floor(one_hot(["true"] * len(risks)), risk, frozenset(range(len(risks))))
        assert floor == min(markov, pairs)

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
        decoded = FormulaEvaluator(decode=True).symbols(readings)
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
    decoded = evaluator.symbols(readings)
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
    from nca.prefix import CorrectionState

    if reference:
        monkeypatch.setattr(priors, "_NATIVE", None)
        monkeypatch.setattr(decoding, "_NATIVE", None)
    rng = np.random.default_rng(25)
    evaluator = FormulaEvaluator(decode=True)
    state = CorrectionState()
    readings = rng.dirichlet(np.ones(len(VOCABULARY)), size=35)
    for _ in range(30):
        k = int(rng.integers(len(readings)))
        readings[k] = rng.dirichlet(np.ones(len(VOCABULARY)))
        assert evaluator.symbols(readings, state) == evaluator.symbols(readings)


@pytest.mark.parametrize("reference", [False, True])
def test_changed_rows_matches_numpy_for_layouts_and_special_values(reference: bool, monkeypatch: pytest.MonkeyPatch) -> None:

    if reference:
        monkeypatch.setattr(prefix, "_NATIVE", None)
        monkeypatch.setattr(share_module, "_NATIVE", None)
    current = np.array([[0.0, -0.0, np.inf], [np.nan, 1.0, -np.inf],
                        [3.0, 4.0, 5.0], [6.0, 7.0, 8.0]])
    previous = current.copy()
    previous[2, 1] = 9.0
    for left, right in ((current, previous), (current[::2], previous[::2]),
                        (current.astype(np.float32), previous.astype(np.float32))):
        expected = tuple(int(k) for k in np.flatnonzero(np.any(left != right, axis=1)))
        assert prefix._changed_rows(left, right) == expected
    assert prefix._changed_rows(np.empty((0, 3)), np.empty((0, 3))) == ()


def test_answer_cursor_reuses_trace_only_for_unchanged_readings(monkeypatch: pytest.MonkeyPatch) -> None:
    from nca.prefix import CorrectionState

    original = decoding.Split.best
    calls = 0

    def best(split: decoding.Split, k: int) -> tuple[float, tuple[int, ...]]:
        nonlocal calls
        calls += 1
        return original(split, k)

    monkeypatch.setattr(decoding.Split, "best", best)
    rng = np.random.default_rng(851)
    readings = rng.dirichlet(np.ones(len(VOCABULARY)), size=15)
    evaluator = FormulaEvaluator(decode=True)
    state = CorrectionState()
    first = evaluator.symbols(readings, state)
    assert calls == 1
    assert evaluator.symbols(readings, state) == first and calls == 1
    readings[7] = rng.dirichlet(np.ones(len(VOCABULARY)))
    assert evaluator.symbols(readings, state) == evaluator.symbols(readings)
    assert calls == 2


def test_correction_state_resets_when_evaluator_or_decoder_mode_changes() -> None:
    from nca.prefix import CorrectionState

    rng = np.random.default_rng(572)
    exact = FormulaEvaluator(decode=True)
    banded = FormulaEvaluator(decode=True, band_slack=1e-4)
    with_prior = FormulaEvaluator(decode=True, prior=priors.format_prior)
    state = CorrectionState()
    for evaluator in (exact, banded, exact, with_prior, exact):
        readings = rng.dirichlet(np.ones(len(VOCABULARY)), size=15)
        assert evaluator.symbols(readings, state) == evaluator.symbols(readings)
    readings = rng.dirichlet(np.ones(len(VOCABULARY)), size=15)
    exact.band_slack = 1e-4
    assert exact.symbols(readings, state) == exact.symbols(readings)
    exact.band_slack = None
    assert exact.symbols(readings, state) == exact.symbols(readings)


def test_native_certificate_matches_reference_including_ties() -> None:
    from nca.domains.boolean import words as word_module

    if getattr(word_module._KERNELS, "certificate", None) is None:
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


def test_native_prefix_validity_matches_general_parser() -> None:
    native = getattr(decoding._NATIVE, "valid_prefix", None)
    if native is None:
        pytest.skip("native prefix validation is not built")
    rng = np.random.default_rng(2034)
    samples = [[], [0], [1], [0, 0], [2, 0, 0], [3, 0, 0, 0], [-1], [2**63 - 1]]
    samples.extend(list(arities) for length in range(1, 7)
                   for arities in itertools.product(range(4), repeat=length))
    samples.extend(rng.integers(-1, 6, size=int(rng.integers(1, 20))).tolist()
                   for _ in range(3000))
    for arities in samples:
        assert native(np.asarray(arities, dtype=np.int64)) == (decoding.parse_reference(arities) is not None)
    assert not native(np.full(100_000, 2, dtype=np.int64))
    assert native(np.r_[np.ones(99_999, dtype=np.int64), np.zeros(1, dtype=np.int64)])


def test_native_grouped_argmax_preserves_first_class_ties() -> None:
    native = getattr(decoding._NATIVE, "grouped_argmax", None)
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
    from nca.prefix import CorrectionState

    if reference:
        monkeypatch.setattr(priors, "_NATIVE", None)
        monkeypatch.setattr(decoding, "_NATIVE", None)
    rng = np.random.default_rng(34)
    readings = rng.dirichlet(np.ones(len(VOCABULARY)), size=35)
    evaluator = FormulaEvaluator(decode=True, band_slack=1e-4)
    state = CorrectionState()
    for _ in range(20):
        k = int(rng.integers(len(readings)))
        readings[k] = rng.dirichlet(np.ones(len(VOCABULARY)))
        assert evaluator.symbols(readings, state) == FormulaEvaluator(decode=True).symbols(readings)
    assert state.answer_band is not None
    assert state.answer_band_result is not None and state.answer_band_result.exact
    assert evaluator.symbols(np.zeros_like(readings), state) == [VOCABULARY[0]] * len(readings)


@pytest.mark.parametrize("reference", [False, True])
def test_banded_correction_charges_selected_answer_conservatively(
        reference: bool, monkeypatch: pytest.MonkeyPatch) -> None:
    from nca.ladder import Distribution
    from nca.prefix import CorrectionState

    if reference:
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
    height = priors.height_prior(5)
    outside_complete = unsupported_length = False
    for i in range(len(dataset)):
        sample = dataset.sample(i)
        assert sample == replica.sample(i)
        assert evaluate(sample.words) == sample.value
        assert len(sample.text.split()) == len(sample.words)
        arities = tuple(ARITY[VOCABULARY.index(word)] for word in sample.words)
        assert height.log_weight(arities) == 0.0
        complete = priors.complete_prior(len(arities))
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


@pytest.mark.parametrize("reference", [False, True])
def test_raw_arity_grouping_preserves_sums_and_inputs(
        reference: bool, monkeypatch: pytest.MonkeyPatch) -> None:
    from nca.domains.boolean import words as word_module

    if reference:
        monkeypatch.setattr(prefix, "_NATIVE", None)
        monkeypatch.setattr(share_module, "_NATIVE", None)
    rng = np.random.default_rng(1702)
    source = rng.dirichlet(np.ones(len(VOCABULARY)), size=34)
    source[0] = 0
    source[2] = [1e-300, 1e-200, 0, 1e200, 1e-300, 1e199]
    source.setflags(write=False)
    # Strided views exercise the CPython boundary's contiguous flattened snapshot.
    rows = source[::2]
    expected = np.array([[sum(r[c] for c in g) for g in ARITY_DECISION] for r in rows])
    before = source.copy()
    for readings in (rows, rows.tolist(), tuple(map(tuple, rows))):
        np.testing.assert_allclose(prefix.arity_masses(readings, word_module.FORMULA), expected, rtol=3e-16, atol=0)
        if not reference and isinstance(readings, list):
            precise = [[sum(r[c] for c in g) for g in ARITY_DECISION] for r in readings]
            np.testing.assert_array_equal(prefix.arity_masses(readings, word_module.FORMULA), precise)
    np.testing.assert_array_equal(source, before)


def test_native_grouped_masses_handles_empty_and_reordered_groups() -> None:

    native = getattr(prefix._NATIVE, "grouped_masses", None)
    if native is None:
        pytest.skip("requires the native grouping kernel")
    groups = np.array([2, 0, 2, 3, 0, 2], dtype=np.int64)
    scores = np.arange(18, dtype=np.float64).reshape(3, 6)
    expected = [[sum(row[c] for c in range(6) if groups[c] == g) for g in range(5)]
                for row in scores]
    np.testing.assert_array_equal(np.array(native(scores.reshape(-1), groups, 5)).reshape(3, 5),
                                  expected)
    assert native(np.empty(0), groups, 5) == []


@pytest.mark.parametrize("decode", [False, True])
def test_solve_formula_preserves_weight_order_when_logs_tie(decode: bool) -> None:
    import math

    from nca.domains.boolean.words import WORD_DISTRIBUTION

    low = 1e-300
    weights = [0.0] * len(VOCABULARY)
    false = VOCABULARY.index("false")
    true = VOCABULARY.index("true")
    first, second = sorted((false, true))
    weights[first] = low
    weights[second] = math.nextafter(low, math.inf)

    class Reader:
        manifest = Manifest("tie-reader", "1", READER, cost=1.0)
        def invoke(self, value: Any) -> Any:
            return tuple(weights)

    reader = Reader()
    route = plan_stable([Tokenizer(), reader, FormulaEvaluator(decode=decode)],
                        (FORMULA_TEXT,), BOOLEAN)
    assert route is not None
    result = solve(route, {WORD_DISTRIBUTION: [Rung(reader)]}, "true", 1.0)
    assert not result.abstained
    assert result.value == (second == true)


def test_formula_correction_recovers_after_missing_restricted_calibration() -> None:
    from nca.ladder import MissingCalibrationError
    from nca.domains.boolean.words import WORD_DISTRIBUTION
    from nca.selective import solve_many

    low = Constant(Manifest("formula-low", "1", READER, cost=1.0),
                   (0.8, 0.1, 0.025, 0.025, 0.025, 0.025))
    high = Constant(Manifest("formula-high", "1", READER, cost=2.0),
                    (0.9, 0.1, 0.0, 0.0, 0.0, 0.0))
    first, second = Rung(low), Rung(high)
    first.calibrate(["true", "true"], torch.tensor([VOCABULARY.index("not"),
                                                    VOCABULARY.index("and")]))
    second.calibrate(["true"] * 10, torch.tensor([VOCABULARY.index("true")] * 9 +
                                                   [VOCABULARY.index("false")]))
    with pytest.raises(MissingCalibrationError):
        first.temperature(ARITY_DECISION[0])
    evaluator = FormulaEvaluator(decode=True)
    route = plan_stable([Tokenizer(), low, high, evaluator], (FORMULA_TEXT,), BOOLEAN)
    assert route is not None
    answers = solve_many(route, {WORD_DISTRIBUTION: [first, second]}, "true", [float("inf"), 0.2])
    assert all(not answer.abstained and answer.value is True and answer.cost == 3.0
               for answer in answers)
    assert answers[1].bound == pytest.approx(0.1, abs=0.02)
    fresh = solve(route, {WORD_DISTRIBUTION: [second]}, "true", 0.2)
    assert not fresh.abstained and fresh.value is True
    assert answers[1].bound == pytest.approx(fresh.bound, abs=1e-14)


@pytest.mark.parametrize("cached", [False, True])
@pytest.mark.parametrize("mode", ["exact", "banded", "prior"])
def test_correction_preserves_subnormal_calibrated_masses(cached: bool, mode: str) -> None:
    words = ["and", "true", "true"]
    readings = one_hot(words)
    rows = np.array([[0.0, 1.0, 1e-320], [1.0, 1e-310, 0.0], [1.0, 0.0, 0.0]])

    def distribution(k: int, decision: Decision) -> torch.Tensor:
        return torch.tensor(rows[k], dtype=torch.float64)

    options = ({"band_slack": 0.01} if mode == "banded" else
               {"prior": priors.format_prior} if mode == "prior" else {})
    evaluator = FormulaEvaluator(decode=True, short_circuit=False, **options)
    def risk(k: int, decision: Decision) -> float:
        return 0.0

    certificate = evaluator.certificate_session() if cached else evaluator.certificate
    account = certificate(readings, risk, distribution)
    assert account is not None
    with np.errstate(divide="ignore"):
        log_probs = np.log(rows)
    posterior = decode(log_probs, ARITY_ORDER)
    assert posterior is not None
    expected = posterior.risk(log_probs, ARITY_ORDER, [2, 0, 0])
    assert expected > 0.999999999
    assert sum(account.values()) == pytest.approx(expected, abs=1e-12)


def test_correction_refresh_preserves_subnormal_masses() -> None:
    from nca.ladder import Distribution

    readings = one_hot(["and", "true", "true"])
    rows = np.array([[0.0, 1.0, 0.2], [1.0, 0.3, 0.0], [1.0, 0.0, 0.0]])
    versions = [0, 0, 0]
    distribution = Distribution(lambda k, decision: torch.tensor(rows[k]), versions.__getitem__)
    evaluator = FormulaEvaluator(decode=True, short_circuit=False)
    def risk(k: int, decision: Decision) -> float:
        return 0.0

    session = evaluator.certificate_session()
    assert session(readings, risk, distribution) is not None
    rows[0, 2] = 1e-320
    rows[1, 1] = 1e-310
    versions[0] += 1
    versions[1] += 1
    cached = session(readings, risk, distribution)
    fresh = evaluator.certificate(readings, risk, distribution)
    assert cached is not None and fresh is not None
    assert sum(cached.values()) > 0.999999999
    assert sum(cached.values()) == pytest.approx(sum(fresh.values()), abs=1e-12)


@pytest.mark.parametrize("mode", ["exact", "banded", "prior"])
def test_correction_refuses_zero_mass_calibrated_row(mode: str) -> None:
    readings = one_hot(["and", "true", "true"])
    rows = np.array([[0.0, 0.0, 0.0], [1.0, 0.0, 0.0], [1.0, 0.0, 0.0]])
    options = ({"band_slack": 0.01} if mode == "banded" else
               {"prior": priors.format_prior} if mode == "prior" else {})
    evaluator = FormulaEvaluator(decode=True, **options)
    account = evaluator.certificate_session()(
        readings, lambda k, decision: 0.0, lambda k, decision: torch.tensor(rows[k]))
    assert account is None


@pytest.mark.parametrize("mode", ["exact", "banded", "prior"])
def test_correction_uses_log_distribution_for_underflowed_mass(mode: str) -> None:
    from nca.ladder import Distribution

    readings = one_hot(["and", "true", "true"])
    log_rows = np.array([[-np.inf, 0.0, -700.0], [0.0, -1000.0, -np.inf],
                         [0.0, -np.inf, -np.inf]])
    linear_rows = np.exp(log_rows)
    distribution = Distribution(lambda k, d: torch.tensor(linear_rows[k]), lambda k: 0,
                                log_lookup=lambda k, d: torch.tensor(log_rows[k]))
    options = ({"band_slack": 0.01} if mode == "banded" else
               {"prior": priors.format_prior} if mode == "prior" else {})
    evaluator = FormulaEvaluator(decode=True, short_circuit=False, **options)

    def risk(k: int, decision: Decision) -> float:
        return 0.0

    account = evaluator.certificate_session()(readings, risk, distribution)
    assert account is not None
    posterior = decode(log_rows, ARITY_ORDER)
    assert posterior is not None
    expected = posterior.risk(log_rows, ARITY_ORDER, [2, 0, 0])
    assert expected > 0
    assert sum(account.values()) == pytest.approx(expected, rel=1e-12, abs=0)


def test_refinement_carries_underflowed_log_masses_to_formula_correction() -> None:
    from nca.ladder import decision_key
    from nca.selective import element_certificate

    def weights(**entries: Any) -> Any:
        return tuple(entries.get(word, 0.0) for word in VOCABULARY)

    rows = [weights(**{"not": 1.0, "and": 1e-250}),
            weights(**{"true": 1.0, "not": 1e-300}), weights(**{"true": 1.0})]
    rungs = [Rung(Constant(Manifest(f"row-{i}", "1", READER, cost=1.0), row))
             for i, row in enumerate(rows)]
    for rung in rungs:
        rung.temperatures[decision_key(ARITY_DECISION)] = 0.5
    evaluator = FormulaEvaluator(decode=True, short_circuit=False)
    adapted = element_certificate(evaluator, [(0, 0), (1, 0), (2, 0)], 3)
    assert adapted is not None

    def certificate(readings: Any, risk: Any, distribution: Any) -> Any:
        return adapted(readings, lambda i, decision: 0.0, distribution)

    result = refine([0, 0, 0], [[rung] for rung in rungs], 1.0,
                    certificate=certificate, ranked=True)
    assert result.available and not result.abstained
    assert result.bound > 0.0
    log_rows = torch.stack([rung.log_distribution(rung.observe_ranked(0), ARITY_DECISION)
                            for rung in rungs]).numpy()
    posterior = decode(log_rows, ARITY_ORDER)
    assert posterior is not None
    expected = posterior.risk(log_rows, ARITY_ORDER, [2, 0, 0])
    assert expected > 0
    assert result.bound == pytest.approx(expected, rel=1e-12, abs=0)


def test_correction_does_not_erase_smallest_positive_sequence_risk() -> None:
    from nca.ladder import Distribution

    readings = one_hot(["and", "true", "true"])
    log_rows = np.array([[-np.inf, 0.0, -700.0], [0.0, -1500.0, -np.inf],
                         [0.0, -np.inf, -np.inf]])
    distribution = Distribution(lambda k, d: torch.tensor(np.exp(log_rows[k])), lambda k: 0,
                                log_lookup=lambda k, d: torch.tensor(log_rows[k]))
    account = FormulaEvaluator(decode=True, short_circuit=False).certificate_session()(
        readings, lambda k, d: 0.0, distribution)
    assert account is not None
    assert sum(account.values()) == np.nextafter(0.0, 1.0)


@pytest.mark.parametrize("mode", ["exact", "banded", "prior"])
def test_log_distribution_revision_refresh_matches_fresh_correction(mode: str) -> None:
    from nca.ladder import Distribution

    readings = one_hot(["and", "true", "true"])
    rows = np.array([[-np.inf, 0.0, -700.0], [0.0, -1000.0, -np.inf],
                     [0.0, -np.inf, -np.inf]])
    revisions = [0, 0, 0]
    distribution = Distribution(lambda k, d: torch.tensor(np.exp(rows[k])), revisions.__getitem__,
                                log_lookup=lambda k, d: torch.tensor(rows[k]))
    options = ({"band_slack": 0.01} if mode == "banded" else
               {"prior": priors.format_prior} if mode == "prior" else {})
    evaluator = FormulaEvaluator(decode=True, short_circuit=False, **options)

    def risk(k: int, decision: Decision) -> float:
        return 0.0

    session = evaluator.certificate_session()
    initial = session(readings, risk, distribution)
    assert initial is not None and sum(initial.values()) > 0
    rows[1, 1] = -999.0
    revisions[1] += 1
    cached = session(readings, risk, distribution)
    fresh = evaluator.certificate(readings, risk, distribution)
    assert cached is not None and fresh is not None
    assert sum(cached.values()) > sum(initial.values())
    assert sum(cached.values()) == pytest.approx(sum(fresh.values()), rel=1e-12, abs=0)


def test_formula_package_answers_like_the_flat_pipeline() -> None:
    """§28.3: the package is an expert whose word-reader requirement the
    planner fills with whatever reader is installed."""
    from nca.abi import Message
    from nca.domains.boolean.package import formulas
    from nca.objects import Store
    from nca.packages import Export, install
    from nca.planner import Apply
    from nca.runtime import execute
    from nca.workspace import Workspace

    reader = EditReader()
    flat = plan_stable([Tokenizer(), reader, FormulaEvaluator()], (FORMULA_TEXT,), BOOLEAN)
    store = Store()
    route = plan_stable([reader, *install(store, formulas(store))], (FORMULA_TEXT,), BOOLEAN)
    assert isinstance(route, Apply) and isinstance(route.module, Export)
    assert [s.module for s in route.slots] == [reader]
    for text in ("and flse or xro true true tru", "and true false", "not tru", "or"):
        answers = [execute(r, [Message(FORMULA_TEXT, text, "input")], Workspace(), 1000).payload
                   for r in (flat, route)]
        assert answers[0] == answers[1]
