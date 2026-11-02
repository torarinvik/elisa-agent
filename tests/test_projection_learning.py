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


def test_native_polynomials_match_reference_bits_and_failures(monkeypatch: pytest.MonkeyPatch) -> None:
    from array import array

    import nca.projection_learning as learning

    native = learning._NATIVE
    if native is None:
        pytest.skip("polynomial kernel not built or disabled")
    rng = random.Random(3628)
    cases = [(tuple(rng.uniform(-2, 2) for _ in range(6)), 3) for _ in range(100)]
    cases += [((1e-300, -1e-300), 3), ((0.0, -0.0), 3),
              ((1e308, -1e308), 3), ((5e-324, -5e-324), 3), ((), 3)]
    for value, degree in cases:
        model = learning.PolynomialEncoder(Measurement(), len(value), degree,
                                           max_terms=100, cost=0)
        results = []
        for backend in (None, native):
            monkeypatch.setattr(learning, "_NATIVE", backend)
            try:
                results.append(array("d", model.invoke(value)).tobytes())
            except ValueError as error:
                results.append(str(error))
        assert results[0] == results[1]


def test_native_polynomials_validate_packed_indices() -> None:
    from array import array

    import nca.projection_learning as learning

    native = learning._NATIVE
    if native is None:
        pytest.skip("polynomial kernel not built or disabled")
    for offsets, indices in [([], []), ([1], []), ([0, 2], [0]),
                              ([0, -1, 1], [0]), ([0, 1], [-1]),
                              ([0, 1], [1]), ([0, 2, 1], [0])]:
        assert native.monomials(array("d", [2.0]), array("q", offsets),
                                array("q", indices)) == []
    assert native.monomials(array("d", [2.0]), array("q", [0, 0, 2]),
                            array("q", [0, 0])) == [1.0, 4.0]


def test_auxiliary_projection_routes_original_object_targets() -> None:
    from collections import Counter
    from nca.discovery import Proposal
    from nca.numeric_learning import midpoint_boundary
    from nca.projection_learning import fit_projection_encoders
    from nca.regional_learning import propose_failure_partitions

    class Expert:
        def __init__(self, manifest: Manifest, function: Any) -> None:
            self.manifest, self.function = manifest, function

        def invoke(self, *args: Any) -> Any:
            return self.function(*args)

    incumbent = Expert(Baseline.manifest, lambda xy: None)
    rng = random.Random(3641)
    rows = [((rng.uniform(-1, 1), rng.uniform(-1, 1)),) for _ in range(1000)]
    targets = [{"kind": "left" if sum(row[0]) < 0 else "right"} for row in rows]
    seen, measurement_calls = [], []

    def learn(train: Any, categories: Any, budget: int) -> Any:
        measurement_calls.append((tuple(train), tuple(categories), budget))
        return [Proposal(encoder, (encoder.constructor,))
                for encoder in fit_projection_encoders(Measurement(), train, categories,
                                                       limit=budget, projection_cost=1)]

    def propose(train: Any, labels: Any) -> Any:
        def acquire(subset: Any, original: Any) -> Any:
            seen.extend(zip(subset, original, strict=True))
            modal = Counter(target["kind"] for target in original).most_common(1)[0][0]
            return [Proposal(Expert(incumbent.manifest, lambda xy: {"kind": modal}))]

        return propose_failure_partitions(incumbent, [], acquire, train, labels,
                    lambda a, b: a == b, max_measurements=1, max_regions=2,
                    encoding_cost=1, overhead_cost=1, max_combinations=1,
                    place_boundary=midpoint_boundary,
                    routing_signal=lambda row, prediction, target: frozenset({target["kind"]}),
                    propose_measurements=learn)

    result = discover(incumbent, propose, rows, targets, lambda a, b: a == b)
    assert result.chosen is not None
    assert len(result.chosen.constructors) == 2
    assert measurement_calls == [(tuple(rows[:500]),
        tuple(frozenset({t["kind"]}) for t in targets[:500]), 1)]
    assert sum(result.trials[-1].outcomes) > 475
    assert sorted((row, target["kind"]) for row, target in seen) == (
        sorted((row, target["kind"]) for row, target in zip(rows[:500], targets[:500])))


def test_projection_encoder_fitting_is_label_agnostic_and_bounded() -> None:
    from nca.projection_learning import fit_projection_encoders

    rows = [((-2.0, 0.0),), ((-1.0, 0.0),), ((1.0, 0.0),), ((2.0, 0.0),)]
    first = fit_projection_encoders(Measurement(), rows, ["a", "a", "b", "b"],
                                    limit=1, projection_cost=0)
    renamed = fit_projection_encoders(Measurement(), rows, [17, 17, 93, 93],
                                      limit=1, projection_cost=0)
    assert first[0].direction == renamed[0].direction == (3.0, 0.0)
    assert first[0].constructor == renamed[0].constructor
    assert fit_projection_encoders(Measurement(), rows, [0] * 4,
                                   limit=1, projection_cost=0) == []
    with pytest.raises(ValueError, match="arity"):
        fit_projection_encoders(Measurement(), [(), ()], [0, 1], limit=1, projection_cost=0)


def test_regression_projection_acquires_a_continuous_intermediate_type() -> None:
    from nca.affine_learning import fit_affine
    from nca.discovery import Proposal
    from nca.interface_learning import propose_heads
    from nca.projection_learning import fit_regression_projection

    rng = random.Random(3644)
    rows = [((rng.uniform(-1, 1), rng.uniform(-1, 1)),) for _ in range(400)]
    targets = [2 * v[0] - 3 * v[1] + 0.7 for v, in rows]
    observed = []

    def propose(train: Any, labels: Any) -> Any:
        observed.append((tuple(train), tuple(labels)))
        encoder = fit_regression_projection(Measurement(), train, labels, projection_cost=1)
        assert encoder is not None
        assert encoder.direction == pytest.approx((2.0, -3.0))
        return propose_heads(Baseline(), [Proposal(encoder, (encoder.constructor,))],
            lambda contract, values, targets, budget: [
                Proposal(fit_affine(contract, values, targets, cost=1))],
            train, labels, max_features=1, max_heads=1)

    result = discover(Baseline(), propose, rows, targets, lambda a, b: abs(a - b) < 1e-9)
    assert result.chosen is not None
    assert sum(result.trials[0].outcomes) == 200
    assert len(result.chosen.constructors) == 1
    assert observed == [(tuple(rows[:200]), tuple(targets[:200]))]


def test_regression_projection_finite_data_and_degenerate_design() -> None:
    from nca.projection_learning import fit_regression_projection

    fit = fit_regression_projection
    assert fit(Measurement(), [((1.0,),), ((2.0,),)], [1.0, 1.0], projection_cost=0) is None
    assert fit(Measurement(), [((),), ((),)], [1.0, 2.0], projection_cost=0) is None
    # Rank deficiency does not identify coefficients individually.
    model = fit(Measurement(), [((1.0, 1.0),), ((2.0, 2.0),)],
                [2.0, 4.0], projection_cost=0)
    assert model is not None and model.direction == pytest.approx((1.0, 1.0))
    with pytest.raises(ValueError, match="finite"):
        fit(Measurement(), [((1.0,),), ((2.0,),)], [1.0, float("nan")], projection_cost=0)
    with pytest.raises(ValueError, match="dimensions"):
        fit(Measurement(), [((1.0,),), ((2.0, 3.0),)], [1.0, 2.0], projection_cost=0)
    with pytest.raises(ValueError, match="aligned"):
        fit(Measurement(), [((1.0,),)], [], projection_cost=0)
    with pytest.raises(ValueError, match="arity"):
        fit(Measurement(), [(), ()], [1.0, 2.0], projection_cost=0)
    with pytest.raises(ValueError, match="cost"):
        fit(Measurement(), [((1.0,),), ((2.0,),)], [1.0, 2.0], projection_cost=-1)


def test_polynomial_growth_stops_when_training_feedback_is_explained() -> None:
    from nca.affine_learning import fit_affine
    from nca.discovery import Proposal
    from nca.interface_learning import propose_heads
    from nca.projection_learning import fit_polynomial_regression_features

    rng = random.Random(3645)
    rows = [((rng.uniform(-1, 1), rng.uniform(-1, 1)),) for _ in range(400)]
    targets = [1.7 * v[0] * v[1] - 0.4 * v[0] ** 2 + 0.2 for v, in rows]
    degrees = []

    def propose(train: Any, labels: Any) -> Any:
        features = fit_polynomial_regression_features(Measurement(), train, labels,
                    max_degree=5, max_terms=100, max_error=1e-9,
                    lifting_cost=1, projection_cost=1)
        degrees.extend(f.expert.measurement.degree for f in features)
        assert all(len(f.constructors) == 2 for f in features)
        return propose_heads(Baseline(), features,
            lambda contract, values, targets, budget: [
                Proposal(fit_affine(contract, values, targets, cost=1))],
            train, labels, max_features=5, max_heads=1)

    result = discover(Baseline(), propose, rows, targets, lambda a, b: abs(a - b) < 1e-9)
    assert degrees == [1, 2]
    assert result.chosen is not None and len(result.chosen.constructors) == 2
    assert [sum(t.outcomes) for t in result.trials] == [0, 200]


def test_polynomial_regression_growth_respects_structural_budgets() -> None:
    from nca.projection_learning import fit_polynomial_regression_features

    rows = [((x, y),) for x in (-1.0, 0.0, 1.0) for y in (-1.0, 0.0, 1.0)]
    targets = [x + x * y for (x, y), in rows]

    def fit(**kwargs: Any) -> Any:
        return fit_polynomial_regression_features(Measurement(), rows, targets,
                    max_error=0, lifting_cost=0, projection_cost=0, **kwargs)

    assert fit(max_degree=5, max_terms=1) == []
    assert [p.expert.measurement.degree for p in fit(max_degree=5, max_terms=2)] == [1]
    assert [p.expert.measurement.degree for p in fit(max_degree=1, max_terms=100)] == [1]
    with pytest.raises(ValueError, match="budgets"):
        fit(max_degree=0, max_terms=100)
    with pytest.raises(ValueError, match="tolerance"):
        fit_polynomial_regression_features(Measurement(), rows, targets,
                    max_degree=2, max_terms=10, max_error=float("nan"),
                    lifting_cost=0, projection_cost=0)
