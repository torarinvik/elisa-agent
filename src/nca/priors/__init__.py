"""Weighted arity automata, structural priors and held-out evidence selection (§27)."""

from __future__ import annotations

import math
from collections.abc import Sequence
from dataclasses import dataclass
from itertools import chain, repeat
from typing import Any

import numpy as np

from nca.native import load
from nca.priors.symbols import (
    _integer_symbols as _integer_symbols,
    _dense_alphabet_needed as _dense_alphabet_needed,
    _dense_native_alphabet as _dense_native_alphabet,
    _native_alphabet as _native_alphabet,
    _native_symbol_pair as _native_symbol_pair,
    _native_decoded_symbols as _native_decoded_symbols,
)
from nca.priors.arithmetic import (
    risk_from_log_weight as risk_from_log_weight,
    risk_from_partition as risk_from_partition,
    _PartitionArithmeticError as _PartitionArithmeticError,
    _WeightArithmeticError as _WeightArithmeticError,
    _MarginalPrecisionError as _MarginalPrecisionError,
    _partition_log_add as _partition_log_add,
    _partition_log_product as _partition_log_product,
    _add_evidence as _add_evidence,
    _decoder_log_product as _decoder_log_product,
    _decoder_log_add as _decoder_log_add,
    _center_log_rows as _center_log_rows,
    _evidence_difference as _evidence_difference,
    _within_score_error as _within_score_error,
)

_NATIVE = load("decoding")


def _center_prior(rows: np.ndarray, prior: ArityPrior, *,
                  require_common: bool = True) -> tuple[np.ndarray, ArityPrior, float, float] | None:
    """Remove common row, edge and final weights when their shifts are representable."""
    centered_rows = _center_log_rows(rows)
    edges = np.where(prior.transitions >= 0, prior.log_weights, -math.inf)
    centered_edges = _center_log_rows(edges.reshape(1, -1))
    centered_final = _center_log_rows(prior.log_final.reshape(1, -1))
    if centered_rows is None or centered_edges is None or centered_final is None:
        return None
    edge_offset, final_offset = float(np.max(edges)), float(np.max(prior.log_final))
    if require_common:
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
    shifted = _center_prior(base_rows, prior, require_common=False)
    if shifted is not None:
        return shifted[1]
    if prior.log_normalizer(base_rows) == -math.inf:
        raise ValueError("candidate prior has zero mass under the base")
    raise ValueError("prior normalizer rescaling is not finite or loses precision")


def _base_normalizer(prior: ArityPrior, base_rows: np.ndarray) -> float:
    """The finite, positive-mass log normalizer of ``prior`` under the base."""
    denominator = prior.log_normalizer(base_rows)
    if denominator == -math.inf:
        raise ValueError("candidate prior has zero mass under the base")
    if not math.isfinite(denominator):
        raise ValueError("candidate base normalizer must be finite")
    return denominator


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


@dataclass(frozen=True)
class ArityPrior:
    """Weighted deterministic arity automaton (§27).

    Missing transitions are -1. Log edge and final weights may be -inf.
    Priors over terms must incorporate the format constraint in their automaton.
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
        if np.array_equal(posterior, base):
            # Z(base) / Z(base) = 1 at any normalizer magnitude; only positive
            # mass is needed, and support decides it without arithmetic (§27.8).
            if not self.supports(base):
                raise ValueError("candidate prior has zero mass under the base")
            return 0.0
        return _evidence_difference(evidence_prior.log_normalizer(posterior),
                                    _base_normalizer(evidence_prior, base), posterior, base)

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

    def supports(self, log_probs: np.ndarray) -> bool:
        """Whether some accepted sequence has positive weight under the rows,
        decided by reachability alone, without adding or multiplying weights."""
        rows = self._rows(log_probs)
        allowed = (self.transitions >= 0) & (self.log_weights > -math.inf)
        reached = np.zeros(len(self.log_final), dtype=bool)
        reached[self.start] = True
        for row in rows:
            usable = allowed & reached[:, None] & (row > -math.inf)[None, :]
            reached = np.zeros_like(reached)
            reached[self.transitions[usable]] = True
        return bool(np.any(reached & (self.log_final > -math.inf)))

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
        selected_values = np.asarray(selected)
        if not _integer_symbols(selected, values=selected_values):
            raise ValueError("selected symbols must be integers")
        membership = getattr(_NATIVE, "symbols_in_alphabet", None)
        encoded = alphabet = None
        if membership is not None:
            alphabet, encoded = _native_symbol_pair(self.alphabet, selected, values=selected_values)
            unsupported = not membership(alphabet, encoded)
        else:
            unsupported = any(symbol not in self.alphabet for symbol in selected)
        if unsupported:
            return -math.inf, self.log_normalizer(rows)
        native = getattr(_NATIVE, "prior_partition", None)
        if native is not None:
            if alphabet is None or encoded is None:
                alphabet, encoded = _native_symbol_pair(self.alphabet, selected, values=selected_values)
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
            shifted = _center_prior(self._rows(log_probs), self, require_common=False)
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
    native = getattr(_NATIVE, "tilt_weights_checked", None)
    if native is not None:
        weights = np.empty_like(prior.log_weights)
        status = native(prior.log_weights.reshape(-1), np.ascontiguousarray(factors),
                        weights.reshape(-1))
        if status == 1:
            raise ValueError("tilted edge weights overflow")
        if status == 2:
            # Overflow takes precedence over precision loss, as in the reference path.
            with np.errstate(over="ignore"):
                trial = prior.log_weights + factors
            if np.any(np.isfinite(prior.log_weights) & ~np.isfinite(trial)):
                raise ValueError("tilted edge weights overflow")
            raise ValueError("tilted edge weights lose precision")
        if status != 0:
            raise ValueError("invalid tilted edge dimensions")
    else:
        with np.errstate(over="ignore"):
            weights = prior.log_weights + factors
        finite = np.isfinite(prior.log_weights)
        if np.any(finite & ~np.isfinite(weights)):
            raise ValueError("tilted edge weights overflow")
        for state, symbol in np.argwhere(finite & (np.abs(weights) >= 67108864.0)):
            try:
                _partition_log_product(float(prior.log_weights[state, symbol]),
                                       float(factors[symbol]), "tilt")
            except _PartitionArithmeticError as exc:
                raise ValueError("tilted edge weights lose precision") from exc
    return ArityPrior(prior.alphabet, prior.transitions, weights, prior.log_final, prior.start)


from nca.priors.factories import (
    format_prior as format_prior,
    complete_prior as complete_prior,
    height_prior as height_prior,
)


from nca.priors.decoding import (
    _native_format_symbols as _native_format_symbols,
    sequence_log_weight as sequence_log_weight,
    _generic_format_sequence_risk as _generic_format_sequence_risk,
    _generic_format_sequence_risk_once as _generic_format_sequence_risk_once,
    format_sequence_risk as format_sequence_risk,
    Decoded as Decoded,
)

from nca.priors.selection import (
    PriorSelection as PriorSelection,
    select_prior as select_prior,
)
