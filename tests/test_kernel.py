from dataclasses import dataclass, field

import pytest

from nca.abi import Contract, Manifest, Message
from nca.planner import Apply, Given, plan
from nca.registry import Registry
from nca.runtime import BudgetExceeded, execute
from nca.workspace import Workspace

TEXT = "text.v1"
INT = "int.v1"
PAIR = "int.pair.v1"


@dataclass
class Fn:
    manifest: Manifest
    fn: object = field(repr=False)

    def invoke(self, *inputs):
        return self.fn(*inputs)


def fn(module_id, inputs, output, f, version="1.0.0"):
    return Fn(Manifest(module_id, version, Contract(tuple(inputs), output)), f)


def arithmetic_registry():
    registry = Registry()
    registry.install(fn("parse-int", [TEXT], INT, int))
    registry.install(fn("add", [INT, INT], INT, lambda a, b: a + b))
    return registry


def test_planner_composes_by_type():
    registry = arithmetic_registry()
    result = plan(registry.modules(), frozenset({TEXT}), INT)
    assert isinstance(result, Apply)
    assert result.module.manifest.module_id == "parse-int"
    assert result.args == (Given(TEXT),)


def test_planner_fails_without_capability():
    assert plan(arithmetic_registry().modules(), frozenset({TEXT}), PAIR) is None


def test_execute_records_provenance():
    registry = Registry()
    registry.install(fn("pair", [TEXT], PAIR, lambda s: tuple(map(int, s.split("+")))))
    registry.install(fn("sum", [PAIR], INT, lambda p: p[0] + p[1]))
    workspace = Workspace()
    source = Message(TEXT, "7+5", producer="input")

    graph = plan(registry.modules(), frozenset({TEXT}), INT)
    result = execute(graph, {TEXT: source}, workspace, budget=10)

    assert result.payload == 12
    chain = [m.producer for m in workspace.provenance(result.message_id)]
    assert chain == ["input", "pair@1.0.0", "sum@1.0.0"]


def test_replacement_requires_same_contract():
    registry = arithmetic_registry()
    registry.replace(fn("parse-int", [TEXT], INT, lambda s: int(s.strip()), version="2.0.0"))
    graph = plan(registry.modules(), frozenset({TEXT}), INT)
    assert execute(graph, {TEXT: Message(TEXT, " 3 ", "input")}, Workspace(), 1).payload == 3

    with pytest.raises(ValueError):
        registry.replace(fn("parse-int", [TEXT], TEXT, str))


def test_budget_exhaustion_rolls_back():
    registry = Registry()
    registry.install(fn("pair", [TEXT], PAIR, lambda s: (1, 2)))
    registry.install(fn("sum", [PAIR], INT, sum))
    workspace = Workspace()
    workspace.post(source := Message(TEXT, "x", "input"))
    graph = plan(registry.modules(), frozenset({TEXT}), INT)

    with pytest.raises(BudgetExceeded):
        execute(graph, {TEXT: source}, workspace, budget=1)
    assert len(workspace) == 1


def test_workspace_rejects_unknown_parents():
    with pytest.raises(ValueError):
        Workspace().post(Message(INT, 1, "x", parents=("msg:missing",)))
