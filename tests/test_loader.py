import random
from dataclasses import dataclass, field
from typing import Any, Callable

import pytest

from nca.abi import Contract, Manifest, Message
from nca.loader import ExpertStore, LazyExpert
from nca.planner import Plan, ProducerIndex, plan, plan_stable_indexed
from nca.runtime import execute
from nca.workspace import Workspace


@dataclass
class Fn:
    manifest: Manifest
    fn: Callable[..., Any] | None = field(repr=False, default=None)

    def invoke(self, *inputs: Any) -> Any:
        assert self.fn is not None
        return self.fn(*inputs)


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
