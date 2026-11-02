"""Weighted arity automata, structural priors and held-out evidence selection (§27)."""

from __future__ import annotations

import math
from collections.abc import Callable, Iterable, Sequence
from dataclasses import dataclass
from functools import lru_cache
from itertools import chain, repeat
from typing import Any

import numpy as np

from nca.native import load

_NATIVE = load("decoding")


def _integer_symbols(symbols: Sequence[int]) -> bool:
    values = np.asarray(symbols)
    if values.ndim != 1:
        return False
    if values.size == 0 or values.dtype.kind in "iu":
        return True
    return all(isinstance(a, (int, np.integer)) for a in symbols)


@lru_cache(maxsize=32)
def _dense_alphabet_needed(alphabet: tuple[int, ...]) -> bool:
    return any(not -(2**63) <= int(a) < 2**63 for a in alphabet)


@lru_cache(maxsize=32)
def _dense_native_alphabet(size: int) -> np.ndarray:
    return np.frombuffer(np.arange(size, dtype=np.int64).tobytes(), dtype=np.int64)


@lru_cache(maxsize=32)
def _native_alphabet(alphabet: tuple[int, ...]) -> np.ndarray:
    """Immutable native buffer shared by priors with the same alphabet."""
    if _dense_alphabet_needed(alphabet):
        return _dense_native_alphabet(len(alphabet))
    return np.frombuffer(np.asarray(alphabet, dtype=np.int64).tobytes(), dtype=np.int64)


def _native_symbol_pair(alphabet: tuple[int, ...], selected: Sequence[int]) -> tuple[np.ndarray, np.ndarray]:
    dense = _dense_alphabet_needed(alphabet)
    values = np.asarray(selected)
    if values.dtype.kind == "u" and np.any(values > np.iinfo(np.int64).max):
        dense = True
    if not dense:
        try:
            return _native_alphabet(alphabet), np.ascontiguousarray(values, dtype=np.int64)
        except OverflowError:
            dense = True
    indices: dict[int, int] = {}
    for j, symbol in enumerate(alphabet):
        indices.setdefault(int(symbol), j)
    encoded = np.fromiter((indices.get(int(symbol), -1) for symbol in selected),
                          dtype=np.int64, count=len(selected))
    return _dense_native_alphabet(len(alphabet)), encoded


def _native_decoded_symbols(alphabet: tuple[int, ...], selected: Sequence[int]) -> tuple[int, ...]:
    if _dense_alphabet_needed(alphabet):
        return tuple(int(alphabet[int(index)]) for index in selected)
    return tuple(int(symbol) for symbol in selected)


def _native_format_symbols(symbols: Sequence[int], length: int) -> np.ndarray:
    """Map arities that cannot fit a complete prefix to an unreachable sentinel."""
    return np.fromiter((max(-1, min(int(a), length)) for a in symbols),
                       dtype=np.int64, count=len(symbols))


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
    total = 0.0
    for offset in offsets:
        total += float(offset)
        if not math.isfinite(total):
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


def _center_prior(rows: np.ndarray, prior: ArityPrior) -> tuple[np.ndarray, ArityPrior, float, float] | None:
    """Remove common row, edge and final weights when their shifts are representable."""
    centered_rows = _center_log_rows(rows)
    edges = np.where(prior.transitions >= 0, prior.log_weights, -math.inf)
    centered_edges = _center_log_rows(edges.reshape(1, -1))
    centered_final = _center_log_rows(prior.log_final.reshape(1, -1))
    if centered_rows is None or centered_edges is None or centered_final is None:
        return None
    edge_offset, final_offset = float(np.max(edges)), float(np.max(prior.log_final))
    try:
        common = math.fsum(chain((float(x) for x in np.max(rows, axis=1)),
                                 repeat(edge_offset, len(rows)), (final_offset,)))
    except OverflowError:
        return None
    if not math.isfinite(common):
        return None
    centered_prior = ArityPrior(prior.alphabet, prior.transitions, centered_edges.reshape(edges.shape),
                                centered_final.ravel(), prior.start)
    return centered_rows, centered_prior, edge_offset, final_offset


def _evidence_prior(base_rows: np.ndarray, prior: ArityPrior) -> ArityPrior:
    """Use common prior shifts that cancel in a fixed-length evidence ratio."""
    if not len(base_rows):
        return prior
    edge_offset = float(np.max(prior.log_weights, where=prior.transitions >= 0, initial=-math.inf))
    final_offset = float(np.max(prior.log_final))
    # Leave generous binary64 headroom for subtracting the two log normalizers.
    if (math.isfinite(edge_offset) and math.isfinite(final_offset)
            and len(base_rows) * abs(edge_offset) + abs(final_offset) < 16777216.0):
        return prior
    shifted = _center_prior(base_rows, prior)
    if shifted is not None:
        return shifted[1]
    if prior.log_normalizer(base_rows) == -math.inf:
        raise ValueError("candidate prior has zero mass under the base")
    raise ValueError("prior normalizer rescaling is not finite or loses precision")


def _evidence_difference(numerator: float, denominator: float,
                         posterior: np.ndarray, base: np.ndarray) -> float:
    if numerator == -math.inf:
        return -math.inf
    if not math.isfinite(numerator):
        raise ValueError("candidate evidence must be finite or negative infinity")
    if max(abs(numerator), abs(denominator)) >= 16777216.0:
        if np.array_equal(posterior, base):
            return 0.0
        raise ValueError("prior evidence normalizers are too large for reliable subtraction")
    return numerator - denominator


def _restore_centered_decoded(rows: np.ndarray, decoded: Decoded | None, *,
                              prior: ArityPrior | None = None,
                              edge_offset: float = 0.0, final_offset: float = 0.0) -> Decoded:
    if decoded is None:
        raise _MarginalPrecisionError("centered decoding unexpectedly has no supported path")
    try:
        log_z = math.fsum(chain((float(offset) for offset in np.max(rows, axis=1)),
                                repeat(edge_offset, len(rows)), (final_offset, decoded.log_z)))
    except OverflowError as exc:
        raise _MarginalPrecisionError("restored decoder normalizer is not finite") from exc
    if not math.isfinite(log_z):
        raise _MarginalPrecisionError("restored decoder normalizer is not finite")
    return Decoded(decoded.arities, log_z, decoded.marginals, prior if prior is not None else decoded.prior)


def sequence_log_weight(log_probs: np.ndarray, alphabet: Sequence[int],
                        selected: Sequence[int]) -> float:
    """Log product of selected weights; reject detected arithmetic loss (§21.5)."""
    if log_probs.shape != (len(selected), len(alphabet)):
        raise ValueError("weights must have one row per selected symbol and one column per class")
    if not _integer_symbols(alphabet) or not _integer_symbols(selected):
        raise ValueError("alphabet and selected symbols must be integers")
    native_weight = getattr(_NATIVE, "sequence_log_weight", None)
    if native_weight is not None:
        symbols, encoded = _native_symbol_pair(tuple(alphabet), selected)
        result = float(native_weight(np.asarray(log_probs, dtype=np.float64).reshape(-1),
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
        reading = float(log_probs[k, column])
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

@dataclass(frozen=True)
class ArityPrior:
    """Weighted deterministic arity automaton (§27).

    Missing transitions are -1. Log edge and final weights may be -inf.
    Formula priors must incorporate the format constraint in their automaton.
    Arrays use immutable backing storage so decoded risks retain their prior.
    """

    alphabet: tuple[int, ...]
    transitions: np.ndarray
    log_weights: np.ndarray
    log_final: np.ndarray
    start: int = 0

    def __post_init__(self) -> None:
        alphabet = tuple(self.alphabet)
        transitions = np.array(self.transitions, copy=True)
        weights = np.array(self.log_weights, dtype=np.float64, copy=True)
        final = np.array(self.log_final, dtype=np.float64, copy=True)
        if (not alphabet or len(set(alphabet)) != len(alphabet)
                or any(not isinstance(a, (int, np.integer)) or a < 0 for a in alphabet)
                or final.ndim != 1 or not len(final)
                or transitions.shape != (len(final), len(alphabet))
                or not np.issubdtype(transitions.dtype, np.integer)
                or weights.shape != transitions.shape
                or not isinstance(self.start, (int, np.integer))
                or not 0 <= self.start < len(final)
                or np.any(transitions < -1) or np.any(transitions >= len(final))
                or np.any(np.isnan(weights)) or np.any(np.isposinf(weights))
                or np.any(np.isnan(final)) or np.any(np.isposinf(final))):
            raise ValueError("invalid weighted arity automaton")
        object.__setattr__(self, "alphabet", alphabet)
        for name, array in (("transitions", transitions.astype(np.int64)),
                            ("log_weights", weights), ("log_final", final)):
            frozen = np.frombuffer(array.tobytes(order="C"), dtype=array.dtype).reshape(array.shape)
            object.__setattr__(self, name, frozen)

    def __setstate__(self, state: dict[str, Any]) -> None:
        if self.__dict__:
            raise TypeError("cannot restore state into an initialized prior")
        for name, value in state.items():
            object.__setattr__(self, name, value)
        self.__post_init__()

    def log_weight(self, arities: Sequence[int]) -> float:
        """Log prior weight, or -inf for a forbidden sequence."""
        if not _integer_symbols(arities):
            raise ValueError("selected symbols must be integers")
        native = getattr(_NATIVE, "prior_log_weight", None)
        if native is not None:
            alphabet, selected = _native_symbol_pair(self.alphabet, arities)
            result = float(native(alphabet,
                                  self.transitions.reshape(-1), self.log_weights.reshape(-1),
                                  self.log_final, self.start, selected))
            if math.isnan(result) or result == math.inf:
                raise _WeightArithmeticError("prior log weight arithmetic is not finite or loses precision")
            return result
        state, total, failed = self.start, 0.0, False
        for a in arities:
            if a not in self.alphabet:
                return -math.inf
            j = self.alphabet.index(a)
            target = int(self.transitions[state, j])
            if target < 0:
                return -math.inf
            weight = float(self.log_weights[state, j])
            if weight == -math.inf:
                return -math.inf
            if not failed:
                try:
                    total = _partition_log_product(total, weight, "prior log weight")
                except _PartitionArithmeticError:
                    failed = True
            state = target
        final = float(self.log_final[state])
        if final == -math.inf:
            return -math.inf
        if failed:
            raise _WeightArithmeticError("prior log weight arithmetic is not finite or loses precision")
        try:
            return _partition_log_product(total, final, "prior log weight")
        except _PartitionArithmeticError as exc:
            raise _WeightArithmeticError("prior log weight arithmetic is not finite or loses precision") from exc

    def log_evidence(self, log_posteriors: np.ndarray, log_base: np.ndarray) -> float:
        """Relative log evidence Z(q)/Z(base) for a base-prior tilt (§27.5).

        Rows must be normalized probabilities from the same observation model.
        Candidate priors must share the same base and posterior rows. This is
        evidence relative to the common observation marginal, not a risk bound.
        """
        posterior = np.asarray(log_posteriors, dtype=np.float64)
        base = np.asarray(log_base, dtype=np.float64)
        if (posterior.ndim != 2 or posterior.shape != base.shape
                or posterior.shape[1] != len(self.alphabet)):
            raise ValueError("requires matching posterior and base rows")
        for rows in (posterior, base):
            if (np.any(np.isnan(rows)) or np.any(rows > 0)
                    or not np.allclose(np.exp(rows).sum(axis=1), 1.0, rtol=0, atol=1e-12)):
                raise ValueError("evidence rows must be normalized log probabilities")
        if np.any(np.isneginf(base) & np.isfinite(posterior)):
            raise ValueError("posterior support must lie within base support")
        evidence_prior = _evidence_prior(base, self)
        denominator = evidence_prior.log_normalizer(base)
        if denominator == -math.inf:
            raise ValueError("candidate prior has zero mass under the base")
        if not math.isfinite(denominator):
            raise ValueError("candidate base normalizer must be finite")
        return _evidence_difference(evidence_prior.log_normalizer(posterior), denominator, posterior, base)

    def _rows(self, log_probs: np.ndarray) -> np.ndarray:
        rows = np.asarray(log_probs, dtype=np.float64)
        if rows.ndim != 2 or rows.shape[1] != len(self.alphabet):
            raise ValueError("requires finite or -inf log weights over the prior alphabet")
        validate = getattr(_NATIVE, "valid_log_weights", None)
        if validate is not None and rows.flags.c_contiguous:
            valid = validate(rows.reshape(-1))
        else:
            valid = not (np.any(np.isnan(rows)) or np.any(np.isposinf(rows)))
        if not valid:
            raise ValueError("requires finite or -inf log weights over the prior alphabet")
        return rows

    def log_normalizer(self, log_probs: np.ndarray) -> float:
        """Total accepted log weight, using two native state rows when available."""
        rows = self._rows(log_probs)
        if not len(rows):
            return float(self.log_final[self.start])
        native = getattr(_NATIVE, "prior_normalizer", None)
        if native is not None:
            result = float(native(np.ascontiguousarray(rows).reshape(-1),
                                  _native_alphabet(self.alphabet),
                                  self.transitions.reshape(-1), self.log_weights.reshape(-1),
                                  self.log_final, self.start))
            if math.isnan(result) or result == math.inf:
                raise ValueError("prior normalizer arithmetic is not finite")
            return result
        result = self.decode(rows)
        return -math.inf if result is None else result.log_z

    def partition(self, log_probs: np.ndarray, selected: Sequence[int]) -> tuple[float, float]:
        """Log weights of the selected sequence and all other sequences."""
        rows = self._rows(log_probs)
        selected = tuple(selected)
        if len(selected) != len(rows):
            raise ValueError("selected sequence must match the number of rows")
        if not _integer_symbols(selected):
            raise ValueError("selected symbols must be integers")
        if any(symbol not in self.alphabet for symbol in selected):
            return -math.inf, self.log_normalizer(rows)
        native = getattr(_NATIVE, "prior_partition", None)
        if native is not None:
            alphabet, encoded = _native_symbol_pair(self.alphabet, selected)
            result = native(np.ascontiguousarray(rows).reshape(-1), alphabet,
                            self.transitions.reshape(-1), self.log_weights.reshape(-1),
                            self.log_final, self.start, encoded)
            if len(result) != 2:
                raise _PartitionArithmeticError("prior partition arithmetic is not finite or loses precision")
            return float(result[0]), float(result[1])
        alternatives = np.full(len(self.log_final), -np.inf)
        state, matched = self.start, 0.0
        for k, symbol in enumerate(selected):
            following = np.full_like(alternatives, -np.inf)
            for source in range(len(alternatives)):
                for j, target in enumerate(self.transitions[source]):
                    if target < 0:
                        continue
                    reading, edge = float(rows[k, j]), float(self.log_weights[source, j])
                    if reading == -math.inf or edge == -math.inf:
                        continue
                    previous = float(alternatives[source])
                    same = source == state and matched != -math.inf
                    if previous == -math.inf and (not same or self.alphabet[j] == symbol):
                        continue
                    weight = _partition_log_product(reading, edge, "prior")
                    for prefix in (previous, matched if same and self.alphabet[j] != symbol else -math.inf):
                        if prefix != -math.inf:
                            value = _partition_log_product(prefix, weight, "prior")
                            following[target] = _partition_log_add(float(following[target]), value, "prior")
            if matched != -math.inf:
                j = self.alphabet.index(symbol)
                target = int(self.transitions[state, j])
                reading, edge = float(rows[k, j]), float(self.log_weights[state, j])
                if target < 0 or reading == -math.inf or edge == -math.inf:
                    matched = -math.inf
                else:
                    weight = _partition_log_product(reading, edge, "prior")
                    matched = _partition_log_product(matched, weight, "prior")
                    state = target
            alternatives = following
        chosen = (-math.inf if matched == -math.inf or self.log_final[state] == -math.inf
                  else _partition_log_product(matched, float(self.log_final[state]), "prior"))
        other = -math.inf
        for value, final in zip(alternatives, self.log_final, strict=True):
            if value != -math.inf and final != -math.inf:
                weight = _partition_log_product(float(value), float(final), "prior")
                other = _partition_log_add(other, weight, "prior")
        return chosen, other

    def sequence_risk(self, log_probs: np.ndarray, selected: Sequence[int]) -> float:
        """Selected-sequence risk, with a checked common-weight rescaling retry."""
        selected = tuple(selected)
        try:
            return risk_from_partition(*self.partition(log_probs, selected))
        except _PartitionArithmeticError as failure:
            shifted = _center_prior(self._rows(log_probs), self)
            if shifted is None:
                raise
            centered, centered_prior, _, _ = shifted
            try:
                return risk_from_partition(*centered_prior.partition(centered, selected))
            except _PartitionArithmeticError:
                raise failure from None

    def best(self, log_probs: np.ndarray) -> tuple[int, ...] | None:
        """Maximum-weight sequence without computing sums or marginals (§27.2–3)."""
        rows = self._rows(log_probs)
        if not len(rows):
            return () if self.log_final[self.start] != -math.inf else None
        native = getattr(_NATIVE, "prior_best", None)
        if native is not None:
            selected = native(np.ascontiguousarray(rows).reshape(-1),
                              _native_alphabet(self.alphabet),
                              self.transitions.reshape(-1), self.log_weights.reshape(-1),
                              self.log_final, self.start)
            if selected:
                return _native_decoded_symbols(self.alphabet, selected)
            if (getattr(_NATIVE, "prior_normalizer", None) is not None
                    and self.log_normalizer(rows) != -math.inf):
                shifted = _center_prior(rows, self)
                if shifted is not None:
                    centered, centered_prior, edge_offset, final_offset = shifted
                    if (not np.array_equal(centered, rows) or edge_offset != 0.0
                            or final_offset != 0.0):
                        retried = native(np.ascontiguousarray(centered).reshape(-1),
                                         _native_alphabet(centered_prior.alphabet),
                                         centered_prior.transitions.reshape(-1),
                                         centered_prior.log_weights.reshape(-1),
                                         centered_prior.log_final, centered_prior.start)
                        if retried:
                            return _native_decoded_symbols(self.alphabet, retried)
                raise ValueError("prior maximum unavailable despite nonzero mass")
            return None
        result = self.decode(rows)
        return None if result is None else result.arities

    def decode(self, log_probs: np.ndarray) -> Decoded | None:
        """Sum, maximize and marginalize reading weight times prior weight."""
        rows = self._rows(log_probs)
        try:
            return self._decode_rows(rows)
        except _MarginalPrecisionError as failure:
            shifted = _center_prior(rows, self)
            if shifted is None:
                raise
            centered, centered_prior, edge_offset, final_offset = shifted
            if (np.array_equal(centered, rows) and edge_offset == 0.0 and final_offset == 0.0):
                raise
            try:
                return _restore_centered_decoded(rows, centered_prior._decode_rows(centered),
                                                  prior=self, edge_offset=edge_offset,
                                                  final_offset=final_offset)
            except ValueError:
                raise failure from None

    def _decode_rows(self, rows: np.ndarray) -> Decoded | None:
        m, width = rows.shape
        if not m:
            log_z = float(self.log_final[self.start])
            return None if log_z == -math.inf else Decoded((), log_z, np.empty((0, width)), self)
        native = getattr(_NATIVE, "decode_prior", None)
        if native is not None:
            out = native(np.ascontiguousarray(rows).reshape(-1),
                         _native_alphabet(self.alphabet),
                         self.transitions.reshape(-1), self.log_weights.reshape(-1),
                         self.log_final, self.start)
            if out is None:
                if (getattr(_NATIVE, "prior_normalizer", None) is not None
                        and self.log_normalizer(rows) != -math.inf):
                    raise _MarginalPrecisionError("prior decoding unavailable despite nonzero mass")
                return None
            if not math.isfinite(out["log_z"]):
                raise ValueError("prior decoder normalizer is not finite")
            return Decoded(_native_decoded_symbols(self.alphabet, out["arities"]), out["log_z"],
                           np.asarray(out["marginals"], dtype=np.float64), self)
        states = len(self.log_final)
        forward = np.full((m + 1, states), -np.inf)
        backward = np.full_like(forward, -np.inf)
        best = np.full_like(forward, -np.inf)
        forward[0, self.start] = 0.0
        backward[m] = best[m] = self.log_final
        for k in range(m):
            for state in range(states):
                for j, target in enumerate(self.transitions[state]):
                    if target >= 0:
                        reading = float(rows[k, j])
                        edge_weight = float(self.log_weights[state, j])
                        previous = float(forward[k, state])
                        if -math.inf in (reading, edge_weight, previous):
                            continue
                        weight = _decoder_log_product(reading, edge_weight)
                        through = _decoder_log_product(previous, weight)
                        forward[k + 1, target] = _decoder_log_add(float(forward[k + 1, target]), through)
        log_z = -math.inf
        for state in range(states):
            if forward[m, state] != -math.inf and self.log_final[state] != -math.inf:
                terminal = _decoder_log_product(float(forward[m, state]), float(self.log_final[state]))
                log_z = _decoder_log_add(log_z, terminal)
        if log_z == -math.inf:
            return None
        if not math.isfinite(log_z):
            raise ValueError("prior normalizer is not finite")
        marginals = np.zeros_like(rows)
        for k in reversed(range(m)):
            for state in range(states):
                previous = float(forward[k, state])
                if previous == -math.inf:
                    continue
                for j, target in enumerate(self.transitions[state]):
                    if target >= 0:
                        reading = float(rows[k, j])
                        edge_weight = float(self.log_weights[state, j])
                        suffix = float(backward[k + 1, target])
                        if -math.inf in (reading, edge_weight, suffix):
                            continue
                        weight = _decoder_log_product(reading, edge_weight, "prior decoder")
                        through = _decoder_log_product(weight, suffix, "prior decoder")
                        first = _decoder_log_product(previous, reading, "prior decoder")
                        second = _decoder_log_product(first, edge_weight, "prior decoder")
                        third = _decoder_log_product(second, suffix, "prior decoder")
                        exponent = _decoder_log_product(third, -log_z, "prior decoder")
                        backward[k, state] = _decoder_log_add(float(backward[k, state]), through, "prior decoder")
                        best_suffix = float(best[k + 1, target])
                        if best_suffix != -math.inf:
                            candidate = _decoder_log_product(weight, best_suffix, "prior decoder")
                            best[k, state] = max(best[k, state], candidate)
                        try:
                            marginals[k, j] += math.exp(exponent)
                        except OverflowError as exc:
                            raise _MarginalPrecisionError("decoder marginal arithmetic overflows") from exc
        selected, state = [], self.start
        for k in range(m):
            candidates = []
            for j, target in enumerate(self.transitions[state]):
                if (target < 0 or rows[k, j] == -math.inf
                        or self.log_weights[state, j] == -math.inf or best[k + 1, target] == -math.inf):
                    candidates.append(-math.inf)
                else:
                    weight = _decoder_log_product(float(rows[k, j]), float(self.log_weights[state, j]),
                                                  "prior decoder")
                    candidates.append(_decoder_log_product(weight, float(best[k + 1, target]),
                                                           "prior decoder"))
            j = int(np.argmax(candidates))
            selected.append(self.alphabet[j])
            state = int(self.transitions[state, j])
        return Decoded(tuple(selected), log_z, marginals, self)

def tilt_prior(prior: ArityPrior, log_factors: Sequence[float]) -> ArityPrior:
    """Multiply each symbol's edge weights by a positive factor (§27.13).

    Factors follow the prior alphabet. Finite log factors preserve support;
    they do not fit parameters or imply a calibrated observation model.
    Native weighted-automaton kernels evaluate the resulting immutable prior.
    """
    factors = np.asarray(log_factors, dtype=np.float64)
    if factors.shape != (len(prior.alphabet),) or not np.all(np.isfinite(factors)):
        raise ValueError("requires one finite log factor per prior symbol")
    with np.errstate(over="ignore"):
        weights = prior.log_weights + factors
    if np.any(np.isfinite(prior.log_weights) & ~np.isfinite(weights)):
        raise ValueError("tilted edge weights overflow")
    return ArityPrior(prior.alphabet, prior.transitions, weights, prior.log_final, prior.start)


@lru_cache(maxsize=32)
def format_prior(length: int) -> ArityPrior:
    """Unit-weight prefix counter as a prior automaton for a fixed length."""
    if not isinstance(length, int) or length < 1:
        raise ValueError("length must be a positive integer")
    states = length + 2
    transitions = np.full((states, 3), -1, dtype=np.int64)
    for state in range(1, states):
        for arity in range(3):
            if state - 1 + arity < states:
                transitions[state, arity] = state - 1 + arity
    final = np.full(states, -np.inf)
    final[0] = 0.0
    return ArityPrior((0, 1, 2), transitions, np.zeros((states, 3)), final, start=1)


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
    native = getattr(_NATIVE, "format_partition", None)
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
class PriorSelection:
    index: int
    scores: tuple[float, ...]
    samples: int
    score_error: float = 0.0
    score_clip: float | None = None
    alpha: float | None = None

def select_prior(candidates: Sequence[Callable[[int], ArityPrior | None]],
                 readings: Iterable[np.ndarray], log_base: np.ndarray,
                 alphabet: Sequence[int] = (0, 1, 2), *,
                 score_error: float = 0.0, score_clip: float | None = None,
                 alpha: float | None = None) -> PriorSelection:
    """Empirical summed-evidence selection on unlabeled held-out readings.

    With a supplied uniform error bound on summed scores, choose the first
    candidate within twice that bound of the empirical best (§27.9). Order
    must be declared in advance, broadest support first if that is the policy.
    The default is empirical maximization with exact ties. This API does not
    estimate or certify score_error; it also performs no risk certification
    or automatic installation. Without clipping, None providers are excluded;
    with clipping, unavailability receives -B. Zero base mass in a provided
    model remains invalid rather than zero evidence.
    Supplying score_clip B and alpha clips each log evidence to [-B,B] and
    derives B*sqrt(2*n*log(2*K/alpha)) as the simultaneous total-score error.
    This requires IID observations, fixed models/base/B/K, and valid base
    normalizers wherever a provider supplies a model. It bounds clipped-score means, not raw evidence
    or answer errors. Each reading is copied before provider callbacks so all
    candidates score the same snapshot. The concentration step is not formalized in Lean.
    """
    if not math.isfinite(score_error) or score_error < 0:
        raise ValueError("score_error must be finite and nonnegative")
    if (score_clip is None) != (alpha is None):
        raise ValueError("score_clip and alpha must be supplied together")
    if score_clip is not None:
        if (not math.isfinite(score_clip) or score_clip <= 0 or alpha is None
                or not math.isfinite(alpha) or not 0 < alpha < 1 or score_error != 0):
            raise ValueError("bounded scoring requires positive finite clipping, 0 < alpha < 1, and no manual error")
    candidates = tuple(candidates)
    alphabet = tuple(alphabet)
    base = np.array(log_base, dtype=np.float64, copy=True)
    base.setflags(write=False)
    if (not candidates or base.shape != (len(alphabet),)
            or np.any(np.isnan(base)) or np.any(base > 0)
            or not np.isclose(np.exp(base).sum(), 1.0, rtol=0, atol=1e-12)):
        raise ValueError("requires candidates and a normalized shared base vector")
    scores = [0.0] * len(candidates)
    models: dict[tuple[int, int], tuple[ArityPrior, float] | None] = {}
    count = 0
    for observation in readings:
        # Freeze each reading before invoking providers, which may mutate caller storage.
        rows = np.array(observation, dtype=np.float64, copy=True)
        if rows.ndim != 2 or rows.shape[1] != len(alphabet):
            raise ValueError("readings must be matrices over the shared alphabet")
        # Validate every observation even after some candidates become unavailable.
        fast_validate = getattr(_NATIVE, "normalized_rows_fast", None)
        fast_valid = (fast_validate is not None
                      and fast_validate(rows.reshape(-1), base))
        if (not fast_valid and (np.any(np.isnan(rows)) or np.any(rows > 0)
                or not np.allclose(np.exp(rows).sum(axis=1), 1.0, rtol=0, atol=1e-12)
                or np.any(np.isneginf(base) & np.isfinite(rows)))):
            raise ValueError("readings must be normalized and supported by the shared base")
        for i, provider in enumerate(candidates):
            if scores[i] == -math.inf:
                continue
            key = (i, len(rows))
            if key not in models:
                prior = provider(len(rows))
                if prior is None:
                    models[key] = None
                else:
                    if prior.alphabet != alphabet:
                        raise ValueError("candidate alphabet must match the shared base")
                    base_rows = np.broadcast_to(base, rows.shape)
                    prior = _evidence_prior(base_rows, prior)
                    denominator = prior.log_normalizer(base_rows)
                    if denominator == -math.inf:
                        raise ValueError("candidate prior has zero mass under the base")
                    if not math.isfinite(denominator):
                        raise ValueError("candidate base normalizer must be finite")
                    models[key] = prior, denominator
            model = models[key]
            if model is None:
                if score_clip is None:
                    scores[i] = -math.inf
                    continue
                evidence = -score_clip
            else:
                prior, denominator = model
                evidence = _evidence_difference(prior.log_normalizer(rows), denominator, rows,
                                                np.broadcast_to(base, rows.shape))
            if math.isnan(evidence) or evidence == math.inf:
                raise ValueError("candidate evidence must be finite or negative infinity")
            if score_clip is not None:
                evidence = max(-score_clip, min(score_clip, evidence))
            scores[i] += evidence
            if not math.isfinite(scores[i]) and math.isfinite(evidence):
                raise ValueError("summed evidence overflow")
        count += 1
    if not count or not any(math.isfinite(score) for score in scores):
        raise ValueError("requires observations and at least one finite-evidence candidate")
    if score_clip is not None:
        assert alpha is not None
        score_error = score_clip * math.sqrt(2 * count * (math.log(2 * len(candidates)) - math.log(alpha)))
        if not math.isfinite(score_error):
            raise ValueError("derived score error overflow")
    best = max(range(len(scores)), key=scores.__getitem__)
    chosen = (best if score_error == 0 else next(
        i for i, score in enumerate(scores) if math.isfinite(score)
        and scores[best] / 2 - score / 2 <= score_error))
    return PriorSelection(chosen, tuple(scores), count, score_error, score_clip, alpha)

@lru_cache(maxsize=32)
def complete_prior(length: int) -> ArityPrior | None:
    """Unit-weight complete binary skeleton prior inferred from length (§27.4).

    Leaves may be constants or unary negations of constants. Unsupported
    lengths return None. This is a structural prior, not a reader calibration.
    """
    if not isinstance(length, int) or length < 1:
        raise ValueError("length must be a positive integer")
    depth = (length + 1).bit_length() - 2
    if length + 1 > 3 * 2 ** depth:
        return None
    pending = [(depth,)]
    indices = {pending[0]: 0}
    transitions: list[list[int]] = []
    for stack in pending:
        row = [-1, -1, -1]
        if stack:
            head, rest = stack[0], stack[1:]
            successors = ({2: (head - 1, head - 1, *rest)} if head > 0 else
                          {0: rest, 1: (-1, *rest)} if head == 0 else {0: rest})
            for arity, target in successors.items():
                if target not in indices:
                    indices[target] = len(pending)
                    pending.append(target)
                row[arity] = indices[target]
        transitions.append(row)
    final = np.full(len(pending), -np.inf)
    final[indices[()]] = 0.0
    return ArityPrior((0, 1, 2), np.array(transitions, dtype=np.int64),
                      np.zeros((len(pending), 3)), final)

@lru_cache(maxsize=16)
def height_prior(height: int) -> ArityPrior:
    """Unit-weight prefix trees of height at most ``height`` (§27.4).

    Height counts edges; a constant has height zero. Unlike the complete-tree
    prior, branches may end early and unary nodes may occur at any level.
    """
    if not isinstance(height, int) or height < 0:
        raise ValueError("height must be a nonnegative integer")
    pending = [(height,)]
    indices = {pending[0]: 0}
    transitions: list[list[int]] = []
    for stack in pending:
        row = [-1, -1, -1]
        if stack:
            head, rest = stack[0], stack[1:]
            successors = {0: rest}
            if head:
                successors |= {1: (head - 1, *rest), 2: (head - 1, head - 1, *rest)}
            for arity, target in successors.items():
                if target not in indices:
                    indices[target] = len(pending)
                    pending.append(target)
                row[arity] = indices[target]
        transitions.append(row)
    final = np.full(len(pending), -np.inf)
    final[indices[()]] = 0.0
    return ArityPrior((0, 1, 2), np.array(transitions, dtype=np.int64),
                      np.zeros((len(pending), 3)), final)

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
        check = getattr(_NATIVE, "posterior_rows_valid", None)
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
