"""Data-driven partition boundaries and generated intermediate contracts."""

from collections import Counter

import pytest

from nca.abi import Contract, Manifest
from nca.discovery import Decoded
from nca.numeric_learning import PartitionEncoder, propose_partition


class Measurement:
    manifest = Manifest("measurement", "1", Contract(("input",), "measurement"), effects=frozenset())

    def invoke(self, value: float) -> float:
        return value


class Incumbent(Measurement):
    manifest = Manifest("baseline", "1", Contract(("input",), "target"))

    def invoke(self, value: float) -> str:
        return "constant"


def test_learned_partition_matches_exhaustive_threshold_optimum() -> None:
    values = [0.0, 0.0, 0.2, 0.4, 0.4, 0.8, 1.0]
    labels = ["a", "b", "a", "b", "b", "b", "a"]
    proposal = propose_partition(Incumbent(), Measurement(), [(x,) for x in values], labels,
                                 encoding_cost=0.1, decoder_cost=0.2)[0]
    expert = proposal.expert
    assert isinstance(expert, Decoded) and isinstance(expert.feature, PartitionEncoder)
    successes = sum(expert.invoke(x) == y for x, y in zip(values, labels))
    for boundary in sorted(set(values))[1:]:
        groups = [[y for x, y in zip(values, labels) if (x >= boundary) == side]
                  for side in (False, True)]
        assert successes >= sum(Counter(group).most_common(1)[0][1] for group in groups)
    assert expert.manifest.contract == Incumbent.manifest.contract
    assert expert.decoder.manifest.contract.inputs == (proposal.constructors[0].type(),)
    assert expert.feature.invoke(expert.feature.boundary) == 1


def test_constant_and_invalid_measurements() -> None:
    assert propose_partition(Incumbent(), Measurement(), [(1.0,), (1.0,)], ["a", "b"],
                             encoding_cost=0, decoder_cost=0) == []
    with pytest.raises(ValueError, match="finite floats"):
        propose_partition(Incumbent(), Measurement(), [(float("nan"),), (1.0,)], ["a", "b"],
                          encoding_cost=0, decoder_cost=0)
