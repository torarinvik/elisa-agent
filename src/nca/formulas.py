"""Noisy Boolean formulas in prefix notation (§18).

By default a formula is a complete binary tree of depth ``depth`` whose levels alternate
between ``and`` and ``or`` (root chosen at random); with probability ``xor``
a connective is ``xor`` instead. Leaves are uniform random constants, each
negated with probability ``negation``. It is written in prefix (Polish)
notation, one word per node, so no brackets are needed: arities alone
determine the tree (``NCA.code_prefix``).
An optional ``early_leaf`` probability stops branches before depth zero,
producing a structural shift while preserving the vocabulary and channel.

Each word passes through a noisy typing channel (``corrupt``) at level
``noise``; spaces are never corrupted. Splits are independent random streams:
``train`` for learned readers, ``validation`` for calibration, ``test`` for
evaluation; different seeds give independent samples of one split, such as
an audit and an evaluation set.

``decode`` corrects arities by the format (§21): the arity sequences of
formulas are exactly the words of a counter automaton (``NCA.accepts_iff_codes``),
so the most probable parseable sequence, the total weight ``Z`` of all of
them and each word's posterior arity follow from dynamic programs over its
states (``NCA.dpSum_eq``, ``NCA.dpMax_ge``, ``NCA.dpMax_attained``).
"""

from __future__ import annotations

from collections.abc import Sequence
from dataclasses import dataclass

import numpy as np

from nca.priors import (
    sequence_log_weight as sequence_log_weight,
    ArityPrior as ArityPrior,
    format_prior as format_prior,
    PriorSelection as PriorSelection,
    select_prior as select_prior,
    complete_prior as complete_prior,
    height_prior as height_prior,
    Decoded as Decoded,
)
from nca.decoding import (
    _NATIVE as _NATIVE,
    parse as parse,
    parse_reference as parse_reference,
    decode as decode,
    decode_reference as decode_reference,
    Banded as Banded,
    band_changes as band_changes,
    decode_banded as decode_banded,
    _banded_passes as _banded_passes,
    Split as Split,
    CertifiedSplit as CertifiedSplit,
)


VOCABULARY = ("true", "false", "not", "and", "or", "xor")
ARITY = (0, 0, 1, 2, 2, 2)
ALPHABET = "abcdefghijklmnopqrstuvwxyz"
SPLITS = ("train", "validation", "test")


def corrupt(word: str, noise: float, rng: np.random.Generator) -> str:
    """Each character is replaced by a random letter with probability
    ``noise / 2``, deleted with probability ``noise / 5``, followed by an
    inserted random letter with probability ``noise / 5``, or swapped with the
    next character with probability ``noise / 10``. Never returns an empty word."""
    def letter() -> str:
        return ALPHABET[rng.integers(len(ALPHABET))]

    out: list[str] = []
    i = 0
    while i < len(word):
        u = rng.random()
        if u < noise * 0.5:
            out.append(letter())
        elif u < noise * 0.7:
            pass
        elif u < noise * 0.9:
            out += [word[i], letter()]
        elif u < noise and i + 1 < len(word):
            out += [word[i + 1], word[i]]
            i += 1
        else:
            out.append(word[i])
        i += 1
    return "".join(out) or letter()


def formula(depth: int, rng: np.random.Generator, xor: float = 0.0,
            negation: float = 0.25, early_leaf: float = 0.0) -> list[str]:
    """Alternating prefix formula, optionally stopping branches before depth zero."""
    if not 0 <= early_leaf <= 1:
        raise ValueError("early_leaf must be between zero and one")
    def node(conjunction: bool, d: int) -> list[str]:
        if d == 0 or (early_leaf > 0 and rng.random() < early_leaf):
            leaf = [VOCABULARY[rng.integers(2)]]
            return ["not", *leaf] if rng.random() < negation else leaf
        op = "xor" if rng.random() < xor else "and" if conjunction else "or"
        return [op, *node(not conjunction, d - 1), *node(not conjunction, d - 1)]

    return node(bool(rng.integers(2)), depth)


def apply(word: str, values: Sequence[bool]) -> bool:
    """The value of a node labeled ``word`` with children of ``values``."""
    if word in ("true", "false"):
        return word == "true"
    if word == "not":
        return not values[0]
    a, b = values
    return a and b if word == "and" else a or b if word == "or" else a != b


def evaluate(words: Sequence[str]) -> bool | None:
    """The value of a prefix formula, ``None`` if the words form none."""
    children = parse([ARITY[VOCABULARY.index(w)] for w in words])
    if children is None:
        return None
    values = [False] * len(words)
    for k in reversed(range(len(words))):
        values[k] = apply(words[k], [values[c] for c in children[k]])
    return values[0]


@dataclass(frozen=True)
class FormulaSample:
    words: tuple[str, ...]
    text: str
    value: bool


class FormulaDataset:
    def __init__(self, split: str, size: int, depth: int, noise: float, seed: int = 0,
                 xor: float = 0.0, negation: float = 0.25, early_leaf: float = 0.0) -> None:
        if not 0 <= early_leaf <= 1:
            raise ValueError("early_leaf must be between zero and one")
        assert split in SPLITS
        self.split, self.size, self.depth, self.noise = split, size, depth, noise
        self.seed, self.xor, self.negation = seed, xor, negation
        self.early_leaf = early_leaf

    def __len__(self) -> int:
        return self.size

    def sample(self, index: int) -> FormulaSample:
        rng = np.random.default_rng([SPLITS.index(self.split), self.seed, index])
        words = formula(self.depth, rng, self.xor, self.negation, self.early_leaf)
        text = " ".join(corrupt(w, self.noise, rng) for w in words)
        value = evaluate(words)
        assert value is not None
        return FormulaSample(tuple(words), text, value)


def labeled_words(dataset: FormulaDataset) -> tuple[list[str], np.ndarray]:
    """The noisy words of every formula, with the index of the true word."""
    words: list[str] = []
    labels: list[int] = []
    for index in range(len(dataset)):
        sample = dataset.sample(index)
        words += sample.text.split()
        labels += [VOCABULARY.index(w) for w in sample.words]
    return words, np.array(labels)
