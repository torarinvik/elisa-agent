"""Training failures acquire conditional experts without restricting target values."""

import random
from collections.abc import Callable, Sequence
from dataclasses import dataclass, replace
from typing import Any

import pytest

from nca.abi import Calls, Contract, Manifest
from nca.affine_learning import fit_affine
from nca.discovery import Proposal, discover
from nca.learning.regional import RegionalExpert, propose_regional_experts


@dataclass
class Expert:
    manifest: Manifest
    function: Callable[..., Any]

    def invoke(self, *values: Any) -> Any:
        return self.function(*values)


CONTRACT = Contract(("input",), "output")


def test_failures_acquire_continuous_specialist_on_training_region_only() -> None:
    incumbent = Expert(Manifest("incumbent", "1", CONTRACT), lambda x: x)
    feature = Expert(Manifest("feature", "1", replace(CONTRACT, output="key")), lambda x: x >= 0)
    rng = random.Random(3630)
    rows = [(rng.uniform(-1, 1),) for _ in range(1000)]
    targets = [x if x < 0 else 2 * x + 1 for x, in rows]
    seen = []

    def acquire(train: Sequence[tuple[Any, ...]], labels: Sequence[Any]) -> list[Proposal]:
        seen.append(tuple(train))
        return [Proposal(fit_affine(CONTRACT, [row[0] for row in train], labels, cost=1))]

    def propose(train: Sequence[tuple[Any, ...]], labels: Sequence[Any]) -> list[Proposal]:
        return propose_regional_experts(incumbent, feature, acquire, train, labels,
                    lambda a, b: abs(a - b) < 1e-9, max_regions=1, overhead_cost=0)

    result = discover(incumbent, propose, rows, targets, lambda a, b: abs(a - b) < 1e-9)
    assert seen == [tuple(row for row in rows[:500] if row[0] >= 0)]
    assert result.chosen is not None
    assert sum(result.trials[0].outcomes) == 500
    assert all(result.chosen.expert.invoke(x) == incumbent.invoke(x) for x in (-0.93, -0.17))


def test_region_budget_uses_error_count_and_keeps_successful_controls() -> None:
    incumbent = Expert(Manifest("incumbent", "1", CONTRACT), lambda x: [x[1]])
    feature = Expert(Manifest("feature", "1", replace(CONTRACT, output="key")), lambda x: x[0])
    rows = [(("a", 0),), (("a", 1),), (("b", 2),), (("b", 3),), (("b", 4),), (("c", 5),)]
    labels = [[0], [99], [88], [77], [4], [5]]  # Targets need not be hashable.
    seen = []

    def acquire(train: Any, targets: Any) -> list[Proposal]:
        seen.append((train, targets))
        return []

    assert propose_regional_experts(incumbent, feature, acquire, rows, labels,
                lambda a, b: a == b, max_regions=1, overhead_cost=0) == []
    assert seen == [(tuple(rows[2:5]), tuple(labels[2:5]))]
    seen.clear()
    propose_regional_experts(incumbent, feature, acquire, rows, [[x[0][1]] for x in rows],
                            lambda a, b: a == b, max_regions=1, overhead_cost=0)
    assert not seen


def test_regional_dispatch_preserves_slots_and_conservative_metadata() -> None:
    contract = replace(CONTRACT, slots=((("input",), "slot-output"),))
    invoked = []

    def branch(name: str) -> Callable[..., Any]:
        def invoke(*values: Any) -> str:
            invoked.append(name)
            return name
        return invoke

    incumbent = Expert(Manifest("a", "1", contract, cost=2, calls=(Calls(1, 2),),
                                effects=frozenset({"io"})), branch("incumbent"))
    specialist = Expert(Manifest("b", "1", contract, cost=5, calls=(Calls(3, 0),)),
                        branch("specialist"))
    feature = Expert(Manifest("f", "1", replace(contract, output="key"), cost=3,
                              calls=(Calls(0, 1),), effects=frozenset()), lambda slot, x: x)
    regional = RegionalExpert(incumbent, feature, True, specialist, 1)
    assert regional.invoke(None, False) == "incumbent"
    assert regional.invoke(None, True) == "specialist"
    assert invoked == ["incumbent", "specialist"]
    assert regional.manifest.contract == contract
    assert regional.manifest.cost == 11
    assert regional.manifest.calls == (Calls(4, 3),)
    assert regional.manifest.effects is None and regional.manifest.expected_calls is None
    with pytest.raises(ValueError, match="external contract"):
        RegionalExpert(incumbent, feature, True, feature, 0)


def test_failure_boundaries_are_learned_without_a_supplied_region() -> None:
    from nca.learning.numeric import midpoint_boundary
    from nca.learning.regional import propose_failure_partitions

    incumbent = Expert(Manifest("incumbent", "1", CONTRACT), lambda x: x)
    measurement = Expert(Manifest("measurement", "1", replace(CONTRACT, output="reading")),
                         lambda x: x)
    rng = random.Random(3631)
    rows = [(rng.uniform(-1, 1),) for _ in range(1000)]
    labels = [x if x < 0.23 else 2 * x + 0.7 for x, in rows]
    seen = []

    def acquire(train: Sequence[tuple[Any, ...]], targets: Sequence[Any]) -> list[Proposal]:
        seen.append((tuple(train), tuple(targets)))
        return [Proposal(fit_affine(CONTRACT, [r[0] for r in train], targets, cost=1))]

    def propose(train: Sequence[tuple[Any, ...]], targets: Sequence[Any]) -> list[Proposal]:
        return propose_failure_partitions(incumbent, [measurement], acquire, train, targets,
                    lambda a, b: abs(a - b) < 1e-9, max_measurements=1, max_regions=1,
                    encoding_cost=0, overhead_cost=0, place_boundary=midpoint_boundary)

    result = discover(incumbent, propose, rows, labels, lambda a, b: abs(a - b) < 1e-9)
    assert result.chosen is not None
    regional = result.chosen.expert
    boundary = regional.feature.boundary
    assert abs(boundary - 0.23) < 0.01
    expected = [(r, y) for r, y in zip(rows[:500], labels[:500]) if r[0] >= boundary]
    assert seen == [(tuple(r for r, _ in expected), tuple(y for _, y in expected))]
    assert result.chosen.constructors == (regional.feature.constructor,)
    assert regional.feature.manifest.contract.output == result.chosen.constructors[0].type()
    assert sum(result.trials[0].outcomes) >= 495


def test_failure_partition_degenerate_signal_and_measurement_budget() -> None:
    from nca.learning.regional import propose_failure_partitions

    incumbent = Expert(Manifest("incumbent", "1", CONTRACT), lambda x: x)
    contract = replace(CONTRACT, output="reading")
    unusable = Expert(Manifest("unusable", "1", contract),
                       lambda x: pytest.fail("measurement was outside the search budget"))
    constant = Expert(Manifest("constant", "1", contract), lambda x: 0.0)
    rows = [(-1.0,), (1.0,)]
    kwargs = dict(max_measurements=1, max_regions=1, encoding_cost=0, overhead_cost=0)

    def acquire(train: Any, targets: Any) -> list[Proposal]:
        pytest.fail("no usable routing cut should train an expert")

    assert propose_failure_partitions(incumbent, [unusable], acquire, rows, [-1.0, 1.0],
                                      lambda a, b: a == b, **kwargs) == []
    assert propose_failure_partitions(incumbent, [unusable], acquire, rows, [0.0, 0.0],
                                      lambda a, b: a == b, **kwargs) == []
    assert propose_failure_partitions(incumbent, [constant, unusable], acquire, rows, [-1.0, 3.0],
                                      lambda a, b: a == b, **kwargs) == []


def test_multi_interval_failure_routing_isolates_an_interior_specialist() -> None:
    from nca.learning.numeric import midpoint_boundary, purity_tiebreak
    from nca.learning.regional import propose_failure_partitions

    incumbent = Expert(Manifest("incumbent", "1", CONTRACT), lambda x: x)
    measurement = Expert(Manifest("measurement", "1", replace(CONTRACT, output="reading")),
                         lambda x: x)
    rows = [(i / 100,) for i in range(-100, 101)]
    labels = [2 * x + 0.7 if -0.25 <= x < 0.35 else x for x, in rows]
    seen = []

    def acquire(train: Sequence[tuple[Any, ...]], targets: Sequence[Any]) -> list[Proposal]:
        seen.append(tuple(train))
        return [Proposal(fit_affine(CONTRACT, [r[0] for r in train], targets, cost=1))]

    proposals = propose_failure_partitions(incumbent, [measurement], acquire, rows, labels,
                    lambda a, b: abs(a - b) < 1e-9, max_measurements=1, max_regions=1,
                    encoding_cost=0, overhead_cost=0, place_boundary=midpoint_boundary,
                    routing_regions=3, tie_break=purity_tiebreak)
    assert len(proposals) == 1
    regional = proposals[0].expert
    assert seen == [tuple(row for row in rows if -0.25 <= row[0] < 0.35)]
    assert len(regional.feature.boundaries) == 2
    assert regional.invoke(-0.7) == -0.7 and regional.invoke(0.9) == 0.9
    assert regional.invoke(0.1) == pytest.approx(0.9)


def test_combined_specialists_cover_disjoint_regions_with_one_routing_read() -> None:
    from nca.learning.numeric import midpoint_boundary, purity_tiebreak
    from nca.learning.regional import RegionalPolicy, propose_failure_partitions

    incumbent = Expert(Manifest("incumbent", "1", CONTRACT), lambda x: x)
    reads = []

    def read(x: float) -> float:
        reads.append(x)
        return x

    measurement = Expert(Manifest("reading", "1", replace(CONTRACT, output="reading")), read)
    rows = [(i / 100,) for i in range(-100, 101)]
    labels = [2 * x - 1 if x < -0.3 else 2 * x + 1 if x >= 0.4 else x for x, in rows]

    def acquire(train: Any, targets: Any) -> list[Proposal]:
        return [Proposal(fit_affine(CONTRACT, [r[0] for r in train], targets, cost=1))]

    proposals = propose_failure_partitions(incumbent, [measurement], acquire, rows, labels,
                lambda a, b: abs(a - b) < 1e-9, max_measurements=1, max_regions=2,
                routing_regions=3, encoding_cost=0, overhead_cost=0,
                place_boundary=midpoint_boundary, tie_break=purity_tiebreak, max_combinations=1)
    assert len(proposals) == 3
    combined = proposals[-1].expert
    assert isinstance(combined, RegionalPolicy) and len(combined.specialists) == 2
    for x, target in [(-0.9, -2.8), (0.2, 0.2), (0.8, 2.6)]:
        reads.clear()
        assert combined.invoke(x) == pytest.approx(target)
        assert reads == [x]
    assert len(proposals[-1].constructors) == 1


def test_combination_budget_limits_cartesian_prefix() -> None:
    incumbent = Expert(Manifest("incumbent", "1", CONTRACT), lambda x: 0)
    feature = Expert(Manifest("feature", "1", replace(CONTRACT, output="key")), lambda x: x >= 0)

    def acquire(train: Any, targets: Any) -> list[Proposal]:
        return [Proposal(Expert(Manifest(f"alternative-{i}", "1", CONTRACT),
                                lambda x, value=targets[0] + i: value)) for i in range(2)]

    proposals = propose_regional_experts(incumbent, feature, acquire,
                [(-2,), (-1,), (1,), (2,)], [1, 1, 2, 2], lambda a, b: a == b,
                max_regions=2, overhead_cost=0, max_combinations=2)
    assert len(proposals) == 6  # Four singles plus two of four possible combinations.
    assert [proposals[-2].expert.invoke(x) for x in (-1, 1)] == [1, 2]
    assert [proposals[-1].expert.invoke(x) for x in (-1, 1)] == [1, 3]


def test_ranked_product_matches_exhaustive_small_family_order() -> None:
    from itertools import product

    from nca.learning.regional import _ranked_combinations

    families = []
    for axis, values in enumerate([[(8, 1.0), (5, 0.5)],
                                   [(7, 2.0), (7, 3.0), (2, 0.0)],
                                   [(4, 0.0), (1, 2.0)]]):
        families.append([(score, Proposal(Expert(Manifest(f"{axis}-{i}", "1", CONTRACT, cost=cost),
                                                 lambda x: x)))
                         for i, (score, cost) in enumerate(values)])
    for family in families:
        family.append((0, None))
    positions = list(product(*(range(len(family)) for family in families)))
    positions.sort(key=lambda indices: (
        -sum(families[i][j][0] for i, j in enumerate(indices)),
        sum(0.0 if families[i][j][1] is None else families[i][j][1].expert.manifest.cost
            for i, j in enumerate(indices)), indices))
    expected = [tuple(families[i][j][1] for i, j in enumerate(indices)) for indices in positions]
    assert list(_ranked_combinations(families, 100)) == expected
    assert list(_ranked_combinations(families, 3)) == expected[:3]
    assert list(_ranked_combinations([], 3)) == []


def test_combination_budget_prefers_training_supported_choices_over_trainer_order() -> None:
    incumbent = Expert(Manifest("incumbent", "1", CONTRACT), lambda x: 0)
    feature = Expert(Manifest("feature", "1", replace(CONTRACT, output="key")), lambda x: x >= 0)
    seen = []

    def acquire(train: Any, targets: Any) -> list[Proposal]:
        seen.append(tuple(targets))
        good = Expert(Manifest("good", "1", CONTRACT), lambda x, value=targets[0]: value)
        return [Proposal(incumbent), Proposal(good)]

    proposals = propose_regional_experts(incumbent, feature, acquire,
                [(-2,), (-1,), (1,), (2,)], [1, 1, 2, 2], lambda a, b: a == b,
                max_regions=2, overhead_cost=0, max_combinations=1)
    assert seen == [(1, 1), (2, 2)]
    assert len(proposals) == 5
    assert [proposals[-1].expert.invoke(x) for x in (-3, 3)] == [1, 2]


def test_partial_composition_leaves_a_harmful_region_with_incumbent() -> None:
    incumbent = Expert(Manifest("incumbent", "1", CONTRACT), lambda x: x[1])
    feature = Expert(Manifest("feature", "1", replace(CONTRACT, output="key")), lambda x: x[0])
    rows = [(("a", 0),), (("a", 1),), (("b", 2),), (("b", 3),),
            (("c", 4),), (("c", 5),), (("c", 6),), (("c", 7),)]
    labels = [10, 10, 20, 20, 4, 5, 6, 99]

    def acquire(train: Any, targets: Any) -> list[Proposal]:
        model = Expert(Manifest("constant", "1", CONTRACT), lambda x, value=targets[0]: value)
        return [Proposal(model)]

    proposals = propose_regional_experts(incumbent, feature, acquire, rows, labels,
                lambda a, b: a == b, max_regions=3, overhead_cost=0, max_combinations=1)
    assert len(proposals) == 4
    combined = proposals[-1].expert
    assert set(combined.specialists) == {"a", "b"}
    assert sum(combined.invoke(*r) == y for r, y in zip(rows, labels)) == 7
    assert combined.invoke(("c", 8)) == 8
    assert combined.manifest.cost == 4


def test_fallback_only_assignments_do_not_emit_duplicate_joint_candidates() -> None:
    incumbent = Expert(Manifest("incumbent", "1", CONTRACT), lambda x: 0)
    feature = Expert(Manifest("feature", "1", replace(CONTRACT, output="key")), lambda x: x >= 0)
    proposals = propose_regional_experts(incumbent, feature, lambda rows, targets: [Proposal(incumbent)],
                [(-1,), (1,)], [1, 2], lambda a, b: a == b,
                max_regions=2, overhead_cost=0, max_combinations=100)
    assert len(proposals) == 2


def test_skipped_baseline_and_singles_do_not_consume_joint_output_budget() -> None:
    incumbent = Expert(Manifest("incumbent", "1", CONTRACT), lambda x: 0)
    feature = Expert(Manifest("feature", "1", replace(CONTRACT, output="key")), lambda x: x[0])
    bad = Expert(Manifest("bad", "1", CONTRACT), lambda x: 2)
    rows = [((key, i),) for key in ("a", "b") for i in range(3)]
    proposals = propose_regional_experts(incumbent, feature, lambda rows, labels: [Proposal(bad)],
                rows, [0, 0, 1] * 2, lambda a, b: a == b,
                max_regions=2, overhead_cost=0, max_combinations=1)
    assert len(proposals) == 3
    assert set(proposals[-1].expert.specialists) == {"a", "b"}
    assert proposals[-1].expert.invoke(("a", 10)) == 2


def test_refinement_targets_only_the_unsolved_region_with_its_best_seed() -> None:
    from nca.learning.numeric import midpoint_boundary
    from nca.learning.regional import propose_failure_partitions

    incumbent = Expert(Manifest("incumbent", "1", CONTRACT), lambda x: x)
    feature = Expert(Manifest("coarse", "1", replace(CONTRACT, output="region")),
                     lambda x: 0 if x < -0.33 else 1 if x < 0.33 else 2)
    reading = Expert(Manifest("reading", "1", replace(CONTRACT, output="reading")), lambda x: x)
    rows = [(i / 100,) for i in range(-100, 101)]
    labels = [2 * x - 1 if x < -0.33 else 2 * x + 1 if x < 0.33
              else 3 * x + 1 if x >= 0.9 else x for x, in rows]
    refined = []

    def acquire(train: Any, targets: Any) -> list[Proposal]:
        return [Proposal(fit_affine(CONTRACT, [r[0] for r in train], targets, cost=1))]

    def refine(seed: Any, train: Any, targets: Any) -> list[Proposal]:
        refined.append((seed, tuple(train), tuple(targets)))
        return propose_failure_partitions(seed, [reading], acquire, train, targets,
                    lambda a, b: abs(a - b) < 1e-9, max_measurements=1, max_regions=1,
                    encoding_cost=0, overhead_cost=0, place_boundary=midpoint_boundary)

    proposals = propose_regional_experts(incumbent, feature, acquire, rows, labels,
                lambda a, b: abs(a - b) < 1e-9, max_regions=3, overhead_cost=0,
                max_combinations=1, refine=refine, max_refinements=1)
    expected = [(r, y) for r, y in zip(rows, labels) if r[0] >= 0.33]
    assert refined == [(incumbent, tuple(r for r, _ in expected), tuple(y for _, y in expected))]
    model = proposals[-1].expert
    inner = model.specialists[2]
    assert abs(inner.feature.boundary - 0.9) < 0.01
    assert model.invoke(0.5) == 0.5
    assert model.invoke(0.95) == pytest.approx(3.85)
    assert model.invoke(-0.8) == pytest.approx(-2.6)
    assert len(proposals[-1].constructors) == 1


def test_refinement_budget_applies_even_without_direct_alternatives() -> None:
    incumbent = Expert(Manifest("incumbent", "1", CONTRACT), lambda x: 0)
    feature = Expert(Manifest("feature", "1", replace(CONTRACT, output="key")), lambda x: x)
    seen = []

    def refine(seed: Any, rows: Any, labels: Any) -> list[Proposal]:
        seen.append((seed, tuple(rows), tuple(labels)))
        return [Proposal(Expert(Manifest("replacement", "1", CONTRACT), lambda x: 1))]

    proposals = propose_regional_experts(incumbent, feature, lambda rows, labels: [],
                [(0,), (1,), (2,)], [1, 1, 1], lambda a, b: a == b,
                max_regions=3, overhead_cost=0, refine=refine, max_refinements=1)
    assert seen == [(incumbent, ((0,),), (1,))]
    assert len(proposals) == 1
    with pytest.raises(ValueError, match="requires a refiner"):
        propose_regional_experts(incumbent, feature, lambda rows, labels: [],
                                [(0,)], [1], lambda a, b: a == b,
                                max_regions=1, overhead_cost=0, max_refinements=1)


def test_refined_proposals_carry_seed_and_new_constructor_declarations() -> None:
    from nca.learning.numeric import midpoint_boundary, propose_partition
    from nca.learning.regional import propose_failure_partitions

    incumbent = Expert(Manifest("incumbent", "1", CONTRACT), lambda x: 0)
    feature = Expert(Manifest("coarse", "1", replace(CONTRACT, output="key")), lambda x: 0)
    reading = Expert(Manifest("reading", "1", replace(CONTRACT, output="reading")), lambda x: x)
    rows, labels = [(-2.0,), (-1.0,), (1.0,), (2.0,)], [1, 1, 2, 3]
    seeds = []

    def acquire(train: Any, targets: Any) -> list[Proposal]:
        return propose_partition(incumbent, reading, train, targets, encoding_cost=0, decoder_cost=1)

    def refine(seed: Any, train: Any, targets: Any) -> list[Proposal]:
        seeds.append(seed)
        return propose_failure_partitions(seed, [reading],
                    lambda rows, labels: [Proposal(Expert(Manifest("leaf", "1", CONTRACT),
                                                          lambda x: labels[0]))],
                    train, targets, lambda a, b: a == b, max_measurements=1, max_regions=1,
                    encoding_cost=0, overhead_cost=0, place_boundary=midpoint_boundary)

    proposals = propose_regional_experts(incumbent, feature, acquire, rows, labels,
                lambda a, b: a == b, max_regions=1, overhead_cost=0,
                refine=refine, max_refinements=1)
    assert len(seeds) == 1 and seeds[0] is not incumbent
    assert len(proposals[-1].constructors) == 2
    assert proposals[-1].constructors[0] == seeds[0].feature.constructor
    assert [proposals[-1].expert.invoke(*r) for r in rows] == labels


def test_learned_failure_routing_forwards_the_refinement_budget() -> None:
    from nca.learning.numeric import midpoint_boundary
    from nca.learning.regional import propose_failure_partitions

    incumbent = Expert(Manifest("incumbent", "1", CONTRACT), lambda x: 0)
    reading = Expert(Manifest("reading", "1", replace(CONTRACT, output="reading")), lambda x: x)
    seen = []

    def refine(seed: Any, rows: Any, targets: Any) -> list[Proposal]:
        seen.append((seed, tuple(rows), tuple(targets)))
        return [Proposal(Expert(Manifest("replacement", "1", CONTRACT), lambda x: 1))]

    proposals = propose_failure_partitions(incumbent, [reading], lambda rows, labels: [],
                [(-2.0,), (-1.0,), (1.0,), (2.0,)], [0, 0, 1, 1], lambda a, b: a == b,
                max_measurements=1, max_regions=1, encoding_cost=0, overhead_cost=0,
                place_boundary=midpoint_boundary, refine=refine, max_refinements=1)
    assert seen == [(incumbent, ((1.0,), (2.0,)), (1, 1))]
    assert len(proposals) == 1 and proposals[0].expert.invoke(0.5) == 1


def test_auxiliary_feedback_bootstraps_an_all_wrong_incumbent() -> None:
    from nca.learning.numeric import midpoint_boundary
    from nca.learning.regional import propose_failure_partitions

    incumbent = Expert(Manifest("incumbent", "1", CONTRACT), lambda x: 0.0)
    reading = Expert(Manifest("reading", "1", replace(CONTRACT, output="reading")), lambda x: x)
    rows = [(x / 100,) for x in range(-100, 101)]
    random.Random(3639).shuffle(rows)
    labels = [2 * x - 3 if x < 0.13 else 3 * x + 2 for x, in rows]
    feedback, trained = [], []

    def signal(row: tuple[Any, ...], prediction: Any, target: Any) -> Any:
        feedback.append((row, prediction, target))
        return frozenset({prediction < target})

    def acquire(train: Any, targets: Any) -> list[Proposal]:
        trained.extend(zip(train, targets, strict=True))
        return [Proposal(fit_affine(CONTRACT, [r[0] for r in train], targets, cost=1))]

    def propose(train: Any, targets: Any, auxiliary: bool = True) -> list[Proposal]:
        return propose_failure_partitions(incumbent, [reading], acquire, train, targets,
                    lambda a, b: abs(a - b) < 1e-9, max_measurements=1, max_regions=2,
                    encoding_cost=0, overhead_cost=0, place_boundary=midpoint_boundary,
                    max_combinations=1, routing_signal=signal if auxiliary else None)

    assert propose(rows, labels, False) == []
    chosen = discover(incumbent, propose, rows, labels, lambda a, b: abs(a - b) < 1e-9)
    assert chosen.chosen is not None
    n = len(rows) // 2
    assert feedback == [(row, 0.0, target) for row, target in zip(rows[:n], labels[:n])]
    assert sorted(trained) == sorted(zip(rows[:n], labels[:n], strict=True))
    assert chosen.chosen.constructors
    assert abs(chosen.chosen.expert.invoke(-0.5) + 4) < 1e-9
    assert abs(chosen.chosen.expert.invoke(0.5) - 3.5) < 1e-9
    assert len(feedback) == n


def test_auxiliary_feedback_does_not_acquire_for_a_perfect_incumbent() -> None:
    from nca.learning.regional import propose_failure_partitions

    incumbent = Expert(Manifest("identity", "1", CONTRACT), lambda x: x)
    seen = []
    result = propose_failure_partitions(incumbent, [incumbent],
                lambda rows, targets: pytest.fail("perfect incumbent must not train"),
                [(-1.0,), (1.0,)], [-1.0, 1.0], lambda a, b: a == b,
                max_measurements=1, max_regions=2, encoding_cost=0, overhead_cost=0,
                routing_signal=lambda row, prediction, target: seen.append(row) or row)
    assert result == [] and seen == [(-1.0,), (1.0,)]


def test_router_screening_spends_specialist_budget_on_training_signal() -> None:
    from nca.learning.numeric import midpoint_boundary
    from nca.learning.regional import propose_failure_partitions

    incumbent = Expert(Manifest("incumbent", "1", CONTRACT), lambda xy: 0.0)
    reading_contract = replace(CONTRACT, output="reading")
    irrelevant = Expert(Manifest("irrelevant", "1", reading_contract), lambda xy: xy[1])
    useful = Expert(Manifest("useful", "1", reading_contract), lambda xy: xy[0])
    rng = random.Random(3640)
    rows = [((rng.uniform(-1, 1), rng.uniform(-1, 1)),) for _ in range(400)]
    labels = [2 * xy[0] - 3 if xy[0] < 0.13 else 3 * xy[0] + 2 for xy, in rows]
    seen = []

    def acquire(train: Any, targets: Any) -> list[Proposal]:
        seen.append((tuple(train), tuple(targets)))
        model = fit_affine(CONTRACT, [row[0][0] for row in train], targets, cost=1)
        return [Proposal(Expert(model.manifest, lambda xy: model.invoke(xy[0])))]

    proposals = propose_failure_partitions(incumbent, [irrelevant, useful], acquire,
                rows, labels, lambda a, b: abs(a - b) < 1e-9,
                max_measurements=1, max_measurement_candidates=2, max_regions=2,
                encoding_cost=0, overhead_cost=0, max_combinations=1,
                place_boundary=midpoint_boundary,
                routing_signal=lambda row, prediction, target: prediction < target)
    assert len(seen) == 2
    assert sorted(pair for train, targets in seen for pair in zip(train, targets, strict=True)) == (
        sorted(zip(rows, labels, strict=True)))
    assert len(proposals) == 3
    assert all(p.expert.feature.measurement is useful for p in proposals)
    assert abs(proposals[-1].expert.invoke((-0.5, 0.2)) + 4) < 1e-9
    assert abs(proposals[-1].expert.invoke((0.5, -0.2)) - 3.5) < 1e-9

    seen.clear()
    duplicate = Expert(Manifest("duplicate", "1", reading_contract), lambda xy: xy[0])
    tied = propose_failure_partitions(incumbent, [useful, duplicate], acquire, rows, labels,
                lambda a, b: abs(a - b) < 1e-9, max_measurements=1,
                max_measurement_candidates=2, max_regions=2, encoding_cost=0, overhead_cost=0,
                routing_signal=lambda row, prediction, target: prediction < target)
    assert len(tied) == len(seen) == 2
    assert all(p.expert.feature.measurement is useful for p in tied)
    with pytest.raises(ValueError, match="candidate budget"):
        propose_failure_partitions(incumbent, [], acquire, rows, labels,
                    lambda a, b: a == b, max_measurements=1, max_regions=1,
                    max_measurement_candidates=0, encoding_cost=0, overhead_cost=0)


def test_measurement_acquisition_budget_and_degenerate_feedback() -> None:
    from nca.objects import Constructor
    from nca.learning.regional import propose_failure_partitions

    incumbent = Expert(Manifest("incumbent", "1", CONTRACT), lambda x: 0)
    reading = Expert(Manifest("reading", "1", replace(CONTRACT, output="reading")), lambda x: x)
    constructor = Constructor("auxiliary", "1", 0, "hypothetical learned measurement")
    calls = []

    def learn(rows: Any, signals: Any, budget: int) -> list[Proposal]:
        calls.append((rows, signals, budget))
        # Extra outputs must not consume extra fitting or specialist calls.
        invalid = Expert(Manifest("invalid", "1", Contract((), "reading")), lambda: 1.0)
        return [Proposal(reading, (constructor,)), Proposal(invalid)]

    def run(labels: Any, measurements: Any = (), **kwargs: Any) -> Any:
        return propose_failure_partitions(incumbent, measurements,
                    lambda rows, targets: [Proposal(incumbent)],
                    [(-1.0,), (1.0,)], labels, lambda a, b: a == b,
                    max_measurements=1, max_regions=1, encoding_cost=0, overhead_cost=0,
                    propose_measurements=learn, **kwargs)

    proposals = run([0, 1])
    assert calls == [(((-1.0,), (1.0,)), (False, True), 1)]
    assert len(proposals) == 1 and proposals[0].constructors[0] == constructor
    calls.clear()
    assert run([0, 0]) == []
    assert run([0, 0], routing_signal=lambda row, prediction, target: row) == []
    assert run([1, 1]) == []
    run([0, 1], [reading])
    assert calls == []
    invalid = Expert(Manifest("invalid", "1", Contract((), "reading")), lambda: 1.0)
    with pytest.raises(ValueError, match="learned measurements"):
        propose_failure_partitions(incumbent, [], lambda rows, labels: [],
                    [(-1.0,), (1.0,)], [0, 1], lambda a, b: a == b,
                    max_measurements=1, max_regions=1, encoding_cost=0, overhead_cost=0,
                    propose_measurements=lambda rows, signals, budget: [Proposal(invalid)])
