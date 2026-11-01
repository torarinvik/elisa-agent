"""Confidence intervals for reported accuracies and paired differences, and
count tests against predicted probabilities."""

from __future__ import annotations

import math
from decimal import ROUND_CEILING, Context, Decimal, localcontext
from typing import Sequence

import numpy as np

from nca.native import load

_NATIVE = load("stats")

Z95 = 1.959963984540054


def family_audit_alpha(total: float, audits: int) -> float:
    """Allocate one confidence budget over a predeclared finite audit family."""
    if (not math.isfinite(total) or not 0 < total < 1
            or not isinstance(audits, int) or audits < 1):
        raise ValueError("requires 0 < total < 1 and a positive integer audit count")
    level = total / audits
    if audits > 1:
        level = math.nextafter(level, 0.0)
    if level <= 0:
        raise ValueError("audit confidence allocation underflow")
    return level


def wilson(successes: int, n: int, z: float = Z95) -> tuple[float, float]:
    """Wilson score interval for a binomial proportion."""
    if n == 0:
        return 0.0, 1.0
    p = successes / n
    denominator = 1 + z * z / n
    center = (p + z * z / (2 * n)) / denominator
    half = z * math.sqrt(p * (1 - p) / n + z * z / (4 * n * n)) / denominator
    return max(0.0, center - half), min(1.0, center + half)


def paired_difference(first: Sequence[bool], second: Sequence[bool],
                      z: float = Z95) -> tuple[float, float, float]:
    """Mean of ``second − first`` over paired samples, with a normal-approximation interval.

    Pairing removes the variance shared by both systems on the same samples,
    so the interval is much narrower than one built from two separate
    accuracy intervals.
    """
    n = len(first)
    diffs = [int(b) - int(a) for a, b in zip(first, second)]
    mean = sum(diffs) / n
    variance = sum((d - mean) ** 2 for d in diffs) / (n - 1) if n > 1 else 0.0
    half = z * math.sqrt(variance / n)
    return mean, mean - half, mean + half


def format_interval(value: float, low: float, high: float) -> str:
    return f"{value:.4f} [{low:.4f}, {high:.4f}]"


def format_upper_bound(value: float, digits: int = 3) -> str:
    """Format a binary64 upper bound without rounding it down in decimal."""
    if digits < 1:
        raise ValueError("digits must be positive")
    if not math.isfinite(value):
        return str(value)
    with localcontext(Context(prec=digits, rounding=ROUND_CEILING)):
        return format(+Decimal.from_float(value), f".{digits}g")


def binomial_cdf(k: int, n: int, r: float) -> float:
    """``P(Binomial(n, r) <= k)``."""
    if n < 0:
        raise ValueError("binomial trial count must be nonnegative")
    if k < 0:
        return 0.0
    if k >= n:
        return 1.0
    if r <= 0.0:
        return 1.0
    if r >= 1.0:
        return float(k >= n)
    return sum(math.exp(math.lgamma(n + 1) - math.lgamma(i + 1) - math.lgamma(n - i + 1)
                        + i * math.log(r) + (n - i) * math.log1p(-r))
               for i in range(k + 1))


def clopper_pearson_upper(k: int, n: int, alpha: float) -> float:
    """Exact one-sided upper confidence bound on a binomial rate: the largest
    ``r`` with ``P(Binomial(n, r) <= k) >= alpha``, so that the true rate
    exceeds it with probability at most ``alpha``."""
    if n == 0 or k >= n:
        return 1.0
    low, high = k / n, 1.0
    for _ in range(60):
        mid = (low + high) / 2
        if binomial_cdf(k, n, mid) >= alpha:
            low = mid
        else:
            high = mid
    return low


def poisson_binomial_tails(observed: int, probabilities: Sequence[float]) -> tuple[float, float]:
    """``P(X >= observed)`` and ``P(X <= observed)`` for ``X`` a sum of
    independent Bernoulli variables with the given probabilities (clipped to
    ``[0, 1]``). If each event's probability is only bounded above by its
    entry, the first is still a valid one-sided p-value for an excess."""
    if observed < 0:
        return 1.0, 0.0
    if observed > len(probabilities):
        return 0.0, 1.0
    clipped = np.clip(probabilities, 0.0, 1.0)
    # Promote reduced-precision probabilities before computing their complements:
    # rounding 1-p in float16/32 can make p + (1-p) differ substantially from 1.
    if clipped.dtype.kind == "f" and clipped.dtype.itemsize < 8:
        clipped = clipped.astype(np.float64)
    native = getattr(_NATIVE, "poisson_binomial_pmf", None)
    if (native is not None and clipped.ndim == 1 and clipped.dtype.kind in "biuf"
            and clipped.dtype.itemsize <= 8):
        values = np.ascontiguousarray(clipped, dtype=np.float64)
        complements = np.ascontiguousarray(1 - clipped, dtype=np.float64)
        pmf = np.asarray(native(values, complements), dtype=float)
    else:
        pmf = _poisson_binomial_pmf_reference(clipped)
    upper = float(pmf[observed:].sum())
    lower = float(pmf[:observed + 1].sum())
    if not math.isnan(upper):
        upper = 1.0 if observed == 0 else min(upper, 1.0)
    if not math.isnan(lower):
        lower = 1.0 if observed == len(probabilities) else min(lower, 1.0)
    return upper, lower


def _poisson_binomial_pmf_reference(probabilities: Sequence[float]) -> np.ndarray:
    pmf = np.zeros(len(probabilities) + 1)
    pmf[0] = 1.0
    for n, p in enumerate(probabilities, start=1):
        pmf[1:n + 1] = pmf[1:n + 1] * (1 - p) + pmf[:n] * p
        pmf[0] *= 1 - p
    return pmf


def poisson_binomial_upper_bound(observed: int, probabilities: Sequence[float]) -> float:
    """Upward-rounded bound on the excess tail for independent Bernoulli events.

    Arithmetic assumes IEEE 754 binary64 operations rounded to nearest,
    gradual underflow, and a correctly rounded ``nextafter``. NaNs propagate.
    """
    clipped = np.clip(probabilities, 0.0, 1.0)
    if clipped.ndim != 1 or clipped.dtype.kind not in "biuf":
        raise ValueError("probabilities must be a one-dimensional real sequence")
    if np.isnan(clipped).any():
        return math.nan
    n = len(clipped)
    if observed <= 0:
        return 1.0
    if observed > n:
        return 0.0
    with np.errstate(under="ignore"):
        values = np.ascontiguousarray(clipped, dtype=np.float64)
        if clipped.dtype.kind == "f" and clipped.dtype.itemsize > 8:
            lower = np.nextafter(values, 0.0)
            upper = np.nextafter(values, 1.0)
        else:
            lower = upper = values
        complements = np.nextafter(1.0 - lower, 1.0)
    complements = np.where(lower == 1.0, 0.0, complements)
    native = getattr(_NATIVE, "poisson_binomial_upper", None)
    if native is not None:
        return float(native(upper, complements, observed))
    return _poisson_binomial_upper_reference(observed, upper, complements)


def _poisson_binomial_upper_reference(observed: int, probabilities: np.ndarray,
                                      complements: np.ndarray) -> float:
    """Directed-rounding reference for the truncated failure-count recurrence."""
    def product(a: float, b: float) -> float:
        if a == 0 or b == 0:
            return 0.0
        return min(1.0, math.nextafter(a * b, 1.0))

    def add(a: float, b: float) -> float:
        if a == 0:
            return b
        if b == 0:
            return a
        return min(1.0, math.nextafter(a + b, 1.0))

    width = len(probabilities) - observed
    pmf = [1.0] + [0.0] * width
    for i, (p, q) in enumerate(zip(probabilities, complements)):
        p, q = float(p), float(q)
        for k in range(min(i + 1, width), 0, -1):
            pmf[k] = add(product(p, pmf[k]), product(q, pmf[k - 1]))
        pmf[0] = product(p, pmf[0])
    total = 0.0
    for value in pmf:
        total = add(total, value)
    return total
