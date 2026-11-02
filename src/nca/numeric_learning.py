"""Learn a partition interface over supplied numeric measurements (§36.13)."""

import math
from bisect import bisect_left, bisect_right
from collections import Counter
from collections.abc import Callable, Hashable, Sequence
from dataclasses import replace
from typing import Any

from nca.abi import Contract, Module
from nca.discovery import Decoded, Decoder, Proposal
from nca.objects import Constructor, canonical


def _observation(value: Any) -> float:
    if type(value) is not float or not math.isfinite(value):
        raise ValueError("numeric observations must be finite floats")
    return value


def midpoint_boundary(lower: float, upper: float) -> float:
    """Finite gap midpoint, falling back to the upper edge if rounding closes it."""
    lower, upper = _observation(lower), _observation(upper)
    if not lower < upper:
        raise ValueError("boundary placement requires an increasing observed gap")
    midpoint = lower / 2 + upper / 2
    return midpoint if lower < midpoint <= upper else upper


def _placed_boundary(lower: float, upper: float,
                     policy: Callable[[float, float], float] | None) -> float:
    boundary = upper if policy is None else _observation(policy(lower, upper))
    if not lower < boundary <= upper:
        raise ValueError("placed boundary must stay inside the observed gap (lower, upper]")
    return boundary


class PartitionEncoder:
    """A learned threshold, with a generated source/boundary-specific interface."""

    def __init__(self, measurement: Module, boundary: float, cost: float) -> None:
        self.measurement, self.boundary = measurement, boundary
        self.constructor = Constructor("learned-numeric-partition", "1", 0,
            canonical({"source": measurement.manifest.contract.output, "boundary": boundary,
                       "meaning": "code 0 below boundary; code 1 at or above boundary"}).decode())
        self.manifest = replace(measurement.manifest,
                                module_id=f"{measurement.manifest.module_id}/partition",
                                contract=replace(measurement.manifest.contract,
                                                 output=self.constructor.type()),
                                cost=measurement.manifest.cost + cost)

    def invoke(self, *inputs: Any) -> int:
        return int(_observation(self.measurement.invoke(*inputs)) >= self.boundary)


def propose_partition(incumbent: Module, measurement: Module,
                      rows: Sequence[tuple[Any, ...]], labels: Sequence[Hashable], *,
                      encoding_cost: float, decoder_cost: float,
                      place_boundary: Callable[[float, float], float] | None = None) -> list[Proposal]:
    """Fit the empirical best observed threshold and two modal output labels.

    Use only training rows, e.g. inside discover's proposer. Labels are opaque
    hashable values; measurements are finite floats. Modal ties follow sorted
    observation order; boundary ties prefer the smallest value. Equal-valued
    observations are never split. A constant measurement yields no proposal.
    An optional placement policy chooses within the selected empty gap (§36.22),
    preserving training outcomes; the default is the upper observed edge.
    Sorting costs O(n log n); modal-count scans also depend on label cardinality.
    No persistence, calibration or unrestricted feature discovery is claimed.
    """
    ordered = _ordered(incumbent, measurement, rows, labels, encoding_cost, decoder_cost)
    return _partition_from_ordered(incumbent, measurement, ordered, encoding_cost,
                                   decoder_cost, place_boundary)


def _partition_from_ordered(incumbent: Module, measurement: Module,
                            ordered: Sequence[tuple[float, Hashable]], encoding_cost: float,
                            decoder_cost: float,
                            place_boundary: Callable[[float, float], float] | None
                            ) -> list[Proposal]:
    """Build a proposal from validated observations sorted by measured value."""
    best = _fitted_split(ordered, place_boundary)
    if best is None:
        return []
    boundary, lower_label, upper_label = best
    encoder = PartitionEncoder(measurement, boundary, encoding_cost)
    decoder = Decoder(Contract((encoder.constructor.type(),), incumbent.manifest.contract.output),
                      {0: lower_label, 1: upper_label}, lower_label, decoder_cost)
    return [Proposal(Decoded(encoder, decoder, incumbent.manifest.contract), (encoder.constructor,))]


def _ordered(incumbent: Module, measurement: Module,
             rows: Sequence[tuple[Any, ...]], labels: Sequence[Hashable],
             encoding_cost: float, decoder_cost: float) -> list[tuple[float, Hashable]]:
    if any(not math.isfinite(c) or c < 0 for c in (encoding_cost, decoder_cost)):
        raise ValueError("declared costs must be finite and nonnegative")
    contract = incumbent.manifest.contract
    if replace(measurement.manifest.contract, output=contract.output) != contract:
        raise ValueError("measurement must preserve inputs, slots and relevance")
    return _observations(measurement, rows, labels)


def _observations(measurement: Module, rows: Sequence[tuple[Any, ...]],
                  labels: Sequence[Hashable]) -> list[tuple[float, Hashable]]:
    if len(rows) < 2 or len(rows) != len(labels):
        raise ValueError("partition training needs at least two aligned observations")
    contract = measurement.manifest.contract
    if any(len(row) != len(contract.slots) + len(contract.inputs) for row in rows):
        raise ValueError("rows must supply slot fillings followed by inputs")
    return sorted(((_observation(measurement.invoke(*row)), label)
                      for row, label in zip(rows, labels, strict=True)), key=lambda item: item[0])


def _fitted_split(ordered: Sequence[tuple[float, Hashable]],
                  place_boundary: Callable[[float, float], float] | None
                  ) -> tuple[float, Hashable, Hashable] | None:
    best, _ = _best_split(ordered)
    if best is None:
        return None
    boundary, lower_label, upper_label = best
    if place_boundary is not None:
        lower = next(value for value, _ in reversed(ordered) if value < boundary)
        boundary = _placed_boundary(lower, boundary, place_boundary)
    return boundary, lower_label, upper_label


def fit_partition_encoder(measurement: Module, rows: Sequence[tuple[Any, ...]],
                          labels: Sequence[Hashable], *, encoding_cost: float,
                          place_boundary: Callable[[float, float], float] | None = None
                          ) -> PartitionEncoder | None:
    """Fit only the representation; labels supervise fitting without becoming an output type."""
    if not math.isfinite(encoding_cost) or encoding_cost < 0:
        raise ValueError("encoding cost must be finite and nonnegative")
    best = _fitted_split(_observations(measurement, rows, labels), place_boundary)
    return None if best is None else PartitionEncoder(measurement, best[0], encoding_cost)


def _best_split(ordered: Sequence[tuple[float, Hashable]]) -> tuple[
        tuple[float, Hashable, Hashable] | None, int]:
    left: Counter[Hashable] = Counter()
    right = Counter(label for _, label in ordered)
    best: tuple[float, Hashable, Hashable] | None = None
    best_score = -1
    for i in range(1, len(ordered)):
        label = ordered[i - 1][1]
        left[label] += 1
        right[label] -= 1
        if not right[label]:
            del right[label]
        if ordered[i - 1][0] == ordered[i][0]:
            continue
        lower, upper = left.most_common(1)[0], right.most_common(1)[0]
        score = lower[1] + upper[1]
        if score > best_score:
            best, best_score = (ordered[i][0], lower[0], upper[0]), score
    return best, best_score


class RegionsEncoder:
    """Codes a learned, resource-bounded collection of scalar intervals."""

    def __init__(self, measurement: Module, boundaries: tuple[float, ...], cost: float) -> None:
        self.measurement, self.boundaries = measurement, boundaries
        self.constructor = Constructor("learned-numeric-regions", "1", 0,
            canonical({"source": measurement.manifest.contract.output, "boundaries": boundaries,
                       "meaning": "code is the count of boundaries at or below the observation"}).decode())
        self.manifest = replace(measurement.manifest,
                                module_id=f"{measurement.manifest.module_id}/regions",
                                contract=replace(measurement.manifest.contract,
                                                 output=self.constructor.type()),
                                cost=measurement.manifest.cost + cost)

    def invoke(self, *inputs: Any) -> int:
        return bisect_right(self.boundaries, _observation(self.measurement.invoke(*inputs)))


def propose_regions(incumbent: Module, measurement: Module,
                    rows: Sequence[tuple[Any, ...]], labels: Sequence[Hashable], *,
                    max_regions: int, encoding_cost: float, decoder_cost: float,
                    place_boundary: Callable[[float, float], float] | None = None) -> list[Proposal]:
    """Greedily refine numeric intervals using training data alone (§36.14).

    Pure intervals are not split. Zero-gain refinements remain eligible, up to
    the explicit region budget. This is not a globally optimal segmentation.
    Features remain fixed; modal scan costs depend on label cardinality.
    Optional placement changes only thresholds inside empty observed gaps.
    """
    if type(max_regions) is not int or max_regions < 1:
        raise ValueError("maximum regions must be a positive integer")
    ordered = _ordered(incumbent, measurement, rows, labels, encoding_cost, decoder_cost)
    values = [value for value, _ in ordered]
    regions = [(0, len(ordered))]
    while len(regions) < max_regions:
        chosen: tuple[int, int] | None = None
        best_gain = -1
        for index, (start, end) in enumerate(regions):
            count = Counter(label for _, label in ordered[start:end])
            if len(count) == 1:
                continue
            split, score = _best_split(ordered[start:end])
            if split is not None:
                gain = score - count.most_common(1)[0][1]
                if gain > best_gain:
                    chosen = index, bisect_left(values, split[0], start, end)
                    best_gain = gain
        if chosen is None:
            break
        index, middle = chosen
        start, end = regions[index]
        regions[index:index + 1] = [(start, middle), (middle, end)]
    boundaries = tuple(_placed_boundary(values[start - 1], values[start], place_boundary)
                       for start, _ in regions[1:])
    encoder = RegionsEncoder(measurement, boundaries, encoding_cost)
    table = {index: Counter(label for _, label in ordered[start:end]).most_common(1)[0][0]
             for index, (start, end) in enumerate(regions)}
    decoder = Decoder(Contract((encoder.constructor.type(),), incumbent.manifest.contract.output),
                      table, table[0], decoder_cost)
    return [Proposal(Decoded(encoder, decoder, incumbent.manifest.contract), (encoder.constructor,))]
