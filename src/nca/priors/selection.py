"""Held-out evidence selection among supplied structural priors."""

from __future__ import annotations

from collections.abc import Callable, Iterable, Sequence
from dataclasses import dataclass
import math
import numpy as np
from nca import priors as _priors
from nca.priors import ArityPrior, _base_normalizer, _evidence_prior
from nca.priors.arithmetic import (
    _PartitionArithmeticError, _add_evidence, _evidence_difference,
    _partition_log_product, _within_score_error,
)


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
    Its outward rounding assumes the platform logarithm is within one ulp.
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
    corrections = [0.0] * len(candidates)
    models: dict[tuple[int, int], tuple[ArityPrior, float | None] | None] = {}
    count = 0
    for observation in readings:
        # Freeze each reading before invoking providers, which may mutate caller storage.
        rows = np.array(observation, dtype=np.float64, copy=True)
        if rows.ndim != 2 or rows.shape[1] != len(alphabet):
            raise ValueError("readings must be matrices over the shared alphabet")
        # Validate every observation even after some candidates become unavailable.
        fast_validate = getattr(_priors._NATIVE, "normalized_rows_fast", None)
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
                    if not prior.supports(base_rows):
                        raise ValueError("candidate prior has zero mass under the base")
                    # The base normalizer is needed only for readings unlike the base.
                    models[key] = prior, None
            model = models[key]
            if model is None:
                if score_clip is None:
                    scores[i] = -math.inf
                    continue
                evidence = -score_clip
            else:
                prior, denominator = model
                base_rows = np.broadcast_to(base, rows.shape)
                if np.array_equal(rows, base_rows):
                    evidence = 0.0
                else:
                    if denominator is None:
                        denominator = _base_normalizer(prior, base_rows)
                        models[key] = prior, denominator
                    evidence = _evidence_difference(prior.log_normalizer(rows), denominator,
                                                    rows, base_rows)
            if math.isnan(evidence) or evidence == math.inf:
                raise ValueError("candidate evidence must be finite or negative infinity")
            if score_clip is not None:
                evidence = max(-score_clip, min(score_clip, evidence))
            if evidence == -math.inf:
                scores[i] = -math.inf
            else:
                scores[i], corrections[i] = _add_evidence(scores[i], corrections[i], evidence)
        count += 1
    for i, score in enumerate(scores):
        if math.isfinite(score):
            try:
                scores[i] = _partition_log_product(score, corrections[i], "summed evidence")
            except _PartitionArithmeticError as exc:
                raise ValueError("summed evidence overflow or loses precision") from exc
    if not count or not any(math.isfinite(score) for score in scores):
        raise ValueError("requires observations and at least one finite-evidence candidate")
    if score_clip is not None:
        assert alpha is not None
        # Outward steps cover binary64 rounding; log accuracy remains a libm assumption.
        log_upper = math.nextafter(math.log(2 * len(candidates)), math.inf)
        log_lower = math.nextafter(math.log(alpha), -math.inf)
        log_ratio = math.nextafter(log_upper - log_lower, math.inf)
        sample_count = float(count)
        if sample_count < count:
            sample_count = math.nextafter(sample_count, math.inf)
        scale = math.nextafter(2.0 * sample_count, math.inf)
        variance = math.nextafter(scale * log_ratio, math.inf)
        root = math.nextafter(math.sqrt(variance), math.inf)
        score_error = math.nextafter(score_clip * root, math.inf)
        if not math.isfinite(score_error):
            raise ValueError("derived score error overflow")
    best = max(range(len(scores)), key=scores.__getitem__)
    chosen = (best if score_error == 0 else next(
        i for i, score in enumerate(scores) if math.isfinite(score)
        and _within_score_error(scores[best], score, score_error)))
    return PriorSelection(chosen, tuple(scores), count, score_error, score_clip, alpha)
