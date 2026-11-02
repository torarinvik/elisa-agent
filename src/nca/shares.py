"""Risk shares of the format's accounts, rounded towards safety (§19, §21.6).

Charges are rounded upward and floors downward, so every account computed in
binary64 still bounds the exact one.
"""

from __future__ import annotations

import math
from collections.abc import Sequence

import numpy as np

from nca.ladder import _lower_sum, _lower_values, _upper_sum
from nca.native import load

_NATIVE = load("decoding")
_STATS_NATIVE = load("stats")


def _upper_values(risks: Sequence[float]) -> list[float]:
    values = []
    for risk in risks:
        value = float(risk)
        values.append(math.nextafter(value, math.inf) if risk > value else value)
    return values


def _pair_shares(risks: Sequence[float]) -> list[float]:
    """Conservative pair shares without subtracting a risk from the total."""
    values = _upper_values(risks)
    native = getattr(_NATIVE, "pair_shares", None)
    if native is not None:
        return list(native(np.asarray(values, dtype=np.float64)))
    prefix = [0.0]
    for value in values:
        prefix.append(_upper_sum([prefix[-1], value]))
    suffix = [0.0] * (len(values) + 1)
    for i in reversed(range(len(values))):
        suffix[i] = _upper_sum([suffix[i + 1], values[i]])
    def product(a: float, b: float) -> float:
        value = a * b
        return value if a == 0.0 or b == 0.0 or math.isinf(value) else math.nextafter(value, math.inf)
    return [product(product(value, _upper_sum([prefix[i], suffix[i + 1]])), 0.5)
            for i, value in enumerate(values)]


def pair_risk_upper(risks: Sequence[float]) -> float:
    """Upper bound on the unordered pair sum, capped at one."""
    values = _upper_values(risks)
    if any(not math.isfinite(value) or value < 0.0 for value in values):
        return math.nan
    native = getattr(_STATS_NATIVE, "pair_risk_upper", None)
    if native is not None:
        return float(native(np.asarray(values, dtype=np.float64)))
    return min(_upper_sum(_pair_shares(values)), 1.0)


def _markov_shares(risks: Sequence[float]) -> list[float]:
    values = _upper_values(risks)
    native = getattr(_NATIVE, "markov_shares", None)
    if native is not None:
        return list(native(np.asarray(values, dtype=np.float64)))
    result = []
    for value in values:
        half = value * 0.5
        result.append(math.nextafter(half, math.inf) if half + half < value else half)
    return result


def _combine_shares(shares: Sequence[float], within: Sequence[float]) -> list[float]:
    native = getattr(_NATIVE, "combine_shares", None)
    if native is not None:
        # These types convert exactly to binary64; other inputs need upward
        # conversion before they reach the native addition kernel.
        additions = (within if set(map(type, within)) <= {float, np.float16, np.float32, np.float64}
                     else _upper_values(within))
        return list(native(np.asarray(shares, dtype=np.float64), np.asarray(additions, dtype=np.float64)))
    additions = _upper_values(within)
    return [_upper_sum([share, addition]) for share, addition in zip(shares, additions, strict=True)]


def _detection_floors(risks: Sequence[float]) -> tuple[float, float]:
    values = _lower_values(risks)
    native = getattr(_NATIVE, "detection_floors", None)
    if native is not None:
        markov, pairs = native(np.asarray(values, dtype=np.float64))
        return float(markov), float(pairs)
    prefix = pairs = 0.0
    for value in values:
        product = prefix * value
        if product > 0.0:
            product = math.nextafter(product, 0.0)
        pairs = _lower_sum([pairs, product])
        prefix = _lower_sum([prefix, value])
    half = prefix * 0.5
    return (math.nextafter(half, 0.0) if half + half > prefix else half), pairs
