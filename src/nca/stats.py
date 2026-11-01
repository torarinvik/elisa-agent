"""Confidence intervals for reported accuracies and paired differences, and
count tests against predicted probabilities."""

from __future__ import annotations

import math
from typing import Sequence

import numpy as np

Z95 = 1.959963984540054


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


def binomial_cdf(k: int, n: int, r: float) -> float:
    """``P(Binomial(n, r) <= k)``."""
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
    pmf = np.zeros(len(probabilities) + 1)
    pmf[0] = 1.0
    for n, p in enumerate(np.clip(probabilities, 0.0, 1.0), start=1):
        pmf[1:n + 1] = pmf[1:n + 1] * (1 - p) + pmf[:n] * p
        pmf[0] *= 1 - p
    return float(pmf[observed:].sum()), float(pmf[:observed + 1].sum())
