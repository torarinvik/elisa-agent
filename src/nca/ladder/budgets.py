"""Conservative binary64 sums and refinement risk allocation."""

from __future__ import annotations

from collections.abc import Sequence
import math
import numpy as np
from nca import ladder as _ladder


def _upper_sum(values: Sequence[float]) -> float:
    """Bound the exact sum of nonnegative binary64 inputs from above."""
    native = getattr(_ladder._NATIVE, "upper_sum", None)
    if native is not None:
        return float(native(np.asarray(values, dtype=np.float64)))
    total = 0.0
    for x in values:
        rounded = total + float(x)
        if math.isinf(rounded):
            return rounded
        part = rounded - total
        residual = (total - (rounded - part)) + (float(x) - part)
        total = math.nextafter(rounded, math.inf) if residual > 0.0 else rounded
    return total


def _lower_values(values: Sequence[float]) -> list[float]:
    rounded_values = []
    for value in values:
        rounded = float(value)
        rounded_values.append(math.nextafter(rounded, 0.0) if rounded > value else rounded)
    return rounded_values


def _lower_sum(values: Sequence[float]) -> float:
    """Bound the exact sum of nonnegative inputs from below."""
    rounded_values = _lower_values(values)
    native = getattr(_ladder._NATIVE, "lower_sum", None)
    if native is not None:
        return float(native(np.asarray(rounded_values, dtype=np.float64)))
    total = 0.0
    for x in rounded_values:
        rounded = total + x
        if math.isinf(rounded):
            total = math.nextafter(rounded, 0.0)
            continue
        part = rounded - total
        residual = (total - (rounded - part)) + (x - part)
        total = math.nextafter(rounded, 0.0) if residual < 0.0 else rounded
    return total


def allocate_risk(bound: float, priorities: Sequence[float]) -> list[float]:
    """Allocate a current bound using possibly stale, nonnegative priorities.

    Priorities may be a Python sequence or a one-dimensional NumPy array.
    They guide refinement only; their age does not affect the total
    charge in exact arithmetic (THEORY 23.11). Zero priorities receive a
    uniform allocation. If every share underflows, one retains the bound;
    positive allocations are adjusted to cover the bound under binary64 arithmetic.
    """
    if not math.isfinite(bound) or bound < 0:
        raise ValueError("bound must be finite and nonnegative")
    if len(priorities) == 0:
        raise ValueError("risk allocation requires at least one item")
    checked = getattr(_ladder._NATIVE, "risk_shares_covering", None)
    if checked is not None:
        values = np.asarray(priorities)
        if values.ndim == 1 and values.dtype.kind in "biuf" and values.dtype.itemsize <= 8:
            shares = checked(bound, np.asarray(values, dtype=np.float64))
            if not shares:
                raise ValueError("priorities must be finite and nonnegative")
            return shares
    if any(not math.isfinite(p) or p < 0 for p in priorities):
        raise ValueError("priorities must be finite and nonnegative")
    native = getattr(_ladder._NATIVE, "risk_shares", None)
    if native is not None:
        shares = native(bound, np.asarray(priorities, dtype=np.float64))
    else:
        scale = max(priorities)
        weights = [p / scale for p in priorities] if scale > 0 else [1.0] * len(priorities)
        total = math.fsum(weights)
        shares = [bound * (w / total) for w in weights]
    if bound > 0 and not any(shares):
        shares[max(range(len(priorities)), key=priorities.__getitem__)] = bound
    if bound > 0:
        top = max(range(len(shares)), key=shares.__getitem__)
        total, correction = 0.0, 0.0
        for share in shares:
            if share > 0:
                updated = total + share
                if updated == math.inf:
                    return shares
                virtual = updated - total
                residual = (total - (updated - virtual)) + (share - virtual)
                if residual:
                    correction = math.nextafter(correction + residual, -math.inf)
                total = updated
        estimate = total + correction
        lower = math.nextafter(estimate, 0.0) if estimate > 0 else 0.0
        if shares[top] < bound and lower < bound:
            deficit = math.nextafter(bound - lower, math.inf)
            increased = shares[top] + deficit
            shares[top] = bound if increased >= bound else math.nextafter(increased, math.inf)
    return shares
