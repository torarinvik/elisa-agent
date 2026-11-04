"""Whole-candidate revision and end-to-end correction semantics (§31.11)."""

from itertools import product
from pathlib import Path
from typing import Any

import pytest

from nca.abi import Contract, Manifest, Message, Module, Request
from nca.cache import ResultCache
from nca.kernel import Kernel
from nca.learning.discovery import Corrected, decoder_object, fit_decoder
from nca.objects import Composite, Store
from nca.packages import install
from nca.planner import Apply, Given, Plan
from nca.retention.ensembles import EnsembleSearch, VoteCase, VoteFailure
from nca.runtime import BudgetExceeded, execute
from nca.workspace import Workspace
from test_vote_feedback import Lookup


class InputKey:
    manifest = Manifest("key", "1", Contract(("s",), "s"), effects=frozenset())

    def invoke(self, value: Any) -> Any:
        return value


def test_whole_revision_learns_endpoints_and_preserves_the_incumbent() -> None:
    base = Lookup({})
    original = Apply(base, (Given("s"),))
    cursor = 0
    sizes: list[int] = []

    def propose(cap: int, failures: tuple[VoteFailure, ...]) -> tuple[Plan, ...]:
        sizes.append(len(failures))
        corrections = {}
        for failure in failures:
            inputs, label = failure.case
            assert not isinstance(inputs, dict)
            corrections[inputs[0].payload] = label
        model = Corrected(base, InputKey(), corrections, 0.0)
        return (Apply(model, (Given("s"),)),)

    def sample(count: int) -> list[VoteCase]:
        nonlocal cursor
        cases = [((Message("s", i % 2, "input"),), i % 2)
                 for i in range(cursor, cursor + count)]
        cursor += count
        return cases

    search = EnsembleSearch(counts=(1, 1, 1), tolerance=0.1, confidence=0.05, budget=2)
    result = search.revise(Contract(("s",), "g"), propose, sample)
    assert result is not None and len(result.routes) == 1
    assert sizes == [0, 1, 2] and search.requests == search.tests == 3
    assert base.table == {} and original.module.invoke(0) == "unlearned"


@pytest.mark.parametrize("count", [0, 2])
def test_revision_respects_declared_family_cap(count: int) -> None:
    route = Apply(Lookup({0: 0}), (Given("s"),))
    search = EnsembleSearch(counts=(1,), tolerance=0.1, confidence=0.05, budget=2)
    with pytest.raises(ValueError, match="declared cap"):
        search.revise(Contract(("s",), "g"), lambda cap, failures: [route] * count,
                      lambda n: [((Message("s", 0, "input"),), 0)] * n)
    assert search.labels == 0


def test_complete_key_correction_matches_the_pointwise_proof() -> None:
    for truth in product(range(2), repeat=4):
        for base_values in product(range(2), repeat=4):
            base = Lookup(dict(enumerate(base_values)))
            for point in range(4):
                corrected = Corrected(base, InputKey(), {point: truth[point]}, 0.0)
                for x in range(4):
                    if x != point:
                        assert corrected.invoke(x) == base_values[x]
                    if corrected.invoke(x) != truth[x]:
                        assert base_values[x] != truth[x] and x != point


def test_public_export_and_kernel_accept_a_larger_planning_budget() -> None:
    modules: list[Module] = [fit_decoder(Contract((f"t{i}",), f"t{i + 1}"), [i], [i + 1], cost=1.0)
                             for i in range(9)]
    contract = Contract(("t0",), "t9")
    store = Store()
    references = tuple(store.put(decoder_object(m, size=0)) for m in modules)
    reference = store.put(Composite("deep", "1", references, exports=(contract,), effects=frozenset()))
    with pytest.raises(ValueError, match="cannot implement"):
        install(store, reference)
    expert = install(store, reference, budget=20, fuel=12)[0]
    assert expert.invoke(0) == 9
    kernel = Kernel(modules, fuel=12)
    assert kernel.resolve(Request("t9", (("t0", 0),)), ()) is not None


def test_export_cache_distinguishes_planning_context_and_keeps_binding_refutation() -> None:
    store = Store()
    modules = [fit_decoder(Contract((f"t{i}",), f"t{i + 1}"), [i], [i + 1], cost=1.0)
               for i in range(9)]
    modules.append(fit_decoder(Contract(("t0",), "t9"), [0], [99], cost=1.0))
    refs = tuple(store.put(decoder_object(module, size=0)) for module in modules)
    ref = store.put(Composite("alternatives", "1", refs,
                              exports=(Contract(("t0",), "t9"),), effects=frozenset()))
    shallow = install(store, ref, fuel=8)[0]
    deep = install(store, ref, fuel=12)[0]
    assert shallow.identity == deep.identity and shallow.cache_identity != deep.cache_identity
    from nca.packages import resolve_binding

    assert resolve_binding(store, ref, 0, shallow).invoke(0) == 99
    with pytest.raises(ValueError, match="content identity"):
        resolve_binding(store, ref, 0, deep)
    constrained = install(store, ref, budget=1)[0]
    assert constrained.manifest == shallow.manifest
    with pytest.raises(ValueError, match="execution configuration"):
        resolve_binding(store, ref, 0, constrained)
    cache = ResultCache()
    inputs = (Message("t0", 0, "input"),)
    for expert, expected in ((shallow, 99), (deep, 9), (shallow, 99), (deep, 9)):
        route = Apply(expert, (Given("t0"),))
        assert execute(route, inputs, Workspace(), 30, cache=cache).payload == expected
    assert cache.stats.hits == 2
    refuted = ResultCache(refuted=(deep.identity,))
    route = Apply(deep, (Given("t0"),))
    execute(route, inputs, Workspace(), 30, cache=refuted)
    assert len(refuted) == 0


@pytest.mark.parametrize("fuel", [8, 12])
@pytest.mark.parametrize("budget", [0, 20])
def test_configured_exports_retain_route_and_refusal(tmp_path: Path, fuel: int, budget: int) -> None:
    from nca.learning.acquisition_objects import store_acquired_model
    from nca.packages import Export

    store = Store()
    modules = [fit_decoder(Contract((f"t{i}",), f"t{i + 1}"), [i], [i + 1], cost=1.0)
               for i in range(9)]
    modules.append(fit_decoder(Contract(("t0",), "t9"), [0], [99], cost=1.0))
    refs = tuple(store.put(decoder_object(module, size=0)) for module in modules)
    composite = Composite("configured", "1", refs,
                          exports=(Contract(("t0",), "t9"),), effects=frozenset())
    original = Export(composite, 0, modules, fuel=fuel, budget=budget, length=3)

    def no_opaque(module: Module) -> tuple[str, int]:
        raise AssertionError("known graph must be retained without an opaque binding")

    binding = store_acquired_model(store, original, no_opaque, size=lambda module: 0)
    store.save(tmp_path)
    restored = install(Store.open(tmp_path), binding[0])[binding[1]]
    assert restored.accounts_inside and restored.manifest == original.manifest
    for candidate in (original, restored):
        if budget == 0:
            with pytest.raises(BudgetExceeded) as failure:
                candidate.invoke(0)
            assert "budget" in str(failure.value).lower()
        else:
            assert candidate.invoke(0) == (99 if fuel == 8 else 9)
    implementation = restored.store.acquire(restored)
    assert (implementation.fuel, implementation.budget, implementation.length) == (fuel, budget, 3)


def test_nested_configured_exports_keep_the_actual_members(tmp_path: Path) -> None:
    from nca.learning.acquisition_objects import store_acquired_model
    from nca.packages import Export

    store = Store()
    head = fit_decoder(Contract(("x",), "y"), [0], [7], cost=1.0)
    inner = Export(Composite("inner", "1", (), exports=(head.manifest.contract,),
                             effects=frozenset()), 0, [head], fuel=11, budget=4)
    outer = Export(Composite("outer", "1", (), exports=(head.manifest.contract,),
                             effects=frozenset()), 0, [inner], fuel=13, budget=6)

    def no_opaque(module: Module) -> tuple[str, int]:
        raise AssertionError("nested members are known")

    reference, index = store_acquired_model(store, outer, no_opaque, size=lambda module: 0)
    store.save(tmp_path)
    restored = install(Store.open(tmp_path), reference)[index]
    assert restored.invoke(0) == outer.invoke(0) == 7
    implementation = restored.store.acquire(restored)
    child = implementation.members[0]
    nested = child.store.acquire(child)
    assert (nested.fuel, nested.budget) == (11, 4)


class ExportRisk:
    manifest = Manifest("reported-export-member", "1", Contract(("x",), "y"),
                        effects=frozenset())

    def invoke(self, value: int) -> int:
        return value

    def risk(self, output: int, *values: int) -> float:
        return 0.25


@pytest.mark.parametrize("compiled", [False, True])
def test_retained_export_keeps_internal_ledger_on_cache_replay(tmp_path: Path, compiled: bool) -> None:
    from nca.compile import compile_route
    from nca.learning.acquisition_objects import store_acquired_model
    from nca.objects import Primitive
    from nca.packages import Export
    from nca.runtime import RiskLedger

    store = Store()
    ref = store.put(Primitive(ExportRisk.manifest, f"{__name__}:ExportRisk"))
    member = install(store, ref)[0]
    expert = Export(Composite("risk", "1", (ref,), exports=(member.manifest.contract,),
                              effects=frozenset()), 0, [member], fuel=11, budget=3)
    saved, index = store_acquired_model(store, expert, lambda module: (ref, 0), size=lambda module: 0)
    store.save(tmp_path)
    restored = install(Store.open(tmp_path), saved)[index]
    cache = ResultCache()
    route = Apply(restored, (Given("x"),))
    # Warm without a ledger, then require fresh accounting on both replays.
    execute(route, (Message("x", 7, "input"),), Workspace(), 3, cache=cache)
    for _ in range(2):
        ledger = RiskLedger()
        if compiled:
            assert compile_route(route, ("x",))([(7,)], cache=cache, ledgers=[ledger]) == [7]
        else:
            assert execute(route, (Message("x", 7, "input"),), Workspace(), 3,
                           cache=cache, ledger=ledger).payload == 7
        assert ledger.certified and ledger.charge == 0.25 and len(ledger.entries) == 1


def test_retained_export_keeps_requirement_fillings(tmp_path: Path) -> None:
    from nca.learning.acquisition_objects import store_acquired_model
    from test_packages import counting_package, primitive

    store = Store()
    ref = counting_package(store)
    original = install(store, ref, fuel=11, budget=20, length=3)[0]

    def bind(module: Module) -> tuple[str, int]:
        return module.identity, 0

    saved, index = store_acquired_model(store, original, bind, size=lambda module: 0)
    store.save(tmp_path)
    reopened = Store.open(tmp_path)
    restored = install(reopened, saved)[index]
    filling_ref = reopened.put(primitive("count-letters", ["word.v1"], "int.v1"))
    filling = install(reopened, filling_ref)[0]
    assert restored.invoke(filling.invoke, "one two!") == original.invoke(filling.invoke, "one two!") == 6
    assert restored.manifest.calls == original.manifest.calls
