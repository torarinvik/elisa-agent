"""Training-only search over proposed intermediate representations."""

from collections.abc import Callable, Hashable, Sequence
from dataclasses import replace
from pathlib import Path
from typing import Any

import pytest

from nca.abi import Calls, Contract, Manifest
from nca.learning.discovery import (Decoded, FeatureTree, JointFeature, Proposal, TreeStateEncoder,
                           discover, discover_packages, factor_tree, joint_features,
                           propose_decoders, train_tree)
from nca.objects import Composite, Constructor, Primitive, Store
from nca.packages import install


class Constant:
    manifest = Manifest("baseline", "1", Contract(("source",), "result"))

    def invoke(self, value: float) -> float:
        return 0.0


class Split:
    """A learned encoder followed by a learned table decoder."""

    manifest = Constant.manifest

    def __init__(self, threshold: float, outputs: tuple[float, float]) -> None:
        self.threshold = threshold
        self.outputs = outputs
        self.interface = Constructor("partition", "1", 0, f"branch at {threshold!r}")
        self.encoder_contract = Contract(("source",), self.interface.type())
        self.decoder_contract = Contract((self.interface.type(),), "result")

    def encode(self, value: float) -> int:
        return int(value >= self.threshold)

    def decode(self, branch: int) -> float:
        return self.outputs[branch]

    def invoke(self, value: float) -> float:
        return self.decode(self.encode(value))


def propose_split(rows: Sequence[tuple[Any, ...]], labels: Sequence[Any]) -> list[Proposal]:
    ordered = sorted(zip((row[0] for row in rows), labels))
    candidates = []
    for index in range(1, len(ordered)):
        threshold = (ordered[index - 1][0] + ordered[index][0]) / 2
        left = sum(y for _, y in ordered[:index]) / index
        right = sum(y for _, y in ordered[index:]) / (len(ordered) - index)
        expert = Split(threshold, (left, right))
        loss = sum((expert.invoke(x) - y) ** 2 for x, y in ordered)
        candidates.append((loss, index, expert))
    expert = min(candidates, key=lambda item: item[:2])[2]
    return [Proposal(expert, (expert.interface,))]


def same(output: float, target: float) -> bool:
    return abs(output - target) < 0.01


def test_learned_split_proposes_new_interface_and_wins_held_out() -> None:
    xs = [i / 100 for i in range(100)]
    # Interleave independent positions, rather than split one sorted interval.
    rows = [(x,) for x in xs[::2] + xs[1::2]]
    labels = [-1.0 if row[0] < 0.3 else 1.0 for row in rows]
    result = discover(Constant(), propose_split, rows, labels, same)
    assert result.chosen is not None
    assert result.chosen.constructors[0].ref.startswith("sha256:")
    assert sum(result.trials[0].outcomes) >= 49
    assert result.baseline == (False,) * 50


def test_proposer_gets_only_training_half_and_family_budget_is_charged() -> None:
    rows = [(float(i),) for i in range(40)]
    seen = []

    def propose(train: Sequence[tuple[Any, ...]], targets: Sequence[Any]) -> list[Proposal]:
        seen.extend(train)
        assert tuple(targets) == (1.0,) * 20
        return [Proposal(Split(0, (1, 1)))] * 100

    result = discover(Constant(), propose, rows, [1.0] * 40, same, alpha=0.00001)
    assert seen == rows[:20]
    assert all(not trial.accepted for trial in result.trials)
    assert result.chosen is None  # p=2^-20 > alpha/100, despite being below alpha.


def test_no_proposal_and_contract_mismatch() -> None:
    result = discover(Constant(), lambda rows, labels: [], [(0.0,), (1.0,)], [0, 0], same)
    assert result.chosen is None and result.trials == ()

    class Wrong(Constant):
        manifest = Manifest("wrong", "1", Contract(("other",), "result"))

    with pytest.raises(ValueError, match="external contract"):
        discover(Constant(), lambda rows, labels: [Proposal(Wrong())],
                 [(0.0,), (1.0,)], [0, 0], same)


def test_discovery_accepts_multi_input_experts_with_slot_fillings() -> None:
    from collections.abc import Callable

    class Higher:
        manifest = Manifest("higher", "1", Contract(("source", "extra"), "result",
                                                    ((("source",), "source"),)))

        def __init__(self, accurate: bool) -> None:
            self.accurate = accurate

        def invoke(self, filling: Callable[[int], int], first: int, second: int) -> int:
            return filling(first) + second if self.accurate else -1

    def identity(value: int) -> int:
        return value

    rows = [(identity, i, 1) for i in range(40)]
    result = discover(Higher(False), lambda rows, labels: [Proposal(Higher(True))],
                      rows, [i + 1 for i in range(40)], lambda a, b: a == b)
    assert result.chosen is not None


class StoredPart:
    """Serializable learned encoder or decoder used by a proposed composite."""

    def __init__(self, encoder: bool, interface: str, threshold: float,
                 outputs: list[float]) -> None:
        self.encoder = encoder
        self.threshold = threshold
        self.outputs = outputs
        self.manifest = Manifest(
            "encode" if encoder else "decode", "1",
            Contract(("source" if encoder else interface,), interface if encoder else "result"),
            effects=frozenset())

    def invoke(self, value: Any) -> Any:
        return int(value >= self.threshold) if self.encoder else self.outputs[value]


def stored_split(store: Store, expert: Split, copies: int = 1) -> str:
    store.put(expert.interface)
    members = []
    for encoder in (True, False):
        arguments = {"encoder": encoder, "interface": expert.interface.type(),
                     "threshold": expert.threshold, "outputs": list(expert.outputs)}
        part = StoredPart(**arguments)
        members.append(store.put(Primitive(part.manifest, f"{__name__}:StoredPart", arguments)))
    return store.put(Composite("learned-split", "1", tuple(members),
                               exports=(Constant.manifest.contract,) * copies,
                               effects=frozenset()))


def test_package_discovery_reloads_a_learned_decomposition(tmp_path: Path) -> None:
    store = Store()
    xs = [i / 100 for i in range(100)]
    rows = [(x,) for x in xs[::2] + xs[1::2]]
    labels = [-1.0 if row[0] < 0.3 else 1.0 for row in rows]

    def propose(train: Sequence[tuple[Any, ...]], targets: Sequence[Any]) -> list[str]:
        assert tuple(train) == tuple(rows[:50])
        assert tuple(targets) == tuple(labels[:50])
        proposal = propose_split(train, targets)[0]
        assert isinstance(proposal.expert, Split)
        return [stored_split(store, proposal.expert)]

    result = discover_packages(Constant(), store, propose, rows, labels, same)
    assert result.chosen is not None and result.chosen.package is not None
    chosen = result.chosen
    store.save(tmp_path)
    reopened = Store.open(tmp_path)
    experts = install(reopened, chosen.package)
    assert len(experts) == 1
    assert experts[0].identity == chosen.expert.identity
    assert [experts[0].invoke(*row) for row in rows] == [chosen.expert.invoke(*row) for row in rows]
    assert sum(result.trials[0].outcomes) >= 49
    assert len(reopened) == 4  # constructor, encoder, decoder, composite


def test_package_discovery_counts_exports_rather_than_packages() -> None:
    store = Store()
    package = stored_split(store, Split(0, (1, 1)), copies=100)
    result = discover_packages(Constant(), store, lambda rows, labels: [package],
                               [(float(i),) for i in range(40)], [1.0] * 40,
                               same, alpha=0.00001)
    assert len(result.trials) == 100 and result.chosen is None
    assert all(trial.proposal.package == package for trial in result.trials)


def test_package_discovery_requires_a_matching_export() -> None:
    store = Store()
    constructor = store.put(Constructor("unrelated", "1", 0, "test representation"))
    with pytest.raises(ValueError, match="no export"):
        discover_packages(Constant(), store, lambda rows, labels: [constructor],
                           [(0.0,), (1.0,)], [0, 0], same)


class Feature:
    def __init__(self, contract: Contract, project: Callable[..., Hashable]) -> None:
        self.manifest = Manifest("feature", "1", contract, effects=frozenset())
        self.project = project

    def invoke(self, *values: Any) -> Hashable:
        return self.project(*values)


def test_decoder_proposals_learn_compositions_and_generalize_to_unseen_rows() -> None:
    rows = [(f"{i % 4}:{i}",) for i in range(160)]
    labels = [f"target-{(i % 4 + 1) % 4}" for i in range(160)]
    features = [Feature(Contract(("source",), "category"), lambda x: x.split(":")[0]),
                Feature(Contract(("source",), "whole"), lambda x: x)]

    def propose(train: Sequence[tuple[Any, ...]], targets: Sequence[Any]) -> list[Proposal]:
        return propose_decoders(Constant(), features, train, targets, decoder_cost=0.1)

    result = discover(Constant(), propose, rows, labels, lambda a, b: a == b)
    assert result.chosen is result.trials[0].proposal
    assert sum(result.trials[0].outcomes) == 80
    assert sum(result.trials[1].outcomes) == 20  # Memorization falls back on unseen keys.
    expert = result.chosen.expert
    assert isinstance(expert, Decoded)
    assert expert.decoder.manifest.contract == Contract(("category",), "result")
    assert expert.manifest.contract == Constant.manifest.contract
    assert expert.manifest.cost == features[0].manifest.cost + 0.1
    assert expert.manifest.effects == frozenset()


def test_decoder_table_minimizes_training_error_and_has_deterministic_ties() -> None:
    from itertools import product

    rows = [(key,) for key in "aabbccc"]
    labels = ["x", "y", "y", "y", "x", "x", "y"]
    feature = Feature(Contract(("source",), "key"), lambda x: x)
    proposal = propose_decoders(Constant(), [feature], rows, labels, decoder_cost=1)[0]
    learned = [proposal.expert.invoke(*row) for row in rows]
    successes = sum(a == b for a, b in zip(learned, labels))
    for outputs in product(("x", "y"), repeat=3):
        table = dict(zip("abc", outputs))
        assert successes >= sum(table[row[0]] == label for row, label in zip(rows, labels))
    assert learned[0] == "x"  # First encountered label breaks the tie at key a.
    assert proposal.expert.invoke("unseen") == "y"  # Global training mode.


def test_decoder_proposals_preserve_multi_input_slots_and_reject_bad_contracts() -> None:
    contract = Contract(("source", "extra"), "result", ((("source",), "source"),))
    feature = Feature(replace(contract, output="new-interface"), lambda f, x, y: f(x) + y)
    incumbent = Feature(contract, lambda f, x, y: 0)
    rows = [(lambda x: x, 1, 2), (lambda x: x, 2, 3)]
    expert = propose_decoders(incumbent, [feature], rows, ["a", "b"], decoder_cost=1)[0].expert
    assert expert.manifest.contract == contract
    assert expert.invoke(*rows[1]) == "b"
    with pytest.raises(ValueError, match="inputs, slots"):
        propose_decoders(Constant(), [feature], [(1,)], ["a"], decoder_cost=1)
    with pytest.raises(ValueError, match="nonempty"):
        propose_decoders(Constant(), [], [], [], decoder_cost=1)
    with pytest.raises(ValueError, match="slot fillings"):
        propose_decoders(Constant(), [], [()], ["a"], decoder_cost=1)


def test_joint_search_discovers_information_absent_from_single_features() -> None:
    rows = [((i % 2, (i // 2) % 2, (i // 4) % 2),) for i in range(256)]
    labels = ["same" if row[0][0] == row[0][1] else "different" for row in rows]
    features = [Feature(Contract(("source",), f"component{i}"),
                        lambda value, index=i: value[index]) for i in range(3)]

    def propose(train: Sequence[tuple[Any, ...]], targets: Sequence[Any]) -> list[Proposal]:
        candidates = joint_features(features, max_size=2, limit=6, pair_cost=0.1)
        return propose_decoders(Constant(), candidates, train, targets, decoder_cost=0.1)

    result = discover(Constant(), propose, rows, labels, lambda a, b: a == b)
    assert [sum(t.outcomes) for t in result.trials] == [64, 64, 64, 128, 64, 64]
    assert result.chosen is result.trials[3].proposal
    expert = result.chosen.expert
    assert isinstance(expert, Decoded)
    assert expert.decoder.manifest.contract.inputs == ("pair[component0,component1]",)


def test_joint_search_limits_order_and_three_component_interfaces() -> None:
    features = [Feature(Contract(("source",), f"part{i}"),
                        lambda value, index=i: value[index]) for i in range(3)]
    candidates = joint_features(features, max_size=3, limit=7, pair_cost=0.5)
    assert candidates[:3] == features
    assert candidates[-1].manifest.contract.output == "pair[pair[part0,part1],part2]"
    assert candidates[-1].invoke(("a", "b", "c")) == (("a", "b"), "c")
    assert candidates[-1].manifest.cost == 4.0
    assert len(joint_features(features, max_size=100, limit=4, pair_cost=0)) == 4
    assert joint_features([], max_size=1, limit=1, pair_cost=0) == []
    with pytest.raises(ValueError, match="positive"):
        joint_features(features, max_size=0, limit=4, pair_cost=0)
    with pytest.raises(ValueError, match="finite"):
        joint_features(features, max_size=2, limit=4, pair_cost=float("nan"))
    with pytest.raises(ValueError, match="share inputs"):
        joint_features([features[0], Feature(Contract(("other",), "part"), lambda x: x)],
                       max_size=1, limit=1, pair_cost=0)


def test_joint_features_sum_slot_usage_and_keep_unknown_declarations_unknown() -> None:
    contract = Contract(("source",), "left", ((("source",), "source"),))
    left = Feature(contract, lambda f, x: f(x))
    right = Feature(replace(contract, output="right"), lambda f, x: f(x))
    left.manifest = replace(left.manifest, calls=(Calls(1, 2),),
                            expected_calls=(Calls(0.5, 1),), effects=frozenset({"read"}))
    right.manifest = replace(right.manifest, calls=(Calls(3, 4),), effects=frozenset({"write"}))
    joint = JointFeature(left, right, 0.25)
    assert joint.invoke(lambda x: x + 1, 2) == (3, 3)
    assert joint.manifest.calls == (Calls(4, 6),)
    assert joint.manifest.expected_calls == (Calls(3.5, 5),)
    assert joint.manifest.effects == frozenset({"read", "write"})
    right.manifest = replace(right.manifest, calls=(), effects=None)
    unknown = JointFeature(left, right, 0)
    assert unknown.manifest.calls == () and unknown.manifest.expected_calls is None
    assert unknown.manifest.effects is None


def test_tree_learns_conditional_execution_and_falls_back_for_unseen_keys() -> None:
    rows = [((i % 2, (i // 2) % 2, (i // 4) % 2),) for i in range(256)]
    labels = [f"label-{row[0][1 + row[0][0]]}" for row in rows]
    calls = []

    def feature(index: int, value: tuple[int, ...]) -> int:
        calls.append(index)
        return value[index]

    features = [Feature(Contract(("source",), f"part{i}"),
                        lambda value, index=i: feature(index, value)) for i in range(3)]

    def propose(train: Sequence[tuple[Any, ...]], targets: Sequence[Any]) -> list[Proposal]:
        return [Proposal(train_tree(Constant(), features, train, targets,
                                    max_nodes=15, overhead_cost=0.1))]

    result = discover(Constant(), propose, rows, labels, lambda a, b: a == b)
    assert result.chosen is not None
    tree = result.chosen.expert
    assert isinstance(tree, FeatureTree)
    assert sum(result.trials[0].outcomes) == 128
    calls.clear()
    assert [tree.invoke(*row) for row in rows] == labels
    assert len(calls) < 3 * len(rows)
    assert tree.root.feature is not None
    assert tree.invoke(("unseen", "unseen", "unseen")) == tree.root.fallback
    assert tree.manifest.cost <= 3.1 and tree.manifest.effects == frozenset()


def test_tree_node_budget_zero_gain_splits_and_empty_feature_family() -> None:
    rows = [((i % 2, (i // 2) % 2),) for i in range(40)]
    labels = ["same" if row[0][0] == row[0][1] else "different" for row in rows]
    features = [Feature(Contract(("source",), f"part{i}"),
                        lambda value, index=i: value[index]) for i in range(2)]
    for budget in range(1, 8):
        tree = train_tree(Constant(), features, rows, labels, max_nodes=budget, overhead_cost=0)
        pending, count = [tree.root], 0
        while pending:
            node = pending.pop()
            count += 1
            pending.extend(node.children.values())
        assert count <= budget
        correct = sum(tree.invoke(*row) == label for row, label in zip(rows, labels))
        assert correct >= 20
        if budget == 7:
            assert correct == 40  # Neither single feature improves on the modal leaf.
    tree = train_tree(Constant(), [], rows, labels, max_nodes=100, overhead_cost=0.5)
    assert tree.root.feature is None and tree.manifest.cost == 0.5
    with pytest.raises(ValueError, match="positive node"):
        train_tree(Constant(), [], rows, labels, max_nodes=0, overhead_cost=0)
    with pytest.raises(ValueError, match="preserve inputs"):
        train_tree(Constant(), [Feature(Contract(("other",), "part"), lambda x: x)],
                   rows, labels, max_nodes=3, overhead_cost=0)


def test_tree_keeps_slot_contract_and_conservative_call_declarations() -> None:
    contract = Contract(("source",), "result", ((("source",), "source"),))
    incumbent = Feature(contract, lambda f, x: 0)
    feature = Feature(replace(contract, output="part"), lambda f, x: f(x))
    feature.manifest = replace(feature.manifest, calls=(Calls(1),), effects=None)
    rows = [(lambda x: x, i) for i in range(4)]
    tree = train_tree(incumbent, [feature], rows, ["a", "b", "a", "b"],
                      max_nodes=5, overhead_cost=1)
    assert tree.manifest.contract == contract and tree.manifest.calls == (Calls(1),)
    assert tree.manifest.effects is None and tree.manifest.expected_calls is None
    assert tree.invoke(*rows[1]) == "b"
    leaf = train_tree(incumbent, [feature], rows, ["a"] * 4, max_nodes=1, overhead_cost=0)
    assert leaf.manifest.calls == (Calls(),) and leaf.manifest.effects == frozenset()


def test_tree_lookahead_discovers_selector_route_and_reduces_actual_calls() -> None:
    rows = [((i % 2, (i // 2) % 2, (i // 4) % 2),) for i in range(128)]
    labels = [f"target-{row[0][1 + row[0][0]]}" for row in rows]
    calls = []

    def read(index: int, value: tuple[int, ...]) -> int:
        calls.append(index)
        return value[index]

    features = [Feature(Contract(("source",), f"part{i}"),
                        lambda value, index=i: read(index, value)) for i in range(3)]
    greedy = train_tree(Constant(), features, rows, labels, max_nodes=127, overhead_cost=0)
    assert greedy.root.feature != 0
    for depth in (2, 4):
        tree = train_tree(Constant(), features, rows, labels, max_nodes=127,
                          overhead_cost=0, lookahead=depth, lookahead_budget=2000)
        assert tree.root.feature == 0
        assert 0 < tree.projection_states <= 2000 and not tree.projection_exhausted
        calls.clear()
        assert [tree.invoke(*row) for row in rows] == labels
        assert len(calls) == 2 * len(rows)


def test_tree_projection_budget_and_cost_ties_are_explicit_and_deterministic() -> None:
    rows = [((i % 2, (i // 2) % 2),) for i in range(32)]
    labels = ["same" if row[0][0] == row[0][1] else "other" for row in rows]
    features = [Feature(Contract(("source",), f"part{i}"),
                        lambda value, index=i: value[index]) for i in range(2)]
    tree = train_tree(Constant(), features, rows, labels, max_nodes=15, overhead_cost=0,
                      lookahead=3, lookahead_budget=1)
    assert tree.projection_states == 1 and tree.projection_exhausted
    with pytest.raises(ValueError, match="explicit work budget"):
        train_tree(Constant(), features, rows, labels, max_nodes=15, overhead_cost=0, lookahead=2)
    with pytest.raises(ValueError, match="positive"):
        train_tree(Constant(), features, rows, labels, max_nodes=15, overhead_cost=0, lookahead=0)
    expensive = Feature(Contract(("source",), "part"), lambda value: value[0])
    cheap = Feature(expensive.manifest.contract, lambda value: value[0])
    expensive.manifest = replace(expensive.manifest, cost=9)
    labels = [row[0][0] for row in rows]
    tree = train_tree(Constant(), [expensive, cheap], rows, labels, max_nodes=3, overhead_cost=0)
    assert tree.root.feature == 1 and tree.manifest.cost == cheap.manifest.cost


def test_tree_factorization_learns_a_type_and_preserves_all_stopping_predictions(tmp_path: Path) -> None:
    import json

    from nca.abi import Message
    from nca.planner import plan_stable
    from nca.runtime import execute
    from nca.workspace import Workspace

    rows = [((i % 2, (i // 2) % 2, (i // 4) % 2),) for i in range(128)]
    labels = [f"target-{row[0][1 + row[0][0]]}" for row in rows]
    features = [Feature(Contract(("source",), f"part{i}"),
                        lambda value, index=i: value[index]) for i in range(3)]
    tree = train_tree(Constant(), features, rows, labels, max_nodes=15, overhead_cost=0,
                      lookahead=2, lookahead_budget=1000)
    proposal = factor_tree(tree, encoding_cost=0.1, decoder_cost=0.2)
    assert isinstance(proposal.expert, Decoded)
    encoder = proposal.expert.feature
    assert isinstance(encoder, TreeStateEncoder)
    interface = proposal.constructors[0]
    assert encoder.manifest.contract.output == interface.type()
    assert proposal.expert.decoder.manifest.contract == Contract((interface.type(),), "result")
    assert proposal.expert.manifest.contract == tree.manifest.contract
    assert proposal.expert.manifest.cost == tree.manifest.cost + 0.1 + 0.2
    check = [*rows, ((9, 9, 9),), ((0, 9, 9),), ((1, 9, 9),)]
    assert [proposal.expert.invoke(*row) for row in check] == [tree.invoke(*row) for row in check]
    again = factor_tree(tree, encoding_cost=0.1, decoder_cost=0.2)
    assert again.constructors == proposal.constructors
    states = json.loads(interface.meaning)["states"]
    same_choice = [s for s in states if s["chosen"] == tree.root.fallback]
    assert len(same_choice) > 1
    assert len({str(s["counts"]) for s in same_choice}) > 1
    assert all(0 <= encoder.invoke(*row) < len(states) for row in check)
    store = Store()
    store.put(interface)
    store.save(tmp_path)
    assert Store.open(tmp_path).get(interface.ref) == interface
    route = plan_stable([encoder, proposal.expert.decoder], ("source",), "result")
    assert route is not None
    for row in check[-3:]:
        result = execute(route, {"source": Message("source", row[0], "input")}, Workspace(), 100)
        assert result.payload == tree.invoke(*row)


def test_tree_state_factorization_rejects_lossy_labels_and_distinguishes_target_types() -> None:
    tree = train_tree(Constant(), [], [(1,), (2,)], ["a", "b"], max_nodes=1, overhead_cost=0)
    first = factor_tree(tree, encoding_cost=0, decoder_cost=0)
    tree.manifest = replace(tree.manifest, contract=Contract(("source",), "another-target"))
    second = factor_tree(tree, encoding_cost=0, decoder_cost=0)
    assert first.constructors[0].ref != second.constructors[0].ref
    opaque = train_tree(Constant(), [], [(1,), (2,)], [(1,), (2,)],
                        max_nodes=1, overhead_cost=0)
    with pytest.raises(TypeError, match="JSON scalar"):
        factor_tree(opaque, encoding_cost=0, decoder_cost=0)
    with pytest.raises(ValueError, match="finite"):
        factor_tree(tree, encoding_cost=float("nan"), decoder_cost=0)


@pytest.mark.parametrize("label", [None, True, 1, 1.5, "é"])
def test_tree_state_scalar_labels_keep_their_values_and_types(label: Any) -> None:
    import json

    tree = train_tree(Constant(), [], [(1,), (2,)], [label, label],
                      max_nodes=1, overhead_cost=0)
    proposal = factor_tree(tree, encoding_cost=0, decoder_cost=0)
    output = proposal.expert.invoke(3)
    recorded = json.loads(proposal.constructors[0].meaning)["states"][0]["chosen"]
    assert output == label and type(output) is type(label)
    assert recorded == label and type(recorded) is type(label)


def test_learned_head_persists_values_fallback_and_canonical_identity(tmp_path: Path) -> None:
    from nca.learning.discovery import Decoder, decoder_object
    from nca.loader import ExpertStore

    contract = Contract(("state",), "target")
    head = Decoder(contract, {"b": False, "a": 1.5, "c": None}, "é", 1)
    obj = decoder_object(head, size=32)
    reordered = Decoder(contract, {"c": None, "a": 1.5, "b": False}, "é", 1)
    assert obj.ref == decoder_object(reordered, size=32).ref
    store = Store()
    reference = store.put(obj)
    store.save(tmp_path)
    resident = ExpertStore(32)
    restored = install(Store.open(tmp_path), reference, experts=resident)[0]
    assert resident.stats.loads == 0
    for key in ("a", "b", "c", "unseen"):
        expected, actual = head.invoke(key), restored.invoke(key)
        assert actual == expected and type(actual) is type(expected)
    assert resident.stats.loads == 1
    head._table["a"] = 99
    assert restored.invoke("a") == 1.5  # Stored data is a snapshot.
    with pytest.raises(TypeError, match="JSON scalar"):
        decoder_object(Decoder(contract, {frozenset({1, 2}): "x"}, "x", 1), size=0)


def test_residual_learning_preserves_good_regions_and_unseen_keys() -> None:
    from nca.learning.discovery import Corrected, propose_corrections

    class Baseline(Constant):
        def invoke(self, value: str) -> str:
            return "old"

    baseline = Baseline()
    feature = Feature(Contract(("source",), "region"), lambda value: value.split(":")[0])
    rows = [(f"{i % 10}:{i}",) for i in range(400)]
    labels = ["new" if i % 10 == 0 else "old" for i in range(400)]

    def propose(train: Sequence[tuple[Any, ...]], targets: Sequence[Any]) -> list[Proposal]:
        return propose_corrections(baseline, [feature], train, targets, correction_cost=0.1)

    result = discover(baseline, propose, rows, labels, lambda a, b: a == b)
    assert result.chosen is not None and isinstance(result.chosen.expert, Corrected)
    expert = result.chosen.expert
    assert expert.corrections == {"0": "new"}
    assert sum(result.baseline) == 180 and sum(result.trials[0].outcomes) == 200
    assert expert.invoke("unseen:1") == "old"
    assert expert.invoke("1:1") == "old"
    assert expert.manifest.contract == baseline.manifest.contract
    assert propose_corrections(baseline, [feature], rows, ["old"] * 400,
                               correction_cost=0) == []


def test_residual_learning_does_not_patch_a_region_where_incumbent_is_better() -> None:
    from nca.learning.discovery import propose_corrections

    feature = Feature(Contract(("source",), "region"), lambda value: "same-key")
    rows = [(float(i),) for i in range(20)]
    assert propose_corrections(Constant(), [feature], rows, [0.0] * 20,
                               correction_cost=1) == []
    with pytest.raises(ValueError, match="aligned"):
        propose_corrections(Constant(), [feature], [], [], correction_cost=1)


def test_discovery_ranks_exact_tails_below_float_range() -> None:
    class Candidate:
        manifest = Constant.manifest

        def __init__(self, limit: int) -> None:
            self.limit = limit

        def invoke(self, x: float) -> float:
            return float(x < self.limit)

    weak, strong = Proposal(Candidate(1102)), Proposal(Candidate(2000))
    rows = [(float(i),) for i in range(2000)] * 2
    result = discover(Constant(), lambda rows, labels: [weak, strong],
                      rows, [1.0] * 4000, lambda a, b: a == b)
    assert [t.p_value for t in result.trials] == [0.0, 0.0]
    assert all(t.accepted for t in result.trials)
    assert result.chosen is strong
    equal = Proposal(Candidate(2000))
    tied = discover(Constant(), lambda rows, labels: [strong, equal],
                    rows, [1.0] * 4000, lambda a, b: a == b)
    assert tied.chosen is strong
