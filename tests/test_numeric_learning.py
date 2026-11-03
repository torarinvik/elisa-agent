"""Data-driven partition boundaries and generated intermediate contracts."""

from collections import Counter

import pytest

from nca.abi import Contract, Manifest
from nca.discovery import Decoded
from nca.learning.numeric import PartitionEncoder, propose_partition


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
    from nca.learning.numeric import RegionsEncoder, propose_regions

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
    from nca.learning.numeric import propose_regions

    proposal = propose_regions(Incumbent(), Measurement(), [(1.0,)] * 4,
                                ["a", "b", "a", "b"], max_regions=100,
                                encoding_cost=0, decoder_cost=0)[0]
    assert proposal.expert.invoke(1.0) == "a"
    assert proposal.expert.feature.boundaries == ()


def test_gap_policy_preserves_training_predictions_and_changes_unseen_gap() -> None:
    from nca.learning.numeric import midpoint_boundary, propose_regions

    rows = [(-2.0,), (-2.0,), (-1.0,), (3.0,), (4.0,), (10.0,), (11.0,)]
    labels = ["a", "a", "a", "b", "b", "c", "c"]
    for regions in (False, True):
        fit = propose_regions if regions else propose_partition
        options = {"max_regions": 3} if regions else {}
        edge = fit(Incumbent(), Measurement(), rows, labels,
                   encoding_cost=0, decoder_cost=0, **options)[0]
        midpoint = fit(Incumbent(), Measurement(), rows, labels,
                       encoding_cost=0, decoder_cost=0, place_boundary=midpoint_boundary,
                       **options)[0]
        assert [edge.expert.invoke(*row) for row in rows] == [
            midpoint.expert.invoke(*row) for row in rows]
        assert edge.constructors != midpoint.constructors
        assert edge.expert.invoke(2.0) != midpoint.expert.invoke(2.0)


def test_gap_policy_rejects_training_changes_and_nonfinite_boundaries() -> None:
    for boundary in (-1.0, 3.1, float("nan"), float("inf")):
        with pytest.raises(ValueError):
            propose_partition(Incumbent(), Measurement(), [(-1.0,), (3.0,)], ["a", "b"],
                              encoding_cost=0, decoder_cost=0,
                              place_boundary=lambda lower, upper: boundary)


def test_midpoint_float_extremes_and_adjacent_values() -> None:
    import math
    import sys

    from nca.learning.numeric import midpoint_boundary

    assert midpoint_boundary(-sys.float_info.max, sys.float_info.max) == 0.0
    for lower, upper in [(1.0, math.nextafter(1.0, math.inf)),
                         (0.0, math.ulp(0.0)), (-math.ulp(0.0), 0.0),
                         (sys.float_info.max / 2, sys.float_info.max)]:
        assert lower < midpoint_boundary(lower, upper) <= upper
    with pytest.raises(ValueError):
        midpoint_boundary(1.0, 1.0)


def test_purity_breaks_zero_gain_ties_without_reducing_modal_training_score() -> None:
    from nca.learning.numeric import propose_regions, purity_tiebreak

    rows = [(float(i),) for i in range(12)]
    labels = ["a"] * 5 + ["b"] * 3 + ["a"] * 4
    kwargs = dict(max_regions=3, encoding_cost=0, decoder_cost=0)
    plain = propose_regions(Incumbent(), Measurement(), rows, labels, **kwargs)[0]
    guided = propose_regions(Incumbent(), Measurement(), rows, labels,
                             tie_break=purity_tiebreak, **kwargs)[0]
    assert sum(plain.expert.invoke(*r) == y for r, y in zip(rows, labels)) == 9
    assert sum(guided.expert.invoke(*r) == y for r, y in zip(rows, labels)) == 12
    assert guided.expert.feature.boundaries == (5.0, 8.0)
    with pytest.raises(ValueError, match="tie score must be finite"):
        propose_regions(Incumbent(), Measurement(), rows, labels,
                         tie_break=lambda left, right: float("nan"), **kwargs)
