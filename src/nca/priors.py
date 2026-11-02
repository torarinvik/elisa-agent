"""Weighted arity automata, structural priors and held-out evidence selection (§27)."""

from __future__ import annotations

import math
from collections.abc import Callable, Iterable, Sequence
from dataclasses import dataclass
from functools import lru_cache
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
    difference = weight - log_z
    if math.isnan(difference) or difference == math.inf:
        raise ValueError("sequence risk requires finite or negative-infinite log probability")
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


def sequence_log_weight(log_probs: np.ndarray, alphabet: Sequence[int],
                        selected: Sequence[int]) -> float:
    """Log product of a selected sequence's position-wise weights (§21.5)."""
    if log_probs.shape != (len(selected), len(alphabet)):
        raise ValueError("weights must have one row per selected symbol and one column per class")
    if not _integer_symbols(alphabet) or not _integer_symbols(selected):
        raise ValueError("alphabet and selected symbols must be integers")
    native_weight = getattr(_NATIVE, "sequence_log_weight", None)
    if native_weight is not None:
        symbols, encoded = _native_symbol_pair(tuple(alphabet), selected)
        return float(native_weight(np.asarray(log_probs, dtype=np.float64).reshape(-1),
                                   symbols, encoded))
    symbols = tuple(alphabet)
    try:
        return float(sum(log_probs[k, symbols.index(a)] for k, a in enumerate(selected)))
    except ValueError:
        return -math.inf

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
            return float(native(alphabet,
                                self.transitions.reshape(-1), self.log_weights.reshape(-1),
                                self.log_final, self.start, selected))
        state, total = self.start, 0.0
        for a in arities:
            if a not in self.alphabet:
                return -math.inf
            j = self.alphabet.index(a)
            target = int(self.transitions[state, j])
            if target < 0:
                return -math.inf
            total += float(self.log_weights[state, j])
            state = target
        return total + float(self.log_final[state])

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
        denominator = self.log_normalizer(base)
        if denominator == -math.inf:
            raise ValueError("candidate prior has zero mass under the base")
        if not math.isfinite(denominator):
            raise ValueError("candidate base normalizer must be finite")
        evidence = self.log_normalizer(posterior) - denominator
        if math.isnan(evidence) or evidence == math.inf:
            raise ValueError("candidate evidence must be finite or negative infinity")
        return evidence

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
                raise ValueError("prior partition arithmetic is not finite")
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
                    weight = reading + edge
                    if not math.isfinite(weight):
                        raise ValueError("prior partition arithmetic is not finite")
                    for prefix in (previous, matched if same and self.alphabet[j] != symbol else -math.inf):
                        if prefix != -math.inf:
                            value = prefix + weight
                            if not math.isfinite(value):
                                raise ValueError("prior partition arithmetic is not finite")
                            following[target] = np.logaddexp(following[target], value)
            if matched != -math.inf:
                j = self.alphabet.index(symbol)
                target = int(self.transitions[state, j])
                reading, edge = float(rows[k, j]), float(self.log_weights[state, j])
                if target < 0 or reading == -math.inf or edge == -math.inf:
                    matched = -math.inf
                else:
                    weight = reading + edge
                    matched += weight
                    if not math.isfinite(weight) or not math.isfinite(matched):
                        raise ValueError("prior partition arithmetic is not finite")
                    state = target
            alternatives = following
        chosen = -math.inf if matched == -math.inf or self.log_final[state] == -math.inf else matched + float(self.log_final[state])
        if matched != -math.inf and self.log_final[state] != -math.inf and not math.isfinite(chosen):
            raise ValueError("prior partition arithmetic is not finite")
        other = -math.inf
        for value, final in zip(alternatives, self.log_final, strict=True):
            if value != -math.inf and final != -math.inf:
                weight = float(value) + float(final)
                if not math.isfinite(weight):
                    raise ValueError("prior partition arithmetic is not finite")
                other = float(np.logaddexp(other, weight))
        return chosen, other

    def sequence_risk(self, log_probs: np.ndarray, selected: Sequence[int]) -> float:
        return risk_from_partition(*self.partition(log_probs, selected))

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
                raise ValueError("prior maximum unavailable despite nonzero mass")
            return None
        result = self.decode(rows)
        return None if result is None else result.arities

    def decode(self, log_probs: np.ndarray) -> Decoded | None:
        """Sum, maximize and marginalize reading weight times prior weight."""
        rows = self._rows(log_probs)
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
                    raise ValueError("prior decoding unavailable despite nonzero mass")
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
                        weight = reading + edge_weight
                        if not math.isfinite(weight) or not math.isfinite(previous + weight):
                            raise ValueError("prior normalizer arithmetic is not finite")
                        forward[k + 1, target] = np.logaddexp(
                            forward[k + 1, target], previous + weight)
        with np.errstate(over="ignore", invalid="ignore"):
            terminal = forward[m] + self.log_final
        if np.any(np.isfinite(forward[m]) & np.isfinite(self.log_final) & ~np.isfinite(terminal)):
            raise ValueError("prior normalizer arithmetic is not finite")
        log_z = float(np.logaddexp.reduce(terminal))
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
                        weight = reading + edge_weight
                        through = weight + suffix
                        first = previous + reading
                        second = first + edge_weight
                        third = second + suffix
                        exponent = third - log_z
                        if not all(map(math.isfinite, (through, first, second, third, exponent))):
                            raise ValueError("prior decoder arithmetic is not finite")
                        backward[k, state] = np.logaddexp(backward[k, state], through)
                        best_suffix = float(best[k + 1, target])
                        candidate = weight + best_suffix
                        if best_suffix != -math.inf and not math.isfinite(candidate):
                            raise ValueError("prior decoder arithmetic is not finite")
                        best[k, state] = max(best[k, state], candidate)
                        marginals[k, j] += math.exp(exponent)
        selected, state = [], self.start
        for k in range(m):
            candidates = [rows[k, j] + self.log_weights[state, j] + best[k + 1, target]
                          if target >= 0 else -np.inf
                          for j, target in enumerate(self.transitions[state])]
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
    """Exact model risk with selected and alternative paths summed separately."""
    native = getattr(_NATIVE, "format_partition", None)
    if native is not None:
        m = len(rows)
        partition = native(np.ascontiguousarray(rows, dtype=np.float64).reshape(-1),
                           _native_format_symbols(alphabet, m),
                           _native_format_symbols(selected, m))
        if len(partition) == 2:
            return risk_from_partition(*partition)
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
                    through = float(alternatives[n]) + reading
                    if not math.isfinite(through):
                        raise ValueError("format partition arithmetic is not finite")
                    following[target] = np.logaddexp(following[target], through)
                if n == state and arity != selected[k] and matched != -math.inf and reading != -math.inf:
                    through = matched + reading
                    if not math.isfinite(through):
                        raise ValueError("format partition arithmetic is not finite")
                    following[target] = np.logaddexp(following[target], through)
        column = next((j for j, value in enumerate(alphabet) if value == selected[k]), None)
        if column is None or state < 1 or state - 1 + int(selected[k]) > m - k - 1:
            matched = -math.inf
        else:
            reading = float(rows[k, column])
            if matched != -math.inf and reading != -math.inf:
                matched += reading
                if not math.isfinite(matched):
                    raise ValueError("format partition arithmetic is not finite")
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
                    denominator = prior.log_normalizer(np.broadcast_to(base, rows.shape))
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
                evidence = prior.log_normalizer(rows) - denominator
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
            raise ValueError("decoder marginals are not normalized; numerical precision was lost")

    def log_weight(self, log_probs: np.ndarray, alphabet: Sequence[int],
                   arities: Sequence[int]) -> float:
        """Log weight of a sequence under readings and the optional prior."""
        if self.prior is not None and tuple(alphabet) != self.prior.alphabet:
            raise ValueError("alphabet must match the decoded prior")
        reading = sequence_log_weight(log_probs, alphabet, arities)
        return reading + (0.0 if self.prior is None else self.prior.log_weight(arities))

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
