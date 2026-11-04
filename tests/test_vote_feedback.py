"""Failure transport and monotonic-repair links (§31.10)."""

from itertools import combinations
from typing import Any

import pytest

from nca.abi import Contract, Manifest, Message
from nca.evidence.redundancy import disjoint_routes
from nca.planner import Apply, Given, Plan
from nca.retention.ensembles import EnsembleSearch, VoteCase, VoteFailure
from test_redundancy import paths


class Lookup:
    manifest = Manifest("lookup", "1", Contract(("s",), "g"), effects=frozenset())

    def __init__(self, table: dict[int, int]) -> None:
        self.table = dict(table)

    def invoke(self, key: int) -> Any:
        return self.table.get(key, "unlearned")


def test_feedback_can_train_later_candidates_without_reusing_draws() -> None:
    table: dict[int, int] = {}
    cursor = 0
    feedback_ids: list[int] = []
    drawn_ids: list[int] = []

    def sample(count: int) -> list[VoteCase]:
        nonlocal cursor
        batch = []
        for _ in range(count):
            index = cursor
            cursor += 1
            drawn_ids.append(index)
            batch.append(((Message("s", index % 2, "input", message_id=str(index)),), index % 2))
        return batch

    def learn(failure: VoteFailure) -> None:
        inputs, label = failure.case
        assert not isinstance(inputs, dict)
        feedback_ids.append(int(inputs[0].message_id))
        assert failure.vote.answer != label and failure.drawn == 1
        table[inputs[0].payload] = label

    def acquire(old: tuple[Plan, ...]) -> Plan:
        return Apply(Lookup(table), (Given("s"),))

    search = EnsembleSearch(counts=(1,), tolerance=0.1, confidence=0.05, budget=2)
    result = None
    for _ in range(3):
        result = search(Contract(("s",), "g"), acquire, sample, feedback=learn)
        if result is not None:
            break
    assert result is not None and table == {0: 0, 1: 1}
    assert feedback_ids == [0, 1]
    assert len(set(drawn_ids)) == len(drawn_ids)
    assert search.labels == result.cases + 2


def test_feedback_is_after_scoring_and_before_the_next_acquisition() -> None:
    events: list[str] = []
    available = disjoint_routes(paths(3, {0: frozenset({5})}), ("s",), "g", 3)

    def acquire(old: tuple[Plan, ...]) -> Plan:
        events.append("acquire")
        return available[len(old)]

    def agree(answer: Any, target: Any) -> bool:
        events.append("score")
        return bool(answer == target)

    def feedback(failure: VoteFailure) -> None:
        assert events == ["acquire", "score"]
        assert len(failure.routes) == 1
        events.append("feedback")

    search = EnsembleSearch(counts=(1, 3), tolerance=0.1, confidence=0.05, budget=10)
    result = search(Contract(("s",), "g"), acquire,
                    lambda n: [((Message("s", 5, "input"),), 7)] * n,
                    agree=agree, feedback=feedback)
    assert result is not None and events[:5] == ["acquire", "score", "feedback", "acquire", "acquire"]
    assert events.count("feedback") == 1


def test_admission_and_missing_data_emit_no_failure() -> None:
    route = Apply(Lookup({0: 0}), (Given("s"),))
    seen: list[VoteFailure] = []
    search = EnsembleSearch(counts=(1,), tolerance=0.1, confidence=0.05,
                            budget=2, retain_controls=16, retain_training=16)
    assert search(Contract(("s",), "g"), lambda old: route,
                  lambda n: [((Message("s", 0, "input"),), 0)] * n, feedback=seen.append)
    assert search(Contract(("s",), "g"), lambda old: route,
                  lambda n: None, feedback=seen.append) is None
    assert seen == []


def test_feedback_exception_is_not_an_admission_and_keeps_costs() -> None:
    search = EnsembleSearch(counts=(1,), tolerance=0.1, confidence=0.05, budget=2)

    def broken(failure: VoteFailure) -> None:
        raise RuntimeError("repair unavailable")

    with pytest.raises(RuntimeError, match="repair unavailable"):
        search(Contract(("s",), "g"), lambda old: Apply(Lookup({}), (Given("s"),)),
               lambda n: [((Message("s", 0, "input"),), 0)] * n, feedback=broken)
    assert search.labels == search.evaluations == search.tests == 1


def test_feedback_names_the_first_scored_failure_inside_a_larger_batch() -> None:
    cursor = 0
    seen: list[VoteFailure] = []

    def sample(count: int) -> list[VoteCase]:
        nonlocal cursor
        cases = [((Message("s", i, "input"),), i) for i in range(cursor, cursor + count)]
        cursor += count
        return cases

    search = EnsembleSearch(counts=(1,), tolerance=0.1, confidence=0.05, budget=2)
    assert search(Contract(("s",), "g"),
                  lambda old: Apply(Lookup({0: 0, 1: 1}), (Given("s"),)),
                  sample, feedback=seen.append) is None
    assert len(seen) == 1 and seen[0].case[1] == 2
    assert seen[0].drawn == search.labels == cursor == 3


def test_all_finite_monotonic_repairs_strictly_reduce_error_count() -> None:
    """Brute-force link to feedback_repair_progress and feedback_chain_bound;
    these are learner hypotheses, not properties of arbitrary callbacks."""
    domain = range(6)
    for size in range(7):
        for elements in combinations(domain, size):
            errors = set(elements)
            for failed in errors:
                remainder = errors - {failed}
                for kept in range(len(remainder) + 1):
                    for repaired in combinations(remainder, kept):
                        assert len(repaired) < len(errors)
            current = errors.copy()
            for steps, failed in enumerate(elements, 1):
                current.remove(failed)
                assert len(current) + steps <= len(errors)


@pytest.mark.parametrize("capacity", [0, 1, 8])
def test_controls_include_only_scored_successes_before_rejection(capacity: int) -> None:
    cursor = 0
    seen: list[VoteFailure] = []

    def sample(count: int) -> list[VoteCase]:
        nonlocal cursor
        cases = [((Message("s", i, "input"),), i) for i in range(cursor, cursor + count)]
        cursor += count
        return cases

    search = EnsembleSearch(counts=(1,), tolerance=0.1, confidence=0.05,
                            budget=2, retain_controls=capacity)
    route = Apply(Lookup({i: i for i in range(4)}), (Given("s"),))
    assert search(Contract(("s",), "g"), lambda old: route, sample,
                  feedback=seen.append) is None
    assert len(seen) == 1
    assert seen[0].case[1] == 4
    assert [case[1] for case in seen[0].controls] == list(range(min(capacity, 4)))
    assert search.labels == seen[0].drawn == cursor == 7
    assert search.evaluations == 5  # Two drawn cases were never scored.


@pytest.mark.parametrize("capacity", [-1, True, 1.5])
def test_control_capacity_is_a_nonnegative_integer(capacity: Any) -> None:
    with pytest.raises(ValueError, match="control capacity"):
        EnsembleSearch(counts=(1,), tolerance=0.1, confidence=0.05,
                       budget=2, retain_controls=capacity)


def test_protected_corrections_preserve_all_observed_successes_exhaustively() -> None:
    """Finite link to keyCorrection_protected, including conflicting fibers."""
    from itertools import product

    from nca.learning.discovery import propose_corrections
    from test_discovery import Constant, Feature

    rows = [(float(i),) for i in range(4)]
    for keys in product(range(2), repeat=4):
        feature = Feature(Contract(("source",), "region"), lambda x: keys[int(x)])
        for labels in product(range(2), repeat=4):
            proposals = propose_corrections(Constant(), [feature], rows, labels,
                                            correction_cost=0, preserve_successes=True)
            for proposal in proposals:
                outputs = [proposal.expert.invoke(*row) for row in rows]
                assert all(output == label for output, label in zip(outputs, labels, strict=True)
                           if label == 0)
                assert sum(a == b for a, b in zip(outputs, labels, strict=True)) > labels.count(0)


def test_protected_corrections_reject_a_net_gain_that_breaks_a_control() -> None:
    from nca.learning.discovery import propose_corrections
    from test_discovery import Constant, Feature

    feature = Feature(Contract(("source",), "region"), lambda x: 0)
    rows, labels = [(0.0,), (1.0,), (2.0,)], [0, 1, 1]
    assert propose_corrections(Constant(), [feature], rows, labels, correction_cost=0)
    assert not propose_corrections(Constant(), [feature], rows, labels,
                                   correction_cost=0, preserve_successes=True)


def test_label_sufficient_noninjective_keys_remove_only_existing_errors() -> None:
    """Exhaustive finite link to fiber_correction_errors."""
    from itertools import product

    from nca.learning.discovery import Corrected
    from test_discovery import Feature

    feature = Feature(Contract(("s",), "key"), lambda x: x // 2)
    for labels in product(range(2), repeat=2):
        truth = [labels[x // 2] for x in range(4)]
        for outputs in product(range(2), repeat=4):
            base = Lookup(dict(enumerate(outputs)))
            for point in range(4):
                model = Corrected(base, feature, {point // 2: truth[point]}, 0)
                for x in range(4):
                    if model.invoke(x) != truth[x]:
                        assert outputs[x] != truth[x] and x // 2 != point // 2


def test_feature_chain_search_matches_all_small_typed_graphs() -> None:
    """Differential link to featureClosure_iff, retaining distinct paths."""
    from itertools import product

    from nca.learning.features import compose_features
    from test_discovery import Feature

    seed = Feature(Contract(("input",), "a"), lambda x: x)
    edges = [(a, b) for a in ("a", "b") for b in ("a", "b")]
    for enabled in product((False, True), repeat=4):
        transforms = [Feature(Contract((a,), b), lambda x: x + 1)
                      for (a, b), use in zip(edges, enabled, strict=True) if use]
        expected = [("a", 0)]
        frontier = expected.copy()
        for depth in range(4):
            actual = compose_features([seed], transforms, max_depth=depth, limit=1000)
            assert [(m.manifest.contract.output, m.invoke(0)) for m in actual] == expected
            for cap in (1, 2, 5):
                assert [m.invoke(0) for m in compose_features(
                    [seed], transforms, max_depth=depth, limit=cap)] == [
                        m.invoke(0) for m in actual[:cap]]
            frontier = [(b, length + 1) for a, length in frontier
                        for (source, b), use in zip(edges, enabled, strict=True)
                        if use and source == a]
            expected.extend(frontier)


def test_feature_chain_search_checks_bounds_and_does_not_execute_models() -> None:
    from nca.learning.features import compose_features
    from test_discovery import Feature

    def unavailable(x: Any) -> Any:
        raise AssertionError("search must inspect metadata only")

    seed = Feature(Contract(("input",), "a"), unavailable)
    edge = Feature(Contract(("a",), "b"), unavailable)
    irrelevant = Feature(Contract(("absent", "absent"), "b"), unavailable)
    result = compose_features([seed], [irrelevant, edge], max_depth=1, limit=10)
    assert [m.manifest.contract.output for m in result] == ["a", "b"]
    assert result[1].manifest.cost == seed.manifest.cost + edge.manifest.cost
    for depth, cap in ((-1, 1), (True, 1), (1, 0), (1, True)):
        with pytest.raises(ValueError):
            compose_features([seed], [edge], max_depth=depth, limit=cap)
    with pytest.raises(ValueError, match="share external"):
        compose_features([seed, edge], [], max_depth=0, limit=10)


@pytest.mark.parametrize("capacity", [0, 2, 16])
def test_training_feedback_reuses_drawn_but_unscored_cases(capacity: int) -> None:
    cursor = 0
    seen: list[VoteFailure] = []

    def sample(count: int) -> list[VoteCase]:
        nonlocal cursor
        cases = [((Message("s", i, "input"),), i) for i in range(cursor, cursor + count)]
        cursor += count
        return cases

    search = EnsembleSearch(counts=(1,), tolerance=0.1, confidence=0.05,
                            budget=2, retain_training=capacity)
    route = Apply(Lookup({i: i for i in range(4)}), (Given("s"),))
    assert search(Contract(("s",), "g"), lambda old: route, sample,
                  feedback=seen.append) is None
    retained = {case[1] for case in seen[0].training}
    drawn = set(range(cursor))
    future = set(range(cursor, cursor + 10))
    assert retained == set(range(min(capacity, 7)))
    assert search.evaluations == 5 and search.labels == 7
    # Finite link to retained_feedback_account; identifier equality is not
    # payload equality, and statistical independence is an additional hypothesis.
    assert len(drawn | retained) == len(drawn) and retained.isdisjoint(future)


@pytest.mark.parametrize("capacity", [-1, True, 1.5])
def test_training_retention_capacity_is_validated(capacity: Any) -> None:
    from nca.retention.ensembles import EnsembleSearch

    with pytest.raises(ValueError, match="training capacity"):
        EnsembleSearch(counts=(1,), tolerance=0.1, confidence=0.05,
                       budget=2, retain_training=capacity)


def test_feature_tree_search_matches_exhaustive_typed_rules() -> None:
    """Link closure, filter and demand-index lemmas, including ordered prefixes."""
    from itertools import product
    from pathlib import Path
    from runpy import run_path

    from nca.learning.features import compose_features
    from test_discovery import Feature

    baseline = run_path(str(Path(__file__).resolve().parents[1] / "benchmarks" / "feature_search.py"))
    compose_unindexed, signature = baseline["compose_unindexed"], baseline["signature"]

    seeds = [Feature(Contract(("input",), t), lambda x, i=i: ("seed", i))
             for i, t in enumerate(("a", "b"))]
    rules = [(("a",), "a"), (("a", "a"), "b"),
             (("a", "b"), "a"), (("b", "a"), "b")]
    for enabled in product((False, True), repeat=len(rules)):
        transforms = [Feature(Contract(inputs, output), lambda *xs, i=i: (i, *xs))
                      for i, ((inputs, output), use) in enumerate(zip(rules, enabled, strict=True))
                      if use]
        expected = {(t, ("seed", i)) for i, t in enumerate(("a", "b"))}
        for depth in range(3):
            actual = compose_features(seeds, transforms, max_depth=depth, limit=10000)
            reference = compose_unindexed(seeds, transforms, max_depth=depth, limit=10000)
            assert [signature(m) for m in actual] == [signature(m) for m in reference]
            observed = [(m.manifest.contract.output, m.invoke(None)) for m in actual]
            assert len(set(observed)) == len(observed)
            assert set(observed) == expected
            for budget in (None, 0, 1, 3):
                for cap in (1, 3, 7, 10000):
                    prefix = compose_features(seeds, transforms, max_depth=depth,
                                              limit=cap, index_entries=budget)
                    assert [signature(m) for m in prefix] == [signature(m) for m in reference[:cap]]
            following = set(expected)
            for i, ((inputs, output), use) in enumerate(zip(rules, enabled, strict=True)):
                if use:
                    choices = [[tree for t, tree in expected if t == required] for required in inputs]
                    following.update((output, (i, *children)) for children in product(*choices))
            expected = following


def test_multi_input_features_keep_positions_cost_effects_and_slot_calls() -> None:
    from dataclasses import replace

    from nca.abi import Calls
    from nca.learning.features import AppliedFeature, compose_features
    from test_discovery import Feature

    left = Feature(Contract(("input",), "part"), lambda x: "left")
    right = Feature(left.manifest.contract, lambda x: "right")
    head = Feature(Contract(("part", "part"), "joined"), lambda a, b: (a, b))
    results = compose_features([left, right], [head], max_depth=1, limit=20)
    assert {m.invoke(None) for m in results[2:]} == {
        ("left", "left"), ("left", "right"), ("right", "left"), ("right", "right")}
    from itertools import product

    triple = Feature(Contract(("part",) * 3, "triple"), lambda *xs: tuple(xs))
    triples = compose_features([left, right], [triple], max_depth=1, limit=20)
    assert {m.invoke(None) for m in triples[2:]} == set(product(("left", "right"), repeat=3))
    slot = ((("p",), "q"),)
    for feature, count, effect in ((left, 2, "first"), (right, 3, "second")):
        feature.manifest = replace(feature.manifest,
            contract=replace(feature.manifest.contract, slots=slot, relevant=((0,),)),
            calls=(Calls(count, 1),), effects=frozenset({effect}))
        feature.project = lambda filling, value, tag=effect: (tag, filling(value))
    head.manifest = replace(head.manifest, effects=frozenset({"third"}))
    model = AppliedFeature(head, [left, right])
    assert model.manifest.calls == (Calls(5, 2),)
    assert model.manifest.cost == 3
    assert model.manifest.effects == frozenset({"first", "second", "third"})
    assert model.manifest.contract.slots == slot
    assert model.manifest.contract.relevant == ((0,),)
    assert model.invoke(lambda x: x + 1, 2) == (("first", 3), ("second", 3))
    with pytest.raises(ValueError, match="ordered head inputs"):
        AppliedFeature(head, [left])


@pytest.mark.parametrize("budget", [None, 0, 1])
def test_lazy_feature_index_does_not_read_an_unneeded_rule_suffix(budget: int | None) -> None:
    from nca.learning.features import compose_features
    from test_discovery import Feature

    class Unread:
        @property
        def manifest(self) -> Manifest:
            raise AssertionError("capped search must not inspect the unread suffix")

        def invoke(self, *inputs: Any) -> Any:
            raise AssertionError("search must not invoke experts")

    seed = Feature(Contract(("input",), "a"), lambda x: x)
    head = Feature(Contract(("a",), "a"), lambda x: x)
    assert len(compose_features([seed], [head, Unread()], max_depth=2,
                                limit=2, index_entries=budget)) == 2
    assert compose_features([seed], [Unread()], max_depth=0,
                            limit=10, index_entries=budget) == [seed]
    assert compose_features([seed], [Unread()], max_depth=2,
                            limit=1, index_entries=budget) == [seed]


@pytest.mark.parametrize("budget", [-1, True, 1.5])
def test_feature_index_entry_budget_is_validated(budget: Any) -> None:
    from nca.learning.features import compose_features

    with pytest.raises(ValueError, match="index entry budget"):
        compose_features([], [], max_depth=0, limit=1, index_entries=budget)


def test_native_feature_selection_rechecks_deliberate_hash_collisions(
        monkeypatch: pytest.MonkeyPatch) -> None:
    from pathlib import Path
    from runpy import run_path

    from nca.learning import features
    from test_discovery import Feature

    if features._NATIVE is None:
        pytest.skip("native record selector unavailable or disabled")
    signature = run_path(str(Path(__file__).resolve().parents[1] /
                            "benchmarks" / "feature_search.py"))["signature"]
    seeds = [Feature(Contract(("input",), t), lambda x: x) for t in ("a", "b")]
    heads = [Feature(Contract(("a",), "b"), lambda x: x),
             Feature(Contract(("a", "b"), "a"), lambda a, b: (a, b)),
             Feature(Contract(("absent",), "absent"), lambda x: x)]
    monkeypatch.setattr(features, "hash", lambda value: 0, raising=False)
    accelerated = features.compose_features(seeds, heads, max_depth=4, limit=40, index_entries=0)
    monkeypatch.setattr(features, "_NATIVE", None)
    fallback = features.compose_features(seeds, heads, max_depth=4, limit=40, index_entries=0)
    assert [signature(m) for m in accelerated] == [signature(m) for m in fallback]
