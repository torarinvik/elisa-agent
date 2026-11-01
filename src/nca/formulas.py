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

import math
from collections.abc import Callable, Iterable, Sequence
from dataclasses import dataclass
from functools import lru_cache

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


def sequence_log_weight(log_probs: np.ndarray, alphabet: Sequence[int],
                        selected: Sequence[int]) -> float:
    """Log product of a selected sequence's position-wise weights (§21.5)."""
    if log_probs.shape != (len(selected), len(alphabet)):
        raise ValueError("weights must have one row per selected symbol and one column per class")
    native_weight = getattr(_NATIVE, "sequence_log_weight", None)
    if native_weight is not None:
        return float(native_weight(np.asarray(log_probs, dtype=np.float64).reshape(-1),
                                   np.asarray(alphabet, dtype=np.int64),
                                   np.asarray(selected, dtype=np.int64)))
    symbols = tuple(alphabet)
    try:
        return float(sum(log_probs[k, symbols.index(a)] for k, a in enumerate(selected)))
    except ValueError:
        return -math.inf


def parse(arities: Sequence[int]) -> list[list[int]] | None:
    """Parse a prefix formula, using the native binary-arity parser when built."""
    native = getattr(_NATIVE, "parse_tree", None)
    if native is not None and all(a in (0, 1, 2) for a in arities):
        result = native(np.asarray(arities, dtype=np.int64))
        return ([[c for c in result[2 * k:2 * k + 2] if c >= 0]
                 for k in range(len(arities))] if result else None)
    return parse_reference(arities)


def parse_reference(arities: Sequence[int]) -> list[list[int]] | None:
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
class ArityPrior:
    """Weighted deterministic arity automaton (§27).

    Missing transitions are -1. Log edge and final weights may be -inf.
    Formula priors must incorporate the format constraint in their automaton.
    Arrays are copied and made read-only so decoded risks retain their prior.
    """

    alphabet: tuple[int, ...]
    transitions: np.ndarray
    log_weights: np.ndarray
    log_final: np.ndarray
    start: int = 0

    def __post_init__(self) -> None:
        alphabet = tuple(self.alphabet)
        transitions = np.array(self.transitions, copy=True)
        weights = np.array(self.log_weights, dtype=np.float64, copy=True)
        final = np.array(self.log_final, dtype=np.float64, copy=True)
        if (not alphabet or len(set(alphabet)) != len(alphabet)
                or any(a not in (0, 1, 2) for a in alphabet)
                or final.ndim != 1 or not len(final)
                or transitions.shape != (len(final), len(alphabet))
                or not np.issubdtype(transitions.dtype, np.integer)
                or weights.shape != transitions.shape
                or not isinstance(self.start, (int, np.integer))
                or not 0 <= self.start < len(final)
                or np.any(transitions < -1) or np.any(transitions >= len(final))
                or np.any(np.isnan(weights)) or np.any(np.isposinf(weights))
                or np.any(np.isnan(final)) or np.any(np.isposinf(final))):
            raise ValueError("invalid weighted arity automaton")
        object.__setattr__(self, "alphabet", alphabet)
        for name, array in (("transitions", transitions.astype(np.int64)),
                            ("log_weights", weights), ("log_final", final)):
            array.setflags(write=False)
            object.__setattr__(self, name, array)

    def log_weight(self, arities: Sequence[int]) -> float:
        """Log prior weight, or -inf for a forbidden sequence."""
        native = getattr(_NATIVE, "prior_log_weight", None)
        if native is not None:
            return float(native(np.asarray(self.alphabet, dtype=np.int64),
                                self.transitions.reshape(-1), self.log_weights.reshape(-1),
                                self.log_final, self.start, np.asarray(arities, dtype=np.int64)))
        state, total = self.start, 0.0
        for a in arities:
            if a not in self.alphabet:
                return -math.inf
            j = self.alphabet.index(a)
            target = int(self.transitions[state, j])
            if target < 0:
                return -math.inf
            total += float(self.log_weights[state, j])
            state = target
        return total + float(self.log_final[state])

    def log_evidence(self, log_posteriors: np.ndarray, log_base: np.ndarray) -> float:
        """Relative log evidence Z(q)/Z(base) for a base-prior tilt (§27.5).

        Rows must be normalized probabilities from the same observation model.
        Candidate priors must share the same base and posterior rows. This is
        evidence relative to the common observation marginal, not a risk bound.
        """
        posterior = np.asarray(log_posteriors, dtype=np.float64)
        base = np.asarray(log_base, dtype=np.float64)
        if (posterior.ndim != 2 or posterior.shape != base.shape
                or posterior.shape[1] != len(self.alphabet) or not len(posterior)):
            raise ValueError("requires matching nonempty posterior and base rows")
        for rows in (posterior, base):
            if (np.any(np.isnan(rows)) or np.any(rows > 0)
                    or not np.allclose(np.exp(rows).sum(axis=1), 1.0, rtol=0, atol=1e-12)):
                raise ValueError("evidence rows must be normalized log probabilities")
        if np.any(np.isneginf(base) & np.isfinite(posterior)):
            raise ValueError("posterior support must lie within base support")
        denominator = self.log_normalizer(base)
        if denominator == -math.inf:
            raise ValueError("candidate prior has zero mass under the base")
        return self.log_normalizer(posterior) - denominator

    def _rows(self, log_probs: np.ndarray) -> np.ndarray:
        rows = np.asarray(log_probs, dtype=np.float64)
        if (rows.ndim != 2 or rows.shape[1] != len(self.alphabet)
                or np.any(np.isnan(rows)) or np.any(np.isposinf(rows))):
            raise ValueError("requires finite or -inf log weights over the prior alphabet")
        return rows

    def log_normalizer(self, log_probs: np.ndarray) -> float:
        """Total accepted log weight, using two native state rows when available."""
        rows = self._rows(log_probs)
        if not len(rows):
            return -math.inf
        native = getattr(_NATIVE, "prior_normalizer", None)
        if native is not None:
            return float(native(np.ascontiguousarray(rows).reshape(-1),
                                np.asarray(self.alphabet, dtype=np.int64),
                                self.transitions.reshape(-1), self.log_weights.reshape(-1),
                                self.log_final, self.start))
        result = self.decode(rows)
        return -math.inf if result is None else result.log_z

    def decode(self, log_probs: np.ndarray) -> Decoded | None:
        """Sum, maximize and marginalize reading weight times prior weight."""
        rows = self._rows(log_probs)
        m, width = rows.shape
        if not m:
            return None
        native = getattr(_NATIVE, "decode_prior", None)
        if native is not None:
            out = np.asarray(native(np.ascontiguousarray(rows).reshape(-1),
                                    np.asarray(self.alphabet, dtype=np.int64),
                                    self.transitions.reshape(-1), self.log_weights.reshape(-1),
                                    self.log_final, self.start))
            if not len(out):
                return None
            return Decoded(tuple(int(a) for a in out[1:m + 1]), float(out[0]),
                           out[m + 1:].reshape(m, width), self)
        states = len(self.log_final)
        forward = np.full((m + 1, states), -np.inf)
        backward = np.full_like(forward, -np.inf)
        best = np.full_like(forward, -np.inf)
        forward[0, self.start] = 0.0
        backward[m] = best[m] = self.log_final
        for k in range(m):
            for state in range(states):
                for j, target in enumerate(self.transitions[state]):
                    if target >= 0:
                        weight = rows[k, j] + self.log_weights[state, j]
                        forward[k + 1, target] = np.logaddexp(
                            forward[k + 1, target], forward[k, state] + weight)
        log_z = float(np.logaddexp.reduce(forward[m] + self.log_final))
        if not math.isfinite(log_z):
            return None
        marginals = np.zeros_like(rows)
        for k in reversed(range(m)):
            for state in range(states):
                for j, target in enumerate(self.transitions[state]):
                    if target >= 0:
                        weight = rows[k, j] + self.log_weights[state, j]
                        through = weight + backward[k + 1, target]
                        backward[k, state] = np.logaddexp(backward[k, state], through)
                        best[k, state] = max(best[k, state], weight + best[k + 1, target])
                        marginals[k, j] += math.exp(forward[k, state] + through - log_z)
        selected, state = [], self.start
        for k in range(m):
            candidates = [rows[k, j] + self.log_weights[state, j] + best[k + 1, target]
                          if target >= 0 else -np.inf
                          for j, target in enumerate(self.transitions[state])]
            j = int(np.argmax(candidates))
            selected.append(self.alphabet[j])
            state = int(self.transitions[state, j])
        return Decoded(tuple(selected), log_z, marginals, self)


@lru_cache(maxsize=32)
def format_prior(length: int) -> ArityPrior:
    """Unit-weight prefix counter as a prior automaton for a fixed length."""
    if not isinstance(length, int) or length < 1:
        raise ValueError("length must be a positive integer")
    states = length + 2
    transitions = np.full((states, 3), -1, dtype=np.int64)
    for state in range(1, states):
        for arity in range(3):
            if state - 1 + arity < states:
                transitions[state, arity] = state - 1 + arity
    final = np.full(states, -np.inf)
    final[0] = 0.0
    return ArityPrior((0, 1, 2), transitions, np.zeros((states, 3)), final, start=1)


@dataclass(frozen=True)
class PriorSelection:
    index: int
    scores: tuple[float, ...]
    samples: int
    score_error: float = 0.0
    score_clip: float | None = None
    alpha: float | None = None


def select_prior(candidates: Sequence[Callable[[int], ArityPrior | None]],
                 readings: Iterable[np.ndarray], log_base: np.ndarray,
                 alphabet: Sequence[int] = (0, 1, 2), *,
                 score_error: float = 0.0, score_clip: float | None = None,
                 alpha: float | None = None) -> PriorSelection:
    """Empirical summed-evidence selection on unlabeled held-out readings.

    With a supplied uniform error bound on summed scores, choose the first
    candidate within twice that bound of the empirical best (§27.9). Order
    must be declared in advance, broadest support first if that is the policy.
    The default is empirical maximization with exact ties. This API does not
    estimate or certify score_error; it also performs no risk certification
    or automatic installation. Without clipping, None providers are excluded;
    with clipping, unavailability receives -B. Zero base mass in a provided
    model remains invalid rather than zero evidence.
    Supplying score_clip B and alpha clips each log evidence to [-B,B] and
    derives B*sqrt(2*n*log(2*K/alpha)) as the simultaneous total-score error.
    This requires IID observations, fixed models/base/B/K, and valid base
    normalizers wherever a provider supplies a model. It bounds clipped-score means, not raw evidence
    or answer errors. The concentration step is not formalized in Lean.
    """
    if not math.isfinite(score_error) or score_error < 0:
        raise ValueError("score_error must be finite and nonnegative")
    if (score_clip is None) != (alpha is None):
        raise ValueError("score_clip and alpha must be supplied together")
    if score_clip is not None:
        if (not math.isfinite(score_clip) or score_clip <= 0 or alpha is None
                or not math.isfinite(alpha) or not 0 < alpha < 1 or score_error != 0):
            raise ValueError("bounded scoring requires positive finite clipping, 0 < alpha < 1, and no manual error")
    candidates = tuple(candidates)
    alphabet = tuple(alphabet)
    base = np.array(log_base, dtype=np.float64, copy=True)
    base.setflags(write=False)
    if (not candidates or base.shape != (len(alphabet),)
            or np.any(np.isnan(base)) or np.any(base > 0)
            or not np.isclose(np.exp(base).sum(), 1.0, rtol=0, atol=1e-12)):
        raise ValueError("requires candidates and a normalized shared base vector")
    scores = [0.0] * len(candidates)
    models: dict[tuple[int, int], tuple[ArityPrior, float] | None] = {}
    count = 0
    for observation in readings:
        rows = np.asarray(observation, dtype=np.float64)
        if rows.ndim != 2 or not len(rows) or rows.shape[1] != len(alphabet):
            raise ValueError("readings must be nonempty matrices over the shared alphabet")
        common = np.broadcast_to(base, rows.shape)
        # Validate every observation even after some candidates become unavailable.
        if (np.any(np.isnan(rows)) or np.any(rows > 0)
                or not np.allclose(np.exp(rows).sum(axis=1), 1.0, rtol=0, atol=1e-12)
                or np.any(np.isneginf(common) & np.isfinite(rows))):
            raise ValueError("readings must be normalized and supported by the shared base")
        for i, provider in enumerate(candidates):
            if scores[i] == -math.inf:
                continue
            key = (i, len(rows))
            if key not in models:
                prior = provider(len(rows))
                if prior is None:
                    models[key] = None
                else:
                    if prior.alphabet != alphabet:
                        raise ValueError("candidate alphabet must match the shared base")
                    denominator = prior.log_normalizer(common)
                    if denominator == -math.inf:
                        raise ValueError("candidate prior has zero mass under the base")
                    models[key] = prior, denominator
            model = models[key]
            if model is None:
                if score_clip is None:
                    scores[i] = -math.inf
                    continue
                evidence = -score_clip
            else:
                prior, denominator = model
                evidence = prior.log_normalizer(rows) - denominator
            if math.isnan(evidence) or evidence == math.inf:
                raise ValueError("candidate evidence must be finite or negative infinity")
            if score_clip is not None:
                evidence = max(-score_clip, min(score_clip, evidence))
            scores[i] += evidence
            if not math.isfinite(scores[i]) and math.isfinite(evidence):
                raise ValueError("summed evidence overflow")
        count += 1
    if not count or not any(math.isfinite(score) for score in scores):
        raise ValueError("requires observations and at least one finite-evidence candidate")
    if score_clip is not None:
        assert alpha is not None
        score_error = score_clip * math.sqrt(2 * count * (math.log(2 * len(candidates)) - math.log(alpha)))
        if not math.isfinite(score_error):
            raise ValueError("derived score error overflow")
    best = max(range(len(scores)), key=scores.__getitem__)
    chosen = (best if score_error == 0 else next(
        i for i, score in enumerate(scores) if math.isfinite(score)
        and scores[best] / 2 - score / 2 <= score_error))
    return PriorSelection(chosen, tuple(scores), count, score_error, score_clip, alpha)


@lru_cache(maxsize=32)
def complete_prior(length: int) -> ArityPrior | None:
    """Unit-weight complete binary skeleton prior inferred from length (§27.4).

    Leaves may be constants or unary negations of constants. Unsupported
    lengths return None. This is a structural prior, not a reader calibration.
    """
    if not isinstance(length, int) or length < 1:
        raise ValueError("length must be a positive integer")
    depth = (length + 1).bit_length() - 2
    if length + 1 > 3 * 2 ** depth:
        return None
    pending = [(depth,)]
    indices = {pending[0]: 0}
    transitions: list[list[int]] = []
    for stack in pending:
        row = [-1, -1, -1]
        if stack:
            head, rest = stack[0], stack[1:]
            successors = ({2: (head - 1, head - 1, *rest)} if head > 0 else
                          {0: rest, 1: (-1, *rest)} if head == 0 else {0: rest})
            for arity, target in successors.items():
                if target not in indices:
                    indices[target] = len(pending)
                    pending.append(target)
                row[arity] = indices[target]
        transitions.append(row)
    final = np.full(len(pending), -np.inf)
    final[indices[()]] = 0.0
    return ArityPrior((0, 1, 2), np.array(transitions, dtype=np.int64),
                      np.zeros((len(pending), 3)), final)


@lru_cache(maxsize=16)
def height_prior(height: int) -> ArityPrior:
    """Unit-weight prefix trees of height at most ``height`` (§27.4).

    Height counts edges; a constant has height zero. Unlike the complete-tree
    prior, branches may end early and unary nodes may occur at any level.
    """
    if not isinstance(height, int) or height < 0:
        raise ValueError("height must be a nonnegative integer")
    pending = [(height,)]
    indices = {pending[0]: 0}
    transitions: list[list[int]] = []
    for stack in pending:
        row = [-1, -1, -1]
        if stack:
            head, rest = stack[0], stack[1:]
            successors = {0: rest}
            if head:
                successors |= {1: (head - 1, *rest), 2: (head - 1, head - 1, *rest)}
            for arity, target in successors.items():
                if target not in indices:
                    indices[target] = len(pending)
                    pending.append(target)
                row[arity] = indices[target]
        transitions.append(row)
    final = np.full(len(pending), -np.inf)
    final[indices[()]] = 0.0
    return ArityPrior((0, 1, 2), np.array(transitions, dtype=np.int64),
                      np.zeros((len(pending), 3)), final)


@dataclass(frozen=True)
class Decoded:
    """Maximum-weight accepted arity sequence, log normalizer and marginals.

    Acceptance is the prefix format by default, or the supplied prior automaton.
    Posterior weights include the prior when present.
    """

    arities: tuple[int, ...]
    log_z: float
    marginals: np.ndarray
    prior: ArityPrior | None = None

    def log_weight(self, log_probs: np.ndarray, alphabet: Sequence[int],
                   arities: Sequence[int]) -> float:
        """Log weight of a sequence under readings and the optional prior."""
        if self.prior is not None and tuple(alphabet) != self.prior.alphabet:
            raise ValueError("alphabet must match the decoded prior")
        reading = sequence_log_weight(log_probs, alphabet, arities)
        return reading + (0.0 if self.prior is None else self.prior.log_weight(arities))

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
    ``2(j − 1)`` of each word's most probable arity sequence. ``j`` starts at
    ``band_changes`` and widens until the tail bound is at most ``slack``
    times the band's weight, so the risk is within ``slack`` of the exact one
    (THEORY §23.3). ``None`` if no parseable sequence has positive weight."""
    m = len(log_probs)
    if m == 0:
        return None
    reference = np.argmax(log_probs, axis=1)
    changes, tail = band_changes(log_probs, reference, slack)
    probs = np.exp(log_probs)
    off = float(np.sum(probs.sum(axis=1) - probs[np.arange(m), reference]))
    centre = 1 + np.concatenate(([0], np.cumsum(np.asarray(alphabet)[reference] - 1)))
    while True:
        half = 2 * (changes - 1)
        if half > m:  # the band holds every state 0 ..= m − k at every k
            tail = 0.0
        passes = _banded_passes(log_probs, alphabet, centre, half)
        log_tail = math.log(tail) if tail > 0 else -math.inf
        if passes is not None and log_tail <= math.log(slack) + passes[0]:
            break
        if tail == 0.0:
            return None
        changes += 1
        tail *= off / changes
    log_z, log_x, arities = passes
    risk = max(0.0, 1.0 - math.exp(log_x - float(np.logaddexp(log_z, log_tail))))
    return Banded(arities, risk, log_x >= log_tail, changes, 2 * half + 1)


def _banded_passes(log_probs: np.ndarray, alphabet: Sequence[int], centre: np.ndarray,
                   half: int) -> tuple[float, float, tuple[int, ...]] | None:
    """Sum and max passes over states within ``half`` of ``centre``: the log
    weight of the band, the log weight of its best sequence, and that sequence."""
    m = len(log_probs)
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
    if forward[m, 0] == -np.inf:
        return None
    arities = []
    state = 0
    for k in range(m, 0, -1):
        a = alphabet[int(choice[k, state])]
        arities.append(a)
        state = state + 1 - a
    return float(forward[m, 0]), float(best[m, 0]), tuple(reversed(arities))


class Split:
    """Forward and backward vectors of the decoding programs, in log space,
    kept valid around a cursor so that a change to one word's weights is
    rescored from the vectors on either side of it (THEORY §23.4, Theorems
    23.7–23.9). With ``centre`` and ``half``, the programs are restricted to
    counter values within ``half`` of ``centre[k]`` at position ``k``, a band
    fixed for the object's lifetime. Forward vectors ``0 ..= ahead`` and
    backward vectors ``behind ..= m`` are current; ``swept`` counts the
    positions recomputed."""

    def __init__(self, log_probs: np.ndarray, alphabet: Sequence[int] = (0, 1, 2),
                 centre: np.ndarray | None = None, half: int | None = None) -> None:
        self.log_probs = np.array(log_probs, dtype=np.float64)
        m = len(self.log_probs)
        self.alphabet = tuple(alphabet)
        self.arities = np.asarray(alphabet, dtype=np.int64)
        width = m + 2
        self.width = width
        position = np.arange(m + 1)
        if centre is None or half is None:
            self.low, self.high = np.zeros(m + 1, dtype=np.int64), m - position
        else:
            self.low = np.maximum(0, centre - half)
            self.high = np.minimum(m - position, centre + half)
        self.low = np.ascontiguousarray(self.low, dtype=np.int64)
        self.high = np.ascontiguousarray(self.high, dtype=np.int64)
        # The native kernel keeps the sum tables in linear space, each row of total 1 with
        # its log scale beside it (THEORY §23.7); the NumPy path keeps them in log space.
        start, empty = (1.0, 0.0) if _NATIVE is not None else (0.0, -np.inf)
        self.weights = np.exp(self.log_probs)
        self.forward = np.full((m + 1, width), empty)
        self.backward = np.full((m + 1, width), empty)
        self.forward_scale = np.full(m + 1, -np.inf)
        self.backward_scale = np.full(m + 1, -np.inf)
        self.forward_max = np.full((m + 1, width), -np.inf)
        self.backward_max = np.full((m + 1, width), -np.inf)
        if self.low[0] <= 1 <= self.high[0]:
            self.forward[0, 1], self.forward_max[0, 1], self.forward_scale[0] = start, 0.0, 0.0
        if self.low[m] <= 0:
            self.backward[m, 0], self.backward_max[m, 0], self.backward_scale[m] = start, 0.0, 0.0
        self.ahead, self.behind, self.swept = 0, m, 0
        self._advance(m)
        self._retreat(0)
        self.swept = 0

    def _moves(self, i: int) -> list[tuple[int, int, int, int]]:
        """For each arity ``a`` (index ``j``), the run of in-band states
        ``s ≥ 1`` at position ``i`` whose successor ``s − 1 + a`` is in band at
        ``i + 1``: ``(j, s0, length, t0)``."""
        moves = []
        for j, a in enumerate(self.alphabet):
            s0 = max(int(self.low[i]), 1, int(self.low[i + 1]) + 1 - a)
            s1 = min(int(self.high[i]), int(self.high[i + 1]) + 1 - a)
            if s1 >= s0:
                moves.append((j, s0, s1 - s0 + 1, s0 - 1 + a))
        return moves

    def _advance(self, k: int) -> None:
        """Make forward vectors current through position ``k``."""
        if _NATIVE is not None and self.ahead < k:
            self.swept += _NATIVE.advance(self.forward.reshape(-1), self.forward_scale,
                                          self.forward_max.reshape(-1), self.weights.reshape(-1),
                                          self.log_probs.reshape(-1), self.arities, self.low,
                                          self.high, self.width, self.ahead, k)
            self.ahead = k
        while self.ahead < k:
            i = self.ahead
            band = slice(int(self.low[i + 1]), int(self.high[i + 1]) + 1)
            self.forward[i + 1, band] = self.forward_max[i + 1, band] = -np.inf
            for j, s0, n, t0 in self._moves(i):
                step = self.log_probs[i, j]
                self.forward[i + 1, t0:t0 + n] = np.logaddexp(
                    self.forward[i + 1, t0:t0 + n], self.forward[i, s0:s0 + n] + step)
                self.forward_max[i + 1, t0:t0 + n] = np.maximum(
                    self.forward_max[i + 1, t0:t0 + n], self.forward_max[i, s0:s0 + n] + step)
            self.ahead += 1
            self.swept += 1

    def _retreat(self, k: int) -> None:
        """Make backward vectors current from position ``k``."""
        if _NATIVE is not None and self.behind > k:
            self.swept += _NATIVE.retreat(self.backward.reshape(-1), self.backward_scale,
                                          self.backward_max.reshape(-1), self.weights.reshape(-1),
                                          self.log_probs.reshape(-1), self.arities, self.low,
                                          self.high, self.width, self.behind, k)
            self.behind = k
        while self.behind > k:
            i = self.behind - 1
            band = slice(int(self.low[i]), int(self.high[i]) + 1)
            self.backward[i, band] = self.backward_max[i, band] = -np.inf
            for j, s0, n, t0 in self._moves(i):
                step = self.log_probs[i, j]
                self.backward[i, s0:s0 + n] = np.logaddexp(
                    self.backward[i, s0:s0 + n], self.backward[i + 1, t0:t0 + n] + step)
                self.backward_max[i, s0:s0 + n] = np.maximum(
                    self.backward_max[i, s0:s0 + n], self.backward_max[i + 1, t0:t0 + n] + step)
            self.behind -= 1
            self.swept += 1

    def scores(self, k: int, row: np.ndarray) -> tuple[float, float]:
        """``log Z`` and the best log weight with word ``k``'s log weights
        replaced by ``row``, from the vectors before and after it."""
        self._advance(k)
        self._retreat(k + 1)
        if _NATIVE is not None:
            log_row = np.ascontiguousarray(row, dtype=np.float64)
            log_z, log_x = _NATIVE.scores(self.forward.reshape(-1), self.forward_scale,
                                          self.forward_max.reshape(-1), self.backward.reshape(-1),
                                          self.backward_scale, self.backward_max.reshape(-1),
                                          self.arities, self.low, self.high, self.width, k,
                                          np.exp(log_row), log_row)
            return float(log_z), float(log_x)
        log_z = log_x = -np.inf
        for j, s0, n, t0 in self._moves(k):
            log_z = np.logaddexp(log_z, np.logaddexp.reduce(
                self.forward[k, s0:s0 + n] + self.backward[k + 1, t0:t0 + n]) + row[j])
            best = self.forward_max[k, s0:s0 + n] + self.backward_max[k + 1, t0:t0 + n]
            log_x = max(log_x, float(best.max()) + row[j])
        return float(log_z), log_x

    def best(self, k: int) -> tuple[float, tuple[int, ...]]:
        """The best log weight and a sequence attaining it, traced from the
        max vectors before and after word ``k`` (THEORY §23.4, Theorem 23.10)."""
        self._advance(k)
        self._retreat(k + 1)
        if _NATIVE is not None:
            out = np.asarray(_NATIVE.trace(self.forward_max.reshape(-1), self.backward_max.reshape(-1),
                                           self.log_probs.reshape(-1), self.arities, self.low,
                                           self.high, self.width, k))
            return float(out[0]), tuple(int(a) for a in out[1:])
        m, alphabet = len(self.log_probs), self.alphabet
        log_x, state, choice = -np.inf, 0, 0
        for j, s0, n, t0 in self._moves(k):
            best = self.forward_max[k, s0:s0 + n] + self.backward_max[k + 1, t0:t0 + n]
            t = int(np.argmax(best))
            if best[t] + self.log_probs[k, j] > log_x:
                log_x, state, choice = float(best[t] + self.log_probs[k, j]), s0 + t, j
        arities = [0] * m
        arities[k] = alphabet[choice]
        before = state
        for i in reversed(range(k)):
            options = [(self.forward_max[i, n] + self.log_probs[i, j], n, a)
                       for j, a in enumerate(alphabet)
                       for n in (before + 1 - a,) if max(1, self.low[i]) <= n <= self.high[i]]
            _, before, arities[i] = max(options)
        after = state - 1 + alphabet[choice]
        for i in range(k + 1, m):
            options = [(self.log_probs[i, j] + self.backward_max[i + 1, n], n, a)
                       for j, a in enumerate(alphabet)
                       for n in (after - 1 + a,) if after >= 1 and self.low[i + 1] <= n <= self.high[i + 1]]
            _, after, arities[i] = max(options)
        return log_x, tuple(arities)

    def climb(self, k: int, row: np.ndarray) -> tuple[float, float]:
        """Replace word ``k``'s log weights by ``row`` and return the new
        ``log Z`` and best log weight. Vectors that depend on word ``k`` (forward
        after it, backward before it) stop being current."""
        result = self.scores(k, row)
        self.log_probs[k] = row
        self.weights[k] = np.exp(row)
        self.ahead = min(self.ahead, k)
        self.behind = max(self.behind, k + 1)
        return result


class CertifiedSplit:
    """Fixed-reference banded cursor with relative-tail and maximum certificates.

    Uses the native Split sweeps when built. Weights must be probabilities
    over arities 0–2; bounds refer to this decoding model (THEORY §23.3–23.4).
    """

    def __init__(self, log_probs: np.ndarray, alphabet: Sequence[int] = (0, 1, 2),
                 slack: float = 1e-4) -> None:
        if not 0 < slack < 1:
            raise ValueError("slack must be strictly between zero and one")
        self.log_probs = np.array(log_probs, dtype=np.float64)
        self.alphabet = tuple(alphabet)
        if (self.log_probs.ndim != 2 or not len(self.log_probs)
                or self.log_probs.shape[1] != len(alphabet) or not self.alphabet
                or len(set(self.alphabet)) != len(self.alphabet)
                or any(a not in (0, 1, 2) for a in alphabet)):
            raise ValueError("requires nonempty rows of arity 0–2 weights")
        self._validate(self.log_probs)
        self.slack = slack
        self.reference = np.argmax(self.log_probs, axis=1)
        self.centre = 1 + np.concatenate(([0], np.cumsum(
            np.asarray(alphabet)[self.reference] - 1)))
        self.changes = band_changes(self.log_probs, self.reference, slack)[0]
        self.rebuilds = 0
        self.log_upper: float | None = None
        self.split = self._build()

    @staticmethod
    def _validate(rows: np.ndarray) -> None:
        if (np.any(np.isnan(rows)) or np.any(rows > 0)
                or np.any(np.exp(rows).sum(axis=-1) > 1 + 1e-12)):
            raise ValueError("rows must contain log probabilities with mass at most one")

    def _build(self) -> Split:
        return Split(self.log_probs, self.alphabet, self.centre, 2 * (self.changes - 1))

    def _certify(self, k: int, scores: tuple[float, float] | None,
                 maximum: bool) -> tuple[float, int] | None:
        """Certify the normalizer, optionally requiring a global maximum."""
        self.log_upper = None
        m = len(self.log_probs)
        probabilities = np.exp(self.log_probs)
        off = float(np.sum(probabilities.sum(axis=1)
                           - probabilities[np.arange(m), self.reference]))
        while True:
            half = 2 * (self.changes - 1)
            log_tail = (-math.inf if half > m or off <= 0 else
                        self.changes * math.log(off) - math.lgamma(self.changes + 1))
            log_z, log_x = (scores if scores is not None else
                            self.split.scores(k, self.log_probs[k]))
            if (math.isfinite(log_z) and log_tail <= math.log(self.slack) + log_z
                    and (not maximum or log_x >= log_tail)):
                upper = float(np.logaddexp(log_z, log_tail))
                self.log_upper = upper
                return log_x, half
            if half > m:
                return None
            self.changes += 1
            self.rebuilds += 1
            self.split = self._build()
            scores = None

    def normalizer(self, k: int = 0,
                   scores: tuple[float, float] | None = None) -> float | None:
        """Upper-bound total accepted weight in log space without tracing an answer."""
        self._certify(k, scores, maximum=False)
        return self.log_upper

    def result(self, k: int = 0,
               scores: tuple[float, float] | None = None) -> Banded | None:
        """Widen until both relative slack and exact-maximum certificates hold."""
        certified = self._certify(k, scores, maximum=True)
        if certified is None:
            return None
        log_x, half = certified
        _, arities = self.split.best(k)
        assert self.log_upper is not None
        risk = max(0.0, float(-np.expm1(min(0.0, log_x - self.log_upper))))
        return Banded(arities, risk, True, self.changes, 2 * half + 1)

    def sequence_risk(self, arities: Sequence[int]) -> float:
        """Upper-bound any accepted sequence's risk, including outside the band.

        Requires a successful result or normalizer certificate for the current rows.
        The normalizer bound
        and relative slack apply independently of which accepted answer is scored
        (THEORY §23.3). This is a model bound, not a floating-point enclosure.
        """
        if len(arities) != len(self.log_probs):
            raise ValueError("sequence must be a complete prefix formula of matching length")
        native = getattr(_NATIVE, "accepted_log_weight", None)
        if native is not None:
            accepted = native(self.log_probs.reshape(-1),
                              np.asarray(self.alphabet, dtype=np.int64),
                              np.asarray(arities, dtype=np.int64))
            if not accepted:
                raise ValueError("sequence must be accepted by the arity alphabet")
            weight = float(accepted[0])
        else:
            if parse(arities) is None or any(a not in self.alphabet for a in arities):
                raise ValueError("sequence must be accepted by the arity alphabet")
            weight = sequence_log_weight(self.log_probs, self.alphabet, arities)
        if self.log_upper is None:
            raise ValueError("requires a successful result for the current rows")
        return max(0.0, float(-np.expm1(min(0.0, weight - self.log_upper))))

    def _replace(self, k: int, row: np.ndarray) -> tuple[float, float]:
        """Replace one validated row and retain the reference and band."""
        row = np.asarray(row, dtype=np.float64)
        if row.shape != (len(self.alphabet),):
            raise ValueError("row width must match the alphabet")
        self._validate(row)
        scores = self.split.climb(k, row)
        self.log_probs[k] = row
        self.log_upper = None
        return scores

    def climb(self, k: int, row: np.ndarray) -> Banded | None:
        """Replace one probability row and certify a maximum and its risk."""
        return self.result(k, self._replace(k, row))

    def climb_normalizer(self, k: int, row: np.ndarray) -> float | None:
        """Replace one probability row and certify only the normalizer."""
        return self.normalizer(k, self._replace(k, row))


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
