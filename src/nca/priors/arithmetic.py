"""Checked log arithmetic and posterior risk calculations for structural priors."""

from __future__ import annotations

import math
from fractions import Fraction

import numpy as np


def risk_from_log_weight(weight: float, log_z: float) -> float:
    """Complement of a normalized log weight, stable near probability one."""
    if math.isnan(weight) or weight == math.inf or not math.isfinite(log_z):
        raise ValueError("sequence risk requires a finite normalizer and finite or zero weight")
    difference = weight - log_z
    if difference >= 1.01e-8:
        raise ValueError("sequence risk selected weight exceeds the normalizer")
    return -math.expm1(min(0.0, difference))


def risk_from_partition(chosen: float, alternative: float) -> float:
    """Normalize separately summed selected and alternative log weights."""
    if any(math.isnan(x) or x == math.inf for x in (chosen, alternative)):
        raise ValueError("sequence risk requires finite or negative-infinite log weights")
    if chosen == -math.inf:
        if alternative == -math.inf:
            raise ValueError("sequence risk requires positive total mass")
        return 1.0
    if alternative == -math.inf:
        return 0.0
    difference = alternative - chosen
    if difference <= 0:
        ratio = math.exp(difference)
        return math.nextafter(0.0, 1.0) if ratio == 0.0 else ratio / (1.0 + ratio)
    return 1.0 / (1.0 + math.exp(-difference))


class _PartitionArithmeticError(ValueError):
    """A partition could not be represented with the required local precision."""


class _WeightArithmeticError(ValueError):
    """A sequence weight could not be represented accurately."""


class _MarginalPrecisionError(ValueError):
    """A decoder produced visibly invalid marginal probabilities."""


def _partition_log_add(left: float, right: float, context: str) -> float:
    with np.errstate(over="ignore"):
        result = float(np.logaddexp(left, right))
    if abs(result) >= 67108864.0 and math.isfinite(left) and math.isfinite(right):
        larger, smaller = max(left, right), min(left, right)
        correction = math.log1p(math.exp(smaller - larger))
        if abs((result - larger) - correction) >= 1.01e-8:
            raise _PartitionArithmeticError(f"{context} partition arithmetic loses precision")
    return result


def _partition_log_product(left: float, right: float, context: str) -> float:
    result = left + right
    if not math.isfinite(result):
        raise _PartitionArithmeticError(f"{context} partition arithmetic is not finite")
    if abs(result) < 67108864.0:
        return result
    virtual = result - left
    residual = (left - (result - virtual)) + (right - virtual)
    if not math.isfinite(residual) or abs(residual) >= 1.01e-8:
        raise _PartitionArithmeticError(f"{context} partition arithmetic loses precision")
    return result


def _add_evidence(total: float, correction: float, value: float) -> tuple[float, float]:
    """Accumulate a TwoSum residual for later score recovery."""
    result = total + value
    if not math.isfinite(result):
        raise ValueError("summed evidence overflow")
    virtual = result - total
    residual = (total - (result - virtual)) + (value - virtual)
    try:
        correction = _partition_log_product(correction, residual, "summed evidence")
    except _PartitionArithmeticError as exc:
        raise ValueError("summed evidence overflow or loses precision") from exc
    return result, correction


def _decoder_log_product(left: float, right: float, context: str = "prior normalizer") -> float:
    if not math.isfinite(left + right):
        raise ValueError(f"{context} arithmetic is not finite")
    try:
        return _partition_log_product(left, right, "prior decoder")
    except _PartitionArithmeticError as exc:
        raise _MarginalPrecisionError(f"{context} arithmetic is not finite or loses precision") from exc


def _decoder_log_add(left: float, right: float, context: str = "prior normalizer") -> float:
    try:
        return _partition_log_add(left, right, "prior decoder")
    except _PartitionArithmeticError as exc:
        raise _MarginalPrecisionError(f"{context} arithmetic is not finite or loses precision") from exc


def _center_log_rows(rows: np.ndarray) -> np.ndarray | None:
    """Remove common row weights if the shifts retain local precision."""
    offsets = np.max(rows, axis=1)
    if not np.all(np.isfinite(offsets)):
        return None
    with np.errstate(over="ignore", invalid="ignore"):
        centered = rows - offsets[:, None]
        virtual = centered - rows
        residual = (rows - (centered - virtual)) + (-offsets[:, None] - virtual)
    finite = np.isfinite(rows)
    if (np.any(~np.isfinite(centered[finite])) or np.any(~np.isfinite(residual[finite]))
            or np.any(np.abs(residual[finite]) >= 1.01e-8)):
        return None
    return centered


def _evidence_difference(numerator: float, denominator: float,
                         posterior: np.ndarray, base: np.ndarray) -> float:
    if numerator == -math.inf:
        return -math.inf
    if not math.isfinite(numerator):
        raise ValueError("candidate evidence must be finite or negative infinity")
    if max(abs(numerator), abs(denominator)) >= 16777216.0:
        raise ValueError("prior evidence normalizers are too large for reliable subtraction")
    return numerator - denominator


def _within_score_error(best: float, score: float, error: float) -> bool:
    """Compare the score gap with twice the error without avoidable underflow."""
    gap = best - score
    if math.isfinite(gap):
        threshold = 2.0 * float(error)
        if gap != threshold:
            return gap < threshold
    else:
        half_gap = best / 2 - score / 2
        if half_gap != error:
            return half_gap < error
    # Rounded equality can conceal a gap on either side of the boundary.
    return (Fraction.from_float(best) - Fraction.from_float(score)
            <= 2 * Fraction.from_float(float(error)))
