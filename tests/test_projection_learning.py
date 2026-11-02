"""Acquire intermediate features beyond fixed coordinate partitions."""

import random
from dataclasses import dataclass
from typing import Any

import pytest

from nca.abi import Contract, Manifest
from nca.discovery import discover
from nca.projection_learning import ProjectionEncoder, propose_projections


@dataclass
class Measurement:
    manifest = Manifest("measurement", "1", Contract(("input",), "vector"), effects=frozenset())

    def invoke(self, value: Any) -> Any:
        return value


class Baseline:
    manifest = Manifest("baseline", "1", Contract(("input",), "output"), effects=frozenset())

    def invoke(self, value: Any) -> bool:
        return True


def test_acquire_oblique_type_and_select_on_fresh_rows() -> None:
    rng = random.Random(70)
    rows = [((rng.uniform(-1, 1), rng.uniform(-1, 1)),) for _ in range(1000)]
    labels = [row[0][0] + row[0][1] >= 0 for row in rows]
    sizes = []

    def propose(train: Any, targets: Any) -> Any:
        sizes.append(len(train))
        return propose_projections(Baseline(), Measurement(), train, targets, limit=1,
                                   projection_cost=1, encoding_cost=1, decoder_cost=1)

    result = discover(Baseline(), propose, rows, labels, lambda a, b: a == b)
    assert sizes == [500]
    assert result.chosen is not None
    assert sum(result.trials[0].outcomes) >= 475
    proposal = propose(rows[:500], labels[:500])[0]
    assert len(proposal.constructors) == 2
    projection, partition = proposal.constructors
    assert projection.type() != partition.type()
    assert proposal.expert.feature.measurement.manifest.contract.output == projection.type()


def test_coincident_centroids_and_invalid_observations() -> None:
    rows = [((-1.0, -1.0),), ((1.0, 1.0),), ((-1.0, 1.0),), ((1.0, -1.0),)]
    options = dict(limit=1, projection_cost=1, encoding_cost=1, decoder_cost=1)
    assert propose_projections(Baseline(), Measurement(), rows, [True, True, False, False],
                               **options) == []
    for bad in [[((0.0,),), ((0.0, 1.0),)], [((float("nan"),),), ((1.0,),)]]:
        with pytest.raises(ValueError):
            propose_projections(Baseline(), Measurement(), bad, [True, False], **options)
    projection = ProjectionEncoder(Measurement(), (1.0, 2.0), 1)
    with pytest.raises(ValueError, match="dimension"):
        projection.invoke((1.0,))


def test_pair_search_budget() -> None:
    rows = [((float(i),),) for i in range(6)]
    labels = [i // 2 for i in range(6)]
    assert len(propose_projections(Baseline(), Measurement(), rows, labels, limit=2,
                                  projection_cost=0, encoding_cost=0, decoder_cost=0)) == 2


def test_polynomial_lift_budget_semantics_and_finiteness() -> None:
    from nca.projection_learning import PolynomialEncoder

    lift = PolynomialEncoder(Measurement(), 2, 2, max_terms=5, cost=1)
    assert lift.invoke((2.0, 3.0)) == (2.0, 3.0, 4.0, 6.0, 9.0)
    assert lift.manifest.contract.output == lift.constructor.type()
    cubic = PolynomialEncoder(Measurement(), 1, 3, max_terms=3, cost=0)
    assert cubic.invoke((2.0,)) == (2.0, 4.0, 8.0)
    assert PolynomialEncoder(Measurement(), 0, 3, max_terms=1, cost=0).invoke(()) == ()
    with pytest.raises(ValueError, match="term budget"):
        PolynomialEncoder(Measurement(), 100, 5, max_terms=10, cost=1)
    with pytest.raises(ValueError, match="finite"):
        lift.invoke((1e308, 1.0))
    with pytest.raises(ValueError, match="dimension"):
        lift.invoke((1.0,))


def test_nonlinear_decomposition_overcomes_equal_centroids() -> None:
    from nca.projection_learning import propose_polynomial_partitions

    rows = [((s * a, t * a),) for a in (0.1, 1.0)
            for s, t in ((1, 1), (-1, -1), (1, -1), (-1, 1))]
    targets = [True, True, False, False] * 2
    kwargs = dict(limit=1, projection_cost=1, encoding_cost=1, decoder_cost=1)
    assert propose_projections(Baseline(), Measurement(), rows, targets, **kwargs) == []
    proposals = propose_polynomial_partitions(Baseline(), Measurement(), rows, targets,
                degrees=(1, 2), max_terms=5, lifting_cost=1, **kwargs)
    assert len(proposals) == 1
    proposal = proposals[0]
    assert len(proposal.constructors) == 3
    assert len({c.type() for c in proposal.constructors}) == 3
    assert proposal.expert.invoke((0.3, 0.7)) is True
    assert proposal.expert.invoke((0.3, -0.7)) is False
    assert proposal.expert.invoke((-0.8, -0.2)) is True
    assert proposal.expert.invoke((-0.8, 0.2)) is False


def test_gap_policy_reaches_nonlinear_partition_without_runtime_callback() -> None:
    from nca.numeric_learning import midpoint_boundary
    from nca.projection_learning import propose_polynomial_partitions

    calls = []

    def placement(lower: float, upper: float) -> float:
        calls.append((lower, upper))
        return midpoint_boundary(lower, upper)

    rows = [((s * 1.0, t * 1.0),) for s, t in ((1, 1), (-1, -1), (1, -1), (-1, 1))]
    proposal = propose_polynomial_partitions(Baseline(), Measurement(), rows,
                [True, True, False, False], degrees=(2,), max_terms=5, limit=1,
                lifting_cost=0, projection_cost=0, encoding_cost=0, decoder_cost=0,
                place_boundary=placement)[0]
    assert len(calls) == 1
    assert proposal.expert.invoke((0.2, -0.3)) is False
    assert proposal.expert.invoke((0.2, 0.3)) is True
    assert len(calls) == 1


def test_reuse_preserves_models_and_avoids_repeated_training_measurements() -> None:
    from nca.projection_learning import propose_polynomial_partitions

    class Counting(Measurement):
        def __init__(self) -> None:
            self.calls = 0

        def invoke(self, value: Any) -> tuple[float, ...]:
            self.calls += 1
            return tuple(value)

    source = Counting()
    # Lists make the rows unhashable: reuse is by training position, not input keys.
    rows = [([float(i), float(i % 2)],) for i in range(6)]
    labels = [i // 2 for i in range(6)]
    kwargs = dict(degrees=(2,), max_terms=5, limit=3, lifting_cost=1,
                  projection_cost=1, encoding_cost=1, decoder_cost=1)
    reference = propose_polynomial_partitions(Baseline(), source, rows, labels, **kwargs)
    assert source.calls == 25
    source.calls = 0
    reused = propose_polynomial_partitions(Baseline(), source, rows, labels,
                                          reuse_observations=True, **kwargs)
    assert source.calls == 7
    assert len(reused) == len(reference) == 3
    for before, after in zip(reference, reused, strict=True):
        assert before.constructors == after.constructors
        assert before.expert.manifest == after.expert.manifest
        assert after.expert.feature.measurement.measurement.measurement is source
        count = source.calls
        assert after.expert.invoke([0.37, 0.62]) == before.expert.invoke([0.37, 0.62])
        assert source.calls == count + 2


@pytest.mark.parametrize("effects", [None, frozenset({"external"})])
def test_reuse_rejects_unknown_or_nonempty_effects_before_invocation(effects: Any) -> None:
    from dataclasses import replace

    from nca.projection_learning import propose_polynomial_partitions

    class Unusable(Measurement):
        manifest = replace(Measurement.manifest, effects=effects)

        def invoke(self, value: Any) -> Any:
            pytest.fail("unsafe measurement must be rejected before invocation")

    kwargs = dict(limit=1, projection_cost=0, encoding_cost=0, decoder_cost=0,
                  reuse_observations=True)
    rows = [((0.0,),), ((1.0,),)]
    with pytest.raises(ValueError, match="known empty effects"):
        propose_projections(Baseline(), Unusable(), rows, [True, False], **kwargs)
    with pytest.raises(ValueError, match="known empty effects"):
        propose_polynomial_partitions(Baseline(), Unusable(), rows, [True, False],
                                      degrees=(2,), max_terms=2, lifting_cost=0, **kwargs)


def test_reuse_rejects_slots_even_with_empty_declared_effects() -> None:
    from dataclasses import replace

    slots = ((("input",), "slot-output"),)
    source = Measurement()
    source.manifest = replace(source.manifest,
                              contract=replace(source.manifest.contract, slots=slots))
    baseline = Baseline()
    baseline.manifest = replace(baseline.manifest,
                                contract=replace(baseline.manifest.contract, slots=slots))
    with pytest.raises(ValueError, match="no slots"):
        propose_projections(baseline, source, [(None, (0.0,)), (None, (1.0,))],
                            [True, False], limit=1, projection_cost=0, encoding_cost=0,
                            decoder_cost=0, reuse_observations=True)
