"""The constructors of handwritten arithmetic's types (THEORY §29.1).

Each module names its types by these constructors' references, and the
package puts them into the store with its members. ``BOOLEAN`` is stated
with the same contents in every domain that answers with truth values, so
it has one reference and those domains share the type without importing
each other.
"""

from __future__ import annotations

from nca.objects import Constructor

BOOLEAN = Constructor("nca.boolean", "1", 0,
                      "A truth value: a Python bool, or None when the producer has no answer.")
INTEGER = Constructor("nca.arithmetic.integer", "1", 0,
                      "An integer of any size: a Python int, or None when the expression "
                      "has no value.")
GLYPH = Constructor("nca.arithmetic.glyph", "1", 0,
                    "A handwritten glyph: torch.Tensor of shape (28, 28), float in [0, 1], "
                    "white ink on black.")
NORMALIZED_GLYPH = Constructor("nca.arithmetic.normalized-glyph", "1", 0,
                               "A glyph after nca.domains.arithmetic.normalizer.normalize: "
                               "torch.Tensor of shape (28, 28) in [0, 1].")
EXPRESSION_IMAGE = Constructor("nca.arithmetic.expression-image", "1", 0,
                               "A handwritten expression: torch.Tensor of shape (H, W), float "
                               "in [0, 1], white ink on black.")
GLYPH_EMBEDDING = Constructor("nca.arithmetic.glyph-embedding", "1", 0,
                              "torch.Tensor of shape (128,) from nca.glyph-encoder version 1.")
DIGIT_DISTRIBUTION = Constructor("nca.arithmetic.digit-distribution", "1", 0,
                                 "Tuple of 10 probabilities summing to 1, indexed by digit "
                                 "value.")
OPERATOR_DISTRIBUTION = Constructor("nca.arithmetic.operator-distribution", "1", 0,
                                    "Tuple of 4 probabilities over (+, -, *, not an "
                                    "operator).")
RELATION_DISTRIBUTION = Constructor("nca.arithmetic.relation-distribution", "1", 0,
                                    "Tuple of 4 probabilities over (<, >, =, not a "
                                    "relation).")
SYMBOL_DISTRIBUTION = Constructor("nca.arithmetic.symbol-distribution", "1", 0,
                                  "Dict mapping each digit and operator to its probability.")
EXPRESSION = Constructor("nca.arithmetic.expression", "1", 0,
                         "Tuple of tokens (digit, operator, digit, ..., digit), or None "
                         "if the symbols form no expression.")
COMPARISON_SYMBOL_DISTRIBUTION = Constructor(
    "nca.arithmetic.comparison-symbol-distribution", "1", 0,
    "Dict mapping each digit and relation to its probability.")
COMPARISON_CHAIN = Constructor("nca.arithmetic.comparison-chain", "1", 0,
                               "Tuple of tokens (digit, relation, digit, ..., digit), or None "
                               "if the symbols form no chain.")
MIXED_SYMBOL_DISTRIBUTION = Constructor("nca.arithmetic.mixed-symbol-distribution", "1", 0,
                                        "Dict mapping each digit, operator and relation to "
                                        "its probability.")
RELATIONAL_EXPRESSION = Constructor("nca.arithmetic.relational-expression", "1", 0,
                                    "Tuple of tokens digit ((operator | relation) digit)* "
                                    "with at least one relation, or None.")

CONSTRUCTORS = (BOOLEAN, INTEGER, GLYPH, NORMALIZED_GLYPH, EXPRESSION_IMAGE, GLYPH_EMBEDDING,
                DIGIT_DISTRIBUTION, OPERATOR_DISTRIBUTION, RELATION_DISTRIBUTION,
                SYMBOL_DISTRIBUTION, EXPRESSION, COMPARISON_SYMBOL_DISTRIBUTION,
                COMPARISON_CHAIN, MIXED_SYMBOL_DISTRIBUTION, RELATIONAL_EXPRESSION)
