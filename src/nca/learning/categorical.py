"""Exact empirical category scoring, independent of category meanings (§36.68)."""

from array import array
from collections import Counter
from collections.abc import Hashable, Sequence

from nca.native import load

_NATIVE = load("records")


def modal_score(keys: Sequence[Hashable], labels: Sequence[Hashable]) -> int:
    """Best observed constant-label accuracy within each key, as a count.

    Lawful stable hashing/equality and frozen observations are required.
    Identifier interning compares actual values even on hash collisions. The
    Elisa kernel uses linear index storage rather than a dense contingency
    table. This empirical score says nothing about unseen cases.
    """
    if len(keys) != len(labels):
        raise ValueError("category scoring needs aligned keys and labels")
    native = getattr(_NATIVE, "modal_score", None)
    if native is not None:
        key_ids: dict[Hashable, int] = {}
        label_ids: dict[Hashable, int] = {}
        packed = array("q")
        for key, label in zip(keys, labels, strict=True):
            packed.append(key_ids.setdefault(key, len(key_ids)))
            packed.append(label_ids.setdefault(label, len(label_ids)))
        return int(native(packed))
    counts: dict[Hashable, Counter[Hashable]] = {}
    for key, label in zip(keys, labels, strict=True):
        counts.setdefault(key, Counter())[label] += 1
    return sum(max(histogram.values()) for histogram in counts.values())
