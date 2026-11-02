"""Incremental selected/alternative weights for an immutable prior automaton."""

from __future__ import annotations

from numbers import Integral
from sys import getsizeof

import numpy as np

from nca.native import load
from nca.priors import ArityPrior, _integer_symbols, _native_symbol_pair

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
        self._symbols: frozenset[int] | None = None
        self._max_cache_bytes = None if max_cache_bytes is None else int(max_cache_bytes)
        self._rows: np.ndarray | None = None
        self._selected: np.ndarray | None = None
        self._alphabet: np.ndarray | None = None
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
        rows = self.prior._rows(log_probs)
        selected = tuple(selected)
        if len(selected) != len(rows):
            raise ValueError("selected sequence must match the number of rows")
        selected_values = np.asarray(selected)
        if not _integer_symbols(selected, values=selected_values):
            raise ValueError("selected symbols must be integers")
        if _NATIVE is None or self.max_cache_bytes == 0:
            return self.prior.partition(rows, selected)
        m, states = len(rows), len(self.prior.log_final)
        cache_bytes = (m + 1) * (states * 8 + 32) + m * (rows.shape[1] + 1) * 8
        # Each set entry must at least store a pointer to its alphabet symbol.
        if (self._symbols is None and self.max_cache_bytes is not None
                and (cache_bytes > self.max_cache_bytes
                     or len(self.prior.alphabet) >
                     (self.max_cache_bytes - cache_bytes) // np.dtype(np.intp).itemsize)):
            return self.prior.partition(rows, selected)
        if self._symbols is None:
            self._symbols = frozenset(self.prior.alphabet)
        symbol_bytes = getsizeof(self._symbols)
        if self.max_cache_bytes is not None and symbol_bytes > self.max_cache_bytes:
            self._symbols = None
            return self.prior.partition(rows, selected)
        try:
            unsupported = any(symbol not in self._symbols for symbol in selected)
        except TypeError:
            # Integer subclasses may deliberately disable hashing.
            unsupported = any(symbol not in self.prior.alphabet for symbol in selected)
        if unsupported:
            # The rolling fallback does not mutate the cached prefix snapshot.
            return self.prior.partition(rows, selected)
        cache_bytes += symbol_bytes
        if self.max_cache_bytes is not None and cache_bytes > self.max_cache_bytes:
            self._rows = self._selected = self._alphabet = self._result = None
            self._alternatives = self._bounds = self._matched_states = self._matched_weights = None
            self._symbols = None
            self._valid = False
            return self.prior.partition(rows, selected)
        alphabet, chosen = _native_symbol_pair(self.prior.alphabet, selected, values=selected_values)
        if alphabet is not self._alphabet:
            self._valid = False
        if self._rows is None or self._rows.shape != rows.shape:
            self._valid = False
            alternatives = np.full((m + 1, states), -np.inf)
            bounds = np.tile([states, -1], (m + 1, 1)).astype(np.int64)
            matched_states = np.full(m + 1, self.prior.start, dtype=np.int64)
            matched_weights = np.full(m + 1, -np.inf)
            matched_weights[0] = 0.0
            self._alternatives, self._bounds = alternatives, bounds
            self._matched_states, self._matched_weights = matched_states, matched_weights
        first = 0
        if self._valid:
            assert self._rows is not None and self._selected is not None
            find_change = getattr(_NATIVE, "first_change", None)
            if find_change is None:
                changed = np.flatnonzero(np.any(rows != self._rows, axis=1)
                                         | (chosen != self._selected))
                first = int(changed[0]) if len(changed) else m
            else:
                first = int(find_change(np.ascontiguousarray(rows).reshape(-1), self._rows.reshape(-1),
                                        chosen, self._selected, rows.shape[1]))
            if first == m:
                assert self._result is not None
                self.last_start = m
                return self._result
        rows = np.array(rows, dtype=np.float64, order="C", copy=True)
        assert self._alternatives is not None and self._bounds is not None
        assert self._matched_states is not None and self._matched_weights is not None
        if not self._valid:
            self._alternatives.fill(-np.inf)
            self._bounds[:, 0] = states
            self._bounds[:, 1] = -1
            self._matched_states[0] = self.prior.start
            self._matched_weights[0] = 0.0
        # The native update mutates suffix rows; any exception leaves them untrusted.
        self._valid = False
        result = _NATIVE.update(rows.reshape(-1), alphabet,
                                self.prior.transitions.reshape(-1), self.prior.log_weights.reshape(-1),
                                self.prior.log_final, chosen, self._alternatives.reshape(-1),
                                self._bounds.reshape(-1), self._matched_states,
                                self._matched_weights, first)
        if len(result) != 2:
            self._valid = False
            raise ValueError("prior partition arithmetic is not finite or loses precision")
        self._rows, self._selected, self._alphabet = rows, chosen, alphabet
        self._result = float(result[0]), float(result[1])
        self._valid = True
        self.last_start = first
        return self._result
