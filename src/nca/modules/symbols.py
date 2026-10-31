"""Exact symbolic modules: symbol fusion, expression parsing, and evaluation.

Each is parameterized by an operator vocabulary, giving one module family for
arithmetic (``+ - *``, integer values) and one for comparison (``< > =``,
boolean values), with distinct module ids and semantic types.
"""

from __future__ import annotations

from dataclasses import dataclass

from nca.abi import Contract, Manifest, TypeId, seq_type
from nca.expressions import OPERATORS, RELATIONS, evaluate
from nca.modules.digit_recognizer import DIGIT_DISTRIBUTION
from nca.modules.operator_recognizer import OPERATOR_DISTRIBUTION, RELATION_DISTRIBUTION

DIGITS = "0123456789"


@dataclass(frozen=True)
class Vocabulary:
    prefix: str
    operators: tuple[str, ...]
    operator_distribution: TypeId
    symbol_distribution: TypeId
    """Dict mapping each digit and operator to its probability."""
    expression: TypeId
    """Tuple of tokens ``(digit, op, digit, op, ..., digit)``."""
    value: TypeId


ARITHMETIC = Vocabulary("nca", OPERATORS, OPERATOR_DISTRIBUTION, "symbol.distribution.v1",
                        "expression.infix.v1", "int.v1")
COMPARISON = Vocabulary("nca.comparison", RELATIONS, RELATION_DISTRIBUTION,
                        "comparison-symbol.distribution.v1", "comparison.chain.v1",
                        "bool.v1")

SYMBOL_DISTRIBUTION = ARITHMETIC.symbol_distribution
EXPRESSION = ARITHMETIC.expression
INTEGER = ARITHMETIC.value
BOOLEAN = COMPARISON.value


class SymbolFuser:
    """P(op) = q_op; P(digit d) = q_none * p_d.

    Exact under the reading that the operator recognizer decides whether the
    glyph is an operator and the digit recognizer gives the digit otherwise.
    """

    def __init__(self, vocabulary: Vocabulary = ARITHMETIC) -> None:
        self.vocabulary = vocabulary
        self.manifest = Manifest(
            f"{vocabulary.prefix}.symbol-fuser", "1.0.0",
            Contract((DIGIT_DISTRIBUTION, vocabulary.operator_distribution),
                     vocabulary.symbol_distribution),
        )

    def invoke(self, digits: tuple[float, ...], operators: tuple[float, ...]) -> dict[str, float]:
        ops = self.vocabulary.operators
        fused = {str(d): operators[len(ops)] * p for d, p in enumerate(digits)}
        fused.update(zip(ops, operators))
        return fused


class ExpressionParser:
    """Most probable well-formed expression ``digit (op digit)*``.

    Under independent per-position distributions the grammar constrains each
    position's class (digit at even, operator at odd positions), so the
    maximum a posteriori parse is the per-position argmax within that class.
    Returns ``None`` when no well-formed parse exists (even length).
    """

    def __init__(self, vocabulary: Vocabulary = ARITHMETIC) -> None:
        self.vocabulary = vocabulary
        self.manifest = Manifest(
            f"{vocabulary.prefix}.expression-parser", "1.0.0",
            Contract((seq_type(vocabulary.symbol_distribution),), vocabulary.expression),
        )

    def invoke(self, symbols: list[dict[str, float]]) -> tuple[str, ...] | None:
        if len(symbols) % 2 == 0:
            return None
        return tuple(
            max(self.vocabulary.operators if i % 2 else DIGITS, key=dist.__getitem__)
            for i, dist in enumerate(symbols)
        )


class Evaluator:
    """Evaluate an infix expression; ``*`` binds tighter than ``+`` and ``-``."""

    manifest = Manifest("nca.evaluator", "1.0.0", Contract((EXPRESSION,), INTEGER))

    def invoke(self, tokens: tuple[str, ...] | None) -> int | None:
        if tokens is None:
            return None
        terms = [int(tokens[0])]
        signs = [1]
        for op, digit in zip(tokens[1::2], tokens[2::2]):
            if op == "*":
                terms[-1] = evaluate(terms[-1], op, int(digit))
            else:
                terms.append(int(digit))
                signs.append(1 if op == "+" else -1)
        return sum(s * t for s, t in zip(signs, terms))


class ComparisonEvaluator:
    """A relation chain ``a r b s c ...`` holds when every adjacent relation holds."""

    manifest = Manifest("nca.comparison.evaluator", "1.0.0",
                        Contract((COMPARISON.expression,), BOOLEAN))

    def invoke(self, tokens: tuple[str, ...] | None) -> bool | None:
        if tokens is None:
            return None
        values = [int(t) for t in tokens[::2]]
        return all(evaluate(a, r, b) for a, r, b in zip(values, tokens[1::2], values[1:]))
