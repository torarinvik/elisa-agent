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


def test_refinement_learns_multiple_regions_under_explicit_budget() -> None:
    from nca.numeric_learning import RegionsEncoder, propose_regions

    rows = [(i / 100,) for i in range(100)]
    labels = ["a" if x[0] < 0.25 else "b" if x[0] < 0.75 else "c" for x in rows]
    previous = 0
    for budget in (1, 2, 3, 10):
        proposal = propose_regions(Incumbent(), Measurement(), rows, labels, max_regions=budget,
                                    encoding_cost=0.1, decoder_cost=0.2)[0]
        assert isinstance(proposal.expert, Decoded)
        encoder = proposal.expert.feature
        assert isinstance(encoder, RegionsEncoder)
        assert len(encoder.boundaries) + 1 <= budget
        correct = sum(proposal.expert.invoke(*x) == y for x, y in zip(rows, labels))
        assert correct >= previous
        previous = correct
        if budget >= 3:
            assert correct == 100 and encoder.boundaries == (0.25, 0.75)
            assert encoder.invoke(0.25) == 1 and encoder.invoke(0.75) == 2
    with pytest.raises(ValueError, match="positive integer"):
        propose_regions(Incumbent(), Measurement(), rows, labels, max_regions=0,
                         encoding_cost=0, decoder_cost=0)


def test_refinement_keeps_equal_measurements_together() -> None:
    from nca.numeric_learning import propose_regions

    proposal = propose_regions(Incumbent(), Measurement(), [(1.0,)] * 4,
                                ["a", "b", "a", "b"], max_regions=100,
                                encoding_cost=0, decoder_cost=0)[0]
    assert proposal.expert.invoke(1.0) == "a"
    assert proposal.expert.feature.boundaries == ()
