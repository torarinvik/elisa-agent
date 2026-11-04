"""Working-state transitions reuse runtime budgets, provenance and risk."""
from dataclasses import dataclass
from typing import Any

import pytest

from nca.abi import Contract, Manifest, Message
from nca.planner import Apply, Given
from nca.runtime import BudgetExceeded, Process, RiskLedger
from nca.workspace import Workspace


@dataclass
class Transition:
    manifest: Manifest = Manifest(
        "transition", "1", Contract(("state", "event"), "state"),
        effects=frozenset(), cost=2.0)

    def invoke(self, state: tuple[Any, ...], event: Any) -> tuple[Any, ...]:
        if event is None:
            raise ValueError("failed event")
        return (*state, event)

    def risk(self, output: Any, *inputs: Any) -> float:
        return 0.01


def process(ledger: RiskLedger | None = None) -> Process:
    module = Transition()
    route = Apply(module, (Given("state", 0), Given("event", 1)))
    return Process(route, module.manifest.contract,
                   Message("state", (), "input"), Workspace(), ledger=ledger)


def test_transitions_preserve_state_provenance_and_ledger() -> None:
    ledger = RiskLedger()
    runner = process(ledger)
    initial = runner.state
    a = runner.step((Message("event", "a", "input"),), budget=1)
    b = runner.step((Message("event", "b", "input"),), budget=1)
    assert b.payload == ("a", "b")
    assert runner.state is b
    assert initial in runner.workspace.provenance(b.message_id)
    assert a in runner.workspace.provenance(b.message_id)
    assert runner.workspace.spent == 4.0
    assert ledger.charge == pytest.approx(0.02)
    assert len(ledger.invocations) == 2


def test_failure_preserves_committed_cursor_and_history() -> None:
    runner = process()
    before = runner.step((Message("event", "kept", "input"),), budget=1)
    history = runner.workspace.messages()
    with pytest.raises(ValueError, match="failed event"):
        runner.step((Message("event", None, "input"),), budget=1)
    assert runner.state is before
    assert runner.workspace.messages() == history
    # Work already executed is still paid, even when its workspace posts roll back.
    assert runner.workspace.spent == 4.0
    assert runner.step((Message("event", "next", "input"),), budget=1).payload == (
        "kept", "next")


@pytest.mark.parametrize("budget,cost", [(0, None), (1, 1.0)])
def test_budget_refusal_preserves_state(budget: int, cost: float | None) -> None:
    runner = process()
    before = runner.state
    with pytest.raises(BudgetExceeded):
        runner.step((Message("event", "x", "input"),), budget=budget, cost_budget=cost)
    assert runner.state is before
    assert len(runner.workspace) == 0


def test_event_signature_rejected_before_invocation() -> None:
    runner = process()
    for events in [(), (Message("other", None, "input"),)]:
        with pytest.raises(ValueError, match="event types"):
            runner.step(events, budget=1)
    assert runner.workspace.spent == 0


def test_stream_is_lazy_bounded_and_stoppable() -> None:
    runner = process()
    consumed = []

    def events() -> Any:
        for i in range(10):
            consumed.append(i)
            yield (Message("event", i, "input"),)

    source = events()
    stream = runner.stream(source, max_steps=2, budget=1)
    assert consumed == []
    assert next(stream).payload == (0,)
    stream.close()
    assert consumed == [0]
    assert list(runner.stream(source, max_steps=2, budget=1))[-1].payload == (0, 1, 2)
    assert consumed == [0, 1, 2]
    assert list(runner.stream(source, max_steps=0, budget=1)) == []
    assert consumed == [0, 1, 2]


def test_stream_failure_keeps_successful_prefix() -> None:
    runner = process()
    events = [(Message("event", value, "input"),) for value in (1, None, 3)]
    stream = runner.stream(events, max_steps=3, budget=1)
    first = next(stream)
    with pytest.raises(ValueError):
        next(stream)
    assert runner.state is first
    assert first.payload == (1,)


def test_state_signature_validation_and_repeated_types() -> None:
    runner = process()
    for contract, initial in [
        (Contract((), "state"), runner.state),
        (Contract(("other",), "state"), runner.state),
        (Contract(("state",), "other"), runner.state),
        (runner.contract, Message("other", (), "input")),
    ]:
        with pytest.raises(ValueError):
            Process(runner.plan, contract, initial, Workspace())
    module = Transition(Manifest("same", "1", Contract(("state", "state"), "state")))
    same = Process(Apply(module, (Given("state", 0), Given("state", 1))),
                   module.manifest.contract, runner.state, Workspace())
    assert same.step((Message("state", "separate", "input"),), budget=1).payload == (
        "separate",)


@pytest.mark.parametrize("limit", [-1, True, 1.5])
def test_invalid_stream_limit(limit: Any) -> None:
    with pytest.raises(ValueError, match="max_steps"):
        list(process().stream((), max_steps=limit, budget=1))


def test_transition_requests_share_budget_and_risk() -> None:
    from nca.abi import Request
    from nca.kernel import Kernel

    @dataclass
    class Delegate(Transition):
        def invoke(self, state: tuple[Any, ...], event: Any) -> Any:
            yield Request("next", (("state", state), ("event", event)))
            return (*state, event)

    delegate = Delegate(Manifest("delegate", "1", Transition().manifest.contract))
    worker = Transition(Manifest("worker", "1", Contract(("state", "event"), "next")))
    route = Apply(delegate, (Given("state", 0), Given("event", 1)))
    ledger = RiskLedger()
    runner = Process(route, delegate.manifest.contract, Message("state", (), "input"),
                     Workspace(), resolver=Kernel((delegate, worker)), ledger=ledger)
    initial = runner.state
    with pytest.raises(BudgetExceeded):
        runner.step((Message("event", "x", "input"),), budget=1)
    assert runner.state is initial
    assert runner.step((Message("event", "x", "input"),), budget=2).payload == ("x",)
    assert len(ledger.invocations) == 2
    assert ledger.charge == pytest.approx(0.02)


def test_reentrant_transition_rejected_and_cursor_recovers() -> None:
    @dataclass
    class Reenter(Transition):
        def invoke(self, state: tuple[Any, ...], event: Any) -> Any:
            if event == "reenter":
                runner.step((Message("event", "inner", "input"),), budget=1)
            return (*state, event)

    module = Reenter()
    runner = Process(Apply(module, (Given("state", 0), Given("event", 1))),
                     module.manifest.contract, Message("state", (), "input"), Workspace())
    initial = runner.state
    with pytest.raises(RuntimeError, match="already running"):
        runner.step((Message("event", "reenter", "input"),), budget=1)
    assert runner.state is initial
    assert runner.step((Message("event", "next", "input"),), budget=1).payload == ("next",)


@pytest.mark.parametrize("budget,cost", [(-1, None), (True, None), (1.5, None),
                                       (1, -1.0), (1, float("nan")), (1, float("inf"))])
def test_invalid_budgets_cannot_bypass_transition_limits(budget: Any, cost: Any) -> None:
    runner = process()
    initial = runner.state
    with pytest.raises(ValueError):
        runner.step((Message("event", "x", "input"),), budget=budget, cost_budget=cost)
    assert runner.state is initial
    assert len(runner.workspace) == 0
    assert runner.workspace.spent == 0
