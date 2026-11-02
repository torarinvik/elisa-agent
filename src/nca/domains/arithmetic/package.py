"""Handwritten arithmetic as a package (§28).

The package holds the domain's exact experts (segmenter, symbol fuser,
expression parser and evaluator) and exports one contract, expression image
to integer. The glyph readers are requirements, not members: whoever
installs the package supplies a digit reader and an operator reader, of any
architecture or provenance, and the planner fills the requirements with them
as it fills any slot.
"""

from __future__ import annotations

from nca.abi import Contract
from nca.domains.arithmetic import types
from nca.domains.arithmetic.digit_recognizer import DIGIT_DISTRIBUTION, GLYPH
from nca.domains.arithmetic.operator_recognizer import OPERATOR_DISTRIBUTION
from nca.domains.arithmetic.segmenter import EXPRESSION_IMAGE, Segmenter
from nca.domains.arithmetic.symbols import INTEGER, Evaluator, ExpressionParser, SymbolFuser
from nca.objects import Composite, Primitive, Ref, Store

MEMBERS = ((Segmenter, "nca.domains.arithmetic.segmenter:Segmenter"),
           (SymbolFuser, "nca.domains.arithmetic.symbols:SymbolFuser"),
           (ExpressionParser, "nca.domains.arithmetic.symbols:ExpressionParser"),
           (Evaluator, "nca.domains.arithmetic.symbols:Evaluator"))

REQUIRES = (((GLYPH,), DIGIT_DISTRIBUTION), ((GLYPH,), OPERATOR_DISTRIBUTION))


def arithmetic(store: Store) -> Ref:
    """Put the arithmetic package, its types and its members into ``store``."""
    constructors = tuple(store.put(c) for c in types.CONSTRUCTORS)
    members = tuple(store.put(Primitive(cls().manifest, entry)) for cls, entry in MEMBERS)
    return store.put(Composite("nca.arithmetic", "1.0.0", (*constructors, *members),
                               requires=REQUIRES,
                               exports=(Contract((EXPRESSION_IMAGE,), INTEGER),),
                               effects=frozenset()))
