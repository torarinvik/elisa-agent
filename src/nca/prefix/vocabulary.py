"""Ranked vocabulary declarations and per-position readout."""

from __future__ import annotations

from collections.abc import Sequence
from dataclasses import dataclass
from functools import cached_property
import numpy as np
from nca.ladder import RankedReading
from nca import prefix as _api


@dataclass(frozen=True)
class RankedVocabulary:
    """Symbols and their arities, the alphabet of a prefix format."""

    symbols: tuple[str, ...]
    arities: tuple[int, ...]

    def __post_init__(self) -> None:
        if (not self.symbols or len(self.symbols) != len(self.arities)
                or len(set(self.symbols)) != len(self.symbols)
                or any(isinstance(a, bool) or not isinstance(a, int) or a < 0
                       for a in self.arities)):
            raise ValueError("a ranked vocabulary needs distinct symbols, each with a "
                             "nonnegative integer arity")

    @cached_property
    def order(self) -> tuple[int, ...]:
        """The distinct arities in increasing order: the decoder's alphabet."""
        return tuple(sorted(set(self.arities)))

    @cached_property
    def decision(self) -> tuple[tuple[int, ...], ...]:
        """The grouped decision a parser needs of every symbol: its arity, one
        group of classes per entry of ``order``."""
        return tuple(tuple(c for c, a in enumerate(self.arities) if a == arity)
                     for arity in self.order)

    def group(self, arity: int) -> tuple[int, ...]:
        """The classes of arity ``arity``."""
        return self.decision[self.order.index(arity)]

    @cached_property
    def _index(self) -> dict[str, int]:
        return {symbol: c for c, symbol in enumerate(self.symbols)}

    def index(self, symbol: str) -> int:
        return self._index[symbol]

    def arity(self, symbol: str) -> int:
        return self.arities[self._index[symbol]]

    @cached_property
    def class_arities(self) -> np.ndarray:
        """Each class's arity, for native kernels."""
        values = np.asarray(self.arities, dtype=np.int64)
        values.setflags(write=False)
        return values

    @cached_property
    def class_groups(self) -> np.ndarray:
        """Each class's position in ``order``, for native kernels."""
        values = np.asarray([self.order.index(a) for a in self.arities], dtype=np.int64)
        values.setflags(write=False)
        return values


def most_likely(readings: Sequence[Sequence[float]], vocabulary: RankedVocabulary) -> list[str]:
    """Each reading's most probable symbol."""
    symbols = vocabulary.symbols
    native = getattr(_api._NATIVE, "row_argmax", None)
    if len(readings) and all(isinstance(row, RankedReading) for row in readings):
        if native is not None:
            scores = np.asarray([row.weights for row in readings], dtype=np.float64)
            return [symbols[i] for i in native(scores.reshape(-1), scores.shape[1])]
        return [symbols[row.top()] for row in readings]
    # A shared NumPy dtype must not round one row merely because another row
    # has a different dtype. Python float tuples and binary float arrays are
    # safe to convert together; other inputs retain per-row NumPy semantics.
    if (native is not None and len(readings) and
            (isinstance(readings, np.ndarray) or
             all(isinstance(row, (tuple, list)) and
                 set(map(type, row)) <= {float} for row in readings))):
        try:
            scores = np.asarray(readings)
        except (TypeError, ValueError):
            scores = None
        if (scores is not None and scores.ndim == 2 and scores.shape[1] == len(symbols)
                and scores.dtype.kind == "f" and scores.dtype.itemsize <= 8):
            values = np.asarray(scores, dtype=np.float64).reshape(-1)
            return [symbols[i] for i in native(values, scores.shape[1])]
    return [symbols[int(np.argmax(r))] for r in readings]


def arity_masses(readings: Sequence[Sequence[float]], vocabulary: RankedVocabulary) -> np.ndarray:
    """Group raw readings by arity without applying a calibration or normalization."""
    native = getattr(_api._NATIVE, "grouped_masses", None)
    if native is not None:
        scores = np.asarray(readings, dtype=np.float64)
        if scores.shape == (len(readings), len(vocabulary.symbols)):
            entries = len(vocabulary.order)
            return np.asarray(native(scores.reshape(-1), vocabulary.class_groups, entries)
                              ).reshape(len(readings), entries)
    return np.array([[sum(r[c] for c in group) for group in vocabulary.decision]
                     for r in readings])
