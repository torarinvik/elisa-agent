"""Posterior decoding and checked sequence risks."""

from __future__ import annotations

from collections.abc import Sequence
from dataclasses import dataclass
import math
import numpy as np
from nca import priors as _priors
from nca.priors import ArityPrior, format_prior
from nca.priors.arithmetic import (
    _MarginalPrecisionError, _PartitionArithmeticError, _WeightArithmeticError,
    _center_log_rows, _partition_log_add, _partition_log_product,
    risk_from_log_weight, risk_from_partition,
)
from nca.priors.symbols import _integer_symbols, _native_symbol_pair


def _native_format_symbols(symbols: Sequence[int], length: int) -> np.ndarray:
    """Map arities that cannot fit a complete prefix to an unreachable sentinel."""
    native = getattr(_priors._NATIVE, "clamp_format_symbols", None)
    if native is not None and len(symbols) >= 32:
        values = np.asarray(symbols)
        if values.dtype.kind == "i":
            result = np.array(values, dtype=np.int64, order="C", copy=True)
            native(result, length)
            return result
        unsigned = getattr(_priors._NATIVE, "clamp_unsigned_format_symbols", None)
        if unsigned is not None and values.dtype.kind == "u":
            # Values with the high bit set exceed any representable sequence length.
            result = np.array(values, dtype=np.uint64, order="C", copy=True).view(np.int64)
            unsigned(result, length)
            return result
    return np.fromiter((max(-1, min(int(a), length)) for a in symbols),
                       dtype=np.int64, count=len(symbols))


def sequence_log_weight(log_probs: np.ndarray, alphabet: Sequence[int],
                        selected: Sequence[int]) -> float:
    """Log product of selected weights; reject detected arithmetic loss (§21.5)."""
    if log_probs.shape != (len(selected), len(alphabet)):
        raise ValueError("weights must have one row per selected symbol and one column per class")
    if not _integer_symbols(alphabet) or not _integer_symbols(selected):
        raise ValueError("alphabet and selected symbols must be integers")
    rows = np.ascontiguousarray(log_probs, dtype=np.float64)
    validate = getattr(_priors._NATIVE, "valid_log_weights", None)
    valid = (validate(rows.reshape(-1)) if validate is not None
             else not (np.any(np.isnan(rows)) or np.any(np.isposinf(rows))))
    if not valid:
        raise ValueError("weights must be finite or negative infinity")
    native_weight = getattr(_priors._NATIVE, "sequence_log_weight", None)
    if native_weight is not None:
        symbols, encoded = _native_symbol_pair(tuple(alphabet), selected)
        result = float(native_weight(rows.reshape(-1),
                                     symbols, encoded))
        if math.isnan(result) or result == math.inf:
            raise _WeightArithmeticError("sequence log weight arithmetic is not finite or loses precision")
        return result
    symbols = tuple(alphabet)
    total, failed = 0.0, False
    for k, symbol in enumerate(selected):
        try:
            column = symbols.index(symbol)
        except ValueError:
            return -math.inf
        reading = float(rows[k, column])
        if reading == -math.inf:
            return -math.inf
        if not failed:
            try:
                total = _partition_log_product(total, reading, "sequence log weight")
            except _PartitionArithmeticError:
                failed = True
    if failed:
        raise _WeightArithmeticError("sequence log weight arithmetic is not finite or loses precision")
    return total


def _generic_format_sequence_risk(rows: np.ndarray, alphabet: Sequence[int], selected: Sequence[int]) -> float:
    """Format risk with a checked rescaling retry after arithmetic failure."""
    try:
        return _generic_format_sequence_risk_once(rows, alphabet, selected)
    except _PartitionArithmeticError as failure:
        centered = _center_log_rows(rows)
        if centered is None:
            raise
        try:
            return _generic_format_sequence_risk_once(centered, alphabet, selected)
        except _PartitionArithmeticError:
            raise failure from None


def _generic_format_sequence_risk_once(rows: np.ndarray, alphabet: Sequence[int], selected: Sequence[int]) -> float:
    """Exact model risk with selected and alternative paths summed separately."""
    native = getattr(_priors._NATIVE, "format_partition", None)
    if native is not None:
        m = len(rows)
        partition = native(np.ascontiguousarray(rows, dtype=np.float64).reshape(-1),
                           _native_format_symbols(alphabet, m),
                           _native_format_symbols(selected, m))
        if len(partition) == 2:
            return risk_from_partition(*partition)
        raise _PartitionArithmeticError("format partition arithmetic is not finite or loses precision")
    m = len(rows)
    alternatives = np.full(m + 2, -np.inf)
    matched, state = 0.0, 1
    for k in range(m):
        following = np.full(m + 2, -np.inf)
        for n in range(1, m - k + 1):
            for j, value in enumerate(alphabet):
                arity = int(value)
                target = n - 1 + arity
                if target > m - k - 1:
                    continue
                reading = float(rows[k, j])
                if alternatives[n] != -math.inf and reading != -math.inf:
                    through = _partition_log_product(float(alternatives[n]), reading, "format")
                    following[target] = _partition_log_add(float(following[target]), through, "format")
                if n == state and arity != selected[k] and matched != -math.inf and reading != -math.inf:
                    through = _partition_log_product(matched, reading, "format")
                    following[target] = _partition_log_add(float(following[target]), through, "format")
        column = next((j for j, value in enumerate(alphabet) if value == selected[k]), None)
        if column is None or state < 1 or state - 1 + int(selected[k]) > m - k - 1:
            matched = -math.inf
        else:
            reading = float(rows[k, column])
            if matched != -math.inf and reading != -math.inf:
                matched = _partition_log_product(matched, reading, "format")
            else:
                matched = -math.inf
            state += int(selected[k]) - 1
        alternatives = following
    return risk_from_partition(matched if state == 0 else -math.inf, float(alternatives[0]))


def format_sequence_risk(log_probs: np.ndarray, alphabet: Sequence[int],
                         selected: Sequence[int]) -> float:
    """Risk of an arity sequence under the complete prefix format."""
    alphabet = tuple(alphabet)
    if (not alphabet or len(set(alphabet)) != len(alphabet)
            or any(not isinstance(a, (int, np.integer)) or a < 0 for a in alphabet)):
        raise ValueError("format risk requires distinct nonnegative arities")
    rows = np.asarray(log_probs, dtype=np.float64)
    if (rows.ndim != 2 or rows.shape[1] != len(alphabet) or not len(rows)
            or len(selected) != len(rows) or np.any(np.isnan(rows)) or np.any(np.isposinf(rows))):
        raise ValueError("format risk requires nonempty rows over the alphabet")
    if not _integer_symbols(selected):
        raise ValueError("selected symbols must be integers")
    if any(a > 2 for a in alphabet):
        return _generic_format_sequence_risk(rows, alphabet, selected)
    if alphabet != (0, 1, 2):
        canonical = np.full((len(rows), 3), -np.inf)
        for column, arity in enumerate(alphabet):
            canonical[:, arity] = rows[:, column]
        rows = canonical
    return format_prior(len(rows)).sequence_risk(rows, selected)


@dataclass(frozen=True)
class Decoded:
    """Maximum-weight accepted arity sequence, log normalizer and marginals.

    Acceptance is the prefix format by default, or the supplied prior automaton.
    Posterior weights include the prior when present.
    Marginal rows are checked for finite nonnegative values and approximate
    unit sum; this check does not certify their numerical accuracy.
    """

    arities: tuple[int, ...]
    log_z: float
    marginals: np.ndarray
    prior: ArityPrior | None = None

    def __post_init__(self) -> None:
        if (self.marginals.ndim != 2 or self.marginals.shape[0] != len(self.arities)
                or (self.prior is not None and self.marginals.shape[1] != len(self.prior.alphabet))):
            raise ValueError("decoder marginal shape must match the sequence and prior alphabet")
        # This detects gross numerical loss; it is not a roundoff certificate.
        check = getattr(_priors._NATIVE, "posterior_rows_valid", None)
        if check is not None and self.marginals.ndim == 2 and self.marginals.shape[1]:
            valid = check(np.ascontiguousarray(self.marginals, dtype=np.float64).ravel(),
                          self.marginals.shape[1], 1.01e-8)
        else:
            with np.errstate(over="ignore", invalid="ignore"):
                totals = self.marginals.sum(axis=1)
            valid = (np.all(np.isfinite(self.marginals)) and np.all(self.marginals >= 0)
                     and np.allclose(totals, 1.0, rtol=1e-8, atol=1e-10))
        if not valid:
            raise _MarginalPrecisionError("decoder marginals are not normalized; numerical precision was lost")

    def log_weight(self, log_probs: np.ndarray, alphabet: Sequence[int],
                   arities: Sequence[int]) -> float:
        """Log weight of a sequence under readings and the optional prior."""
        if self.prior is not None and tuple(alphabet) != self.prior.alphabet:
            raise ValueError("alphabet must match the decoded prior")
        try:
            reading = sequence_log_weight(log_probs, alphabet, arities)
        except _WeightArithmeticError:
            if self.prior is not None and self.prior.log_weight(arities) == -math.inf:
                return -math.inf
            raise
        if self.prior is None or reading == -math.inf:
            return reading
        prior_weight = self.prior.log_weight(arities)
        if prior_weight == -math.inf:
            return -math.inf
        try:
            return _partition_log_product(reading, prior_weight, "decoded log weight")
        except _PartitionArithmeticError as exc:
            raise _WeightArithmeticError(
                "decoded log weight arithmetic is not finite or loses precision"
            ) from exc

    def risk(self, log_probs: np.ndarray, alphabet: Sequence[int],
             arities: Sequence[int] | None = None) -> float:
        """Posterior probability that the true sequence differs from
        ``arities`` (default: the decoded one), ``1 − weight / Z``."""
        chosen = self.arities if arities is None else arities
        if self.prior is not None:
            if tuple(alphabet) != self.prior.alphabet:
                raise ValueError("alphabet must match the decoded prior")
            return self.prior.sequence_risk(log_probs, chosen)
        symbols = tuple(alphabet)
        if symbols and len(set(symbols)) == len(symbols) and all(
                isinstance(a, (int, np.integer)) and a >= 0 for a in symbols):
            return format_sequence_risk(log_probs, symbols, chosen)
        return risk_from_log_weight(self.log_weight(log_probs, symbols, chosen), self.log_z)
