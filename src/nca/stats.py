"""Confidence intervals for reported accuracies and paired differences, and
count tests against predicted probabilities."""

from __future__ import annotations

import math
from decimal import ROUND_CEILING, Context, Decimal, localcontext
from numbers import Integral
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
    if (not isinstance(successes, Integral) or not isinstance(n, Integral)
            or n < 0 or not 0 <= successes <= n):
        raise ValueError("requires integer counts 0 <= successes <= n")
    if not math.isfinite(z) or z < 0:
        raise ValueError("z must be finite and nonnegative")
    successes, n = int(successes), int(n)
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

    Requires at least two matched observations. The normal approximation can
    be unreliable for small samples or few discordant pairs.
    """
    n = len(first)
    if n != len(second) or n < 2:
        raise ValueError("paired inputs must have equal lengths of at least two")
    if not math.isfinite(z) or z < 0:
        raise ValueError("z must be finite and nonnegative")
    diffs = [int(b) - int(a) for a, b in zip(first, second)]
    mean = sum(diffs) / n
    variance = sum((d - mean) ** 2 for d in diffs) / (n - 1)
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


def pair_gap_sum(values: Sequence[float], gap: int) -> float:
    """Estimate the sum of products for pairs separated by at least ``gap``."""
    if not isinstance(gap, Integral) or gap < 1:
        raise ValueError("gap must be a positive integer")
    risks = np.asarray(values, dtype=np.float64)
    if risks.ndim != 1 or not np.isfinite(risks).all() or (risks < 0).any():
        raise ValueError("values must be a one-dimensional sequence of finite nonnegative numbers")
    if gap >= len(risks):
        return 0.0
    native = getattr(_NATIVE, "pair_gap_sum", None)
    if native is not None and gap < 2**63:
        return float(native(np.ascontiguousarray(risks), gap))
    suffix = total = 0.0
    for i in range(len(risks) - gap - 1, -1, -1):
        suffix += float(risks[i + gap])
        total += float(risks[i]) * suffix
    return total


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
    """Conservative numerical upper bound for the Clopper–Pearson limit.

    The exact limit is the largest ``r`` with ``P(Binomial(n, r) <= k)``
    at least ``alpha``. CDF comparisons round upward and the upper bisection
    endpoint is returned, under the IEEE assumptions of
    :func:`poisson_binomial_upper_bound`.
    """
    _validate_binomial_audit(k, n, alpha)
    if n == 0 or k >= n:
        return 1.0
    native_alpha = float(alpha)
    if native_alpha > alpha:
        native_alpha = math.nextafter(native_alpha, 0.0)
    native_zero = getattr(_NATIVE, "clopper_zero_upper", None)
    if k == 0 and native_zero is not None and n < 2**63 and native_alpha > 0.0:
        return float(native_zero(n, native_alpha))
    native = getattr(_NATIVE, "clopper_upper", None)
    if native is not None and n < 2**63 and native_alpha > 0.0:
        return float(native(k, n, native_alpha))
    low, high = 0.0, 1.0
    for _ in range(60):
        mid = (low + high) / 2
        if _binomial_cdf_upper(k, n, mid) >= alpha:
            low = mid
        else:
            high = mid
    return high


def _validate_binomial_audit(k: int, n: int, alpha: float) -> None:
    if not isinstance(k, Integral) or not isinstance(n, Integral) or n < 0 or not 0 <= k <= n:
        raise ValueError("requires integer counts 0 <= k <= n")
    if not math.isfinite(alpha) or not 0 < alpha < 1:
        raise ValueError("alpha must be strictly between zero and one")


def _binomial_cdf_upper(k: int, n: int, rate: float) -> float:
    """Upper bound on P(Binomial(n, rate) <= k), for 0 <= k < n."""
    if rate <= 0.0:
        return 1.0
    if rate >= 1.0:
        return 0.0
    lower_rate = float(rate)
    if lower_rate > rate:
        lower_rate = math.nextafter(lower_rate, 0.0)
    if lower_rate == 0.0:
        return 1.0
    native = getattr(_NATIVE, "binomial_cdf_upper", None)
    if k > 0 and native is not None and n < 2**63:
        return float(native(k, n, lower_rate))
    failure = math.nextafter(1.0 - lower_rate, 1.0)
    if k == 0:
        # P(no failures) = (1-rate)^n; exponentiation by squaring, rounded up.
        power, result, exponent = failure, 1.0, n
        while exponent:
            if exponent & 1:
                result = min(1.0, math.nextafter(result * power, 1.0))
            exponent //= 2
            if exponent:
                power = min(1.0, math.nextafter(power * power, 1.0))
        return result
    return poisson_binomial_upper_bound(n - k, [failure] * n)


def clopper_pearson_exceeds(k: int, n: int, alpha: float, threshold: float) -> bool:
    """Prove that the exact Clopper–Pearson limit exceeds ``threshold``.

    A false result is inconclusive; this is intended for safe early rejection.
    """
    _validate_binomial_audit(k, n, alpha)
    if math.isnan(threshold):
        return False
    if threshold < 0:
        return True
    if threshold >= 1:
        return False
    if n == 0 or k >= n:
        return True
    upper_rate = float(threshold)
    if upper_rate < threshold:
        upper_rate = math.nextafter(upper_rate, 1.0)
    tail = poisson_binomial_upper_bound(k + 1, [upper_rate] * n)
    lower_cdf = math.nextafter(1.0 - tail, 0.0) if tail < 1.0 else 0.0
    return lower_cdf > alpha


def clopper_pearson_within(k: int, n: int, alpha: float, threshold: float) -> bool:
    """Prove the exact Clopper–Pearson limit is at most ``threshold``.

    A false result is inconclusive, so uncertain cases are not certified.
    """
    _validate_binomial_audit(k, n, alpha)
    if math.isnan(threshold) or threshold <= 0:
        return False
    if threshold >= 1:
        return True
    if n == 0 or k >= n:
        return False
    return _binomial_cdf_upper(k, n, threshold) < alpha


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
    """Directed-rounding reference using a short truncated count range."""
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

    certain = 0
    events = []
    for p, q in zip(probabilities, complements):
        p, q = float(p), float(q)
        if p == 1.0 and q == 0.0:
            certain += 1
        elif p != 0.0 or q != 1.0:
            events.append((p, q))
    threshold = observed - certain
    if threshold <= 0:
        return 1.0
    if threshold > len(events):
        return 0.0
    width = len(events) - threshold
    if threshold < width:
        pmf = [1.0] + [0.0] * (threshold - 1)
        tail = 0.0
        for i, (p, q) in enumerate(events):
            tail = add(tail, product(p, pmf[-1]))
            for k in range(min(i + 1, threshold - 1), 0, -1):
                pmf[k] = add(product(q, pmf[k]), product(p, pmf[k - 1]))
            pmf[0] = product(q, pmf[0])
        return tail
    pmf = [1.0] + [0.0] * width
    for i, (p, q) in enumerate(events):
        for k in range(min(i + 1, width), 0, -1):
            pmf[k] = add(product(p, pmf[k]), product(q, pmf[k - 1]))
        pmf[0] = product(p, pmf[0])
    total = 0.0
    for value in pmf:
        total = add(total, value)
    return total
