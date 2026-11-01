"""Incremental selected/alternative weights for an immutable prior automaton."""

from __future__ import annotations

from numbers import Integral

import numpy as np

from nca.native import load
from nca.priors import ArityPrior, _native_alphabet

_NATIVE = load("partition")


class PartitionCursor:
    """Retain prefix summaries and recompute from the first changed position.

    Above ``max_cache_bytes`` the cursor uses the rolling full partition instead.
    Pass ``None`` to leave the prefix cache unbounded.
    """

    def __init__(self, prior: ArityPrior, max_cache_bytes: int | None = 64 * 1024 * 1024) -> None:
        if max_cache_bytes is not None and (isinstance(max_cache_bytes, bool)
                                            or not isinstance(max_cache_bytes, Integral)
                                            or max_cache_bytes < 0):
            raise ValueError("max_cache_bytes must be a nonnegative integer or None")
        self._prior = prior
        self._max_cache_bytes = None if max_cache_bytes is None else int(max_cache_bytes)
        self._rows: np.ndarray | None = None
        self._selected: np.ndarray | None = None
        self._result: tuple[float, float] | None = None
        self._alternatives: np.ndarray | None = None
        self._bounds: np.ndarray | None = None
        self._matched_states: np.ndarray | None = None
        self._matched_weights: np.ndarray | None = None
        self._valid = False
        self.last_start = 0

    @property
    def prior(self) -> ArityPrior:
        return self._prior

    @property
    def max_cache_bytes(self) -> int | None:
        return self._max_cache_bytes

    def partition(self, log_probs: np.ndarray, selected: tuple[int, ...]) -> tuple[float, float]:
        rows = np.array(self.prior._rows(log_probs), dtype=np.float64, order="C", copy=True)
        selected = tuple(selected)
        if len(selected) != len(rows):
            raise ValueError("selected sequence must match the number of rows")
        if _NATIVE is None or any(symbol not in self.prior.alphabet for symbol in selected):
            self._valid = False
            return self.prior.partition(rows, selected)
        chosen = np.asarray(selected, dtype=np.int64)
        m, states = len(rows), len(self.prior.log_final)
        cache_bytes = (m + 1) * (states * 8 + 32) + m * (rows.shape[1] + 1) * 8
        if self.max_cache_bytes is not None and cache_bytes > self.max_cache_bytes:
            self._rows = self._selected = self._result = None
            self._alternatives = self._bounds = self._matched_states = self._matched_weights = None
            self._valid = False
            return self.prior.partition(rows, selected)
        if self._rows is None or self._rows.shape != rows.shape:
            self._alternatives = np.full((m + 1, states), -np.inf)
            self._bounds = np.tile([states, -1], (m + 1, 1)).astype(np.int64)
            self._matched_states = np.full(m + 1, self.prior.start, dtype=np.int64)
            self._matched_weights = np.full(m + 1, -np.inf)
            self._matched_weights[0] = 0.0
            self._valid = False
        first = 0
        if self._valid:
            assert self._rows is not None and self._selected is not None
            changed = np.flatnonzero(np.any(rows != self._rows, axis=1) | (chosen != self._selected))
            first = int(changed[0]) if len(changed) else m
            if first == m:
                assert self._result is not None
                self.last_start = m
                return self._result
        assert self._alternatives is not None and self._bounds is not None
        assert self._matched_states is not None and self._matched_weights is not None
        if not self._valid:
            self._alternatives[0].fill(-np.inf)
            self._bounds[0] = (states, -1)
            self._matched_states[0] = self.prior.start
            self._matched_weights[0] = 0.0
        # The native update mutates suffix rows; any exception leaves them untrusted.
        self._valid = False
        result = _NATIVE.update(rows.reshape(-1), _native_alphabet(self.prior.alphabet),
                                self.prior.transitions.reshape(-1), self.prior.log_weights.reshape(-1),
                                self.prior.log_final, chosen, self._alternatives.reshape(-1),
                                self._bounds.reshape(-1), self._matched_states,
                                self._matched_weights, first)
        if len(result) != 2:
            self._valid = False
            raise ValueError("prior partition arithmetic is not finite")
        self._rows, self._selected = rows, chosen
        self._result = float(result[0]), float(result[1])
        self._valid = True
        self.last_start = first
        return self._result
