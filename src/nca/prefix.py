"""Reading and evaluating prefix terms over any ranked vocabulary (§18–22, §27).

A domain supplies a ``RankedVocabulary`` (its symbols and their arities), the
meaning of each symbol (``semantics``: a node's value from its children's
values), and optionally which symbols a least-weight valid certificate must
evaluate (``evaluates``; by default every symbol). ``PrefixEvaluator`` turns
per-position distributions over the vocabulary into the value of the term they
spell in prefix order, and declares the risk accounts of §18.5 (certificate),
§19 (detection by the format), §21 (correction by decoding) and §27 (priors),
together with their floors (§22). Nothing here depends on what the symbols
mean.
"""

from __future__ import annotations

import copy
import math
from collections.abc import Callable, Sequence
from dataclasses import dataclass, field
from functools import cached_property, lru_cache
from typing import Any

import numpy as np
import torch

from nca.abi import Manifest
from nca.decoding import Banded, CertifiedSplit, Split, decode, parse
from nca.ladder import Decision, RankedReading, _lower_sum, allocate_risk
from nca.native import load
from nca.partition import PartitionCursor
from nca.priors import ArityPrior, format_prior, risk_from_partition
from nca.shares import _combine_shares, _detection_floors, _markov_shares, _pair_shares

_NATIVE = load("decoding")

Semantics = Callable[[str, Sequence[Any]], Any]
"""The value of a node labeled with a symbol, given its children's values."""

Evaluates = Callable[[Sequence[str], Sequence[Sequence[int]], Sequence[float], Sequence[float]],
                     set[int]]
"""The symbols a least-weight valid certificate evaluates, given the parsed
children, the weight ``full[k]`` of evaluating symbol ``k`` and the weight
``shape[k]`` of skipping it (``NCA.bestCert``)."""


@dataclass(frozen=True)
class RankedVocabulary:
    """Symbols and their arities, the alphabet of a prefix format."""

    symbols: tuple[str, ...]
    arities: tuple[int, ...]

    def __post_init__(self) -> None:
        if (not self.symbols or len(self.symbols) != len(self.arities)
                or len(set(self.symbols)) != len(self.symbols)
                or any(isinstance(a, bool) or not isinstance(a, int) or a < 0
                       for a in self.arities)):
            raise ValueError("a ranked vocabulary needs distinct symbols, each with a "
                             "nonnegative integer arity")

    @cached_property
    def order(self) -> tuple[int, ...]:
        """The distinct arities in increasing order: the decoder's alphabet."""
        return tuple(sorted(set(self.arities)))

    @cached_property
    def decision(self) -> tuple[tuple[int, ...], ...]:
        """The grouped decision a parser needs of every symbol: its arity, one
        group of classes per entry of ``order``."""
        return tuple(tuple(c for c, a in enumerate(self.arities) if a == arity)
                     for arity in self.order)

    def group(self, arity: int) -> tuple[int, ...]:
        """The classes of arity ``arity``."""
        return self.decision[self.order.index(arity)]

    @cached_property
    def _index(self) -> dict[str, int]:
        return {symbol: c for c, symbol in enumerate(self.symbols)}

    def index(self, symbol: str) -> int:
        return self._index[symbol]

    def arity(self, symbol: str) -> int:
        return self.arities[self._index[symbol]]

    @cached_property
    def class_arities(self) -> np.ndarray:
        """Each class's arity, for native kernels."""
        values = np.asarray(self.arities, dtype=np.int64)
        values.setflags(write=False)
        return values

    @cached_property
    def class_groups(self) -> np.ndarray:
        """Each class's position in ``order``, for native kernels."""
        values = np.asarray([self.order.index(a) for a in self.arities], dtype=np.int64)
        values.setflags(write=False)
        return values


def _changed_rows(current: np.ndarray, previous: np.ndarray) -> tuple[int, ...]:
    """Find changed rows without materializing a full comparison matrix."""
    native = getattr(_NATIVE, "changed_rows", None)
    if (native is not None and current.ndim == 2 and current.shape == previous.shape
            and current.shape[1] and current.dtype == np.float64 and previous.dtype == np.float64
            and current.flags.c_contiguous and previous.flags.c_contiguous):
        out = np.empty(len(current), dtype=np.int64)
        count = native(current.ravel(), previous.ravel(), out, current.shape[1])
        if count >= 0:
            return tuple(int(index) for index in out[:count])
    return tuple(int(index) for index in np.flatnonzero(np.any(current != previous, axis=1)))


def most_likely(readings: Sequence[Sequence[float]], vocabulary: RankedVocabulary) -> list[str]:
    """Each reading's most probable symbol."""
    symbols = vocabulary.symbols
    native = getattr(_NATIVE, "row_argmax", None)
    if len(readings) and all(isinstance(row, RankedReading) for row in readings):
        if native is not None:
            scores = np.asarray([row.weights for row in readings], dtype=np.float64)
            return [symbols[i] for i in native(scores.reshape(-1), scores.shape[1])]
        return [symbols[row.top()] for row in readings]
    # A shared NumPy dtype must not round one row merely because another row
    # has a different dtype. Python float tuples and binary float arrays are
    # safe to convert together; other inputs retain per-row NumPy semantics.
    if (native is not None and len(readings) and
            (isinstance(readings, np.ndarray) or
             all(isinstance(row, (tuple, list)) and
                 set(map(type, row)) <= {float} for row in readings))):
        try:
            scores = np.asarray(readings)
        except (TypeError, ValueError):
            scores = None
        if (scores is not None and scores.ndim == 2 and scores.shape[1] == len(symbols)
                and scores.dtype.kind == "f" and scores.dtype.itemsize <= 8):
            values = np.asarray(scores, dtype=np.float64).reshape(-1)
            return [symbols[i] for i in native(values, scores.shape[1])]
    return [symbols[int(np.argmax(r))] for r in readings]


def arity_masses(readings: Sequence[Sequence[float]], vocabulary: RankedVocabulary) -> np.ndarray:
    """Group raw readings by arity without applying a calibration or normalization."""
    native = getattr(_NATIVE, "grouped_masses", None)
    if native is not None:
        scores = np.asarray(readings, dtype=np.float64)
        if scores.shape == (len(readings), len(vocabulary.symbols)):
            entries = len(vocabulary.order)
            return np.asarray(native(scores.reshape(-1), vocabulary.class_groups, entries)
                              ).reshape(len(readings), entries)
    return np.array([[sum(r[c] for c in group) for group in vocabulary.decision]
                     for r in readings])


DETECTION = ("none", "markov", "pairs")


@dataclass
class CorrectionState:
    """Per-solve cursor and priorities; never shared between terms."""

    length: int | None = None
    evaluator: PrefixEvaluator | None = None
    decoder_config: tuple[bool, float | None, bool] | None = None
    answer_band: CertifiedSplit | None = None
    answer_band_result: Banded | None = None
    answer_cursor: Split | None = None
    answer_readings: np.ndarray | None = None
    answer_arities: tuple[int, ...] | None = None
    cursor: Split | None = None
    normalizer_valid: bool = False
    risk_band: CertifiedSplit | None = None
    prior_log_probs: np.ndarray | None = None
    priorities: list[float] | None = None
    priorities_prior: ArityPrior | None = None
    steps: int = 0
    changed: tuple[int, ...] = ()
    revisions: tuple[int, ...] | None = None
    distribution_source: object | None = None
    risk_source: object | None = None
    within: dict[tuple[int, int], float] = field(default_factory=dict)
    risk_prior: ArityPrior | None = None
    risk_arities: tuple[int, ...] | None = None
    risk_value: float | None = None
    partition_cursor: PartitionCursor | None = None

    def ensure_length(self, length: int, evaluator: PrefixEvaluator) -> None:
        config = evaluator.decode, evaluator.band_slack, evaluator.prior is not None
        if self.length is not None and (self.length != length or self.evaluator is not evaluator
                                        or self.decoder_config != config):
            self.answer_band = None
            self.answer_band_result = None
            self.answer_cursor = None
            self.answer_readings = None
            self.answer_arities = None
            self.cursor = None
            self.normalizer_valid = False
            self.risk_band = None
            self.prior_log_probs = None
            self.priorities = None
            self.priorities_prior = None
            self.steps = 0
            self.changed = ()
            self.revisions = None
            self.distribution_source = None
            self.risk_source = None
            self.within.clear()
            self.risk_prior = None
            self.risk_arities = None
            self.risk_value = None
            self.partition_cursor = None
        self.length = length
        self.evaluator = evaluator
        self.decoder_config = config

    def cached_risk(self, prior: ArityPrior | None, arities: Sequence[int],
                    calculate: Callable[[], float | None]) -> float | None:
        selected = tuple(arities)
        if self.risk_value is not None and self.risk_prior is prior and self.risk_arities == selected:
            return self.risk_value
        value = calculate()
        self.risk_prior, self.risk_arities, self.risk_value = prior, selected, value
        return value

    def partition_risk(self, prior: ArityPrior, rows: np.ndarray,
                       arities: Sequence[int]) -> float | None:
        if self.partition_cursor is None or self.partition_cursor.prior is not prior:
            self.partition_cursor = PartitionCursor(prior)
        chosen, other = self.partition_cursor.partition(rows, tuple(arities))
        return None if chosen == -math.inf and other == -math.inf else risk_from_partition(chosen, other)


class PrefixEvaluator:
    """The value of the most probable symbols, read as a prefix term; ``None``
    if their arities form no term.

    Its certificate is a risk account over the symbols. By default each symbol
    is charged its arity risk, plus the rest of its full-decision risk if the
    least-risk valid certificate (``evaluates``) evaluates it (§18.5).
    ``short_circuit=False`` evaluates every symbol, the static account, for
    comparison.

    ``detection`` credits the format's error detection (§19): a single wrong
    arity breaks the parse, so only two arity failures can go unnoticed.
    ``"markov"`` charges half of each symbol's arity risk (no further premise);
    ``"pairs"`` charges the smaller of that and each symbol's share
    ``ρ_k (S − ρ_k) / 2`` of the pairs bound (premise: failures at different
    symbols are not positively correlated). Evaluated symbols are then charged
    only the risk of their decision restricted to their arity group.

    ``decode=True`` corrects instead of refusing (§21): the arity sequence is
    the most probable parseable one under the readings' arity masses, and each
    symbol the most probable class of its decoded arity group, so every reading
    is answered. The certificate decodes the same readings the same way, so the
    answer is exactly the term its bound is about; it then charges the
    posterior probability ``R`` that this arity sequence is wrong, under the
    *calibrated* arity distributions and the format (premise P), shared among
    the symbols in proportion to their posterior arity risks, plus each
    evaluated symbol's restricted risk.

    An optional ``prior(length)`` provider supplies a stable, syntax-constrained
    ``ArityPrior`` over ``vocabulary.order`` for both selection and correction
    risk. Unsupported lengths have no certificate. This path uses full native
    prior decoding and cannot yet be combined with the format-only banded cursor.

    Its ``floor`` (§22.3) bounds every account refinement can still reach
    from the symbols whose readings are fixed: the smaller of their full and
    arity risks (certificate account), their full risks (static account), or
    ``min(S / 2, e₂)`` over them (detection accounts,
    ``NCA.detection_account_mono``). Decoding has only the trivial floor 0,
    since a later climb can change the decoded sequence.
    """

    ranked_readings = True

    def __init__(self, vocabulary: RankedVocabulary, semantics: Semantics, manifest: Manifest,
                 *, evaluates: Evaluates | None = None, short_circuit: bool = True,
                 detection: str = "none", decode: bool = False,
                 band_slack: float | None = None,
                 prior: Callable[[int], ArityPrior | None] | None = None) -> None:
        if band_slack is not None and not 0 < band_slack < 1:
            raise ValueError("band_slack must be strictly between zero and one")
        if prior is not None and (not decode or band_slack is not None):
            raise ValueError("prior requires decoding without banding")
        if detection not in DETECTION:
            raise ValueError(f"detection must be one of {DETECTION}")
        self.vocabulary = vocabulary
        self.semantics = semantics
        self.evaluates = evaluates
        self.prior = prior
        self.band_slack = band_slack
        self.short_circuit = short_circuit
        self.detection = detection
        self.decode = decode
        self.manifest = manifest

    def _arity_prior(self, length: int) -> ArityPrior | None:
        prior = None if self.prior is None else self.prior(length)
        if prior is not None and prior.alphabet != self.vocabulary.order:
            raise ValueError("evaluator prior must use the vocabulary's arity order")
        return prior

    def _evaluated(self, symbols: Sequence[str], children: Sequence[Sequence[int]],
                   full: Sequence[float], shape: Sequence[float]) -> set[int]:
        if self.short_circuit and self.evaluates is not None:
            return self.evaluates(symbols, children, full, shape)
        return set(range(len(symbols)))

    def solve_session(self) -> PrefixEvaluator:
        """Keep one prior per length for an entire selective solve."""
        if self.prior is None:
            return self
        session = copy.copy(self)
        session.prior = lru_cache(maxsize=None)(self.prior)
        return session

    def symbols(self, readings: Sequence[Sequence[float]],
                state: CorrectionState | None = None, *,
                _prior: ArityPrior | None = None) -> list[str]:
        """The symbols read: each one's most probable class, or, when decoding,
        the most probable class within its decoded arity group."""
        vocabulary = self.vocabulary
        if state is not None:
            state.ensure_length(len(readings), self)
        if not self.decode:
            return most_likely(readings, vocabulary)
        if state is None or self.prior is not None:
            masses = arity_masses(readings, vocabulary)
            with np.errstate(divide="ignore"):
                prior = (None if self.prior is None else
                         _prior if _prior is not None else self._arity_prior(len(readings)))
                if self.prior is None:
                    decoded = decode(np.log(masses), vocabulary.order)
                    arities = None if decoded is None else decoded.arities
                else:
                    arities = None if prior is None else prior.best(np.log(masses))
            if arities is None:
                return most_likely(readings, vocabulary)
            if state is not None:
                state.answer_readings = np.asarray(readings, dtype=np.float64).copy()
        elif self.band_slack is not None:
            selected = self._banded_arities(readings, state)
            if selected is None:
                return most_likely(readings, vocabulary)
            arities = selected
        else:
            current = np.asarray(readings, dtype=np.float64)
            changed = (() if state.answer_readings is None else
                       _changed_rows(current, state.answer_readings))
            if state.answer_cursor is None:
                masses = arity_masses(readings, vocabulary)
                with np.errstate(divide="ignore"):
                    state.answer_cursor = Split(np.log(masses), vocabulary.order)
            if state.answer_arities is None or len(changed):
                state.answer_arities = None
                anchor = 0
                scored = None
                for k in changed:
                    anchor = int(k)
                    row = arity_masses([readings[k]], vocabulary)[0]
                    with np.errstate(divide="ignore"):
                        scored = state.answer_cursor.climb(anchor, np.log(row))
                state.answer_readings = current.copy()
                log_z, _ = (scored if scored is not None else
                            state.answer_cursor.scores(anchor, state.answer_cursor.log_probs[anchor]))
                if not math.isfinite(log_z):
                    return most_likely(readings, vocabulary)
                _, state.answer_arities = state.answer_cursor.best(anchor)
            arities = state.answer_arities
        symbols = vocabulary.symbols
        native = getattr(_NATIVE, "grouped_argmax", None)
        if len(readings) and all(isinstance(row, RankedReading) for row in readings):
            if native is not None:
                scores = np.asarray([row.weights for row in readings], dtype=np.float64)
                chosen = native(scores.reshape(-1), vocabulary.class_arities,
                                np.asarray(arities, dtype=np.int64))
                return [symbols[c] for c in chosen]
            return [symbols[row.top(vocabulary.group(a))] for row, a in zip(readings, arities)]
        if native is not None:
            scores = (state.answer_readings if state is not None else
                      np.asarray(readings, dtype=np.float64))
            assert scores is not None
            chosen = native(scores.reshape(-1), vocabulary.class_arities,
                            np.asarray(arities, dtype=np.int64))
            return [symbols[c] for c in chosen]
        return [symbols[max(vocabulary.group(a), key=r.__getitem__)]
                for r, a in zip(readings, arities)]

    def _banded_arities(self, readings: Sequence[Sequence[float]],
                        state: CorrectionState) -> tuple[int, ...] | None:
        vocabulary = self.vocabulary
        current = np.asarray(readings, dtype=np.float64)
        changed = (() if state.answer_readings is None else
                   np.flatnonzero(np.any(current != state.answer_readings, axis=1)))
        if state.answer_band is None:
            masses = arity_masses(readings, vocabulary)
            totals = masses.sum(axis=1, keepdims=True)
            if np.any(totals <= 0):
                return None
            with np.errstate(divide="ignore"):
                weights = np.log(masses / totals)
            assert self.band_slack is not None
            state.answer_band = CertifiedSplit(weights, vocabulary.order, self.band_slack)
            state.answer_band_result = state.answer_band.result()
        else:
            for k in changed:
                row = arity_masses([readings[k]], vocabulary)[0]
                total = row.sum()
                if total <= 0:
                    state.answer_band = None
                    state.answer_band_result = None
                    return None
                with np.errstate(divide="ignore"):
                    state.answer_band_result = state.answer_band.climb(int(k), np.log(row / total))
        state.answer_readings = current.copy()
        result = state.answer_band_result
        return None if result is None else result.arities

    def invoke(self, readings: Sequence[Sequence[float]]) -> Any:
        prior = self._arity_prior(len(readings))
        if self.prior is not None and prior is None:
            return None
        symbols = self.symbols(readings, _prior=prior)
        arities = [self.vocabulary.arity(s) for s in symbols]
        if prior is not None and not math.isfinite(prior.log_weight(arities)):
            return None
        children = parse(arities)
        if children is None:
            return None
        values: list[Any] = [None] * len(symbols)
        for k in reversed(range(len(symbols))):
            values[k] = self.semantics(symbols[k], [values[c] for c in children[k]])
        return values[0]

    def corrected(self, symbols: Sequence[str], children: Sequence[Sequence[int]],
                  risk: Callable[[int, Decision], float],
                  distribution: Callable[[int, Decision], torch.Tensor],
                  state: CorrectionState | None = None,
                  *, _prior: ArityPrior | None = None,
                  ) -> dict[int, float] | None:
        """The correction account (§21.5–21.6) of the decoded ``symbols``."""
        vocabulary = self.vocabulary
        order, decision = vocabulary.order, vocabulary.decision
        n = len(symbols)
        if self.band_slack is not None and state is None:
            state = CorrectionState()
        if state is not None:
            state.ensure_length(n, self)
        revision = getattr(distribution, "revision", None)
        source = getattr(distribution, "source", distribution)
        versions = tuple(revision(k) for k in range(n)) if revision is not None else None
        if (state is None or versions is None or state.distribution_source is not source
                or state.revisions is None or len(state.revisions) != n):
            invalidated = tuple(range(n))
        else:
            invalidated = tuple(k for k, (current, previous) in enumerate(
                zip(versions, state.revisions, strict=True)) if current != previous)
        cached = None
        if state is not None:
            if invalidated:
                state.risk_value = None
            risk_source = getattr(risk, "source", risk)
            if state.risk_source is not risk_source:
                state.within.clear()
                state.risk_source = risk_source
            if self.prior is not None:
                cached = state.prior_log_probs
            elif state.cursor is not None:
                cached = state.cursor.log_probs
        log_lookup = getattr(distribution, "log", None)
        def log_row(k: int) -> torch.Tensor:
            if log_lookup is not None:
                return torch.as_tensor(log_lookup(k, decision)).double()
            return torch.as_tensor(distribution(k, decision)).double().log()

        if cached is None or (self.prior is not None and versions is None):
            log_probs = torch.stack([log_row(k) for k in range(n)]).cpu().numpy()
        else:
            log_probs = cached.copy() if invalidated else cached
            for k in invalidated:
                log_probs[k] = log_row(k).cpu().numpy()
        if self.band_slack is not None:
            # Row factors cancel from both the selected weight and normalizer.
            for k in invalidated:
                total = np.logaddexp.reduce(log_probs[k])
                if not math.isfinite(total):
                    return None
                log_probs[k] -= total
        if state is not None:
            if self.prior is not None:
                state.prior_log_probs = log_probs
            state.revisions = versions
            state.distribution_source = source
            for k in invalidated:
                for a in order:
                    state.within.pop((k, a), None)
        arities = [vocabulary.arity(s) for s in symbols]
        if state is None:
            prior = (None if self.prior is None else
                     _prior if _prior is not None else self._arity_prior(n))
            posterior = (decode(log_probs, order) if self.prior is None else
                         None if prior is None else prior.decode(log_probs))
            if posterior is None:
                return None
            sequence_risk = posterior.risk(log_probs, order, arities)
            priorities = [max(0.0, 1.0 - posterior.marginals[k, order.index(a)])
                          for k, a in enumerate(arities)]
        elif self.prior is not None:
            prior = _prior if _prior is not None else self._arity_prior(n)
            if prior is None:
                return None
            state.steps += len(invalidated)
            if (state.priorities is None or state.priorities_prior is not prior
                    or state.steps >= math.isqrt(n)):
                posterior = prior.decode(log_probs)
                if posterior is None:
                    return None
                state.priorities = [max(0.0, 1.0 - posterior.marginals[k, order.index(a)])
                                    for k, a in enumerate(arities)]
                state.priorities_prior = prior
                state.steps = 0
            def calculate_prior_risk() -> float | None:
                return state.partition_risk(prior, log_probs, arities)
            sequence_risk = state.cached_risk(prior, arities, calculate_prior_risk)
            if sequence_risk is None:
                return None
            priorities = state.priorities
        else:
            if state.cursor is None:
                if self.band_slack is None:
                    state.cursor = Split(log_probs, order)
                else:
                    state.risk_band = CertifiedSplit(log_probs, order, self.band_slack)
                    state.cursor = state.risk_band.split
            state.changed = _changed_rows(state.cursor.log_probs, log_probs)
            if state.risk_band is not None:
                for k in state.changed:
                    if state.risk_band.climb_normalizer(k, log_probs[k]) is None:
                        return None
                if (not state.changed and state.risk_band.log_upper is None
                        and state.risk_band.normalizer() is None):
                    return None
                state.cursor = state.risk_band.split
                sequence_risk = state.risk_band.sequence_risk(arities)
                if sequence_risk == 0.0:
                    recovered = state.partition_risk(format_prior(n), log_probs, arities)
                    if recovered is None:
                        return None
                    sequence_risk = recovered
            else:
                scored = None
                if state.changed:
                    state.normalizer_valid = False
                for k in state.changed:
                    scored = state.cursor.climb(k, log_probs[k])
                if not state.normalizer_valid:
                    anchor = state.changed[-1] if state.changed else 0
                    log_z, _ = (scored if scored is not None else
                                state.cursor.scores(anchor, log_probs[anchor]))
                    if not math.isfinite(log_z):
                        # The linear cursor can lose every accepted path to underflow.
                        return self.corrected(symbols, children, risk, distribution, None,
                                              _prior=_prior)
                    state.normalizer_valid = True
                sequence_risk = state.cached_risk(
                    None, arities, lambda: state.partition_risk(format_prior(n), log_probs, arities))
                if sequence_risk is None:
                    return None
            if state.priorities is None or state.steps >= math.isqrt(n):
                posterior = decode(log_probs, order)
                if posterior is None:
                    return None
                state.priorities = [max(0.0, 1.0 - posterior.marginals[k, order.index(a)])
                                    for k, a in enumerate(arities)]
                state.steps = 0
            priorities = state.priorities
            state.steps += len(state.changed)
        shares = allocate_risk(sequence_risk, priorities)
        if state is None:
            within = [risk(k, vocabulary.group(a)) for k, a in enumerate(arities)]
        else:
            for k, a in enumerate(arities):
                if (k, a) not in state.within:
                    state.within[k, a] = risk(k, vocabulary.group(a))
            within = [state.within[k, a] for k, a in enumerate(arities)]
        kept = self._evaluated(symbols, children, within, [0.0] * n)
        combined = _combine_shares(shares, [within[k] if k in kept else 0.0 for k in range(n)])
        return dict(enumerate(combined))

    def certificate_session(self) -> Callable[..., dict[int, float] | None]:
        """Create certificate state owned by one solve, including its cursor."""
        state = CorrectionState()

        def account(readings: Sequence[Sequence[float]],
                    risk: Callable[[int, Decision], float],
                    distribution: Callable[[int, Decision], torch.Tensor],
                    ) -> dict[int, float] | None:
            return self.certificate(readings, risk, distribution, state)

        return account

    def certificate(self, readings: Sequence[Sequence[float]],
                    risk: Callable[[int, Decision], float],
                    distribution: Callable[[int, Decision], torch.Tensor],
                    state: CorrectionState | None = None,
                    ) -> dict[int, float] | None:
        vocabulary = self.vocabulary
        prior = self._arity_prior(len(readings))
        if self.prior is not None and prior is None:
            return None
        symbols = self.symbols(readings, state, _prior=prior)
        children = parse([vocabulary.arity(s) for s in symbols])
        if children is None:
            return None
        n = len(symbols)
        if self.decode:
            return self.corrected(symbols, children, risk, distribution, state, _prior=prior)
        arity = [risk(k, vocabulary.decision) for k in range(n)]
        if self.detection == "none":
            full = [risk(k, None) for k in range(n)]
            kept = self._evaluated(symbols, children, full, arity)
            return {k: full[k] if k in kept else arity[k] for k in range(n)}
        within = [risk(k, vocabulary.group(vocabulary.arity(s))) for k, s in enumerate(symbols)]
        kept = self._evaluated(symbols, children, within, [0.0] * n)
        shares = _markov_shares(arity)
        if self.detection == "pairs":
            pairs = _pair_shares(arity)
            if sum(pairs) < sum(shares):
                shares = pairs
        combined = _combine_shares(shares, [within[k] if k in kept else 0.0 for k in range(n)])
        return dict(enumerate(combined))

    def floor(self, readings: Sequence[Sequence[float]], risk: Callable[[int, Decision], float],
              fixed: frozenset[int]) -> float:
        decision = self.vocabulary.decision
        if self.decode:
            return 0.0
        if self.detection == "none":
            if not self.short_circuit or self.evaluates is None:
                return _lower_sum([risk(k, None) for k in fixed])
            # A symbol is charged its full or its arity risk; under separately
            # fitted temperatures either may be the smaller (§18.3).
            return _lower_sum([min(risk(k, None), risk(k, decision)) for k in fixed])
        arity = [risk(k, decision) for k in fixed]
        markov, pairs = _detection_floors(arity)
        if self.detection == "markov":
            return markov
        return min(markov, pairs)
