"""Confidence intervals for reported accuracies and paired differences."""

from __future__ import annotations

import math
from typing import Sequence

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
