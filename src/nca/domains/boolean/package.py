"""Noisy prefix formulas as a package (§28).

The package holds the tokenizer and the formula evaluator and exports one
contract, formula text to truth value. The word reader is a requirement:
whoever installs the package supplies a reader of noisy words, learned or
exact, and the planner fills the requirement with it.
"""

from __future__ import annotations

from nca.abi import Contract
from nca.domains.boolean.words import BOOLEAN, FORMULA_TEXT, READER, FormulaEvaluator, Tokenizer
from nca.objects import Composite, Primitive, Ref, Store

MEMBERS = ((Tokenizer, "nca.domains.boolean.words:Tokenizer"),
           (FormulaEvaluator, "nca.domains.boolean.words:FormulaEvaluator"))


def formulas(store: Store) -> Ref:
    """Put the formula package and its members into ``store``."""
    members = tuple(store.put(Primitive(cls().manifest, entry)) for cls, entry in MEMBERS)
    return store.put(Composite("nca.formulas", "1.0.0", members,
                               requires=((READER.inputs, READER.output),),
                               exports=(Contract((FORMULA_TEXT,), BOOLEAN),),
                               effects=frozenset()))
