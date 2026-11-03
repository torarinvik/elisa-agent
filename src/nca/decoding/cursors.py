"""Incremental decoding cursors and retained band certificates."""

from __future__ import annotations

import math
from collections.abc import Sequence
from itertools import accumulate
import numpy as np
from nca import decoding as _api


class Split:
    """Forward and backward vectors of the decoding programs, in log space,
    kept valid around a cursor so that a change to one symbol's weights is
    rescored from the vectors on either side of it (THEORY §23.4, Theorems
    23.7–23.9). With ``centre`` and ``half``, the programs are restricted to
    counter values within ``half`` of ``centre[k]`` at position ``k``, a band
    fixed for the object's lifetime. Forward vectors ``0 ..= ahead`` and
    backward vectors ``behind ..= m`` are current; ``swept`` counts the
    positions recomputed."""

    def __init__(self, log_probs: np.ndarray, alphabet: Sequence[int] = (0, 1, 2),
                 centre: Sequence[int] | None = None, half: int | None = None) -> None:
        self.log_probs = np.array(log_probs, dtype=np.float64, order="C")
        self.alphabet = tuple(alphabet)
        if (self.log_probs.ndim != 2 or not self.alphabet
                or self.log_probs.shape[1] != len(self.alphabet)
                or any(not isinstance(a, (int, np.integer)) or a < 0 for a in self.alphabet)
                or np.any(np.isnan(self.log_probs)) or np.any(np.isposinf(self.log_probs))):
            raise ValueError("requires rows of finite or negative-infinite weights over nonnegative arities")
        m = len(self.log_probs)
        self.arities = _api._native_format_symbols(alphabet, m)
        self._arities_ordered = bool(np.all(self.arities[:-1] <= self.arities[1:]))
        self.arities.flags.writeable = False
        self._trace_indices: np.ndarray | None = None
        position = np.arange(m + 1)
        if centre is None and half is None:
            self.low, self.high = np.zeros(m + 1, dtype=np.int64), m - position
        else:
            if (centre is None or not isinstance(half, (int, np.integer)) or half < 0
                    or len(centre) != m + 1
                    or any(not isinstance(c, (int, np.integer)) for c in centre)):
                raise ValueError("band requires an integer centre per row and nonnegative half-width")
            half = int(half)
            self.low = np.array([max(0, min(m - k + 1, int(c) - half))
                                 for k, c in enumerate(centre)], dtype=np.int64)
            self.high = np.array([max(-1, min(m - k, int(c) + half))
                                  for k, c in enumerate(centre)], dtype=np.int64)
        growth = max(0, int(max(self.alphabet)) - 1)
        reachable = np.fromiter((min(m - k, 1 + k * growth) for k in range(m + 1)),
                                dtype=np.int64, count=m + 1)
        self.high = np.minimum(self.high, reachable)
        self.low = np.ascontiguousarray(self.low, dtype=np.int64)
        self.high = np.ascontiguousarray(self.high, dtype=np.int64)
        # Each row stores only its admitted states, relative to its lower bound.
        lengths = np.maximum(0, self.high - self.low + 1)
        self.width = max(1, int(lengths.max()))
        self.offsets = np.empty(m + 2, dtype=np.int64)
        self.offsets[0] = 0
        np.cumsum(lengths, out=self.offsets[1:])
        if np.any(self.offsets[1:] < self.offsets[:-1]):
            raise OverflowError("cursor storage exceeds the 64-bit offset range")
        size = int(self.offsets[-1])
        self._native = (_api._NATIVE if all(getattr(_api._NATIVE, name, None) is not None
                                     for name in ("advance_ragged_log", "retreat_ragged_log",
                                                  "scores_ragged_log", "trace_ragged"))
                        else None)
        self.forward = np.full(size, -np.inf)
        self.backward = np.full(size, -np.inf)
        self.forward_max = np.full(size, -np.inf)
        self.backward_max = np.full(size, -np.inf)
        if self.low[0] <= 1 <= self.high[0]:
            self.forward[1 - self.low[0]], self.forward_max[1 - self.low[0]] = 0.0, 0.0
        if self.low[m] <= 0 <= self.high[m]:
            self.backward[self.offsets[m] - self.low[m]] = 0.0
            self.backward_max[self.offsets[m] - self.low[m]] = 0.0
        self.ahead, self.behind, self.swept = 0, m, 0
        self._advance(m)
        self._retreat(0)
        self.swept = 0

    def _row(self, values: np.ndarray, i: int) -> np.ndarray:
        return values[self.offsets[i]:self.offsets[i + 1]]

    def _moves(self, i: int) -> list[tuple[int, int, int, int]]:
        """For each arity ``a`` (index ``j``), the run of in-band states
        ``s ≥ 1`` at position ``i`` whose successor ``s − 1 + a`` is in band at
        ``i + 1``: ``(j, s0, length, t0)``."""
        moves = []
        for j, value in enumerate(self.alphabet):
            a = int(value)
            s0 = max(int(self.low[i]), 1, int(self.low[i + 1]) + 1 - a)
            s1 = min(int(self.high[i]), int(self.high[i + 1]) + 1 - a)
            if s1 >= s0:
                moves.append((j, s0, s1 - s0 + 1, s0 - 1 + a))
        return moves

    def _advance(self, k: int) -> None:
        """Make forward vectors current through position ``k``."""
        if self._native is not None and self.ahead < k:
            swept = self._native.advance_ragged_log(self.forward,
                                              self.forward_max.reshape(-1),
                                              self.log_probs.reshape(-1), self.arities, self.low,
                                              self.high, self.offsets, self.ahead, k)
            if swept < 0:
                raise ValueError("format decoding arithmetic is not finite")
            self.swept += swept
            self.ahead = k
        while self.ahead < k:
            i = self.ahead
            source, target = self._row(self.forward, i), self._row(self.forward, i + 1)
            source_max, target_max = self._row(self.forward_max, i), self._row(self.forward_max, i + 1)
            target[:] = target_max[:] = -np.inf
            for j, s0, n, t0 in self._moves(i):
                step = self.log_probs[i, j]
                s0 -= int(self.low[i])
                t0 -= int(self.low[i + 1])
                target[t0:t0 + n] = np.logaddexp(
                    target[t0:t0 + n], _api._checked_log_sum(source[s0:s0 + n], step))
                target_max[t0:t0 + n] = np.maximum(
                    target_max[t0:t0 + n], _api._checked_log_sum(source_max[s0:s0 + n], step))
            self.ahead += 1
            self.swept += 1

    def _retreat(self, k: int) -> None:
        """Make backward vectors current from position ``k``."""
        if self._native is not None and self.behind > k:
            swept = self._native.retreat_ragged_log(self.backward,
                                              self.backward_max.reshape(-1),
                                              self.log_probs.reshape(-1), self.arities, self.low,
                                              self.high, self.offsets, self.behind, k)
            if swept < 0:
                raise ValueError("format decoding arithmetic is not finite")
            self.swept += swept
            self.behind = k
        while self.behind > k:
            i = self.behind - 1
            target, source = self._row(self.backward, i), self._row(self.backward, i + 1)
            target_max, source_max = self._row(self.backward_max, i), self._row(self.backward_max, i + 1)
            target[:] = target_max[:] = -np.inf
            for j, s0, n, t0 in self._moves(i):
                step = self.log_probs[i, j]
                s0 -= int(self.low[i])
                t0 -= int(self.low[i + 1])
                target[s0:s0 + n] = np.logaddexp(
                    target[s0:s0 + n], _api._checked_log_sum(source[t0:t0 + n], step))
                target_max[s0:s0 + n] = np.maximum(
                    target_max[s0:s0 + n], _api._checked_log_sum(source_max[t0:t0 + n], step))
            self.behind -= 1
            self.swept += 1

    def scores(self, k: int, row: np.ndarray) -> tuple[float, float]:
        """``log Z`` and the best log weight with symbol ``k``'s log weights
        replaced by ``row``, from the vectors before and after it."""
        if not isinstance(k, (int, np.integer)) or not 0 <= k < len(self.log_probs):
            raise IndexError("symbol index is out of range")
        row = np.asarray(row, dtype=np.float64)
        if (row.shape != (len(self.alphabet),) or np.any(np.isnan(row))
                or np.any(np.isposinf(row))):
            raise ValueError("row must contain one finite or negative-infinite weight per arity")
        return self._scores_validated(k, row)

    def _scores_validated(self, k: int, row: np.ndarray) -> tuple[float, float]:
        """Score a row whose shape, values, and index were already validated."""
        self._advance(k)
        self._retreat(k + 1)
        if self._native is not None:
            log_row = np.ascontiguousarray(row, dtype=np.float64)
            args = (self.forward, self.forward_max, self.backward, self.backward_max,
                    self.arities, self.low, self.high, self.offsets, k, log_row)
            ordered_score = getattr(self._native, "scores_ragged_with_order", None)
            if ordered_score is None:
                log_z, log_x = self._native.scores_ragged_log(*args)
            else:
                log_z, log_x = ordered_score(*args, self._arities_ordered)
            if math.isnan(log_z) or math.isnan(log_x):
                raise ValueError("format decoding arithmetic is not finite")
            return float(log_z), float(log_x)
        log_z = log_x = -np.inf
        for j, s0, n, t0 in self._moves(k):
            if row[j] == -np.inf:
                continue
            s0 -= int(self.low[k])
            t0 -= int(self.low[k + 1])
            suffix = self._row(self.backward, k + 1)[t0:t0 + n]
            prefix = np.where(np.isneginf(suffix), -np.inf, self._row(self.forward, k)[s0:s0 + n])
            sums = _api._checked_log_sum(_api._checked_log_sum(prefix, row[j]), suffix)
            log_z = np.logaddexp(log_z, np.logaddexp.reduce(sums))
            suffix_max = self._row(self.backward_max, k + 1)[t0:t0 + n]
            prefix_max = np.where(np.isneginf(suffix_max), -np.inf,
                                  self._row(self.forward_max, k)[s0:s0 + n])
            best = _api._checked_log_sum(_api._checked_log_sum(prefix_max, row[j]), suffix_max)
            log_x = max(log_x, float(best.max()))
        return float(log_z), log_x

    def best(self, k: int) -> tuple[float, tuple[int, ...]]:
        """The best log weight and a sequence attaining it, traced from the
        max vectors before and after symbol ``k`` (THEORY §23.4, Theorem 23.10).
        If no path has positive weight, return ``(-inf, ())``."""
        if not isinstance(k, (int, np.integer)) or not 0 <= k < len(self.log_probs):
            raise IndexError("symbol index is out of range")
        self._advance(k)
        self._retreat(k + 1)
        if self._native is not None:
            args = (self.forward_max, self.backward_max, self.log_probs.reshape(-1),
                    self.arities, self.low, self.high, self.offsets, k)
            ordered_trace = getattr(self._native, "trace_ragged_with_order", None)
            indexed_trace = getattr(self._native, "trace_ragged_indexed", None)
            if not self._arities_ordered and indexed_trace is not None:
                if self._trace_indices is None:
                    self._trace_indices = np.ascontiguousarray(
                        np.argsort(self.arities, kind="stable"), dtype=np.int64)
                    self._trace_indices.flags.writeable = False
                out = np.asarray(indexed_trace(*args, self._trace_indices))
            elif ordered_trace is None:
                out = np.asarray(self._native.trace_ragged(*args))
            else:
                out = np.asarray(ordered_trace(*args, self._arities_ordered))
            if np.isnan(out[0]):
                raise ValueError("format decoding arithmetic is not finite")
            return float(out[0]), tuple(int(a) for a in out[1:])
        m, alphabet = len(self.log_probs), tuple(map(int, self.alphabet))
        log_x, state, choice = -np.inf, 0, 0
        for j, s0, n, t0 in self._moves(k):
            if self.log_probs[k, j] == -np.inf:
                continue
            source, target = s0 - int(self.low[k]), t0 - int(self.low[k + 1])
            suffix = self._row(self.backward_max, k + 1)[target:target + n]
            prefix = np.where(np.isneginf(suffix), -np.inf,
                              self._row(self.forward_max, k)[source:source + n])
            best = _api._checked_log_sum(_api._checked_log_sum(prefix, self.log_probs[k, j]), suffix)
            t = int(np.argmax(best))
            if best[t] > log_x:
                log_x, state, choice = float(best[t]), s0 + t, j
        if log_x == -np.inf:
            return -np.inf, ()
        arities = [0] * m
        arities[k] = alphabet[choice]
        before = state
        for i in reversed(range(k)):
            options = [(float(_api._checked_log_sum(self._row(self.forward_max, i)[n - self.low[i]],
                                               self.log_probs[i, j])), n, a)
                       for j, a in enumerate(alphabet)
                       for n in (before + 1 - a,) if max(1, self.low[i]) <= n <= self.high[i]]
            _, before, arities[i] = max(options)
        after = state - 1 + alphabet[choice]
        for i in range(k + 1, m):
            options = [(float(_api._checked_log_sum(self.log_probs[i, j],
                                               self._row(self.backward_max, i + 1)[n - self.low[i + 1]])), n, a)
                       for j, a in enumerate(alphabet)
                       for n in (after - 1 + a,) if after >= 1 and self.low[i + 1] <= n <= self.high[i + 1]]
            _, after, arities[i] = max(options)
        return log_x, tuple(arities)

    def climb(self, k: int, row: np.ndarray) -> tuple[float, float]:
        """Replace symbol ``k``'s log weights by ``row`` and return the new
        ``log Z`` and best log weight. Vectors that depend on symbol ``k`` (forward
        after it, backward before it) stop being current."""
        result = self.scores(k, row)
        self._commit_climb(k, row)
        return result

    def _commit_climb(self, k: int, row: np.ndarray) -> None:
        self.log_probs[k] = row
        self.ahead = min(self.ahead, k)
        self.behind = max(self.behind, k + 1)


class CertifiedSplit:
    """Fixed-reference banded cursor with relative-tail and maximum certificates.

    Uses the native Split sweeps when built. Weights must be probabilities
    over distinct nonnegative arities (THEORY §23.3–23.4).
    """

    def __init__(self, log_probs: np.ndarray, alphabet: Sequence[int] = (0, 1, 2),
                 slack: float = 1e-4) -> None:
        if not 0 < slack < 1:
            raise ValueError("slack must be strictly between zero and one")
        self.log_probs = np.array(log_probs, dtype=np.float64, order="C")
        self.alphabet = tuple(alphabet)
        if (self.log_probs.ndim != 2 or not len(self.log_probs)
                or self.log_probs.shape[1] != len(alphabet) or not self.alphabet
                or len(set(self.alphabet)) != len(self.alphabet)
                or any(not isinstance(a, (int, np.integer)) or a < 0 for a in alphabet)):
            raise ValueError("requires nonempty rows over distinct nonnegative arities")
        self._validate(self.log_probs)
        self.slack = slack
        self.reference = np.argmax(self.log_probs, axis=1)
        self.centre = tuple(accumulate((int(alphabet[j]) - 1 for j in self.reference), initial=1))
        self.arity_bound = int(max(alphabet))
        self.cover_half = max(max(c, len(self.log_probs) - k - c)
                              for k, c in enumerate(self.centre))
        self._tail_blocks: np.ndarray | None = None
        self._tail_block_size = math.isqrt(max(1, len(self.log_probs) // len(self.alphabet))) + 1
        self._tail_block_kernel = getattr(_api._NATIVE, "tail_block_summary", None)
        block_summary = _api._tail_mass_blocks(self.log_probs, self.reference)
        if block_summary is None:
            self._tail_summary: tuple[float, float] | None = _api._tail_mass_summary(
                self.log_probs, self.reference)
        else:
            self._tail_summary, self._tail_blocks, self._tail_block_size = block_summary
        log_off, log_factor = self._tail_summary
        self.changes = _api._initial_band_changes(log_off, slack, len(self.log_probs), log_factor)
        if (self.changes > len(self.log_probs)
                or self.arity_bound * (self.changes - 1) >= self.cover_half):
            self._tail_blocks = None
        self.rebuilds = 0
        self.log_upper: float | None = None
        self.split = self._build()

    @staticmethod
    def _validate(rows: np.ndarray) -> None:
        if (np.any(np.isnan(rows)) or np.any(rows > 0)
                or np.any(np.exp(rows).sum(axis=-1) > 1 + 1e-12)):
            raise ValueError("rows must contain log probabilities with mass at most one")

    def _build(self) -> Split:
        split = Split(self.log_probs, self.alphabet, self.centre,
                      self.arity_bound * (self.changes - 1))
        previous = getattr(self, "split", None)
        if previous is not None:
            split._trace_indices = previous._trace_indices
        return split

    def _certify(self, k: int, scores: tuple[float, float] | None,
                 maximum: bool) -> tuple[float, int] | None:
        """Certify the normalizer, optionally requiring a global maximum."""
        self.log_upper = None
        half = self.arity_bound * (self.changes - 1)
        # The band only widens, so a full band has no tail to summarize.
        if half >= self.cover_half or self.changes > len(self.log_probs):
            log_off, log_factor = -math.inf, 0.0
        else:
            if self._tail_summary is None:
                self._tail_summary = _api._tail_mass_summary(self.log_probs, self.reference)
            log_off, log_factor = self._tail_summary
        while True:
            half = self.arity_bound * (self.changes - 1)
            if half >= self.cover_half or self.changes > len(self.log_probs):
                self._tail_blocks = None
                self._tail_summary = None
                log_tail = -math.inf
            else:
                log_tail = _api._band_log_tail(log_off, self.changes, log_factor)
            log_z, log_x = (scores if scores is not None else
                            self.split.scores(k, self.log_probs[k]))
            if (math.isfinite(log_z) and log_tail <= math.log(self.slack) + log_z
                    and (not maximum or log_x >= log_tail)):
                upper = float(np.logaddexp(log_z, log_tail))
                self.log_upper = upper
                return log_x, half
            if log_tail == -math.inf:
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
               scores: tuple[float, float] | None = None) -> _api.Banded | None:
        """Widen until both relative slack and exact-maximum certificates hold."""
        certified = self._certify(k, scores, maximum=True)
        if certified is None:
            return None
        log_x, half = certified
        _, arities = self.split.best(k)
        assert self.log_upper is not None
        risk = _api.risk_from_log_weight(log_x, self.log_upper)
        if risk == 0.0:
            risk = _api._format_sequence_risk(self.log_probs, self.alphabet, arities)
        return _api.Banded(arities, risk, True, self.changes, 2 * half + 1)

    def sequence_risk(self, arities: Sequence[int]) -> float:
        """Upper-bound any accepted sequence's risk, including outside the band.

        Requires a successful result or normalizer certificate for the current rows.
        The normalizer bound
        and relative slack apply independently of which accepted answer is scored
        (THEORY §23.3). This is a model bound, not a floating-point enclosure.
        """
        if len(arities) != len(self.log_probs) or not _api._valid_arities(arities):
            raise ValueError("sequence must be a complete prefix term of matching length")
        native = getattr(_api._NATIVE, "accepted_log_weight", None)
        if native is not None:
            accepted = native(self.log_probs.reshape(-1),
                              _api._native_format_symbols(self.alphabet, len(arities)),
                              _api._native_format_symbols(arities, len(arities)))
            if not accepted:
                raise ValueError("sequence must be accepted by the arity alphabet")
            weight = float(accepted[0])
            if math.isnan(weight) or weight == math.inf:
                raise ValueError("sequence log weight arithmetic is not finite or loses precision")
        else:
            if _api.parse(arities) is None or any(a not in self.alphabet for a in arities):
                raise ValueError("sequence must be accepted by the arity alphabet")
            weight = _api.sequence_log_weight(self.log_probs, self.alphabet, arities)
        if self.log_upper is None:
            raise ValueError("requires a successful result for the current rows")
        risk = _api.risk_from_log_weight(weight, self.log_upper)
        return (_api._format_sequence_risk(self.log_probs, self.alphabet, arities)
                if risk == 0.0 else risk)

    def _replace(self, k: int, row: np.ndarray) -> tuple[float, float]:
        """Replace one validated row and retain the reference and band."""
        row = np.asarray(row, dtype=np.float64)
        if row.shape != (len(self.alphabet),):
            raise ValueError("row width must match the alphabet")
        self._validate(row)
        if not isinstance(k, (int, np.integer)) or not 0 <= k < len(self.log_probs):
            raise IndexError("symbol index is out of range")
        scores = self.split._scores_validated(k, row)
        self.split._commit_climb(k, row)
        self.log_probs[k] = row
        self._tail_summary = None
        self.log_upper = None
        if self._tail_blocks is not None:
            if (self.changes > len(self.log_probs)
                    or self.arity_bound * (self.changes - 1) >= self.cover_half):
                self._tail_blocks = None
            else:
                blocks, self._tail_blocks = self._tail_blocks, None
                summary = self._tail_block_kernel(self.log_probs.reshape(-1), self.reference,
                                                  blocks, self._tail_block_size, k)
                if len(summary) == 2:
                    self._tail_blocks = blocks
                    self._tail_summary = float(summary[0]), float(summary[1])
        return scores

    def climb(self, k: int, row: np.ndarray) -> _api.Banded | None:
        """Replace one probability row and certify a maximum and its risk."""
        return self.result(k, self._replace(k, row))

    def climb_normalizer(self, k: int, row: np.ndarray) -> float | None:
        """Replace one probability row and certify only the normalizer."""
        return self.normalizer(k, self._replace(k, row))
