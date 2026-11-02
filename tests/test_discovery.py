"""Training-only search over proposed intermediate representations."""

from collections.abc import Sequence
from pathlib import Path
from typing import Any

import pytest

from nca.abi import Contract, Manifest
from nca.discovery import Proposal, discover, discover_packages
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
