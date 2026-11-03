"""Prefix parsing, counter decoding and certified incremental bands (§21–23).

Generic over ranked alphabets: a sequence of symbols, each read as its arity,
is decoded into exactly one tree written in prefix order, whatever the symbols
mean in a domain.
"""

from __future__ import annotations

import math
from collections.abc import Callable, Sequence
from dataclasses import dataclass
from itertools import accumulate

import numpy as np

from nca.native import load
from nca.priors import (Decoded, _center_log_rows,
                        _generic_format_sequence_risk as _format_sequence_risk,
                        _MarginalPrecisionError, _native_format_symbols,
                        _restore_centered_decoded, risk_from_log_weight,
                        sequence_log_weight as sequence_log_weight)

_NATIVE = load("decoding")


def _valid_arities(arities: Sequence[int]) -> bool:
    native = getattr(_NATIVE, "nonnegative_arities", None)
    if native is not None and isinstance(arities, np.ndarray) and arities.ndim == 1:
        if arities.dtype.kind == "u":
            return True
        if arities.dtype.kind == "i":
            return bool(native(np.ascontiguousarray(arities, dtype=np.int64)))
    return all(isinstance(a, (int, np.integer)) and a >= 0 for a in arities)


def _format_inputs(log_probs: np.ndarray, alphabet: Sequence[int]) -> np.ndarray:
    if not len(alphabet) or not _valid_arities(alphabet) or len(set(alphabet)) != len(alphabet):
        raise ValueError("alphabet must contain distinct nonnegative arities")
    rows = np.asarray(log_probs, dtype=np.float64)
    if (rows.ndim != 2 or rows.shape[1] != len(alphabet)
            or np.any(np.isnan(rows)) or np.any(np.isposinf(rows))):
        raise ValueError("rows must contain log probabilities or finite log weights for each arity")
    return rows


def parse(arities: Sequence[int]) -> list[list[int]] | None:
    """Parse a prefix term, using a native parser when available."""
    if not _valid_arities(arities):
        return None
    generic = getattr(_NATIVE, "parse_tree_generic", None)
    if generic is not None and (len(arities) >= 32
                                or isinstance(arities, np.ndarray) and arities.ndim == 1):
        result = generic(_native_format_symbols(arities, len(arities)))
        if not result:
            return None
        offset = len(arities) + 1
        return [result[offset + result[k]:offset + result[k + 1]] for k in range(len(arities))]
    native = getattr(_NATIVE, "parse_tree", None)
    if native is not None and all(a in (0, 1, 2) for a in arities):
        result = native(np.asarray(arities, dtype=np.int64))
        return ([[c for c in result[2 * k:2 * k + 2] if c >= 0]
                 for k in range(len(arities))] if result else None)
    if generic is not None:
        if any(a > len(arities) - 1 for a in arities):
            return None
        result = generic(np.asarray(arities, dtype=np.int64))
        if not result:
            return None
        offset = len(arities) + 1
        return [result[offset + result[k]:offset + result[k + 1]] for k in range(len(arities))]
    return parse_reference(arities)

def parse_reference(arities: Sequence[int]) -> list[list[int]] | None:
    """Children of each symbol of a prefix term, by position; ``None`` if the
    arities do not form exactly one term."""
    if not len(arities) or not _valid_arities(arities):
        return None
    children: list[list[int]] = [[] for _ in arities]
    pending: list[tuple[int, int]] = []
    for k, value in enumerate(arities):
        if k:
            if not pending:
                return None
            parent, remaining = pending[-1]
            children[parent].append(k)
            if remaining == 1:
                pending.pop()
            else:
                pending[-1] = (parent, remaining - 1)
        count = int(value)
        if count > len(arities) - k - 1:
            return None
        if count:
            pending.append((k, count))
    return children if not pending else None

def decode(log_probs: np.ndarray, alphabet: Sequence[int] = (0, 1, 2)) -> Decoded | None:
    """Decode an arity sequence from per-symbol arity log-probabilities
    (``log_probs[k, j]`` for arity ``alphabet[j]``) by the counter automaton:
    the state is the number of subterms still awaited, starting at 1; a
    symbol of arity ``a`` read while ``n ≥ 1`` are awaited leaves ``n − 1 + a``;
    the sequence is accepted when none remain at its end. ``None`` if no
    parseable sequence has positive weight. The alphabet must be nonempty and
    contain distinct nonnegative integer arities.

    Uses the native kernel ``nca.native.decoding`` when it is built, and
    ``decode_reference`` otherwise; the two agree to rounding."""
    log_probs = _format_inputs(log_probs, alphabet)
    return _format_decode_with_retry(log_probs, alphabet, _decode_native_once)


def _format_decode_with_retry(
        log_probs: np.ndarray, alphabet: Sequence[int],
        decoder: Callable[[np.ndarray, Sequence[int]], Decoded | None]) -> Decoded | None:
    try:
        return decoder(log_probs, alphabet)
    except _MarginalPrecisionError as failure:
        centered = _center_log_rows(log_probs)
        if centered is None or np.array_equal(centered, log_probs):
            raise
        try:
            return _restore_centered_decoded(log_probs, decoder(centered, alphabet))
        except ValueError:
            raise failure from None


def _decode_native_once(log_probs: np.ndarray, alphabet: Sequence[int]) -> Decoded | None:
    if _NATIVE is None or len(log_probs) == 0:
        return _decode_reference_once(log_probs, alphabet)
    m = len(log_probs)
    flat = np.ascontiguousarray(log_probs, dtype=np.float64).ravel()
    native_alphabet = _native_format_symbols(alphabet, m)
    out = np.asarray(_NATIVE.decode(flat, native_alphabet))
    if out[0] <= -1e300:
        # The linear-space kernel requests log space when it loses precision.
        native_log = getattr(_NATIVE, "decode_log", None)
        if native_log is None:
            return _decode_reference_once(log_probs, alphabet)
        out = np.asarray(native_log(flat, native_alphabet))
        if not len(out):
            return None
        if np.isnan(out[0]):
            raise ValueError("format decoding arithmetic is not finite")
    return Decoded(tuple(int(a) for a in out[1:m + 1]), float(out[0]),
                   out[m + 1:].reshape(m, len(alphabet)))

def _checked_log_sum(left: np.ndarray | float, right: np.ndarray | float) -> np.ndarray:
    with np.errstate(over="ignore", invalid="ignore"):
        result = np.add(left, right)
    if np.any(np.isfinite(left) & np.isfinite(right) & ~np.isfinite(result)):
        raise ValueError("format decoding arithmetic is not finite")
    return result


def decode_reference(log_probs: np.ndarray, alphabet: Sequence[int] = (0, 1, 2)) -> Decoded | None:
    """``decode`` in NumPy: the dynamic programs in log space, with all states
    ``n ≤ m − k`` that can still be completed at position ``k``."""
    log_probs = _format_inputs(log_probs, alphabet)
    return _format_decode_with_retry(log_probs, alphabet, _decode_reference_once)


def _decode_reference_once(log_probs: np.ndarray, alphabet: Sequence[int]) -> Decoded | None:
    m = len(log_probs)
    if m == 0:
        return None
    width = m + 2
    # Determine which states have a supported completion without adding weights.
    completable = np.zeros((m + 1, width), dtype=bool)
    completable[m, 0] = True
    for k in range(m - 1, -1, -1):
        for j, a in enumerate(alphabet):
            a = int(a)
            span = min(a + width - 1, width) - a
            if span > 0 and log_probs[k, j] != -np.inf:
                completable[k, 1:1 + span] |= completable[k + 1, a:a + span]
    if not completable[0, 1]:
        return None
    forward = np.full((m + 1, width), -np.inf)
    best = np.full((m + 1, width), -np.inf)
    choice = np.zeros((m + 1, width), dtype=np.int64)
    forward[0, 1] = best[0, 1] = 0.0
    for k in range(m):
        live = m - k - 1
        for j, a in enumerate(alphabet):
            a = int(a)
            low, high = a, a + width - 1  # state n ≥ 1 moves to n − 1 + a
            span = min(high, width, live + 1) - low
            if span <= 0:
                continue
            step = log_probs[k, j]
            supported = completable[k + 1, low:low + span]
            source = np.where(supported, forward[k, 1:1 + span], -np.inf)
            forward[k + 1, low:low + span] = np.logaddexp(
                forward[k + 1, low:low + span], _checked_log_sum(source, step))
            candidate = _checked_log_sum(np.where(supported, best[k, 1:1 + span], -np.inf), step)
            better = candidate > best[k + 1, low:low + span]
            best[k + 1, low:low + span][better] = candidate[better]
            choice[k + 1, low:low + span][better] = j
        forward[k + 1, live + 1:] = best[k + 1, live + 1:] = -np.inf
    log_z = float(forward[m, 0])
    if log_z == -np.inf:
        return None
    arities = []
    state = 0
    for k in range(m, 0, -1):
        a = alphabet[int(choice[k, state])]
        arities.append(a)
        state = state + 1 - a
    backward = np.full((m + 1, width), -np.inf)
    backward[m, 0] = 0.0
    marginals = np.zeros((m, len(alphabet)))
    for k in range(m - 1, -1, -1):
        for j, a in enumerate(alphabet):
            a = int(a)
            span = min(a + width - 1, width) - a
            if span <= 0:
                continue
            # Unreachable prefix states cannot contribute to any complete path.
            suffix = np.where(forward[k, 1:1 + span] != -np.inf,
                              backward[k + 1, a:a + span], -np.inf)
            through = _checked_log_sum(log_probs[k, j], suffix)
            backward[k, 1:1 + span] = np.logaddexp(backward[k, 1:1 + span], through)
            marginals[k, j] = np.exp(np.logaddexp.reduce(_checked_log_sum(forward[k, 1:1 + span], through))
                                     - log_z)
    return Decoded(tuple(reversed(arities)), log_z, marginals)

@dataclass(frozen=True)
class Banded:
    """Decoding restricted to a band of counter values around a reference
    sequence (THEORY §23.2–23.3): the most probable parseable sequence in the
    band, the certified risk ``1 − x / (Z_band + U)``, and whether ``x ≥ U``
    certifies that the sequence is also the most probable overall."""

    arities: tuple[int, ...]
    risk: float
    exact: bool
    changes: int
    width: int

def _tail_mass_blocks(
        log_probs: np.ndarray, reference: Sequence[int],
) -> tuple[tuple[float, float], np.ndarray, int] | None:
    native = getattr(_NATIVE, "tail_block_summary", None)
    if native is None or len(reference) == 0:
        return None
    width = log_probs.shape[1]
    if width == 0:
        return None
    block_size = math.isqrt(max(1, len(reference) // width)) + 1
    count = (len(reference) - 1) // block_size + 1
    blocks = np.empty(2 * count, dtype=np.float64)
    out = native(np.ascontiguousarray(log_probs, dtype=np.float64).reshape(-1),
                 np.asarray(reference, dtype=np.int64), blocks, block_size, -1)
    if len(out) != 2:
        return None
    return (float(out[0]), float(out[1])), blocks, block_size


def _tail_mass_summary(log_probs: np.ndarray, reference: Sequence[int]) -> tuple[float, float]:
    block_summary = _tail_mass_blocks(log_probs, reference)
    if block_summary is not None:
        return block_summary[0]
    native = getattr(_NATIVE, "tail_mass_summary", None)
    if native is not None:
        off, factor = native(np.ascontiguousarray(log_probs, dtype=np.float64).reshape(-1),
                             np.asarray(reference, dtype=np.int64))
        return float(off), float(factor)
    row_totals = np.logaddexp.reduce(log_probs, axis=1, initial=-np.inf)
    factor = math.fsum(max(0.0, float(value)) for value in row_totals)
    off = np.array(log_probs, dtype=np.float64, copy=True)
    off[np.arange(len(reference)), np.asarray(reference, dtype=np.int64)] = -np.inf
    return float(np.logaddexp.reduce(off.reshape(-1), initial=-np.inf)), factor


def _band_log_tail(log_off: float, changes: int, log_factor: float = 0.0) -> float:
    if log_off == -math.inf:
        return -math.inf
    tail = changes * log_off - math.lgamma(changes + 1) + log_factor
    if not math.isfinite(tail):
        raise ValueError("band tail arithmetic is not finite")
    return tail


def _initial_band_changes(log_off: float, slack: float, length: int, log_factor: float = 0.0) -> int:
    log_slack = math.log(slack)
    native = getattr(_NATIVE, "initial_band_changes_scaled", None)
    if native is not None:
        j = int(native(log_off, log_factor, log_slack, length))
        if j < 0:
            raise ValueError("band tail arithmetic is not finite")
        # libm lgamma and Python's implementation can round boundary cases
        # differently. Preserve the reference decision at the crossing.
        while j > 1 and _band_log_tail(log_off, j - 1, log_factor) <= log_slack:
            j -= 1
        while j <= length and _band_log_tail(log_off, j, log_factor) > log_slack:
            j += 1
        return j
    j = 1
    while j <= length and _band_log_tail(log_off, j, log_factor) > log_slack:
        j += 1
    return j


def _valid_reference(reference: Sequence[int], width: int) -> bool:
    values = np.asarray(reference)
    if values.ndim != 1:
        return False
    if not values.size:
        return True
    if values.dtype.kind == "i":
        return not (np.any(values < 0) or np.any(values >= width))
    if values.dtype.kind == "u":
        return not np.any(values >= width)
    return _valid_arities(reference) and all(j < width for j in reference)


def band_changes(log_probs: np.ndarray, reference: Sequence[int], slack: float) -> tuple[int, float]:
    """The least ``j`` with ``C * S^j / j! ≤ slack``, capped at one more
    than the row count, and a bound on mass with at least ``j`` changes.
    ``S`` is summed off-reference mass and ``C`` is the product of
    ``max(1, row mass)``. Beyond the row count the tail is exactly zero.
    A positive tail below the floating-point range is returned as the smallest
    positive float; this calculation is not an outward-rounding guarantee."""
    if not 0 < slack < 1:
        raise ValueError("slack must be strictly between zero and one")
    if (log_probs.ndim != 2 or log_probs.shape[0] != len(reference)
            or log_probs.shape[1] == 0 or np.any(np.isnan(log_probs))
            or np.any(log_probs > 0)
            or np.any(np.exp(log_probs).sum(axis=1) > 1 + 1e-12)
            or not _valid_reference(reference, log_probs.shape[1])):
        raise ValueError("reference must index each valid log-probability row")
    log_off, log_factor = _tail_mass_summary(log_probs, reference)
    j = _initial_band_changes(log_off, slack, len(reference), log_factor)
    log_tail = -math.inf if j > len(reference) else _band_log_tail(log_off, j, log_factor)
    tail = math.exp(log_tail)
    return j, math.nextafter(0.0, 1.0) if tail == 0.0 and math.isfinite(log_tail) else tail

def decode_banded(log_probs: np.ndarray, alphabet: Sequence[int] = (0, 1, 2),
                  slack: float = 1e-4) -> Banded | None:
    """``decode`` with the dynamic programs restricted to counter values within
    ``max(alphabet) * (j − 1)`` of each symbol's most
    probable arity sequence. ``j`` starts at
    ``band_changes`` and widens until the tail bound is at most ``slack``
    times the band's weight, so the risk is within ``slack`` of the exact one
    (THEORY §23.3). ``None`` if no parseable sequence has positive weight."""
    log_probs = _format_inputs(log_probs, alphabet)
    if not 0 < slack < 1:
        raise ValueError("slack must be strictly between zero and one")
    if (log_probs.ndim != 2 or log_probs.shape[1] != len(alphabet)
            or np.any(np.isnan(log_probs)) or np.any(log_probs > 0)
            or np.any(np.exp(log_probs).sum(axis=1) > 1 + 1e-12)):
        raise ValueError("rows must contain log probabilities with mass at most one")
    m = len(log_probs)
    if m == 0:
        return None
    reference = np.argmax(log_probs, axis=1)
    log_off, log_factor = _tail_mass_summary(log_probs, reference)
    changes = _initial_band_changes(log_off, slack, m, log_factor)
    centre = list(accumulate((int(alphabet[j]) - 1 for j in reference), initial=1))
    arity_bound = int(max(alphabet))
    while True:
        half = arity_bound * (changes - 1)
        full = all(c - half <= 0 and c + half >= m - k for k, c in enumerate(centre))
        passes = _banded_passes(log_probs, alphabet, centre, half)
        log_tail = -math.inf if full or changes > m else _band_log_tail(log_off, changes, log_factor)
        if passes is not None and log_tail <= math.log(slack) + passes[0]:
            break
        if log_tail == -math.inf:
            return None
        changes += 1
    log_z, log_x, arities = passes
    risk = risk_from_log_weight(log_x, float(np.logaddexp(log_z, log_tail)))
    if risk == 0.0:
        risk = _format_sequence_risk(log_probs, alphabet, arities)
    return Banded(arities, risk, log_x >= log_tail, changes, 2 * half + 1)

def _banded_passes(log_probs: np.ndarray, alphabet: Sequence[int], centre: Sequence[int],
                   half: int) -> tuple[float, float, tuple[int, ...]] | None:
    """Sum and max passes over states within ``half`` of ``centre``: the log
    weight of the band, the log weight of its best sequence, and that sequence."""
    m = len(log_probs)
    if m == 0:
        return None
    first, last = int(centre[0]), int(centre[m])
    if (not max(0, first - half) <= 1 <= min(m, first + half)
            or not last - half <= 0 <= last + half):
        return None
    native = getattr(_NATIVE, "banded_format", None)
    if native is not None:
        growth = max(0, int(max(alphabet)) - 1)
        low = np.array([max(0, min(m - k + 1, int(c) - half))
                        for k, c in enumerate(centre)], dtype=np.int64)
        high = np.array([max(-1, min(m - k, int(c) + half, 1 + k * growth))
                         for k, c in enumerate(centre)], dtype=np.int64)
        result = native(np.ascontiguousarray(log_probs, dtype=np.float64).reshape(-1),
                        _native_format_symbols(alphabet, m), low, high)
        if not result:
            return None
        if math.isnan(result[0]):
            raise ValueError("format decoding arithmetic is not finite")
        return float(result[0]), float(result[1]), tuple(int(a) for a in result[2:])
    width = m + 2
    # Bound every m-step path well inside the finite range, leaving room for
    # the logarithm of the finite number of paths accumulated by logaddexp.
    finite = np.abs(log_probs[np.isfinite(log_probs)])
    safe = not len(finite) or float(finite.max()) <= np.finfo(np.float64).max / (4 * (m + 1))
    forward = np.full((m + 1, width), -np.inf)
    best = np.full((m + 1, width), -np.inf)
    choice = np.zeros((m + 1, width), dtype=np.int64)
    forward[0, 1] = best[0, 1] = 0.0
    for k in range(m):
        centre_k = int(centre[k + 1])
        for j, a in enumerate(alphabet):
            a = int(a)
            low = max(a, 0, centre_k - half)
            high = min(a + width - 1, width, m - k, centre_k + half + 1)
            span = high - low
            if span <= 0:
                continue
            step = log_probs[k, j]
            source = 1 + low - a
            incoming = forward[k, source:source + span]
            incoming = incoming + step if safe else _checked_log_sum(incoming, step)
            forward[k + 1, low:high] = np.logaddexp(
                forward[k + 1, low:high], incoming)
            previous_best = best[k, source:source + span]
            candidate = previous_best + step if safe else _checked_log_sum(previous_best, step)
            better = candidate > best[k + 1, low:high]
            best[k + 1, low:high][better] = candidate[better]
            choice[k + 1, low:high][better] = j
    if forward[m, 0] == -np.inf:
        return None
    arities = []
    state = 0
    for k in range(m, 0, -1):
        a = alphabet[int(choice[k, state])]
        arities.append(a)
        state = state + 1 - a
    return float(forward[m, 0]), float(best[m, 0]), tuple(reversed(arities))


from nca.decoding.cursors import (
    Split as Split,
    CertifiedSplit as CertifiedSplit,
)
