"""Training-only search over proposed intermediate representations."""

from collections.abc import Callable, Hashable, Sequence
from dataclasses import replace
from pathlib import Path
from typing import Any

import pytest

from nca.abi import Calls, Contract, Manifest
from nca.discovery import (Decoded, JointFeature, Proposal, discover, discover_packages,
                           joint_features, propose_decoders)
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
