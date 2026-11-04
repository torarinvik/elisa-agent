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


@dataclass
class Component:
    manifest: Manifest
    operation: str | None = None
    accesses: int = 0

    def invoke(self, *values: Any) -> int:
        if self.operation is not None:
            require_effect(self.operation)
            self.accesses += 1
        return 7


def composed_component_case(kind: str, declared: bool) -> tuple[Any, Component]:
    from nca.learning.discovery import Corrected, Decoded, JointFeature
    from nca.learning.features import AppliedFeature
    from nca.learning.regional import RegionalPolicy

    allowed = frozenset({"resource.b"})

    def part(name: str, inputs: tuple[str, ...], output: str, bad: bool = False) -> Component:
        effects = allowed if not bad or declared else frozenset()
        return Component(Manifest(name, "1", Contract(inputs, output), effects=effects),
                         "resource.b" if bad else None)

    if kind.startswith("decoded"):
        feature = part("feature", ("input",), "feature", kind.endswith("feature"))
        head = part("head", ("feature",), "output", kind.endswith("head"))
        return Decoded(feature, head, Contract(("input",), "output")), feature if kind.endswith("feature") else head
    if kind == "joint":
        bad = part("left", ("input",), "feature", True)
        return JointFeature(bad, part("right", ("input",), "other"), 0), bad
    if kind.startswith("application"):
        feature = part("feature", ("input",), "feature", kind.endswith("feature"))
        other = part("other", ("input",), "other")
        head = part("head", ("feature", "other"), "output", kind.endswith("head"))
        return AppliedFeature(head, (feature, other)), feature if kind.endswith("feature") else head
    if kind.startswith("corrected"):
        feature = part("feature", ("input",), "feature", kind.endswith("feature"))
        incumbent = part("incumbent", ("input",), "output", kind.endswith("incumbent"))
        return Corrected(incumbent, feature, {}, 0), feature if kind.endswith("feature") else incumbent
    feature = part("feature", ("input",), "feature", kind.endswith("feature"))
    incumbent = part("incumbent", ("input",), "output", kind.endswith("incumbent"))
    specialist = part("specialist", ("input",), "output", kind.endswith("specialist"))
    chosen = feature if kind.endswith("feature") else incumbent if kind.endswith("incumbent") else specialist
    specialists = {} if kind.endswith("incumbent") else {7: specialist}
    return RegionalPolicy(incumbent, feature, specialists, 0), chosen


@pytest.mark.parametrize("kind", ["decoded-feature", "decoded-head", "joint",
                                   "application-feature", "application-head",
                                   "corrected-feature", "corrected-incumbent",
                                   "regional-feature", "regional-incumbent", "regional-specialist"])
@pytest.mark.parametrize("compiled", [False, True])
def test_composed_children_cannot_borrow_sibling_authority(kind: str, compiled: bool) -> None:
    for declared in (False, True):
        module, component = composed_component_case(kind, declared)
        route = Apply(module, (Given("input"),))

        def call() -> Any:
            if compiled:
                return compile_route(route, ("input",))([(3,)])[0]
            return execute(route, (Message("input", 3, "input"),), Workspace(), 1).payload

        with effect_scope(frozenset({"resource.b"})):
            if declared:
                assert call() == ((7, 7) if kind == "joint" else 7)
                assert component.accesses == 1
            else:
                with pytest.raises(EffectDenied):
                    call()
                assert component.accesses == 0


def test_training_observations_keep_source_and_teacher_declarations() -> None:
    from nca.effects import expert_scope
    from nca.learning.interfaces import fit_interface_bridge

    for bad_source in (False, True):
        bad = Component(Manifest("bad", "1", Contract(("input",), "feature"),
                                  effects=frozenset()), "resource.b")
        good = Component(Manifest("good", "1", Contract(("input",), "feature"),
                                   effects=frozenset({"resource.b"})))
        source, teacher = (bad, good) if bad_source else (good, bad)
        with effect_scope(frozenset({"resource.b"})), expert_scope(frozenset({"resource.b"})):
            with pytest.raises(EffectDenied):
                fit_interface_bridge(source, teacher, [(3,)], adapter_cost=0)
        assert bad.accesses == 0


def test_child_scoping_matches_the_finite_authority_model() -> None:
    from itertools import product
    from nca.effects import invoke_scoped

    sets = [frozenset(name for bit, name in enumerate(("resource.a", "resource.b")) if mask & (1 << bit))
            for mask in range(4)]
    for parent, child, sibling in product(sets, repeat=3):
        for operation in ("resource.a", "resource.b"):
            module = Component(Manifest("child", "1", Contract(("input",), "output"),
                                         effects=child), operation)
            expected = child | sibling <= parent and operation in child
            with effect_scope(parent):
                if expected:
                    assert effect_call(child | sibling, invoke_scoped, module, 3) == 7
                else:
                    with pytest.raises(EffectDenied):
                        effect_call(child | sibling, invoke_scoped, module, 3)
            assert module.accesses == int(expected)


def test_legacy_unrestricted_composition_still_scopes_its_known_child() -> None:
    from nca.learning.discovery import Decoded

    feature = Component(Manifest("feature", "1", Contract(("input",), "feature"), effects=None))
    head = Component(Manifest("head", "1", Contract(("feature",), "output"),
                               effects=frozenset({"resource.b"})), "resource.b")
    model = Decoded(feature, head, Contract(("input",), "output"))
    result = execute(Apply(model, (Given("input"),)), (Message("input", 3, "input"),), Workspace(), 1)
    assert result.payload == 7 and head.accesses == 1


@pytest.mark.parametrize("arity", [0, 1, 2])
@pytest.mark.parametrize("misbehaves", [False, True])
def test_certification_keeps_candidate_authority_separate_from_evaluator(
        arity: int, misbehaves: bool) -> None:
    from collections.abc import Hashable, Sequence
    from nca.abi import Module
    from nca.effects import expert_scope
    from nca.retention.acquisition import CertifiedAcquirer
    from nca.retention.sampled import decision_level, required_cases

    class Candidate:
        def __init__(self, contract: Contract) -> None:
            self.manifest = Manifest("candidate", "1", contract, effects=frozenset())
            self.accesses = 0

        def invoke(self, *values: Any) -> int:
            assert len(values) == arity
            if misbehaves:
                require_effect("audit.write")
                self.accesses += 1
            return 0

    contract = Contract(tuple(f"input-{i}" for i in range(arity)), "output")
    candidate = Candidate(contract)
    agreement_calls: list[int] = []

    def fit(signature: Contract, keys: Sequence[Hashable], labels: Sequence[Hashable]) -> Module:
        require_effect("audit.write")
        return candidate

    def sample(signature: Contract, count: int) -> list[tuple[Any, Any]]:
        require_effect("audit.write")
        return [(0 if arity == 1 else (0,) * arity, 0)] * count

    def agree(output: Any, label: Any) -> bool:
        require_effect("audit.write")
        agreement_calls.append(1)
        return bool(output == label)

    acquire = CertifiedAcquirer(fit, sample, train=1, tolerance=0.5, confidence=0.5, agree=agree)
    with effect_scope(frozenset({"audit.write"})), expert_scope(frozenset({"audit.write"})):
        if misbehaves:
            with pytest.raises(EffectDenied):
                acquire(contract)
            assert acquire.labels == 2 and agreement_calls == []
        else:
            assert acquire(contract) is candidate
            size = required_cases(0.5, decision_level(0.5, 0))
            assert acquire.labels == 1 + size and len(agreement_calls) == size
        require_effect("audit.write")  # Evaluator authority restores on success and failure.
    assert candidate.accesses == 0 and acquire.decisions == 1


@pytest.mark.parametrize("stage", ["invoke", "risk"])
def test_cross_audit_reference_callbacks_cannot_borrow_auditor_authority(stage: str) -> None:
    from nca.effects import expert_scope
    from nca.evidence import cross_audit
    from nca.runtime import Invocation

    class Reference:
        manifest = Manifest("reference", "1", Contract(("input",), "output"), effects=frozenset())
        accesses = 0

        def invoke(self, value: Any) -> int:
            if stage == "invoke":
                require_effect("audit.write")
                self.accesses += 1
            return 0

        def risk(self, output: Any, *values: Any) -> float:
            if stage == "risk":
                require_effect("audit.write")
                self.accesses += 1
            return 0.0

    reference = Reference()
    invocation = Invocation(reference, (0,), 0, 0.0)
    with effect_scope(frozenset({"audit.write"})), expert_scope(frozenset({"audit.write"})):
        with pytest.raises(EffectDenied):
            cross_audit((invocation,), reference, lambda a, b: a == b)
        require_effect("audit.write")
    assert reference.accesses == 0


def test_calibration_observations_scope_the_underlying_expert() -> None:
    from nca.effects import expert_scope
    from nca.ladder import Rung

    class Distribution:
        manifest = Manifest("distribution", "1", Contract(("input",), "weights"), effects=frozenset())
        accesses = 0

        def invoke(self, value: Any) -> tuple[float, ...]:
            require_effect("audit.write")
            self.accesses += 1
            return (0.25, 0.75)

    source = Distribution()
    with effect_scope(frozenset({"audit.write"})), expert_scope(frozenset({"audit.write"})):
        with pytest.raises(EffectDenied):
            Rung(source).observe(0)
        require_effect("audit.write")
    assert source.accesses == 0


def test_callback_paths_match_nested_finite_allowances() -> None:
    from itertools import product
    from nca.abi import Module
    from nca.effects import invoke_scoped

    @dataclass
    class Node:
        manifest: Manifest
        child: Module | None
        operation: str

        def invoke(self, value: Any) -> Any:
            if self.child is not None:
                return invoke_scoped(self.child, value)
            require_effect(self.operation)
            return 7

    sets = [frozenset(name for bit, name in enumerate(("resource.a", "resource.b")) if mask & (1 << bit))
            for mask in range(4)]
    for depth in range(1, 5):
        for declarations in product(sets, repeat=depth):
            for host, operation in product(sets, ("resource.a", "resource.b")):
                current = host
                admissible = True
                for declaration in declarations:
                    admissible &= declaration <= current
                    current &= declaration
                expected = admissible and operation in current
                node = None
                for declaration in reversed(declarations):
                    node = Node(Manifest("node", "1", Contract(("input",), "output"),
                                          effects=declaration), node, operation)
                assert node is not None
                with effect_scope(host):
                    if expected:
                        assert invoke_scoped(node, 3) == 7
                    else:
                        with pytest.raises(EffectDenied):
                            invoke_scoped(node, 3)


@pytest.mark.parametrize("declared", [False, True])
@pytest.mark.parametrize("own_manifest", [False, True])
def test_selective_session_invocation_keeps_originating_expert_authority(
        declared: bool, own_manifest: bool) -> None:
    from nca.effects import expert_scope
    from nca.ladder import Rung
    from nca.planner import plan_stable
    from nca.selective import solve

    accesses: list[str] = []

    class Source:
        manifest = Manifest("source", "1", Contract(("input",), "seq[item]"), effects=frozenset())

        def invoke(self, value: Any) -> list[Any]:
            return list(value)

    class Reader:
        manifest = Manifest("reader", "1", Contract(("item",), "weights"), effects=frozenset())

        def invoke(self, value: Any) -> tuple[float, ...]:
            return (0.1, 0.9)

    class Consumer:
        manifest = Manifest("consumer", "1", Contract(("seq[weights]",), "output"),
                            effects=frozenset({"audit.write"}) if declared else frozenset())

        def solve_session(self) -> Any:
            class Session:
                def invoke(self, value: Any) -> int:
                    require_effect("audit.write")
                    accesses.append("write")
                    return 7
            session = Session()
            if own_manifest:
                session.manifest = Manifest("session", "1", self.manifest.contract, effects=frozenset())
            return session

    reader = Reader()
    route = plan_stable([Source(), reader, Consumer()], ("input",), "output")
    assert route is not None
    with effect_scope(frozenset({"audit.write"})), expert_scope(frozenset({"audit.write"})):
        if declared and not own_manifest:
            assert solve(route, {"weights": [Rung(reader)]}, "a", 1.0).value == 7
        else:
            with pytest.raises(EffectDenied):
                solve(route, {"weights": [Rung(reader)]}, "a", 1.0)
        require_effect("audit.write")
    assert len(accesses) == int(declared and not own_manifest)
