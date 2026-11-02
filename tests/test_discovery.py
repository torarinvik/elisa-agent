"""Training-only search over proposed intermediate representations."""

from collections.abc import Sequence
from typing import Any

import pytest

from nca.abi import Contract, Manifest
from nca.discovery import Proposal, discover
from nca.objects import Constructor


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
