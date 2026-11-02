"""Paired observations can connect distinct interfaces without type aliasing."""

from collections.abc import Sequence
from dataclasses import replace
from pathlib import Path
from typing import Any

import pytest

from nca.abi import Contract, Manifest, Message
from nca.discovery import Decoder, Decoded, Proposal, decoder_object, discover
from nca.interface_learning import propose_adapter
from nca.loader import ExpertStore
from nca.objects import Primitive, Store, contract_data
from nca.packages import install
from nca.planner import plan_stable
from nca.runtime import execute
from nca.workspace import Workspace


class Source:
    manifest = Manifest("source", "1", Contract(("input",), "interface-a"), effects=frozenset())

    def invoke(self, value: int) -> str:
        return f"code-{value % 4}"


class Teacher:
    manifest = Manifest("teacher", "1", Contract(("input",), "interface-b"), effects=frozenset())

    def __init__(self) -> None:
        self.calls = 0

    def invoke(self, value: int) -> int:
        self.calls += 1
        return (2, 0, 3, 1)[value % 4]


class Consumer:
    manifest = Manifest("consumer", "1", Contract(("interface-b",), "output"), effects=frozenset({"read"}))

    def invoke(self, value: int) -> str:
        return ("result-1", "result-3", "result-0", "result-2")[value]


class Baseline:
    manifest = Manifest("baseline", "1", Contract(("input",), "output"))

    def invoke(self, value: int) -> str:
        return "constant"


def test_acquired_adapter_enables_typed_route_without_evaluation_teacher_calls() -> None:
    source, teacher, consumer = Source(), Teacher(), Consumer()
    assert plan_stable([source, consumer], ("input",), "output") is None
    rows = [(i,) for i in range(200)]
    labels = [f"result-{i % 4}" for i in range(200)]

    def propose(train: Sequence[tuple[Any, ...]], targets: Sequence[Any]) -> list[Proposal]:
        return [propose_adapter(Baseline(), source, teacher, consumer, train, decoder_cost=1)]

    result = discover(Baseline(), propose, rows, labels, lambda a, b: a == b)
    assert result.chosen is not None and teacher.calls == 100
    assert sum(result.trials[0].outcomes) == 100
    chain = result.chosen.expert
    assert isinstance(chain, Decoded) and isinstance(chain.feature, Decoded)
    adapter = chain.feature.decoder
    assert adapter.manifest.contract == Contract(("interface-a",), "interface-b")
    assert chain.manifest.effects == frozenset({"read"})
    route = plan_stable([source, adapter, consumer], ("input",), "output")
    assert route is not None
    assert execute(route, {"input": Message("input", 7, "input")}, Workspace(), 10).payload == "result-3"
    assert teacher.calls == 100
    teacher.manifest = replace(teacher.manifest, contract=Contract(("wrong",), "interface-b"))
    with pytest.raises(ValueError, match="preserve external"):
        propose_adapter(Baseline(), source, teacher, consumer, rows, decoder_cost=1)


def test_distinct_stored_bridges_coexist_and_legacy_heads_load(tmp_path: Path) -> None:
    contract = Contract(("a",), "b")
    first = Decoder(contract, {"key": "one"}, "fallback", 1)
    second = Decoder(contract, {"key": "two"}, "fallback", 1)
    store = Store()
    refs = [store.put(decoder_object(head, size=16)) for head in (first, second)]
    store.save(tmp_path)
    reopened, resident = Store.open(tmp_path), ExpertStore()
    experts = [install(reopened, ref, experts=resident)[0] for ref in refs]
    assert [expert.invoke("key") for expert in experts] == ["one", "two"]
    assert resident.stats.loads == 2
    legacy = Primitive(first.manifest, "nca.discovery:_load_decoder",
                       {"contract": contract_data(contract), "table": [["key", "one"]],
                        "fallback": "fallback", "cost": 1})
    assert legacy.load().invoke("key") == "one"


def test_acquire_continuous_heads_on_typed_representations() -> None:
    import random

    from nca.affine_learning import fit_affine
    from nca.interface_learning import propose_heads
    from nca.objects import Constructor

    class Feature:
        def __init__(self, square: bool) -> None:
            self.square = square
            self.constructor = Constructor("candidate", "1", 0, str(square))
            self.manifest = Manifest("feature", "1",
                Contract(("input",), self.constructor.type()), effects=frozenset())

        def invoke(self, value: float) -> float:
            return value * value if self.square else value

    baseline = Feature(False)
    baseline.manifest = replace(baseline.manifest, contract=Contract(("input",), "result"))
    features = [Feature(False), Feature(True)]
    rng = random.Random(3643)
    rows = [(rng.uniform(-1, 1),) for _ in range(400)]
    labels = [2.3 * x * x - 0.7 for x, in rows]
    seen = []

    def fit(contract: Any, observations: Any, targets: Any, budget: int) -> Any:
        seen.append((contract, observations, targets, budget))
        return [Proposal(fit_affine(contract, observations, targets, cost=1))]

    def propose(train: Any, targets: Any) -> Any:
        return propose_heads(baseline, [Proposal(f, (f.constructor,)) for f in features],
                             fit, train, targets, max_features=2, max_heads=1)

    result = discover(baseline, propose, rows, labels, lambda a, b: abs(a - b) < 1e-9)
    assert result.chosen is not None and sum(result.trials[-1].outcomes) == 200
    assert result.chosen.expert.feature is features[1]
    assert result.chosen.constructors == (features[1].constructor,)
    assert len(seen) == 2
    for feature, (contract, observations, targets, budget) in zip(features, seen, strict=True):
        assert contract == Contract((feature.manifest.contract.output,), "result")
        assert observations == tuple(feature.invoke(*row) for row in rows[:200])
        assert targets == tuple(labels[:200]) and budget == 1


def test_head_acquisition_bounds_and_contract_validation() -> None:
    from nca.interface_learning import propose_heads

    feature = Source()
    baseline = Consumer()
    # Use a neutral external signature matching Source, with Consumer's output.
    baseline.manifest = replace(feature.manifest, contract=Contract(("input",), "output"))
    seen = []

    def fit(contract: Any, observations: Any, targets: Any, budget: int) -> Any:
        seen.append(targets)
        good = Decoder(contract, {"code-1": targets[0]}, targets[0], 0)
        bad = Decoder(Contract(("wrong",), "output"), {}, None, 0)
        return [Proposal(good), Proposal(bad)]

    targets = [{"payload": [1, 2]}]
    result = propose_heads(baseline, [Proposal(feature)], fit, [(1,)], targets,
                           max_features=1, max_heads=1)
    assert result[0].expert.invoke(1) == targets[0] and seen == [tuple(targets)]
    with pytest.raises(ValueError, match="unary contract"):
        propose_heads(baseline, [Proposal(feature)], fit, [(1,)], targets,
                       max_features=1, max_heads=2)
    with pytest.raises(ValueError, match="budgets"):
        propose_heads(baseline, [], fit, [(1,)], targets, max_features=0, max_heads=1)


def test_head_failures_trigger_training_only_feature_refinement() -> None:
    import random

    from nca.affine_learning import fit_affine
    from nca.interface_learning import propose_heads
    from nca.projection_learning import (ProjectionEncoder,
                                         fit_polynomial_regression_features)

    class Vector:
        manifest = Manifest("vector", "1", Contract(("input",), "vector"), effects=frozenset())

        def invoke(self, value: Any) -> Any:
            return value

    source = Vector()
    linear = ProjectionEncoder(source, (1.0, 0.0), 0)
    feature = Proposal(linear, (linear.constructor,))
    rng = random.Random(3647)
    rows = [((rng.uniform(-1, 1), rng.uniform(-1, 1)),) for _ in range(400)]
    targets = [1.7 * x * y - 0.4 * x * x + 0.2 for (x, y), in rows]
    seen = []

    def refine(seed: Any, head: Any, train: Any, labels: Any, budget: int) -> Any:
        seen.append((seed, head, train, labels, budget))
        return fit_polynomial_regression_features(source, train, labels,
                    max_degree=budget, max_terms=100, max_error=1e-9,
                    lifting_cost=0, projection_cost=0, reuse_observations=True)

    def correct(a: Any, b: Any) -> bool:
        return isinstance(a, float) and abs(a - b) < 1e-9

    def propose(train: Any, labels: Any) -> Any:
        return propose_heads(Baseline(), [feature],
            lambda contract, values, targets, budget: [
                Proposal(fit_affine(contract, values, targets, cost=1))],
            train, labels, max_features=3, max_heads=1, refine=refine,
            max_refinements=1, correct=correct)

    result = discover(Baseline(), propose, rows, targets, correct)
    assert result.chosen is not None and sum(result.trials[-1].outcomes) == 200
    assert len(result.trials) == 3 and len(result.chosen.constructors) == 2
    assert len(seen) == 1
    seed, head, train, labels, budget = seen[0]
    assert seed is feature and head is result.trials[0].proposal.expert.decoder
    assert train == tuple(rows[:200]) and labels == tuple(targets[:200]) and budget == 2


def test_feature_refinement_skips_solved_and_exhausted_searches() -> None:
    from nca.interface_learning import propose_heads

    def fit(contract: Any, values: Any, targets: Any, budget: int) -> Any:
        return [Proposal(Decoder(contract, {values[0]: targets[0]}, targets[0], 0))]

    def never(*args: Any) -> Any:
        pytest.fail("refinement must be skipped")

    for slots, calls, labels, correct in [(2, 1, [1], lambda a, b: a == b),
                                           (1, 1, [1], lambda a, b: False),
                                           (2, 0, [1], lambda a, b: False)]:
        result = propose_heads(Baseline(), [Proposal(Source())], fit, [(1,)], labels,
                    max_features=slots, max_heads=1, refine=never,
                    max_refinements=calls, correct=correct)
        assert len(result) == 1


def test_feature_refinement_bootstraps_empty_head_families_with_total_budget() -> None:
    from nca.interface_learning import propose_heads

    seen, fitted = [], []
    source = Source()

    def fit(contract: Any, values: Any, targets: Any, budget: int) -> Any:
        fitted.append(contract)
        return []

    def refine(seed: Any, head: Any, rows: Any, labels: Any, budget: int) -> Any:
        seen.append((head, budget))
        return [Proposal(source)] * 10

    result = propose_heads(Baseline(), [Proposal(source)], fit, [(1,)], [1],
                max_features=3, max_heads=1, refine=refine, max_refinements=10,
                correct=lambda a, b: False)
    assert result == [] and seen == [(None, 2)] and len(fitted) == 3
    with pytest.raises(ValueError, match="requires"):
        propose_heads(Baseline(), [Proposal(source)], fit, [(1,)], [1],
                      max_features=3, max_heads=1, max_refinements=1)
    with pytest.raises(ValueError, match="refinement budget"):
        propose_heads(Baseline(), [], fit, [(1,)], [1], max_features=1,
                      max_heads=1, max_refinements=-1)
    with pytest.raises(ValueError, match="refined features"):
        propose_heads(Baseline(), [Proposal(source)], fit, [(1,)], [1],
                      max_features=3, max_heads=1, max_refinements=1,
                      correct=lambda a, b: False,
                      refine=lambda *args: [Proposal(Consumer())])


def test_joint_refiner_learns_an_informative_companion_from_training_ambiguity() -> None:
    import random

    from nca.discovery import fit_decoder
    from nca.interface_learning import propose_heads, propose_joint_refinements
    from nca.objects import Constructor

    class Feature:
        def __init__(self, index: int) -> None:
            self.index = index
            self.constructor = Constructor("feature", "1", 0, str(index))
            self.manifest = Manifest(f"feature-{index}", "1",
                                     Contract(("input",), self.constructor.type()))

        def invoke(self, value: Any) -> Any:
            return value[self.index]

    left, right, noise = (Feature(i) for i in range(3))
    seed = Proposal(left, (left.constructor,))
    companions = [Proposal(f, (f.constructor,)) for f in (noise, right)]
    rng = random.Random(3648)
    rows = [(tuple(rng.randrange(4) for _ in range(3)),) for _ in range(800)]
    labels = [f"label-{(a + b) % 4}" for (a, b, _), in rows]
    seen = []

    def refine(feature: Any, head: Any, train: Any, targets: Any, budget: int) -> Any:
        seen.append((tuple(train), tuple(targets), budget))
        return propose_joint_refinements(feature, companions, train, targets,
                                          max_candidates=2, limit=budget, pair_cost=1)

    def propose(train: Any, targets: Any) -> Any:
        return propose_heads(Baseline(), [seed],
                    lambda c, v, t, b: [Proposal(fit_decoder(c, v, t, cost=1))],
                    train, targets, max_features=2, max_heads=1, refine=refine,
                    max_refinements=1, correct=lambda a, b: a == b)

    result = discover(Baseline(), propose, rows, labels, lambda a, b: a == b)
    assert result.chosen is not None and sum(result.trials[-1].outcomes) == 400
    joint = result.chosen.expert.feature
    assert joint.left is left and joint.right is right
    assert result.chosen.constructors == (left.constructor, right.constructor)
    assert seen == [(tuple(rows[:400]), tuple(labels[:400]), 1)]
    assert propose_joint_refinements(seed, [seed], rows, labels,
                                    max_candidates=1, limit=1, pair_cost=0) == []
    assert propose_joint_refinements(seed, companions, rows, ["same"] * len(rows),
                                    max_candidates=2, limit=1, pair_cost=0) == []

    class ConstantFeature:
        manifest = left.manifest

        def invoke(self, value: Any) -> Any:
            return None

    assert propose_joint_refinements(seed, [Proposal(ConstantFeature())], rows, labels,
                                    max_candidates=1, limit=1, pair_cost=0) == []


def test_joint_refinement_budget_and_signature_validation() -> None:
    from nca.interface_learning import propose_joint_refinements

    seed = Proposal(Source())
    for kwargs, message in [({"max_candidates": 0, "limit": 1, "pair_cost": 0}, "budgets"),
                            ({"max_candidates": 1, "limit": 1, "pair_cost": -1}, "pair cost")]:
        with pytest.raises(ValueError, match=message):
            propose_joint_refinements(seed, [], [(1,)], [1], **kwargs)
    with pytest.raises(ValueError, match="companion features"):
        propose_joint_refinements(seed, [Proposal(Consumer())], [(1,)], [1],
                                  max_candidates=1, limit=1, pair_cost=0)
    with pytest.raises(ValueError, match="aligned"):
        propose_joint_refinements(seed, [], [], [], max_candidates=1, limit=1, pair_cost=0)


def test_joint_lookahead_crosses_non_improving_pairings() -> None:
    from itertools import product

    from nca.discovery import fit_decoder
    from nca.interface_learning import propose_heads, propose_joint_refinements

    class Feature:
        def __init__(self, index: int) -> None:
            self.index, self.calls = index, 0
            self.manifest = Manifest(f"feature-{index}", "1",
                                     Contract(("input",), f"feature-{index}"))

        def invoke(self, value: Any) -> Any:
            self.calls += 1
            return value[self.index]

    features = [Feature(i) for i in range(3)]
    seed = Proposal(features[0])
    companions = [Proposal(f) for f in features[1:]]
    rows = [(value,) for value in product(range(2), repeat=3)] * 50
    labels = [f"label-{sum(value) % 2}" for value, in rows]
    kwargs = {"max_candidates": 2, "limit": 1, "pair_cost": 1}
    assert propose_joint_refinements(seed, companions, rows, labels, **kwargs) == []
    assert propose_joint_refinements(seed, companions, rows, labels, **kwargs,
                                    max_companions=2, max_joint_candidates=2) == []
    for f in features:
        f.calls = 0
    learned = propose_joint_refinements(seed, companions, rows, labels, **kwargs,
                                       max_companions=2, max_joint_candidates=3)
    assert len(learned) == 1 and [f.calls for f in features] == [400, 400, 400]
    assert learned[0].expert.left.left is features[0]
    assert learned[0].expert.left.right is features[1]
    assert learned[0].expert.right is features[2]

    def refine(feature: Any, head: Any, train: Any, labels: Any, budget: int) -> Any:
        return propose_joint_refinements(feature, companions, train, labels, **kwargs,
                                         max_companions=2, max_joint_candidates=3)

    def propose(train: Any, labels: Any) -> Any:
        return propose_heads(Baseline(), [seed],
                    lambda c, v, t, b: [Proposal(fit_decoder(c, v, t, cost=1))],
                    train, labels, max_features=2, max_heads=1, refine=refine,
                    max_refinements=1, correct=lambda a, b: a == b)

    result = discover(Baseline(), propose, rows + rows, labels + labels, lambda a, b: a == b)
    assert result.chosen is not None
    assert [sum(t.outcomes) for t in result.trials] == [200, 400]
    with pytest.raises(ValueError, match="budgets"):
        propose_joint_refinements(seed, companions, rows, labels, **kwargs, max_companions=0)


def test_categorical_partition_generates_label_agnostic_codes_and_compact_heads() -> None:
    from nca.discovery import fit_decoder
    from nca.interface_learning import fit_categorical_partition, propose_heads

    source = Source()
    rows = [(i,) for i in range(4)] * 20
    labels = ["a" if i % 2 == 0 else "b" for i, in rows]
    feature = fit_categorical_partition(source, rows, labels, encoding_cost=1)
    renamed = fit_categorical_partition(source, rows,
        [frozenset({17}) if label == "a" else frozenset({93}) for label in labels], encoding_cost=1)
    assert feature.constructors == renamed.constructors
    assert [feature.expert.invoke(*r) for r in rows] == [renamed.expert.invoke(*r) for r in rows]
    assert set(feature.expert.decoder._table.values()) == {0, 1}
    assert feature.expert.manifest.contract.output == feature.constructors[0].type()
    assert feature.expert.feature is source
    heads = propose_heads(Baseline(), [feature],
                lambda c, v, t, b: [Proposal(fit_decoder(c, v, t, cost=1))],
                rows, labels, max_features=1, max_heads=1)
    assert len(heads[0].expert.decoder._table) == 2
    assert [heads[0].expert.invoke(*r) for r in rows] == labels
    assert heads[0].constructors == feature.constructors


def test_categorical_partition_preserves_conflicted_modal_fit_and_global_fallback() -> None:
    from nca.discovery import fit_decoder
    from nca.interface_learning import fit_categorical_partition

    rows, labels = [], []
    for key, category in enumerate(["a", "b", "c"]):
        rows.extend([(key,)] * 5)
        labels.extend([category] * 3 + ["global"] * 2)
    source = Source()
    feature = fit_categorical_partition(source, rows, labels, encoding_cost=0)
    codes = [feature.expert.invoke(*r) for r in rows]
    head = fit_decoder(Contract((feature.constructors[0].type(),), "output"), codes, labels, cost=0)
    raw = fit_decoder(Contract((source.manifest.contract.output,), "output"),
                      [source.invoke(*r) for r in rows], labels, cost=0)
    assert sum(head.invoke(code) == label for code, label in zip(codes, labels)) == (
        sum(raw.invoke(source.invoke(*r)) == label for r, label in zip(rows, labels))) == 9
    assert feature.expert.invoke(3) not in codes
    assert head.invoke(feature.expert.invoke(3)) == raw.invoke(source.invoke(3)) == "global"
    with pytest.raises(ValueError, match="aligned"):
        fit_categorical_partition(source, [], [], encoding_cost=0)
    with pytest.raises(ValueError, match="cost"):
        fit_categorical_partition(source, rows, labels, encoding_cost=-1)


def test_categorical_partition_matches_raw_modal_predictions_on_noisy_samples() -> None:
    import random

    from nca.discovery import fit_decoder
    from nca.interface_learning import fit_categorical_partition

    rng = random.Random(3651)
    rows = [(rng.randrange(4),) for _ in range(200)]
    labels = [rng.choice(("a", "b", "c")) for _ in rows]
    source = Source()
    feature = fit_categorical_partition(source, rows, labels, encoding_cost=0)
    codes = [feature.expert.invoke(*r) for r in rows]
    head = fit_decoder(Contract((feature.constructors[0].type(),), "output"), codes, labels, cost=0)
    raw = fit_decoder(Contract((source.manifest.contract.output,), "output"),
                      [source.invoke(*r) for r in rows], labels, cost=0)
    assert [head.invoke(code) for code in codes] == [raw.invoke(source.invoke(*r)) for r in rows]


def test_growing_prototype_types_are_selected_on_independent_rows() -> None:
    import random

    from nca.discovery import fit_decoder
    from nca.interface_learning import propose_heads
    from nca.projection_learning import fit_prototype_features

    class Vector:
        manifest = Manifest("vector", "1", Contract(("input",), "vector"), effects=frozenset())

        def invoke(self, value: Any) -> Any:
            return value

    rng = random.Random(3655)
    rows, labels = [], []
    for _ in range(800):
        group = rng.randrange(4)
        center = (-2.0 if group // 2 == 0 else 2.0, -2.0 if group % 2 == 0 else 2.0)
        rows.append((tuple(rng.gauss(x, 0.25) for x in center),))
        labels.append("a" if group in (0, 3) else "b")
    sizes = []

    def propose(train: Any, targets: Any) -> Any:
        features = fit_prototype_features(Vector(), train, targets, max_per_category=4,
                    max_centroids=8, max_errors=0, encoding_cost=1)
        sizes.append((len(train), [len(p.expert.centers) for p in features]))
        return propose_heads(Baseline(), features,
                    lambda c, v, t, b: [Proposal(fit_decoder(c, v, t, cost=1))],
                    train, targets, max_features=4, max_heads=1)

    result = discover(Baseline(), propose, rows, labels, lambda a, b: a == b)
    assert sizes == [(400, [2, 4])]
    assert result.chosen is not None and sum(result.trials[-1].outcomes) == 400
    assert result.chosen.constructors == (result.chosen.expert.feature.constructor,)


def test_error_directed_prototype_growth_uses_an_asymmetric_budget(
        monkeypatch: pytest.MonkeyPatch) -> None:
    from nca.discovery import fit_decoder
    from nca.interface_learning import propose_heads
    import nca.projection_learning as learning

    class Vector:
        manifest = Manifest("vector", "1", Contract(("input",), "vector"), effects=frozenset())

        def invoke(self, value: Any) -> Any:
            return value

    rows = [((-4.0, 0.0),)] * 20 + [((2.0, -2.0),)] * 10 + [((2.0, 2.0),)] * 10
    rows += [((2.0, 0.0),)] * 60
    labels = ["a"] * 20 + ["b"] * 20 + ["c"] * 60
    uniform = learning.fit_prototype_features(Vector(), rows, labels, max_per_category=2,
                    max_centroids=4, max_errors=0, encoding_cost=1)
    assert len(uniform) == 1
    original = learning._centroid_training
    seen = []

    def capture(*args: Any) -> Any:
        seen.append((tuple(args[1]), tuple(args[2]), dict(args[5])))
        return original(*args)

    monkeypatch.setattr(learning, "_centroid_training", capture)

    def propose(train: Any, targets: Any) -> Any:
        features = learning.fit_prototype_features(Vector(), train, targets, max_per_category=2,
                    max_centroids=4, max_errors=0, encoding_cost=1, allocate_by_errors=True)
        return propose_heads(Baseline(), features,
                    lambda c, v, t, b: [Proposal(fit_decoder(c, v, t, cost=1))],
                    train, targets, max_features=4, max_heads=1)

    result = discover(Baseline(), propose, rows + rows, labels + labels, lambda a, b: a == b)
    assert result.chosen is not None and [sum(t.outcomes) for t in result.trials] == [80, 100]
    assert [item[2] for item in seen] == [{"a": 1, "b": 1, "c": 1}, {"a": 1, "b": 2, "c": 1}]
    assert all(train == tuple(rows) and targets == tuple(labels) for train, targets, _ in seen)
    assert len(result.chosen.expert.feature.centers) == 4
    seen.clear()
    learning.fit_prototype_features(Vector(), [((),)] * 8, ["a"] * 4 + ["b"] * 2 + ["c"] * 2,
                max_per_category=2, max_centroids=4, max_errors=0,
                encoding_cost=0, allocate_by_errors=True)
    assert [item[2] for item in seen] == [{"a": 1, "b": 1, "c": 1}, {"a": 1, "b": 2, "c": 1}]
    seen.clear()
    learning.fit_prototype_features(Vector(), rows, labels, max_per_category=1,
                max_centroids=4, max_errors=0, encoding_cost=0, allocate_by_errors=True)
    assert len(seen) == 1


def test_bounded_allocation_search_escapes_greedy_growth_and_deduplicates(
        monkeypatch: pytest.MonkeyPatch) -> None:
    from nca.discovery import fit_decoder
    from nca.interface_learning import propose_heads
    import nca.projection_learning as learning

    class Vector:
        manifest = Manifest("vector", "1", Contract(("input",), "vector"), effects=frozenset())

        def invoke(self, value: Any) -> Any:
            return value

    rows = [((2.0, -2.0),)] * 30 + [((2.0, 2.0),)] * 30 + [((2.0, 0.0),)] * 40
    labels = ["b"] * 60 + ["c"] * 40
    original, seen = learning._centroid_training, []

    def capture(*args: Any) -> Any:
        seen.append(dict(args[5]))
        return original(*args)

    monkeypatch.setattr(learning, "_centroid_training", capture)

    def fit(trials: Any, cap: int = 2, budget: int = 3) -> Any:
        return learning.fit_prototype_features(Vector(), rows, labels, max_per_category=cap,
                    max_centroids=budget, max_errors=0, encoding_cost=1,
                    allocate_by_errors=True, max_allocation_trials=trials)

    assert len(fit(None)) == 2
    seen.clear()
    assert len(fit(2)) == 2
    seen.clear()
    features = fit(3)
    assert seen == [{"b": 1, "c": 1}, {"b": 1, "c": 2}, {"b": 2, "c": 1}]
    heads = propose_heads(Baseline(), features,
                lambda c, v, t, b: [Proposal(fit_decoder(c, v, t, cost=1))],
                rows, labels, max_features=3, max_heads=1)
    assert [sum(p.expert.invoke(*r) == t for r, t in zip(rows, labels)) for p in heads] == [60, 60, 100]
    rows = [((),)] * 100
    seen.clear()
    assert len(fit(20, cap=3, budget=6)) == 9
    assert len({tuple(state.values()) for state in seen}) == len(seen) == 9
    with pytest.raises(ValueError, match="allocation trial budget"):
        fit(0)
