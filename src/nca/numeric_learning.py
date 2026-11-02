"""Learn a partition interface over supplied numeric measurements (§36.13)."""

import math
from collections import Counter
from collections.abc import Hashable, Sequence
from dataclasses import replace
from typing import Any

from nca.abi import Contract, Module
from nca.discovery import Decoded, Decoder, Proposal
from nca.objects import Constructor, canonical


def _observation(value: Any) -> float:
    if type(value) is not float or not math.isfinite(value):
        raise ValueError("numeric partition observations must be finite floats")
    return value


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
                      encoding_cost: float, decoder_cost: float) -> list[Proposal]:
    """Fit the empirical best observed threshold and two modal output labels.

    Use only training rows, e.g. inside discover's proposer. Labels are opaque
    hashable values; measurements are finite floats. Modal ties follow sorted
    observation order; boundary ties prefer the smallest value. Equal-valued
    observations are never split. A constant measurement yields no proposal.
    Sorting costs O(n log n); modal-count scans also depend on label cardinality.
    No persistence, calibration or unrestricted feature discovery is claimed.
    """
    if len(rows) < 2 or len(rows) != len(labels):
        raise ValueError("partition training needs at least two aligned observations")
    if any(not math.isfinite(c) or c < 0 for c in (encoding_cost, decoder_cost)):
        raise ValueError("declared costs must be finite and nonnegative")
    contract = incumbent.manifest.contract
    if replace(measurement.manifest.contract, output=contract.output) != contract:
        raise ValueError("measurement must preserve inputs, slots and relevance")
    if any(len(row) != len(contract.slots) + len(contract.inputs) for row in rows):
        raise ValueError("rows must supply slot fillings followed by inputs")
    ordered = sorted(((_observation(measurement.invoke(*row)), label)
                      for row, label in zip(rows, labels, strict=True)), key=lambda item: item[0])
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
    if best is None:
        return []
    boundary, lower_label, upper_label = best
    encoder = PartitionEncoder(measurement, boundary, encoding_cost)
    decoder = Decoder(Contract((encoder.constructor.type(),), contract.output),
                      {0: lower_label, 1: upper_label}, lower_label, decoder_cost)
    return [Proposal(Decoded(encoder, decoder, contract), (encoder.constructor,))]
