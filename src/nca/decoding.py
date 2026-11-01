"""Prefix parsing, counter decoding and certified incremental bands (§21–23)."""

from __future__ import annotations

import math
from collections.abc import Sequence
from dataclasses import dataclass

import numpy as np

from nca.native import load
from nca.priors import Decoded, risk_from_log_weight, sequence_log_weight

_NATIVE = load("decoding")


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
        # The linear-space kernel requests log space when it loses precision.
        native_log = getattr(_NATIVE, "decode_log", None)
        if native_log is None:
            return decode_reference(log_probs, alphabet)
        out = np.asarray(native_log(flat, np.asarray(alphabet, dtype=np.int64)))
        if not len(out):
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
        risk = risk_from_log_weight(log_x, self.log_upper)
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
        return risk_from_log_weight(weight, self.log_upper)

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
