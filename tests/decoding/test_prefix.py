"""Prefix terms over a ranked vocabulary that no domain defines."""

from collections.abc import Sequence

import numpy as np
import pytest

pytest.importorskip("torch")

from nca import prefix
from nca.abi import Contract, Manifest
from nca.prefix import PrefixEvaluator, RankedVocabulary

# Arities 0, 2 and 3: not the consecutive 0, 1, 2 of any existing domain.
TERMS = RankedVocabulary(("one", "two", "add", "sum3"), (0, 0, 2, 3))


def value(symbol: str, children: Sequence[int]) -> int:
    return {"one": 1, "two": 2}.get(symbol, sum(children))


def evaluator(**options: object) -> PrefixEvaluator:
    manifest = Manifest("test.terms", "1.0.0", Contract(("seq[test.symbol.v1]",), "test.int.v1"))
    return PrefixEvaluator(TERMS, value, manifest, **options)


def readings(symbols: Sequence[str], noise: float = 0.0) -> list[tuple[float, ...]]:
    rows = []
    for symbol in symbols:
        row = np.full(len(TERMS.symbols), noise)
        row[TERMS.index(symbol)] = 1.0
        rows.append(tuple((row / row.sum()).tolist()))
    return rows


def test_vocabulary_groups_by_arity_position() -> None:
    assert TERMS.order == (0, 2, 3)
    assert TERMS.decision == ((0, 1), (2,), (3,))
    assert TERMS.group(3) == (3,)
    assert TERMS.class_groups.tolist() == [0, 0, 1, 2]
    with pytest.raises(ValueError):
        RankedVocabulary(("a", "a"), (0, 0))
    with pytest.raises(ValueError):
        RankedVocabulary(("a",), (-1,))


@pytest.mark.parametrize("native", [True, False])
def test_arity_masses_use_group_positions(native: bool, monkeypatch: pytest.MonkeyPatch) -> None:
    if not native:
        monkeypatch.setattr(prefix, "_NATIVE", None)
    rows = readings(["sum3", "one", "add", "two", "one", "two"], noise=0.1)
    masses = prefix.arity_masses(rows, TERMS)
    expected = [[r[0] + r[1], r[2], r[3]] for r in rows]
    np.testing.assert_allclose(masses, expected, rtol=1e-15)


@pytest.mark.parametrize("decode", [False, True])
def test_terms_are_read_and_evaluated_with_supplied_semantics(decode: bool) -> None:
    term = ["sum3", "one", "add", "two", "one", "two"]
    assert evaluator(decode=decode).invoke(readings(term, noise=0.05)) == 1 + (2 + 1) + 2
    assert evaluator(decode=decode).symbols(readings(term, noise=0.05)) == term


def test_decoding_corrects_an_unparseable_reading() -> None:
    rows = readings(["add", "one", "two"], noise=0.05)
    rows[0] = (0.05, 0.05, 0.40, 0.50)  # "sum3" is likelier but leaves a child missing.
    assert evaluator().invoke(rows) is None
    assert evaluator(decode=True).invoke(rows) == 3


def test_without_a_certificate_rule_every_symbol_is_evaluated() -> None:
    term = ["add", "one", "two"]
    risks = {None: 0.3, TERMS.decision: 0.1}

    def risk(k: int, decision: object) -> float:
        return risks[decision] if decision in risks else 0.05

    account = evaluator().certificate(readings(term), risk, lambda k, d: None)
    assert account == {0: 0.3, 1: 0.3, 2: 0.3}
    assert evaluator().floor(readings(term), risk, frozenset({0, 1})) == pytest.approx(0.6)
    with pytest.raises(ValueError):
        evaluator(detection="unknown")
