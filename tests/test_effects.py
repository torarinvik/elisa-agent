"""Scoped admission and resource-gateway checks across execution paths."""
from dataclasses import dataclass
from typing import Any

import pytest

from nca.abi import Contract, Manifest, Message, Request
from nca.compile import compile_route
from nca.effects import EffectDenied, effect_call, effect_scope, require_effect
from nca.kernel import Kernel
from nca.planner import Apply, Given
from nca.runtime import Process, RiskLedger, execute
from nca.workspace import Workspace


@dataclass
class Expert:
    manifest: Manifest
    accesses: list[str]
    operation: str = "resource.a"

    def invoke(self, value: Any) -> Any:
        require_effect(self.operation)
        self.accesses.append(self.operation)
        return value


def expert(effects: frozenset[str] | None) -> Expert:
    return Expert(Manifest("expert", "1", Contract(("input",), "output"), effects=effects), [])


def run(module: Expert) -> Any:
    return execute(Apply(module, (Given("input"),)),
                   (Message("input", 7, "input"),), Workspace(), 1).payload


def test_gateway_needs_declaration_and_host_grant() -> None:
    module = expert(frozenset({"resource.a"}))
    with effect_scope(frozenset({"resource.a"})):
        assert run(module) == 7
        with pytest.raises(EffectDenied):
            require_effect("resource.a")  # No active expert declaration.
    assert module.accesses == ["resource.a"]
    with effect_scope(frozenset()):
        with pytest.raises(EffectDenied):
            run(module)
    assert len(module.accesses) == 1


@pytest.mark.parametrize("declaration", [None, frozenset(), frozenset({"resource.b"})])
def test_missing_unknown_or_wrong_declaration_cannot_use_gateway(
    declaration: frozenset[str] | None,
) -> None:
    module = expert(declaration)
    with effect_scope(frozenset({"resource.a", "resource.b"})):
        with pytest.raises(EffectDenied):
            run(module)
    assert module.accesses == []


def test_nested_scopes_cannot_widen_and_restore_after_exception() -> None:
    module = expert(frozenset({"resource.a"}))
    with effect_scope(frozenset({"resource.a"})):
        with effect_scope(frozenset({"resource.a", "resource.b"})):
            assert run(module) == 7
            with pytest.raises(EffectDenied):
                run(expert(frozenset({"resource.b"})))
        with pytest.raises(EffectDenied):
            with effect_scope(frozenset()):
                run(module)
        assert run(module) == 7
    # Legacy execution remains available outside explicit restricted scopes.
    assert run(module) == 7


def test_nested_runtime_cannot_acquire_effect_absent_from_caller_declaration() -> None:
    child = expert(frozenset({"resource.a"}))
    with effect_scope(frozenset({"resource.a", "resource.b"})):
        with pytest.raises(EffectDenied):
            effect_call(frozenset({"resource.b"}), run, child)
    assert child.accesses == []


@pytest.mark.parametrize("batched", [False, True])
def test_compiled_invocation_and_batch_have_same_permissions(batched: bool) -> None:
    class Batched(Expert):
        def invoke_batch(self, values: list[Any]) -> list[Any]:
            require_effect(self.operation)
            self.accesses.append(self.operation)
            return list(values)

    module = expert(frozenset({"resource.a"}))
    if batched:
        module = Batched(module.manifest, [])
    compiled = compile_route(Apply(module, (Given("input"),)), ("input",))
    with effect_scope(frozenset({"resource.a"})):
        assert compiled([(1,), (2,)]) == [1, 2]
    calls = len(module.accesses)
    with effect_scope(frozenset()):
        with pytest.raises(EffectDenied):
            compiled([(1,), (2,)])
    assert len(module.accesses) == calls


def test_lazy_batch_iterator_is_consumed_under_declaration() -> None:
    class Lazy(Expert):
        def invoke_batch(self, values: list[Any]) -> Any:
            for value in values:
                require_effect(self.operation)
                self.accesses.append(self.operation)
                yield value

    module = Lazy(expert(frozenset({"resource.a"})).manifest, [])
    compiled = compile_route(Apply(module, (Given("input"),)), ("input",))
    with effect_scope(frozenset({"resource.a"})):
        assert compiled([(1,), (2,)]) == [1, 2]
    assert len(module.accesses) == 2


def test_callbacks_use_their_own_declaration() -> None:
    class Callback(Expert):
        def demand(self, index: int, demand: Any) -> Any:
            require_effect("resource.b")
            return demand

    module = Callback(expert(frozenset({"resource.a"})).manifest, [])
    with effect_scope(frozenset({"resource.a", "resource.b"})):
        with pytest.raises(EffectDenied):
            run(module)
    assert module.accesses == []


def test_risk_callback_is_scoped_and_workspace_rolls_back() -> None:
    class Reporting(Expert):
        def risk(self, output: Any, *inputs: Any) -> float:
            require_effect("resource.b")
            return 0.1

    module = Reporting(expert(frozenset({"resource.a"})).manifest, [])
    workspace = Workspace()
    with effect_scope(frozenset({"resource.a", "resource.b"})):
        with pytest.raises(EffectDenied):
            execute(Apply(module, (Given("input"),)), (Message("input", 7, "input"),),
                    workspace, 1, ledger=RiskLedger())
    assert len(workspace) == 0
    # A performed external effect is not undone by workspace rollback.
    assert module.accesses == ["resource.a"]


@pytest.mark.parametrize("continuation", [False, True])
def test_request_delegation_cannot_exceed_requester_declaration(continuation: bool) -> None:
    class Caller(Expert):
        def invoke(self, value: Any) -> Any:
            request = Request("output", (("input", value),))
            return self.program(request) if continuation else request

        def program(self, request: Request) -> Any:
            require_effect("resource.a")
            result = yield request
            require_effect("resource.a")
            return result

    caller = Caller(Manifest("caller", "1", Contract(("input",), "output"),
                             effects=frozenset({"resource.a"})), [])
    child = expert(frozenset({"resource.b"}))
    child.operation = "resource.b"
    route = Apply(caller, (Given("input"),))
    with effect_scope(frozenset({"resource.a", "resource.b"})):
        with pytest.raises(EffectDenied):
            execute(route, (Message("input", 7, "input"),), Workspace(), 2,
                    resolver=Kernel((caller, child)))
    assert child.accesses == []
    child.manifest = Manifest("expert", "1", child.manifest.contract,
                              effects=frozenset({"resource.a"}))
    child.operation = "resource.a"
    with effect_scope(frozenset({"resource.a"})):
        assert execute(route, (Message("input", 7, "input"),), Workspace(), 2,
                       resolver=Kernel((caller, child))).payload == 7


def test_denied_process_transition_preserves_cursor() -> None:
    module = Expert(Manifest("step", "1", Contract(("state",), "state"),
                              effects=frozenset({"resource.a"})), [])
    initial = Message("state", 7, "input")
    process = Process(Apply(module, (Given("state", 0),)), module.manifest.contract,
                      initial, Workspace())
    with effect_scope(frozenset()):
        with pytest.raises(EffectDenied):
            process.step((), budget=1)
    assert process.state is initial
    assert module.accesses == []


def test_failed_continuation_cleanup_retains_its_declaration() -> None:
    cleaned = []

    class Caller(Expert):
        def invoke(self, value: Any) -> Any:
            try:
                yield Request("missing", (("input", value),))
            finally:
                require_effect("resource.a")
                cleaned.append("closed")

    module = Caller(expert(frozenset({"resource.a"})).manifest, [])
    from nca.runtime import UnresolvedRequest
    with effect_scope(frozenset({"resource.a"})):
        with pytest.raises(UnresolvedRequest):
            run(module)
    assert cleaned == ["closed"]


def test_pure_experts_work_under_empty_host_policy() -> None:
    module = expert(frozenset())
    with effect_scope(frozenset()):
        assert effect_call(module.manifest.effects, lambda value: value, 9) == 9
