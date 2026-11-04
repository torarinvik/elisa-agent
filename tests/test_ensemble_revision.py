"""Whole-candidate revision and end-to-end correction semantics (§31.11)."""

from itertools import product
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
from nca.runtime import execute
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
