"""Integer symbol validation and lossless native alphabet encoding."""

from __future__ import annotations

from collections.abc import Sequence
from functools import lru_cache

import numpy as np


def _integer_symbols(symbols: Sequence[int], *, values: np.ndarray | None = None) -> bool:
    values = np.asarray(symbols) if values is None else values
    if values.ndim != 1:
        return False
    if values.size == 0 or values.dtype.kind in "iu":
        return True
    return all(isinstance(a, (int, np.integer)) for a in symbols)


@lru_cache(maxsize=32)
def _dense_alphabet_needed(alphabet: tuple[int, ...]) -> bool:
    return any(not -(2**63) <= int(a) < 2**63 for a in alphabet)


@lru_cache(maxsize=32)
def _dense_native_alphabet(size: int) -> np.ndarray:
    return np.frombuffer(np.arange(size, dtype=np.int64).tobytes(), dtype=np.int64)


@lru_cache(maxsize=32)
def _native_alphabet(alphabet: tuple[int, ...]) -> np.ndarray:
    """Immutable native buffer shared by priors with the same alphabet."""
    if _dense_alphabet_needed(alphabet):
        return _dense_native_alphabet(len(alphabet))
    return np.frombuffer(np.asarray(alphabet, dtype=np.int64).tobytes(), dtype=np.int64)


def _native_symbol_pair(alphabet: tuple[int, ...], selected: Sequence[int], *,
                        values: np.ndarray | None = None) -> tuple[np.ndarray, np.ndarray]:
    dense = _dense_alphabet_needed(alphabet)
    values = np.asarray(selected) if values is None else values
    # NumPy may infer float64 for mixed signed and out-of-range integers,
    # losing their identity before an integer cast. Encode those from the
    # original Python values instead.
    if values.size and values.dtype.kind not in "iu":
        dense = True
    if values.dtype.kind == "u" and np.any(values > np.iinfo(np.int64).max):
        dense = True
    if not dense:
        try:
            return _native_alphabet(alphabet), np.ascontiguousarray(values, dtype=np.int64)
        except OverflowError:
            dense = True
    indices: dict[int, int] = {}
    for j, symbol in enumerate(alphabet):
        indices.setdefault(int(symbol), j)
    encoded = np.fromiter((indices.get(int(symbol), -1) for symbol in selected),
                          dtype=np.int64, count=len(selected))
    return _dense_native_alphabet(len(alphabet)), encoded


def _native_decoded_symbols(alphabet: tuple[int, ...], selected: Sequence[int]) -> tuple[int, ...]:
    if _dense_alphabet_needed(alphabet):
        return tuple(int(alphabet[int(index)]) for index in selected)
    return tuple(int(symbol) for symbol in selected)
