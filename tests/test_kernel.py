from dataclasses import dataclass, field
from typing import Any, Callable

import numpy as np
import pytest

from nca.abi import Contract, Manifest, Message
from nca.planner import Apply, Given, Map, plan, plan_stable, plan_stable_indexed
from nca.registry import Registry
from nca.router import infer
from nca.runtime import BudgetExceeded, execute
from nca.workspace import Workspace

TEXT = "text.v1"
INT = "int.v1"
PAIR = "int.pair.v1"


@dataclass
class Fn:
    manifest: Manifest
    fn: Callable[..., Any] = field(repr=False)

    def invoke(self, *inputs: Any) -> Any:
        return self.fn(*inputs)


def fn(module_id: str, inputs: list[str], output: str, f: Callable[..., Any],
       version: str = "1.0.0") -> Fn:
    return Fn(Manifest(module_id, version, Contract(tuple(inputs), output)), f)


def arithmetic_registry() -> Registry:
    registry = Registry()
    registry.install(fn("parse-int", [TEXT], INT, int))
    registry.install(fn("add", [INT, INT], INT, lambda a, b: a + b))
    return registry


def test_planner_composes_by_type() -> None:
    registry = arithmetic_registry()
    result = plan(registry.modules(), (TEXT,), INT)
    assert isinstance(result, Apply)
    assert result.module.manifest.module_id == "parse-int"
    assert result.args == (Given(TEXT),)


def test_planner_fails_without_capability() -> None:
    assert plan(arithmetic_registry().modules(), (TEXT,), PAIR) is None


def test_execute_records_provenance() -> None:
    registry = Registry()
    registry.install(fn("pair", [TEXT], PAIR, lambda s: tuple(map(int, s.split("+")))))
    registry.install(fn("sum", [PAIR], INT, lambda p: p[0] + p[1]))
    workspace = Workspace()
    source = Message(TEXT, "7+5", producer="input")

    graph = plan(registry.modules(), (TEXT,), INT)
    result = execute(graph, {TEXT: source}, workspace, budget=10)

    assert result.payload == 12
    chain = [m.producer for m in workspace.provenance(result.message_id)]
    assert chain == ["input", "pair@1.0.0", "sum@1.0.0"]


def test_replacement_requires_same_contract() -> None:
    registry = arithmetic_registry()
    registry.replace(fn("parse-int", [TEXT], INT, lambda s: int(s.strip()), version="2.0.0"))
    graph = plan(registry.modules(), (TEXT,), INT)
    assert execute(graph, {TEXT: Message(TEXT, " 3 ", "input")}, Workspace(), 1).payload == 3

    with pytest.raises(ValueError):
        registry.replace(fn("parse-int", [TEXT], TEXT, str))


def test_budget_exhaustion_rolls_back() -> None:
    registry = Registry()
    registry.install(fn("pair", [TEXT], PAIR, lambda s: (1, 2)))
    registry.install(fn("sum", [PAIR], INT, sum))
    workspace = Workspace()
    workspace.post(source := Message(TEXT, "x", "input"))
    graph = plan(registry.modules(), (TEXT,), INT)

    with pytest.raises(BudgetExceeded):
        execute(graph, {TEXT: source}, workspace, budget=1)
    assert len(workspace) == 1


def test_workspace_rejects_unknown_parents() -> None:
    with pytest.raises(ValueError):
        Workspace().post(Message(INT, 1, "x", parents=("msg:missing",)))


def test_stable_routing_matches_lean_counterexample() -> None:
    # Mirrors NCA.plan_not_stable: installing make1 reroutes the plain planner.
    need1 = fn("need1", ["t1"], "t0", lambda x: x)
    from2 = fn("from2", ["t2"], "t0", lambda x: x)
    make1 = fn("make1", ["t2"], "t1", lambda x: x)
    avail = ("t2",)

    before = plan([need1, from2], avail, "t0")
    after = plan([need1, from2, make1], avail, "t0")
    assert before.module is from2 and after.module is need1

    assert plan_stable([need1, from2, make1], avail, "t0") == before


def test_map_applies_elementwise_composition() -> None:
    registry = Registry()
    registry.install(fn("split", [TEXT], "seq[text.v1]", lambda s: s.split(",")))
    registry.install(fn("parse-int", [TEXT], INT, int))
    registry.install(fn("double", [INT], "int.even.v1", lambda x: 2 * x))
    registry.install(fn("sum", ["seq[int.even.v1]"], INT, sum))
    workspace = Workspace()

    graph = plan(registry.modules(), (TEXT,), "seq[int.even.v1]")
    assert isinstance(graph, Map) and graph.element == TEXT

    total = plan(registry.modules(), ("csv.v1",), INT)
    assert total is None

    result = execute(graph, {TEXT: Message(TEXT, "1,2,3", "input")}, workspace, budget=7)
    assert result.type_id == "seq[int.even.v1]"
    assert result.payload == [2, 4, 6]
    with pytest.raises(BudgetExceeded):
        execute(graph, {TEXT: Message(TEXT, "1,2,3", "input")}, workspace, budget=6)


def test_requests_are_resolved_by_the_kernel_without_the_requester() -> None:
    from nca.abi import Request
    from nca.kernel import Kernel
    from nca.runtime import UnresolvedRequest

    def unsure(x: int) -> int | Request:
        return x if x % 2 == 0 else Request(INT, {TEXT: str(x)})

    requester = fn("unsure", [TEXT], INT, lambda s: unsure(int(s)))
    fallback = fn("parse-int", [TEXT], INT, lambda s: 100 + int(s))
    modules = [requester, fallback]
    kernel = Kernel(modules)
    route = plan(modules, (TEXT,), INT)
    assert route.module is requester

    workspace = Workspace()
    assert execute(route, {TEXT: Message(TEXT, "4", "input")}, workspace, 5, kernel).payload == 4
    assert kernel.requests == 0
    result = execute(route, {TEXT: Message(TEXT, "3", "input")}, workspace, 5, kernel)
    assert result.payload == 103 and kernel.requests == 1
    assert [m.producer for m in workspace.provenance(result.message_id)][-2:] == \
        ["parse-int@1.0.0", "unsure@1.0.0+kernel"]

    with pytest.raises(UnresolvedRequest):
        execute(route, {TEXT: Message(TEXT, "3", "input")}, Workspace(), 5, Kernel([requester]))
    with pytest.raises(UnresolvedRequest):
        execute(route, {TEXT: Message(TEXT, "3", "input")}, Workspace(), 5)


def test_nested_request_chains_terminate() -> None:
    from nca.abi import Request
    from nca.kernel import Kernel
    from nca.runtime import UnresolvedRequest

    always_ask = [fn(f"ask{i}", [TEXT], INT, lambda s: Request(INT, {TEXT: s}))
                  for i in range(4)]
    kernel = Kernel(always_ask)
    route = plan(always_ask, (TEXT,), INT)
    with pytest.raises(UnresolvedRequest):
        execute(route, {TEXT: Message(TEXT, "1", "input")}, Workspace(), 100, kernel)
    assert kernel.requests == len(always_ask)


def test_consumer_declared_irrelevance_skips_resolution() -> None:
    from nca.abi import Request
    from nca.kernel import Kernel

    @dataclass
    class Chooser:
        manifest: Manifest = field(default_factory=lambda: Manifest(
            "choose", "1.0.0", Contract((INT, "flag.v1"), "choice.v1")))

        def relevant(self, index: int, provisional: list) -> bool:
            return index != 0 or provisional[1]

        def invoke(self, value: int, flag: bool) -> int:
            return value if flag else -1

    requester = fn("unsure", [TEXT], INT, lambda s: Request(INT, {TEXT: s}, provisional=0))
    fallback = fn("parse-int", [TEXT], INT, int)
    flag = fn("flag", [TEXT], "flag.v1", lambda s: s.startswith("+"))
    modules = [requester, flag, Chooser(), fallback]
    route = plan(modules, (TEXT,), "choice.v1")
    assert route.module.manifest.module_id == "choose"

    kernel = Kernel(modules)
    workspace = Workspace()
    assert execute(route, {TEXT: Message(TEXT, "7", "input")}, workspace, 9, kernel).payload == -1
    assert kernel.requests == 0
    assert any(m.type_id == "kernel.skipped" for m in workspace.messages())
    assert execute(route, {TEXT: Message(TEXT, "+7", "input")}, Workspace(), 9, kernel).payload == 7
    assert kernel.requests == 1


def test_continuation_requests_resume_with_sub_results() -> None:
    from collections.abc import Generator

    from nca.abi import Request
    from nca.kernel import Kernel

    def split(text: str) -> Generator[Request, int, tuple[int, int]]:
        left, right = text.split("+")
        a = yield Request(INT, {TEXT: left})
        b = yield Request(INT, {TEXT: right})
        return (a, b)

    modules = [fn("split", [TEXT], PAIR, split), fn("parse-int", [TEXT], INT, int)]
    kernel = Kernel(modules)
    graph = plan_stable(modules, (TEXT,), PAIR)
    workspace = Workspace()
    result = execute(graph, {TEXT: Message(TEXT, "7+5", "input")}, workspace, 10, kernel)
    assert result.payload == (7, 5)
    assert kernel.requests == 2
    assert sum(m.type_id == "kernel.request" for m in workspace.messages()) == 2


def test_slots_are_planned_and_called_through_the_kernel() -> None:
    from nca.abi import Calls

    @dataclass
    class Both:
        manifest: Manifest = field(default_factory=lambda: Manifest(
            "both", "1.0.0", Contract((INT,), PAIR, (((INT,), "int.next.v1"),)), cost=1.0,
            calls=(Calls(2.0),)))

        def invoke(self, step: Callable[[int], int], value: int) -> tuple[int, int]:
            return step(value), step(-value)

    inc = fn("inc", [INT], "int.next.v1", lambda x: x + 1)
    modules = [Both(), fn("parse-int", [TEXT], INT, int), inc]
    route = plan_stable(modules, (TEXT,), PAIR)
    assert route == Apply(modules[0], (Apply(modules[1], (Given(TEXT),)),),
                          (Apply(inc, (Given(INT),)),))
    assert infer(modules, (TEXT,), route) == PAIR
    assert infer(modules, (TEXT,), Apply(modules[0], route.args)) is None
    assert plan_stable(modules[:2], (TEXT,), PAIR) is None
    workspace = Workspace()
    result = execute(route, {TEXT: Message(TEXT, "5", "input")}, workspace, budget=4)
    assert result.payload == (6, -4) and workspace.spent == 4.0
    with pytest.raises(BudgetExceeded):
        execute(route, {TEXT: Message(TEXT, "5", "input")}, Workspace(), budget=3)


def test_budgeted_recursion_is_paid_and_refused_never_wrong() -> None:
    """``NCA.serve``: a recursive expert within its budget answers correctly;
    with too little budget it is refused, never wrong."""
    from collections.abc import Generator

    from nca.abi import Request
    from nca.kernel import Kernel
    from nca.runtime import UnresolvedRequest, attempt

    def total(values: tuple[int, ...]) -> Generator[Request, int, int]:
        if len(values) <= 1:
            return sum(values)
        half = len(values) // 2
        left = yield Request(INT, {"ints.v1": values[:half]})
        right = yield Request(INT, {"ints.v1": values[half:]})
        return left + right

    summer = Fn(Manifest("sum", "1.0.0", Contract(("ints.v1",), INT), cost=2.0), total)
    route = Apply(summer, (Given("ints.v1"),))
    values = tuple(range(1, 17))
    needed = 2.0 * (2 * len(values) - 1)
    for budget in (needed, needed + 7):
        workspace = Workspace()
        result = attempt(route, {"ints.v1": Message("ints.v1", values, "input")}, workspace,
                         10_000, Kernel([summer], recursive=True), cost_budget=budget)
        assert result is not None and result.payload == sum(values)
        assert workspace.spent == needed
    for budget in (0.0, 1.0, needed - 2):
        workspace = Workspace()
        assert attempt(route, {"ints.v1": Message("ints.v1", values, "input")}, workspace,
                       10_000, Kernel([summer], recursive=True), cost_budget=budget) is None
        assert workspace.spent <= budget
    with pytest.raises(UnresolvedRequest):
        execute(route, {"ints.v1": Message("ints.v1", values, "input")}, Workspace(), 10_000,
                Kernel([summer]))


def test_extending_registry_supports_an_unrelated_task_without_rerouting() -> None:
    registry = Registry()
    registry.install(fn("tokenize-weather", ["weather.report.v1"], "weather.words.v1", str.split))
    registry.install(fn("summarize-weather", ["weather.words.v1"], "weather.summary.v1",
                        lambda words: "/".join(words)))
    weather = plan_stable(registry.modules(), ("weather.report.v1",), "weather.summary.v1")
    assert weather is not None
    assert execute(weather, {"weather.report.v1": Message("weather.report.v1", "rain north", "input")},
                   Workspace(), budget=4).payload == "rain/north"

    registry.install(fn("music-describe", ["music.notes.v1"], "music.description.v1",
                        lambda notes: ",".join(notes)))
    assert plan_stable(registry.modules(), ("weather.report.v1",), "weather.summary.v1") == weather
    music = plan_stable(registry.modules(), ("music.notes.v1",), "music.description.v1")
    assert music is not None
    assert execute(music, {"music.notes.v1": Message("music.notes.v1", ["C", "G"], "input")},
                   Workspace(), budget=4).payload == "C,G"
    registry.uninstall("music-describe")
    assert plan_stable(registry.modules(), ("music.notes.v1",), "music.description.v1") is None


def test_registry_index_survives_installation_replacement_and_removal() -> None:
    """The registry's index, kept across installations with its cached plans,
    plans exactly like an index built afresh at every step (Theorem 12.18).
    Removal keeps the plans cached for the modules installed before the
    removed one."""
    rng = np.random.default_rng(4)
    names = [f"t{i}.v1" for i in range(6)]
    types = [*names, *(f"seq[{t}]" for t in names)]
    for trial in range(20):
        registry = Registry()
        goals = [str(g) for g in rng.choice(types, size=8)]
        available = tuple(str(t) for t in rng.choice(types, size=2))
        for step in range(12):
            installed = registry.modules()
            action = rng.random()
            if installed and action < 0.15:
                registry.uninstall(installed[int(rng.integers(len(installed)))].manifest.module_id)
            elif installed and action < 0.3:
                old = installed[int(rng.integers(len(installed)))]
                registry.replace(Fn(old.manifest, lambda *x: x))
            else:
                inputs = [str(t) for t in rng.choice(types, size=int(rng.integers(0, 3)))]
                output = str(rng.choice(types))
                if rng.random() < 0.2:
                    inputs, output = ["seq[?a]"], "seq[?a]"
                elif rng.random() < 0.1:
                    inputs, output = ["seq[?a]", "?s"], "?s"
                registry.install(fn(f"m{step}-{trial}", inputs, output, lambda *x: x))
            for goal in goals:
                kept = plan_stable_indexed(registry.index, available, goal, fuel=4)
                fresh = plan_stable(registry.modules(), available, goal, fuel=4)
                assert kept == fresh
                if kept is not None:
                    assert infer(registry.modules(), available, kept) == goal


def test_uninstalling_keeps_plans_for_earlier_modules() -> None:
    registry = Registry()
    for k in range(3):
        registry.install(fn(f"m{k}", [f"t{k}.v1"], f"t{k + 1}.v1", lambda x: x))
    assert plan_stable_indexed(registry.index, ("t0.v1",), "t2.v1") is not None
    cached = dict(registry.index.memo(2))
    assert cached
    registry.uninstall("m2")
    assert registry.index.memo(2) == cached
    registry.uninstall("m0")
    assert not registry.index.memo(2)
    assert plan_stable_indexed(registry.index, ("t0.v1",), "t2.v1") is None
