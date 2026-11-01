"""Noisy Boolean formulas in prefix notation (§18).

A formula is a complete binary tree of depth ``depth`` whose levels alternate
between ``and`` and ``or`` (root chosen at random); with probability ``xor``
a connective is ``xor`` instead. Leaves are uniform random constants, each
negated with probability ``negation``. It is written in prefix (Polish)
notation, one word per node, so no brackets are needed: arities alone
determine the tree (``NCA.code_prefix``).

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

import math
from collections.abc import Sequence
from dataclasses import dataclass

import numpy as np

from nca import native

VOCABULARY = ("true", "false", "not", "and", "or", "xor")
ARITY = (0, 0, 1, 2, 2, 2)
ALPHABET = "abcdefghijklmnopqrstuvwxyz"
SPLITS = ("train", "validation", "test")

_NATIVE = native.load("decoding")


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
            negation: float = 0.25) -> list[str]:
    """Words of a random complete alternating formula, in prefix order."""
    def node(conjunction: bool, d: int) -> list[str]:
        if d == 0:
            leaf = [VOCABULARY[rng.integers(2)]]
            return ["not", *leaf] if rng.random() < negation else leaf
        op = "xor" if rng.random() < xor else "and" if conjunction else "or"
        return [op, *node(not conjunction, d - 1), *node(not conjunction, d - 1)]

    return node(bool(rng.integers(2)), depth)


def parse(arities: Sequence[int]) -> list[list[int]] | None:
    """Children of each word of a prefix formula, by position; ``None`` if the
    arities do not form exactly one formula."""
    children: list[list[int]] = [[] for _ in arities]

    def subtree(k: int) -> int:
        end = k + 1
        for _ in range(arities[k]):
            if end >= len(arities):
                raise ValueError("formula ends early")
            children[k].append(end)
            end = subtree(end)
        return end

    try:
        return children if arities and subtree(0) == len(arities) else None
    except ValueError:
        return None


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
class Decoded:
    """The most probable parseable arity sequence under per-word arity
    probabilities, with the log of the total weight of all parseable
    sequences, and each word's posterior arity distribution (rows over the
    arity alphabet)."""

    arities: tuple[int, ...]
    log_z: float
    marginals: np.ndarray

    def log_weight(self, log_probs: np.ndarray, alphabet: Sequence[int],
                   arities: Sequence[int]) -> float:
        """Log weight of a sequence under the per-word log-probabilities."""
        return float(sum(log_probs[k, alphabet.index(a)] for k, a in enumerate(arities)))

    def risk(self, log_probs: np.ndarray, alphabet: Sequence[int],
             arities: Sequence[int] | None = None) -> float:
        """Posterior probability that the true sequence differs from
        ``arities`` (default: the decoded one), ``1 − weight / Z``."""
        chosen = self.arities if arities is None else arities
        return max(0.0, 1.0 - math.exp(self.log_weight(log_probs, alphabet, chosen) - self.log_z))


def decode(log_probs: np.ndarray, alphabet: Sequence[int] = (0, 1, 2)) -> Decoded | None:
    """Decode an arity sequence from per-word arity log-probabilities
    (``log_probs[k, j]`` for arity ``alphabet[j]``) by the counter automaton:
    the state is the number of subformulas still awaited, starting at 1; a
    word of arity ``a`` read while ``n ≥ 1`` are awaited leaves ``n − 1 + a``;
    the sequence is accepted when none remain at its end. ``None`` if no
    parseable sequence has positive weight.

    Uses the native kernel ``nca.native.decoding`` when it is built, and
    ``decode_reference`` otherwise; the two agree to rounding."""
    if _NATIVE is None or len(log_probs) == 0:
        return decode_reference(log_probs, alphabet)
    m = len(log_probs)
    flat = np.ascontiguousarray(log_probs, dtype=np.float64).ravel()
    out = np.asarray(_NATIVE.decode(flat, np.asarray(alphabet, dtype=np.int64)))
    if out[0] <= -1e300:
        return None
    return Decoded(tuple(int(a) for a in out[1:m + 1]), float(out[0]),
                   out[m + 1:].reshape(m, len(alphabet)))


def decode_reference(log_probs: np.ndarray, alphabet: Sequence[int] = (0, 1, 2)) -> Decoded | None:
    """``decode`` in NumPy: the dynamic programs in log space, with all states
    ``n ≤ m − k`` that can still be completed at position ``k``."""
    m = len(log_probs)
    if m == 0:
        return None
    width = m + 2
    forward = np.full((m + 1, width), -np.inf)
    best = np.full((m + 1, width), -np.inf)
    choice = np.zeros((m + 1, width), dtype=np.int64)
    forward[0, 1] = best[0, 1] = 0.0
    for k in range(m):
        live = m - k - 1
        for j, a in enumerate(alphabet):
            low, high = a, a + width - 1  # state n ≥ 1 moves to n − 1 + a
            span = min(high, width) - low
            if span <= 0:
                continue
            step = log_probs[k, j]
            forward[k + 1, low:low + span] = np.logaddexp(forward[k + 1, low:low + span],
                                                          forward[k, 1:1 + span] + step)
            candidate = best[k, 1:1 + span] + step
            better = candidate > best[k + 1, low:low + span]
            best[k + 1, low:low + span][better] = candidate[better]
            choice[k + 1, low:low + span][better] = j
        forward[k + 1, live + 1:] = best[k + 1, live + 1:] = -np.inf
    log_z = float(forward[m, 0])
    if log_z == -np.inf:
        return None
    arities = []
    state = 0
    for k in range(m, 0, -1):
        a = alphabet[int(choice[k, state])]
        arities.append(a)
        state = state + 1 - a
    backward = np.full((m + 1, width), -np.inf)
    backward[m, 0] = 0.0
    marginals = np.zeros((m, len(alphabet)))
    for k in range(m - 1, -1, -1):
        for j, a in enumerate(alphabet):
            span = min(a + width - 1, width) - a
            through = log_probs[k, j] + backward[k + 1, a:a + span]
            backward[k, 1:1 + span] = np.logaddexp(backward[k, 1:1 + span], through)
            marginals[k, j] = np.exp(np.logaddexp.reduce(forward[k, 1:1 + span] + through)
                                     - log_z)
    return Decoded(tuple(reversed(arities)), log_z, marginals)


@dataclass(frozen=True)
class Banded:
    """Decoding restricted to a band of counter values around a reference
    sequence (THEORY §23.2–23.3): the most probable parseable sequence in the
    band, the certified risk ``1 − x / (Z_band + U)``, and whether ``x ≥ U``
    certifies that the sequence is also the most probable overall."""

    arities: tuple[int, ...]
    risk: float
    exact: bool
    changes: int
    width: int


def band_changes(log_probs: np.ndarray, reference: Sequence[int], slack: float) -> tuple[int, float]:
    """The least ``j`` with ``S^j / j! ≤ slack``, where ``S`` is the summed
    off-reference arity mass, and the tail bound ``U_j = S^j / j!``."""
    probs = np.exp(log_probs)
    rows = np.arange(len(reference))
    s = float(np.sum(probs.sum(axis=1) - probs[rows, reference]))
    j, tail = 1, s
    while tail > slack:
        j += 1
        tail *= s / j
    return j, tail


def decode_banded(log_probs: np.ndarray, alphabet: Sequence[int] = (0, 1, 2),
                  slack: float = 1e-4) -> Banded | None:
    """``decode`` with the dynamic programs restricted to counter values within
    ``2(j − 1)`` of each word's most probable arity sequence, ``j`` chosen by
    ``band_changes``. ``None`` if no parseable sequence lies in the band."""
    m = len(log_probs)
    if m == 0:
        return None
    reference = np.argmax(log_probs, axis=1)
    changes, tail = band_changes(log_probs, reference, slack)
    half = 2 * (changes - 1)
    centre = 1 + np.concatenate(([0], np.cumsum(np.asarray(alphabet)[reference] - 1)))
    width = m + 2
    states = np.arange(width)
    inside = [(np.abs(states - centre[k]) <= half) & (states <= m - k) for k in range(m + 1)]
    forward = np.full((m + 1, width), -np.inf)
    best = np.full((m + 1, width), -np.inf)
    choice = np.zeros((m + 1, width), dtype=np.int64)
    if inside[0][1]:
        forward[0, 1] = best[0, 1] = 0.0
    for k in range(m):
        for j, a in enumerate(alphabet):
            span = min(a + width - 1, width) - a
            step = log_probs[k, j]
            forward[k + 1, a:a + span] = np.logaddexp(forward[k + 1, a:a + span],
                                                      forward[k, 1:1 + span] + step)
            candidate = best[k, 1:1 + span] + step
            better = candidate > best[k + 1, a:a + span]
            best[k + 1, a:a + span][better] = candidate[better]
            choice[k + 1, a:a + span][better] = j
        forward[k + 1, ~inside[k + 1]] = best[k + 1, ~inside[k + 1]] = -np.inf
    log_z, log_x = float(forward[m, 0]), float(best[m, 0])
    if log_z == -np.inf:
        return None
    arities = []
    state = 0
    for k in range(m, 0, -1):
        a = alphabet[int(choice[k, state])]
        arities.append(a)
        state = state + 1 - a
    log_tail = math.log(tail) if tail > 0 else -math.inf
    risk = max(0.0, 1.0 - math.exp(log_x - float(np.logaddexp(log_z, log_tail))))
    return Banded(tuple(reversed(arities)), risk, log_x >= log_tail, changes, 2 * half + 1)


@dataclass(frozen=True)
class FormulaSample:
    words: tuple[str, ...]
    text: str
    value: bool


class FormulaDataset:
    def __init__(self, split: str, size: int, depth: int, noise: float, seed: int = 0,
                 xor: float = 0.0, negation: float = 0.25) -> None:
        assert split in SPLITS
        self.split, self.size, self.depth, self.noise = split, size, depth, noise
        self.seed, self.xor, self.negation = seed, xor, negation

    def __len__(self) -> int:
        return self.size

    def sample(self, index: int) -> FormulaSample:
        rng = np.random.default_rng([SPLITS.index(self.split), self.seed, index])
        words = formula(self.depth, rng, self.xor, self.negation)
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
