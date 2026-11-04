"""Unresolved nodes can acquire trained features without seeing held-out rows."""

from collections.abc import Sequence
from typing import Any

import pytest

from nca.abi import Contract, Manifest, Module
from nca.learning.discovery import Proposal, discover, train_tree
from nca.learning.numeric import propose_partition


class Measurement:
    def __init__(self, index: int) -> None:
        self.index = index
        self.manifest = Manifest(f"measure-{index}", "1", Contract(("input",), f"measure{index}"),
                                 effects=frozenset())

    def invoke(self, value: tuple[float, float]) -> float:
        return value[self.index]


class Baseline:
    manifest = Manifest("baseline", "1", Contract(("input",), "target"))

    def invoke(self, value: tuple[float, float]) -> str:
        return "a"


def acquire(rows: Sequence[tuple[Any, ...]], labels: Sequence[Any]) -> list[Module]:
    features = []
    for index in range(2):
        proposals = propose_partition(Baseline(), Measurement(index), rows, labels,
                                       encoding_cost=0, decoder_cost=1)
        features.extend(proposal.expert.feature for proposal in proposals)
    return features


def test_node_local_acquisition_learns_conditional_boundaries_without_initial_features() -> None:
    rows = [((i / 20, j / 20),) for i in range(20) for j in range(20)]
    labels = ["b" if value[0][1] < (0.3 if value[0][0] < 0.4 else 0.7) else "a"
              for value in rows]
    seen = []

    def refine(subset: Sequence[tuple[Any, ...]], targets: Sequence[Any]) -> list[Module]:
        seen.append(len(subset))
        return acquire(subset, targets)

    tree = train_tree(Baseline(), [], rows, labels, max_nodes=31, overhead_cost=0, refine=refine)
    assert sum(tree.invoke(*row) == label for row, label in zip(rows, labels)) == len(rows)
    assert seen[0] == len(rows) and any(size < len(rows) for size in seen)
    assert len(seen) <= 31
    assert tree.features  # Each was learned by the callback; none was supplied initially.


def test_acquisition_is_training_only_and_skips_exhausted_nodes() -> None:
    rows = [((i / 20, j / 20),) for i in range(20) for j in range(20)]
    labels = ["b" if x[0][1] < 0.5 else "a" for x in rows]
    training = set(rows[:200])

    def refine(subset: Sequence[tuple[Any, ...]], targets: Sequence[Any]) -> list[Module]:
        assert set(subset) <= training
        return acquire(subset, targets)

    def propose(train: Sequence[tuple[Any, ...]], targets: Sequence[Any]) -> list[Proposal]:
        return [Proposal(train_tree(Baseline(), [], train, targets, max_nodes=15,
                                     overhead_cost=0, refine=refine))]

    assert discover(Baseline(), propose, rows, labels, lambda a, b: a == b).chosen is not None
    calls = []
    train_tree(Baseline(), [], rows, labels, max_nodes=1, overhead_cost=0,
                refine=lambda rows, labels: calls.append(rows) or [])
    assert calls == []
    with pytest.raises(ValueError, match="preserve inputs"):
        train_tree(Baseline(), [], rows, labels, max_nodes=3, overhead_cost=0,
                    refine=lambda rows, labels: [Invalid()])


class Invalid(Baseline):
    manifest = Manifest("invalid", "1", Contract(("different",), "target"))
