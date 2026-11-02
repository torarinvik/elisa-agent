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
