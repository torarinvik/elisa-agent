"""Noisy prefix formulas as a package (§28).

The package holds the tokenizer and the formula evaluator and exports one
contract, formula text to truth value. The word reader is a requirement:
whoever installs the package supplies a reader of noisy words, learned or
exact, and the planner fills the requirement with it.
"""

from __future__ import annotations

from nca.abi import Contract
from nca.domains.boolean import types
from nca.domains.boolean.words import BOOLEAN, FORMULA_TEXT, READER, FormulaEvaluator, Tokenizer
from nca.objects import Composite, Primitive, Ref, Store

MEMBERS = ((Tokenizer, "nca.domains.boolean.words:Tokenizer"),
           (FormulaEvaluator, "nca.domains.boolean.words:FormulaEvaluator"))


def formulas(store: Store) -> Ref:
    """Put the formula package, its types and its members into ``store``."""
    constructors = tuple(store.put(c) for c in types.CONSTRUCTORS)
    members = tuple(store.put(Primitive(cls().manifest, entry)) for cls, entry in MEMBERS)
    return store.put(Composite("nca.formulas", "1.0.0", (*constructors, *members),
                               requires=((READER.inputs, READER.output),),
                               exports=(Contract((FORMULA_TEXT,), BOOLEAN),),
                               effects=frozenset()))
