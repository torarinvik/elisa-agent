"""Reading a noisy string as a distribution over a vocabulary by edit distance.

``EditDistanceReader`` is symbolic: ``p(w) ∝ exp(-d(x, w))`` over the
vocabulary's strings, with ``d`` the optimal-string-alignment distance
(substitutions, deletions, insertions and adjacent transpositions, §18.1).
Any domain whose experts read noisy strings can install one with its own
vocabulary and contract.
"""

from __future__ import annotations

from collections.abc import Sequence

import numpy as np
import torch

from nca.abi import Contract, Manifest
from nca.native import load

_EDIT_NATIVE = load("edit")

EDIT_OPERATIONS_PER_CELL = 5
"""Nominal cost of one cell of the dynamic program."""


def edit_distance(a: str, b: str) -> int:
    """Optimal-string-alignment distance on Unicode code points (§18.1)."""
    native = getattr(_EDIT_NATIVE, "edit_distance", None)
    if native is not None:
        return int(native(np.fromiter(map(ord, a), dtype=np.int64),
                          np.fromiter(map(ord, b), dtype=np.int64)))
    return _edit_distance_reference(a, b)


def _edit_distance_reference(a: str, b: str) -> int:
    """Edits (substitution, deletion, insertion, adjacent transposition)
    turning ``a`` into ``b``, each substring edited at most once."""
    d = [[i + j if i * j == 0 else 0 for j in range(len(b) + 1)] for i in range(len(a) + 1)]
    for i in range(1, len(a) + 1):
        for j in range(1, len(b) + 1):
            d[i][j] = min(d[i - 1][j] + 1, d[i][j - 1] + 1,
                          d[i - 1][j - 1] + (a[i - 1] != b[j - 1]))
            if i > 1 and j > 1 and a[i - 1] == b[j - 2] and a[i - 2] == b[j - 1]:
                d[i][j] = min(d[i][j], d[i - 2][j - 2] + 1)
    return d[len(a)][len(b)]


class EditDistanceReader:
    """``p(w) ∝ exp(-d(x, w))`` over ``vocabulary``. Its cost counts the dynamic
    program's cells for an input of ``typical_length``."""

    def __init__(self, vocabulary: Sequence[str], contract: Contract, module_id: str,
                 version: str = "1.0.0", typical_length: int = 4) -> None:
        if not vocabulary:
            raise ValueError("an edit-distance reader needs a nonempty vocabulary")
        self.vocabulary = tuple(vocabulary)
        self.codes = np.array([ord(c) for word in self.vocabulary for c in word], dtype=np.int64)
        self.offsets = np.array([0, *np.cumsum([len(w) for w in self.vocabulary])],
                                dtype=np.int64)
        self.codes.setflags(write=False)
        self.offsets.setflags(write=False)
        self.manifest = Manifest(
            module_id, version, contract,
            cost=EDIT_OPERATIONS_PER_CELL * (typical_length + 1)
            * sum(len(w) + 1 for w in self.vocabulary))

    def invoke(self, word: str) -> tuple[float, ...]:
        native = getattr(_EDIT_NATIVE, "edit_distances", None)
        if native is not None:
            values = native(np.fromiter(map(ord, word), dtype=np.int64), self.codes, self.offsets)
            distances = torch.tensor([float(d) for d in values])
        else:
            distances = torch.tensor([float(edit_distance(word, w)) for w in self.vocabulary])
        return tuple(torch.softmax(-distances, dim=0).tolist())
