"""Continuation order and permission boundaries for unary feature spines."""

from dataclasses import replace
from itertools import product
from typing import Any

import pytest

from nca.abi import Contract, Manifest, Module
from nca.effects import EffectDenied, effect_call, effect_scope, expert_scope, invoke_scoped, require_effect
from nca.learning.discovery import Decoded


class Operation:
    def __init__(self, name: str, trace: list[str], effects: frozenset[str] = frozenset(),
                 required: str | None = None) -> None:
        self.name, self.trace, self.required = name, trace, required
        self.manifest = Manifest(name, "1", Contract(("value",), "value"), effects=effects)

    def invoke(self, value: int) -> int:
        if self.required is not None:
            require_effect(self.required)
        self.trace.append(self.name)
        return value + 1 if self.name == "add" else (-value if self.name == "negate" else value * 2)


def recursive(module: Module, *values: Any) -> Any:
    if type(module) is Decoded:
        return invoke_scoped(module.decoder, effect_call(
            module.feature.manifest.effects, recursive, module.feature, *values))
    return module.invoke(*values)


def test_all_small_chains_preserve_values_and_call_order() -> None:
    for depth in range(5):
        for names in product(("add", "negate", "double"), repeat=depth):
            trace: list[str] = []
            chain: Module = Operation("add", trace)
            for name in names:
                chain = Decoded(chain, Operation(name, trace), chain.manifest.contract)
            for value in (-2, 0, 3):
                expected = effect_call(chain.manifest.effects, recursive, chain, value)
                expected_trace = trace.copy()
                trace.clear()
                assert invoke_scoped(chain, value) == expected
                assert trace == expected_trace
                trace.clear()


def test_deep_spine_has_no_python_recursion_per_composition() -> None:
    trace: list[str] = []
    chain: Module = Operation("add", trace)
    for _ in range(1500):
        chain = Decoded(chain, Operation("add", trace), chain.manifest.contract)
    assert invoke_scoped(chain, 0) == 1501
    assert len(trace) == 1501


def test_deep_changing_declarations_restore_scopes_without_recursion() -> None:
    trace: list[str] = []
    names = frozenset(f"effect-{i}" for i in range(1100))
    chain: Module = Operation("add", trace)
    for name in sorted(names):
        chain = Decoded(chain, Operation("add", trace, frozenset({name}), name),
                        chain.manifest.contract)
    with effect_scope(names | {"host"}), expert_scope(names | {"host"}):
        assert invoke_scoped(chain, 0) == 1101
        require_effect("host")
    assert len(trace) == 1101


@pytest.mark.parametrize("failure", ["leaf", "inner", "outer", "narrowed"])
@pytest.mark.parametrize("iterative", [False, True])
def test_each_scope_restricts_authority_and_restores_host_after_failure(
        failure: str, iterative: bool) -> None:
    trace: list[str] = []
    leaf = Operation("add", trace, required="host" if failure == "leaf" else None)
    inner = Operation("add", trace, required="host" if failure == "inner" else None)
    outer = Operation("add", trace, required="host" if failure == "outer" else None)
    chain = Decoded(Decoded(leaf, inner, leaf.manifest.contract), outer, leaf.manifest.contract)
    if failure == "narrowed":
        leaf.manifest = replace(leaf.manifest, effects=frozenset({"operation"}))
        leaf.required = "operation"  # Inner's stale empty declaration cannot delegate this.
    with effect_scope({"host", "operation"}), expert_scope(frozenset({"host", "operation"})):
        with pytest.raises(EffectDenied):
            if iterative:
                invoke_scoped(chain, 1)
            else:
                effect_call(chain.manifest.effects, recursive, chain, 1)
        require_effect("host")
        require_effect("operation")


def test_overrides_are_opaque_and_cycles_restore_context() -> None:
    trace: list[str] = []
    leaf = Operation("add", trace)
    head = Operation("add", trace)
    opaque = Decoded(leaf, head, leaf.manifest.contract)
    opaque.invoke = lambda value: 100
    chain = Decoded(opaque, head, leaf.manifest.contract)
    assert invoke_scoped(chain, 0) == 101 and trace == ["add"]
    cyclic = Decoded(leaf, head, leaf.manifest.contract)
    cyclic.feature = cyclic
    with effect_scope({"host"}), expert_scope(frozenset({"host"})):
        with pytest.raises(ValueError, match="cyclic"):
            invoke_scoped(cyclic, 0)
        require_effect("host")


def test_inherited_and_overridden_subclasses_keep_normal_dispatch() -> None:
    trace: list[str] = []
    leaf, head = Operation("add", trace), Operation("add", trace)

    class Inherited(Decoded):
        pass

    class Overridden(Decoded):
        def invoke(self, value: int) -> int:
            return 100

    inherited = Inherited(leaf, head, leaf.manifest.contract)
    assert invoke_scoped(inherited, 0) == 2
    assert invoke_scoped(Decoded(inherited, head, leaf.manifest.contract), 0) == 3
    opaque = Overridden(leaf, head, leaf.manifest.contract)
    assert invoke_scoped(Decoded(opaque, head, leaf.manifest.contract), 0) == 101
