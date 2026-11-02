"""Results of pure experts, keyed by content (THEORY §28.5).

A pure expert (declared effects: the empty set) with a content identity is a
function of its inputs, so the output of one invocation is a fact about the
pair (expert, inputs) that any later invocation may reuse (``NCA.cache_lookup_correct``).
``value_digest`` gives inputs a content digest when their type has a
canonical encoding; inputs without one, and experts that are not declared
pure or have no identity, are never cached.

Cached outputs are shared, so consumers must not mutate the values they
receive, which pure experts already guarantee for their inputs.
"""

from __future__ import annotations

import hashlib
import math
from collections import OrderedDict
from collections.abc import Hashable, Mapping
from dataclasses import dataclass
from typing import Any

import numpy as np

from nca.abi import Choice

try:
    import torch
except ImportError:  # The cache works without torch; tensors are then unknown values.
    torch = None


def _feed(sha: Any, value: Any) -> bool:
    """Feed ``value``'s canonical encoding to ``sha``; ``False`` if it has none."""
    if value is None or isinstance(value, bool):
        sha.update(b"n" if value is None else b"T" if value else b"F")
    elif isinstance(value, int):
        sha.update(b"i" + str(value).encode() + b";")
    elif isinstance(value, float):
        if math.isnan(value):
            return False
        sha.update(b"f" + value.hex().encode() + b";")
    elif isinstance(value, str):
        data = value.encode()
        sha.update(b"s" + str(len(data)).encode() + b":" + data)
    elif isinstance(value, (tuple, list)):
        sha.update(b"l" + str(len(value)).encode() + b":")
        return all(_feed(sha, item) for item in value)
    elif isinstance(value, Mapping):
        if any(not isinstance(key, str) for key in value):
            return False
        sha.update(b"d" + str(len(value)).encode() + b":")
        return all(_feed(sha, key) and _feed(sha, value[key]) for key in sorted(value))
    elif isinstance(value, Choice):
        sha.update(b"c" + str(value.index).encode() + b":")
        return _feed(sha, value.value)
    elif isinstance(value, np.ndarray):
        if value.dtype.hasobject:
            return False
        array = np.ascontiguousarray(value)
        sha.update(b"a" + array.dtype.str.encode() + str(array.shape).encode() + b":")
        sha.update(array.tobytes())
    elif torch is not None and isinstance(value, torch.Tensor):
        if value.is_complex() or value.layout != torch.strided:
            return False
        return _feed(sha, value.detach().cpu().numpy())
    else:
        return False
    return True


def value_digest(value: Any) -> str | None:
    """A content digest of ``value``, or ``None`` if its type has no canonical
    encoding. Equal digests mean equal values for the supported types: None,
    booleans, integers, floats (by their exact bits; NaN is unsupported),
    strings, sequences, string-keyed mappings, choices, NumPy arrays and
    tensors (by dtype, shape and bytes; tuples and lists encode alike)."""
    sha = hashlib.sha256()
    return "sha256:" + sha.hexdigest() if _feed(sha, value) else None


@dataclass
class CacheStats:
    hits: int = 0
    misses: int = 0
    stored: int = 0


class ResultCache:
    """Outputs of pure experts by (identity, input digests), keeping
    at most ``limit`` entries, least recently used first out."""

    def __init__(self, limit: int | None = None) -> None:
        self.limit = limit
        self.stats = CacheStats()
        self._entries: OrderedDict[Hashable, Any] = OrderedDict()

    def __len__(self) -> int:
        return len(self._entries)

    def lookup(self, key: Hashable) -> tuple[bool, Any]:
        if key in self._entries:
            self._entries.move_to_end(key)
            self.stats.hits += 1
            return True, self._entries[key]
        self.stats.misses += 1
        return False, None

    def store(self, key: Hashable, value: Any) -> None:
        self._entries[key] = value
        self._entries.move_to_end(key)
        self.stats.stored += 1
        while self.limit is not None and len(self._entries) > self.limit:
            self._entries.popitem(last=False)
