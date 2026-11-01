import random
from dataclasses import dataclass, field
from typing import Any, Callable

import pytest

from nca.abi import NOTHING, Contract, Manifest, Message, Request
from nca.loader import ExpertStore, LazyExpert, route_experts
from nca.index import ProducerIndex
from nca.planner import Apply, Given, Map, Plan, plan, plan_stable_indexed
from nca.runtime import execute
from nca.workspace import Workspace


@dataclass
class Fn:
    manifest: Manifest
    fn: Callable[..., Any] | None = field(repr=False, default=None)

    def invoke(self, *inputs: Any) -> Any:
        assert self.fn is not None
        return self.fn(*inputs)



def placeholder() -> Fn:
    manifest = Manifest("placeholder", "1", Contract((), "placeholder"))
    return Fn(manifest, lambda: None)


def random_library(rng: random.Random, size: int, types: list[str]) -> list[Fn]:
    modules = []
    for i in range(size):
        inputs = tuple(rng.sample(types, rng.randint(0, 2)))
        output = rng.choice(types + [f"seq[{t}]" for t in types[:2]])
        modules.append(Fn(Manifest(f"m{i}", "1.0.0", Contract(inputs, output))))
    return modules


def linear_stable(modules: list[Fn], available: tuple[str, ...], goal: str) -> Plan | None:
    for k in range(len(modules) + 1):
        result = plan(modules[:k], available, goal, 4)
        if result is not None:
            return result
    return None


def test_binary_search_matches_linear_layered_planning() -> None:
    rng = random.Random(0)
    types = [f"t{i}" for i in range(6)]
    for _ in range(300):
        modules = random_library(rng, rng.randint(0, 12), types)
        index = ProducerIndex(modules)
        available = tuple(rng.sample(types, 1))
        goal = rng.choice(types + ["seq[t0]"])
        assert plan_stable_indexed(index, available, goal, 4) == \
            linear_stable(modules, available, goal)


def test_only_route_experts_load_and_lru_evicts() -> None:
    store = ExpertStore(budget=200)
    loads = []

    def expert(module_id: str, inputs: tuple[str, ...], output: str,
               fn: Callable[..., Any] | None, size: int = 100) -> LazyExpert:
        manifest = Manifest(module_id, "1.0.0", Contract(inputs, output))
        return LazyExpert(manifest, lambda: loads.append(module_id) or Fn(manifest, fn),
                          size, store)

    a = expert("a", ("x",), "y", lambda v: v + 1)
    b = expert("b", ("y",), "z", lambda v: v * 2)
    decoys = [expert(f"d{i}", ("q",), "z", None) for i in range(50)]
    c = expert("c", ("x",), "w", lambda v: -v)
    modules = [a, b, *decoys, c]

    route = plan(modules, ("x",), "z")
    assert execute(route, {"x": Message("x", 3, "input")}, Workspace(), 8).payload == 8
    assert loads == ["a", "b"]

    route_w = plan(modules, ("x",), "w")
    execute(route_w, {"x": Message("x", 3, "input")}, Workspace(), 8)
    assert loads == ["a", "b", "c"] and store.stats.evictions == 1
    assert store.resident_bytes <= 200

    with pytest.raises(MemoryError):
        store.acquire(expert("huge", (), "h", None, size=300))


def reference_plan(modules: list[Fn], available: tuple[str, ...], goal: str,
                   fuel: int) -> Plan | None:
    """Unpruned, unmemoized transcription of ``NCA.plan``."""
    from nca.abi import elem_type, seq_type
    from nca.planner import Apply, Given, Map, elem_candidates

    if fuel == 0:
        return None
    if goal in available:
        return Given(goal)
    for module in modules:
        if module.manifest.contract.output != goal:
            continue
        args = [reference_plan(modules, available, i, fuel - 1)
                for i in module.manifest.contract.inputs]
        if all(a is not None for a in args):
            return Apply(module, tuple(args))
    element_goal = elem_type(goal)
    if element_goal is None:
        return None
    for element in elem_candidates(modules, available):
        body = reference_plan(modules, (element,), element_goal, fuel - 1)
        source = reference_plan(modules, available, seq_type(element), fuel - 1)
        if body is not None and source is not None:
            return Map(element, body, source)
    return None


def test_pruned_memoized_planner_matches_lean_reference() -> None:
    rng = random.Random(1)
    types = [f"t{i}" for i in range(6)]
    for _ in range(500):
        modules = random_library(rng, rng.randint(0, 10), types)
        available = tuple(rng.sample(types, rng.randint(1, 2)))
        goal = rng.choice(types + ["seq[t0]", "seq[t1]"])
        assert plan(modules, available, goal, 4) == reference_plan(modules, available, goal, 4)


def test_route_aware_eviction_keeps_shared_experts() -> None:
    from nca.loader import route_experts

    def run(route_aware: bool) -> int:
        store = ExpertStore(budget=200)

        def expert(module_id: str, inputs: tuple[str, ...], output: str,
                   fn: Callable[..., Any]) -> LazyExpert:
            manifest = Manifest(module_id, "1.0.0", Contract(inputs, output))
            return LazyExpert(manifest, lambda: Fn(manifest, fn), 100, store)

        # The shared expert runs first in one route and second in the other,
        # so recency marks it as the eviction victim on every switch.
        modules = [expert("shared", ("text",), "int", int),
                   expert("show", ("int",), "out", str),
                   expert("spell", ("word",), "text", lambda w: str(len(w)))]
        routes = [(plan(modules, ("text",), "out"), {"text": Message("text", "4", "input")}),
                  (plan(modules, ("word",), "int"), {"word": Message("word", "abc", "input")})]
        assert {e.manifest.module_id for e in route_experts(routes[0][0])} == {"shared", "show"}
        for _ in range(5):
            for route, inputs in routes:
                if route_aware:
                    store.prepare(route)
                execute(route, inputs, Workspace(), budget=8)
        return store.stats.loads

    # Route-aware: the first two loads, then one missing expert per switch.
    assert run(True) == 2 + 9
    assert run(False) > run(True)


def test_conflicting_live_expert_references_are_rejected() -> None:
    store = ExpertStore(budget=1)
    manifest = Manifest("expert", "1", Contract(("input",), "output"))
    old = LazyExpert(manifest, lambda: Fn(manifest, lambda x: "old"), 1, store)
    new = LazyExpert(manifest, lambda: Fn(manifest, lambda x: "new"), 1, store)
    with pytest.raises(ValueError, match="conflicting expert definitions"):
        store.prepare(Apply(old, (Apply(new, (Given("input"),)),)))
    assert store.resident_bytes == 0
    assert old.invoke(None) == "old"
    with pytest.raises(ValueError, match="conflicting expert definitions"):
        new.invoke(None)
    with pytest.raises(ValueError, match="conflicting expert definitions"):
        store.prepare(Apply(new, (Given("input"),)))
    assert old.invoke(None) == "old"
    # Once the old implementation is evicted, a new definition can load safely.
    other_manifest = Manifest("other", "1", Contract((), "other"))
    other = LazyExpert(other_manifest, lambda: Fn(other_manifest, lambda: None), 1, store)
    other.invoke()
    assert new.invoke(None) == "new"


def test_unfit_route_does_not_evict_or_replace_existing_pins() -> None:
    store = ExpertStore(budget=2)
    manifest = Manifest("resident", "1", Contract(("x",), "y"))
    resident = LazyExpert(manifest, lambda: Fn(manifest, lambda x: x), 1, store)
    route = Apply(resident, (Given("x"),))
    store.prepare(route)
    before = (list(store.resident), store.pinned, store.stats.evictions)
    huge_manifest = Manifest("huge", "1", Contract(("x",), "z"))
    huge = LazyExpert(huge_manifest, lambda: Fn(huge_manifest, lambda x: x), 3, store)
    with pytest.raises(MemoryError, match="route requires 3 B"):
        store.prepare(Apply(huge, (Given("x"),)))
    assert (list(store.resident), store.pinned, store.stats.evictions) == before
    assert resident.invoke("ok") == "ok"


@pytest.mark.parametrize("invalid", [-1, 0.5, float("nan"), float("inf"), True])
def test_store_rejects_invalid_memory_accounting(invalid: Any) -> None:
    with pytest.raises(ValueError, match="store budget"):
        ExpertStore(invalid)
    store = ExpertStore(1)
    with pytest.raises(ValueError, match="store budget"):
        store.budget = invalid
    assert store.budget == 1
    manifest = Manifest("sample", "1", Contract((), "output"))
    with pytest.raises(ValueError, match="expert size"):
        LazyExpert(manifest, lambda: None, invalid, store)
    expert = LazyExpert(manifest, lambda: Fn(manifest, lambda: None), 0, store)
    with pytest.raises(AttributeError):
        expert.size = 2


def test_budget_cannot_drop_below_resident_bytes() -> None:
    store = ExpertStore(2)
    manifest = Manifest("sample", "1", Contract((), "output"))
    LazyExpert(manifest, lambda: Fn(manifest, lambda: None), 2, store).invoke()
    with pytest.raises(ValueError, match="less than resident"):
        store.budget = 1
    assert store.budget == 2 and store.resident_bytes == 2
    store.budget = None
    assert store.budget is None


def test_failed_load_releases_partial_route_pins() -> None:
    store = ExpertStore(2)
    def make(name: str, loader: Callable[[], Any]) -> LazyExpert:
        return LazyExpert(Manifest(name, "1", Contract((), name)), loader, 1, store)
    previous = make("previous", placeholder)
    store.prepare(Apply(previous, ()))
    partial = make("partial", placeholder)
    def fail() -> Any:
        raise RuntimeError("load failed")
    broken = make("broken", fail)
    with pytest.raises(RuntimeError, match="load failed"):
        store.prepare(Apply(partial, (Apply(broken, ()),)))
    assert store.pinned == frozenset()
    assert list(store.resident) == ["partial@1"]
    extra = make("extra", placeholder)
    store.acquire(extra)
    assert store.resident_bytes <= 2


def test_failed_route_preserves_only_surviving_old_pins() -> None:
    store = ExpertStore(3)
    def expert(name: str, loader: Callable[[], Any]) -> LazyExpert:
        return LazyExpert(Manifest(name, "1", Contract((), name)), loader, 1, store)
    shared = expert("shared", placeholder)
    old_only = expert("old", placeholder)
    store.prepare(Apply(shared, (Apply(old_only, ()),)))
    partial = expert("partial", placeholder)
    def fail() -> Any:
        raise RuntimeError("load failed")
    broken = expert("broken", fail)
    with pytest.raises(RuntimeError, match="load failed"):
        store.prepare(Apply(shared, (Apply(partial, ()), Apply(broken, ()))))
    assert store.pinned == frozenset({"shared@1"})
    assert set(store.resident) == {"shared@1", "partial@1"}
    assert store.resident_bytes == 2


def test_resident_accounting_tracks_eviction_and_cannot_be_mutated_externally() -> None:
    store = ExpertStore(3)
    def make(name: str, size: int) -> LazyExpert:
        manifest = Manifest(name, "1", Contract((), name))
        return LazyExpert(manifest, lambda: Fn(manifest, lambda: name), size, store)
    first, second = make("first", 2), make("second", 2)
    first.invoke()
    assert store.resident_bytes == sum(size for _, size in store.resident.values()) == 2
    view = store.resident
    with pytest.raises(TypeError):
        view["fake@1"] = (object(), 100)
    second.invoke()
    assert list(view) == ["second@1"]
    assert store.resident_bytes == sum(size for _, size in view.values()) == 2


def test_evicts_oldest_unpinned_experts_until_enough_space() -> None:
    store = ExpertStore(5)
    def expert(name: str, size: int) -> LazyExpert:
        manifest = Manifest(name, "1", Contract((), name))
        return LazyExpert(manifest, lambda: Fn(manifest, lambda: name), size, store)
    pinned, first, second, large = (expert("pinned", 1), expert("first", 1),
                                     expert("second", 1), expert("large", 3))
    store.prepare(Apply(pinned, ()))
    first.invoke()
    second.invoke()
    large.invoke()
    assert list(store.resident) == ["pinned@1", "second@1", "large@1"]
    assert store.resident_bytes == 5 and store.stats.evictions == 1
    larger = expert("larger", 4)
    larger.invoke()
    assert list(store.resident) == ["pinned@1", "larger@1"]
    assert store.resident_bytes == 5 and store.stats.evictions == 3


def test_failed_acquire_preserves_evictable_residents() -> None:
    store = ExpertStore(3)
    def expert(name: str, size: int) -> LazyExpert:
        manifest = Manifest(name, "1", Contract((), name))
        return LazyExpert(manifest, lambda: Fn(manifest, lambda: name), size, store)
    pinned, spare, incoming = expert("pinned", 2), expert("spare", 1), expert("incoming", 2)
    store.prepare(Apply(pinned, ()))
    spare.invoke()
    before = (list(store.resident), store.resident_bytes, store.stats.evictions)
    with pytest.raises(MemoryError, match="pinned experts"):
        incoming.invoke()
    assert (list(store.resident), store.resident_bytes, store.stats.evictions) == before


def test_invalid_loaded_implementation_is_not_cached() -> None:
    store = ExpertStore(1)
    manifest = Manifest("bad", "1", Contract((), "output"))
    expert = LazyExpert(manifest, lambda: object(), 1, store)
    with pytest.raises(TypeError, match="must return an implementation with an invoke method"):
        expert.invoke()
    assert not store.resident and store.resident_bytes == 0
    assert store.stats.loads == 0 and store.stats.loaded_bytes == 0


@pytest.mark.parametrize("operation", ["acquire", "prepare", "budget"])
def test_loader_cannot_reenter_own_store(operation: str) -> None:
    store = ExpertStore(1)
    manifest = Manifest("nested", "1", Contract((), "output"))
    nested = LazyExpert(manifest, placeholder, 1, store)

    def load() -> Fn:
        if operation == "acquire":
            store.acquire(nested)
        elif operation == "prepare":
            store.prepare(Apply(nested, ()))
        else:
            store.budget = 0
        return placeholder()

    outer = LazyExpert(Manifest("outer", "1", Contract((), "output")), load, 1, store)
    with pytest.raises(RuntimeError, match="cannot re-enter"):
        outer.invoke()
    assert not store.resident and store.resident_bytes == 0 and store.budget == 1
    assert store.stats.loads == 0
    store.acquire(nested)
    assert store.resident_bytes == 1


def test_loader_can_use_another_store() -> None:
    outer_store, inner_store = ExpertStore(1), ExpertStore(1)
    inner = LazyExpert(Manifest("inner", "1", Contract((), "output")),
                       placeholder, 1, inner_store)
    def load() -> Fn:
        inner_store.acquire(inner)
        return placeholder()
    outer = LazyExpert(Manifest("outer", "1", Contract((), "output")),
                       load, 1, outer_store)
    outer_store.acquire(outer)
    assert outer_store.resident_bytes == inner_store.resident_bytes == 1


def test_foreign_expert_is_rejected_before_store_changes() -> None:
    store, foreign_store = ExpertStore(2), ExpertStore(2)
    def expert(name: str, owner: ExpertStore) -> LazyExpert:
        return LazyExpert(Manifest(name, "1", Contract((), name)), placeholder, 1, owner)
    resident = expert("resident", store)
    store.prepare(Apply(resident, ()))
    local, foreign = expert("local", store), expert("foreign", foreign_store)
    before = (list(store.resident), store.pinned, store.resident_bytes, store.stats.loads)
    with pytest.raises(ValueError, match="different store"):
        store.prepare(Apply(local, (Apply(foreign, ()),)))
    with pytest.raises(ValueError, match="different store"):
        store.acquire(foreign)
    assert (list(store.resident), store.pinned, store.resident_bytes, store.stats.loads) == before
    assert not foreign_store.resident
    foreign.invoke()
    assert list(foreign_store.resident) == ["foreign@1"]


def test_lazy_expert_identity_and_store_are_stable() -> None:
    store = ExpertStore(1)
    manifest = Manifest("original", "1", Contract((), "output"))
    expert = LazyExpert(manifest, placeholder, 1, store)
    store.prepare(Apply(expert, ()))
    with pytest.raises(AttributeError):
        expert.store = ExpertStore(1)
    with pytest.raises(AttributeError):
        expert.manifest = Manifest("replacement", "1", Contract((), "output"))
    assert expert.store is store and expert.manifest is manifest
    expert.invoke()
    assert list(store.resident) == [manifest.ref] and store.stats.loads == 1


def test_lazy_demand_rule_skips_unneeded_expert_without_loading_it() -> None:
    store = ExpertStore(2)
    loads: list[str] = []
    source_manifest = Manifest("source", "1", Contract((), "unused"))
    consumer_manifest = Manifest("consumer", "1", Contract(("unused",), "output"))
    source = LazyExpert(source_manifest,
                        lambda: loads.append("source") or Fn(source_manifest, lambda: 42),
                        1, store)
    consumer = LazyExpert(consumer_manifest,
                          lambda: loads.append("consumer") or Fn(consumer_manifest, lambda _: "ok"),
                          1, store, demand=lambda _index, _demand: NOTHING)
    route = Apply(consumer, (Apply(source, ()),))
    store.prepare(route, eager=False)
    assert not store.resident and store.pinned == frozenset({source_manifest.ref, consumer_manifest.ref})
    result = execute(route, {}, Workspace(), 2)
    assert result.payload == "ok"
    assert loads == ["consumer"] and list(store.resident) == [consumer_manifest.ref]

    eager_store = ExpertStore(2)
    eager_source = LazyExpert(source_manifest,
                              lambda: loads.append("eager source") or Fn(source_manifest, lambda: 42),
                              1, eager_store)
    eager_consumer = LazyExpert(consumer_manifest,
                                lambda: Fn(consumer_manifest, lambda _: "ok"),
                                1, eager_store, demand=lambda _index, _demand: NOTHING)
    route = Apply(eager_consumer, (Apply(eager_source, ()),))
    eager_store.prepare(route)
    assert execute(route, {}, Workspace(), 2).payload == result.payload
    assert eager_store.stats.loaded_bytes == 2 and store.stats.loaded_bytes == 1


def test_deferred_preparation_preserves_route_pins_and_checks_budget() -> None:
    store = ExpertStore(2)
    def expert(name: str, size: int = 1) -> LazyExpert:
        return LazyExpert(Manifest(name, "1", Contract((), name)), placeholder, size, store)
    spare, first, second, outsider = (expert("spare"), expert("first"),
                                      expert("second"), expert("outsider"))
    spare.invoke()
    route = Apply(first, (Apply(second, ()),))
    store.prepare(route, eager=False)
    assert list(store.resident) == ["spare@1"]
    first.invoke()
    second.invoke()
    assert set(store.resident) == {"first@1", "second@1"}
    with pytest.raises(MemoryError, match="pinned experts"):
        outsider.invoke()
    before = (list(store.resident), store.pinned)
    with pytest.raises(MemoryError, match="route requires"):
        store.prepare(Apply(expert("huge", 3), ()), eager=False)
    assert (list(store.resident), store.pinned) == before


def test_deferred_pins_reserve_expert_identity_and_budget() -> None:
    store = ExpertStore(2)
    manifest = Manifest("reserved", "1", Contract((), "output"))
    reserved = LazyExpert(manifest, placeholder, 2, store)
    conflicting = LazyExpert(manifest, placeholder, 1, store)
    store.prepare(Apply(reserved, ()), eager=False)
    with pytest.raises(ValueError, match="conflicting expert"):
        conflicting.invoke()
    with pytest.raises(ValueError, match="pinned route"):
        store.budget = 1
    assert not store.resident and store.budget == 2
    reserved.invoke()
    assert store.resident_bytes == 2


def test_deferred_route_fits_in_any_invocation_order() -> None:
    rng = random.Random(711)
    for _ in range(100):
        sizes = [rng.randrange(1, 5) for _ in range(rng.randrange(1, 9))]
        store = ExpertStore(sum(sizes))
        def expert(name: str, size: int) -> LazyExpert:
            return LazyExpert(Manifest(name, "1", Contract((), name)), placeholder, size, store)
        outsider = expert("outsider", store.budget)
        outsider.invoke()
        route_experts = [expert(f"route-{i}", size) for i, size in enumerate(sizes)]
        route = Apply(route_experts[0], tuple(Apply(e, ()) for e in route_experts[1:]))
        store.prepare(route, eager=False)
        rng.shuffle(route_experts)
        for current in route_experts:
            current.invoke()
            assert store.resident_bytes <= store.budget
        assert set(store.resident) == {e.manifest.ref for e in route_experts}


def test_route_expert_scan_handles_deep_routes_and_preserves_order() -> None:
    store = ExpertStore(4)
    def expert(name: str) -> LazyExpert:
        return LazyExpert(Manifest(name, "1", Contract((), name)), placeholder, 1, store)
    outer, source, body, slot = (expert("outer"), expert("source"),
                                 expert("body"), expert("slot"))
    route = Apply(outer, (Map("element", Apply(body, ()), Apply(source, ())),),
                  (Apply(slot, ()),))
    for _ in range(3_000):
        route = Apply(outer, (route,))
    found = list(route_experts(route))
    assert found == [outer] * 3_001 + [source, body, slot]
    store.prepare(route, eager=False)
    assert store.pinned == frozenset({"outer@1", "source@1", "body@1", "slot@1"})


def test_failed_eager_preparation_restores_pending_pins() -> None:
    store = ExpertStore(2)
    manifest = Manifest("pending", "1", Contract((), "output"))
    pending = LazyExpert(manifest, placeholder, 1, store)
    store.prepare(Apply(pending, ()), eager=False)
    def fail() -> Any:
        raise RuntimeError("failed")
    broken = LazyExpert(Manifest("broken", "1", Contract((), "output")), fail, 1, store)
    with pytest.raises(RuntimeError, match="failed"):
        store.prepare(Apply(broken, ()))
    assert store.pinned == frozenset({manifest.ref})
    with pytest.raises(ValueError, match="conflicting expert"):
        LazyExpert(manifest, placeholder, 1, store).invoke()
    pending.invoke()


def test_lazy_relevance_rule_skips_unneeded_request() -> None:
    store = ExpertStore(1)
    request_manifest = Manifest("request", "1", Contract((), "value"))
    consumer_manifest = Manifest("consumer", "1", Contract(("value",), "output"))
    requester = Fn(request_manifest, lambda: Request("value", {}, provisional=5))
    consumer = LazyExpert(consumer_manifest, lambda: Fn(consumer_manifest, lambda value: value),
                          1, store, relevant=lambda _index, _values: False)
    result = execute(Apply(consumer, (Apply(requester, ()),)), {}, Workspace(), 2)
    assert result.payload == 5 and store.stats.loads == 1


def test_scaling_wrapper_preserves_runtime_rules() -> None:
    pytest.importorskip("torch")
    from nca.scaling import ALGORITHM_BYTES, algorithm_expert

    class Consumer:
        manifest = Manifest("consumer", "1", Contract(("unused",), "output"))

        def demand(self, index: int, demand: Any) -> Any:
            return NOTHING

        def relevant(self, index: int, provisional: list[Any]) -> bool:
            return False

        def invoke(self, value: Any) -> str:
            return "ok"

    store = ExpertStore(ALGORITHM_BYTES)
    wrapped = algorithm_expert(Consumer(), store)
    assert wrapped.demand(0, None) == NOTHING
    assert wrapped.relevant(0, []) is False
    source = Fn(Manifest("source", "1", Contract((), "unused")),
                lambda: pytest.fail("unused input was evaluated"))
    assert execute(Apply(wrapped, (Apply(source, ()),)), {}, Workspace(), 2).payload == "ok"
