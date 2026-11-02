"""The constructors of noisy prefix formulas' types (THEORY §29.1).

Each module names its types by these constructors' references, and the
package puts them into the store with its members. Truth values are the
shared ``nca.prelude.BOOLEAN``.
"""

from __future__ import annotations

from nca.objects import Constructor
from nca.prelude import BOOLEAN

FORMULA_TEXT = Constructor("nca.boolean.formula-text", "1", 0,
                           "A prefix formula as str: words separated by single spaces.")
NOISY_WORD = Constructor("nca.boolean.noisy-word", "1", 0,
                         "A possibly misspelled formula word: str of lowercase letters.")
WORD_DISTRIBUTION = Constructor("nca.boolean.word-distribution", "1", 0,
                                "Tuple of probabilities over the formula vocabulary, in "
                                "nca.domains.boolean.formulas.VOCABULARY order.")
FORMULA_LENGTH = Constructor("nca.boolean.formula-length", "1", 0,
                             "Positive int: the number of words in a prefix formula.")
ARITY_PRIOR = Constructor("nca.boolean.arity-prior", "1", 0,
                          "nca.priors.ArityPrior: a weighted arity automaton including the "
                          "formula syntax restriction.")

CONSTRUCTORS = (BOOLEAN, FORMULA_TEXT, NOISY_WORD, WORD_DISTRIBUTION, FORMULA_LENGTH,
                ARITY_PRIOR)
