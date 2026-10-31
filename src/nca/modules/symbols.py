"""Exact symbolic modules: symbol fusion, expression parsing, and evaluation."""

from __future__ import annotations

from nca.abi import Contract, Manifest, seq_type
from nca.expressions import OPERATORS, evaluate
from nca.modules.digit_recognizer import DIGIT_DISTRIBUTION
from nca.modules.operator_recognizer import OPERATOR_DISTRIBUTION

SYMBOL_DISTRIBUTION = "symbol.distribution.v1"
"""Dict mapping each symbol in ``SYMBOLS`` to its probability."""

EXPRESSION = "expression.infix.v1"
"""Tuple of tokens ``(digit, op, digit, op, ..., digit)``."""

INTEGER = "int.v1"

SYMBOLS = (*"0123456789", *OPERATORS)


class SymbolFuser:
    """P(op) = q_op; P(digit d) = q_none * p_d.

    Exact under the reading that the operator recognizer decides whether the
    glyph is an operator and the digit recognizer gives the digit otherwise.
    """

    manifest = Manifest(
        "nca.symbol-fuser", "1.0.0",
        Contract((DIGIT_DISTRIBUTION, OPERATOR_DISTRIBUTION), SYMBOL_DISTRIBUTION),
    )

    def invoke(self, digits: tuple[float, ...], operators: tuple[float, ...]) -> dict[str, float]:
        not_operator = operators[len(OPERATORS)]
        fused = {str(d): not_operator * p for d, p in enumerate(digits)}
        fused.update(zip(OPERATORS, operators))
        return fused


class ExpressionParser:
    """Most probable well-formed expression ``digit (op digit)*``.

    Under independent per-position distributions the grammar constrains each
    position's class (digit at even, operator at odd positions), so the
    maximum a posteriori parse is the per-position argmax within that class.
    Returns ``None`` when no well-formed parse exists (even length).
    """

    manifest = Manifest(
        "nca.expression-parser", "1.0.0",
        Contract((seq_type(SYMBOL_DISTRIBUTION),), EXPRESSION),
    )

    def invoke(self, symbols: list[dict[str, float]]) -> tuple[str, ...] | None:
        if len(symbols) % 2 == 0:
            return None
        return tuple(
            max(OPERATORS if i % 2 else "0123456789", key=dist.__getitem__)
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
