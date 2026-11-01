import itertools
from dataclasses import dataclass, field
from typing import Any, Callable

import numpy as np
import pytest

from nca.abi import Choice, Contract, Manifest, Message, parse_type, type_variables
from nca.optimize import plan_min
from nca.index import ProducerIndex
from nca.modules.combinators import Case, Fold
from nca.planner import Apply, Given, Map, Plan, plan, plan_stable, plan_stable_indexed
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


def test_polymorphic_contracts_are_instantiated_by_the_goal() -> None:
    """A generic module is planned at the instance its goal selects, checked,
    and executed with the instance's types."""
    dup = fn("dup", ["?a"], "pair[?a,?a]", lambda x: (x, x))
    swap = fn("swap", ["pair[?a,?b]"], "pair[?b,?a]", lambda p: (p[1], p[0]))
    tag = fn("tag", [INT], "pair[int.v1,text.v1]", lambda x: (x, str(x)))
    modules = [dup, swap, tag]
    route = plan(modules, (INT,), "pair[text.v1,int.v1]")
    assert isinstance(route, Apply) and route.module is swap
    assert route.binding == (("a", INT), ("b", TEXT))
    assert infer(modules, (INT,), route) == "pair[text.v1,int.v1]"
    assert infer(modules, (INT,), Apply(swap, route.args, (), (("a", TEXT), ("b", INT)))) is None
    assert infer(modules, (INT,), Apply(swap, route.args, (), (("a", INT),))) is None
    workspace = Workspace()
    message = Message(INT, 7, "input")
    workspace.post(message)
    result = execute(route, {INT: message}, workspace, budget=10)
    assert (result.type_id, result.payload) == ("pair[text.v1,int.v1]", ("7", 7))
    doubled = plan(modules, (TEXT,), "pair[text.v1,text.v1]")
    assert isinstance(doubled, Apply) and doubled.module is dup
    assert plan(modules, (TEXT,), "pair[text.v1,int.v1]") is None
    assert plan_stable(modules, (INT,), "pair[text.v1,int.v1]") == route
    cheapest = plan_min(modules, (INT,), "pair[text.v1,int.v1]", length=1)
    assert cheapest is not None and cheapest[0] == Apply(
        swap, (Apply(tag, (Given(INT),)),), (), (("a", INT), ("b", TEXT)))


def _ground_terms(depth: int) -> list[str]:
    terms = ["c0.v1", "c1.v1", "c2.v1"]
    for _ in range(depth):
        terms = sorted({*terms, *(f"box[{t}]" for t in terms),
                        *(f"pair[{a},{b}]" for a in terms for b in terms)})
    return terms


def test_polymorphic_planning_equals_planning_with_instances() -> None:
    """Planning with range-restricted contracts returns exactly the plan found
    over their instances, each placed at its contract's position (Theorem 2.4:
    a goal selects at most one instance per contract). With fuel 3, goals of
    depth at most 2 and inputs of depth at most 1, every instance a plan can
    use binds one variable to a term of depth at most 2, or two variables to
    terms of depth at most 1."""
    rng = np.random.default_rng(1)
    universe, wide = _ground_terms(1), _ground_terms(2)
    generic = [("dup", ["?a"], "pair[?a,?a]"), ("swap", ["pair[?a,?b]"], "pair[?b,?a]"),
               ("box", ["?a"], "box[?a]"), ("unbox", ["box[?a]", "c0.v1"], "?a")]
    for trial in range(40):
        specs = [(f"m{k}", [str(rng.choice(universe))], str(rng.choice(universe)))
                 for k in range(int(rng.integers(2, 6)))]
        specs += [generic[i] for i in rng.permutation(len(generic))[:int(rng.integers(1, 5))]]
        order = rng.permutation(len(specs))
        modules = [fn(f"{specs[i][0]}-{trial}", specs[i][1], specs[i][2], lambda *x: x)
                   for i in order]
        instances: list[Fn] = []
        origin: dict[int, tuple[str, tuple[tuple[str, str], ...]]] = {}
        for module in modules:
            contract = module.manifest.contract
            names = sorted(type_variables(parse_type(contract.output)))
            for values in itertools.product(wide if len(names) == 1 else universe,
                                            repeat=len(names)):
                binding = tuple(zip(names, values))
                copy = Fn(Manifest(module.manifest.module_id, "1.0.0",
                                   contract.instance(binding)), module.fn)
                instances.append(copy)
                origin[id(copy)] = (module.manifest.module_id, binding)

        def shape(node: Plan, generic_plan: bool) -> Any:
            if isinstance(node, Given):
                return node.type_id
            if isinstance(node, Map):
                return ("map", node.element, shape(node.body, generic_plan),
                        shape(node.source, generic_plan))
            key = ((node.module.manifest.module_id, node.binding) if generic_plan
                   else origin[id(node.module)])
            return (key, tuple(shape(a, generic_plan) for a in node.args))

        available = (str(rng.choice(universe)), "c0.v1")
        near = [f"box[{available[0]}]", f"pair[{available[0]},{available[0]}]",
                f"pair[c0.v1,{available[0]}]", f"box[box[{available[0]}]]"]
        for goal in [*rng.choice(wide, size=30), *near]:
            found = plan(modules, available, str(goal), fuel=3)
            expected = plan(instances, available, str(goal), fuel=3)
            assert (found is None) == (expected is None)
            if found is not None and expected is not None:
                assert shape(found, True) == shape(expected, False)
                assert infer(modules, available, found) == goal


def test_free_variables_are_determined_by_the_inputs() -> None:
    """A contract whose input variables the goal leaves open is planned through
    pattern goals: its inputs' plans determine them (THEORY §2.2)."""
    length = fn("length", ["seq[?a]"], INT, len)
    nothing = fn("nothing", [], "seq[?a]", list)
    split = fn("split", [TEXT], "seq[text.v1]", str.split)
    route = plan([length, nothing, split], (TEXT,), INT)
    assert isinstance(route, Apply) and route.binding == (("a", TEXT),)
    assert route.args == (Apply(split, (Given(TEXT),)),)
    assert infer([length, nothing, split], (TEXT,), route) == INT
    assert infer([length, nothing, split], (TEXT,), Apply(length, route.args)) is None
    workspace = Workspace()
    message = Message(TEXT, "a b c", "input")
    workspace.post(message)
    assert execute(route, {TEXT: message}, workspace, budget=10).payload == 3
    assert plan([length, nothing], (TEXT,), INT) is None
    pairs = fn("pairs", ["seq[?a]", "seq[?a]"], INT, lambda a, b: len(a) + len(b))
    both = plan([pairs, nothing, split], (TEXT,), INT)
    assert isinstance(both, Apply) and both.binding == (("a", TEXT),)
    assert both.args == (Apply(nothing, (), (), (("a", TEXT),)), Apply(split, (Given(TEXT),)))


def test_free_variable_planning_is_sound_and_complete_against_instances() -> None:
    """Pattern search plans a goal exactly when the library of instances does,
    and every plan it returns is well-typed (Theorem 2.5). Within fuel 3 from
    inputs of depth at most 1, every type a plan can produce or bind has depth
    at most 2, so one-variable instances over those terms suffice. Every
    variable occurs in an input, so no candidate is ambiguous and the
    instances are an exact reference."""
    rng = np.random.default_rng(2)
    universe, wide = _ground_terms(1), _ground_terms(2)
    generic = [("forget", ["box[?a]"], "c1.v1"), ("size", ["box[?a]", "c0.v1"], "c2.v1"),
               ("box", ["?a"], "box[?a]"),
               ("unbox", ["box[?a]"], "?a"), ("dup", ["?a"], "pair[?a,?a]")]
    planned = through_free = 0

    def free_used(node: Plan) -> bool:
        if isinstance(node, Given):
            return False
        if isinstance(node, Map):
            return free_used(node.body) or free_used(node.source)
        return bool(node.module.manifest.contract.free) or any(free_used(a) for a in node.args)

    for trial in range(80):
        specs = [(f"m{k}", [str(rng.choice(universe))], str(rng.choice(universe)))
                 for k in range(int(rng.integers(1, 4)))]
        specs += [generic[i] for i in rng.permutation(len(generic))[:int(rng.integers(1, 5))]]
        modules = [fn(f"{specs[i][0]}-{trial}", specs[i][1], specs[i][2], lambda *x: x)
                   for i in rng.permutation(len(specs))]
        instances = [Fn(Manifest(m.manifest.module_id, "1.0.0",
                                 m.manifest.contract.instance(((name, t),))), m.fn)
                     if m.manifest.contract.variables else m
                     for m in modules
                     for name in sorted(m.manifest.contract.variables) or [""]
                     for t in (wide if m.manifest.contract.variables else [""])]
        available = (str(rng.choice(universe)), "c0.v1")
        goals = [*rng.choice(wide, size=20), "c1.v1", "c2.v1", f"box[{available[0]}]"]
        for goal in goals:
            found = plan(modules, available, str(goal), fuel=3)
            expected = plan(instances, available, str(goal), fuel=3)
            assert (found is None) == (expected is None), (goal, specs)
            if found is not None:
                planned += 1
                through_free += free_used(found)
                assert infer(modules, available, found) == goal
    assert planned > 100 and through_free > 30


def test_map_candidate_pruning_changes_no_plan(monkeypatch: pytest.MonkeyPatch) -> None:
    """Skipping ``map`` candidates whose body goal (Theorem 12.7) or source
    (Theorem 12.17) the closure oracle rejects, and pattern-goal candidates
    with another output root (Theorem 2.6) or an underivable input, returns
    exactly the unpruned plan."""
    rng = np.random.default_rng(3)
    names = [f"t{i}.v1" for i in range(6)]
    types = [*names, *(f"seq[{t}]" for t in names), *(f"seq[seq[{t}]]" for t in names[:2])]
    cases = []
    for trial in range(150):
        modules = [fn(f"m{k}-{trial}", [str(t) for t in rng.choice(types, size=int(rng.integers(0, 3)))],
                      str(rng.choice(types)), lambda *x: x) for k in range(int(rng.integers(2, 9)))]
        if rng.random() < 0.3:
            modules.insert(int(rng.integers(len(modules) + 1)),
                           fn(f"sort-{trial}", ["seq[?a]"], "seq[?a]", lambda x: x))
        if rng.random() < 0.3:
            modules.insert(int(rng.integers(len(modules) + 1)),
                           fn(f"length-{trial}", ["seq[?a]"], "t5.v1", len))
        available = tuple(str(t) for t in rng.choice(types, size=int(rng.integers(1, 3))))
        cases += [(modules, available, str(goal)) for goal in rng.choice(types, size=6)]
    pruned = [plan(m, a, g, fuel=4) for m, a, g in cases]
    monkeypatch.setattr(ProducerIndex, "may_derive", lambda *_: True)
    monkeypatch.setattr(ProducerIndex, "sources", lambda *_: None)
    monkeypatch.setattr(ProducerIndex, "seq_elements", lambda *_: None)
    monkeypatch.setattr(ProducerIndex, "pattern_candidates",
                        lambda self, available, goal, limit: list(range(limit)))
    unpruned = [plan(m, a, g, fuel=4) for m, a, g in cases]
    assert pruned == unpruned
    assert sum(isinstance(p, Map) for p in pruned) > 20


def test_registry_index_survives_installation_replacement_and_removal() -> None:
    """The registry's index, kept across installations with its cached plans,
    plans exactly like an index built afresh at every step (Theorem 12.18)."""
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
                registry.install(fn(f"m{step}-{trial}", inputs, output, lambda *x: x))
            for goal in goals:
                kept = plan_stable_indexed(registry.index, available, goal, fuel=4)
                fresh = plan_stable(registry.modules(), available, goal, fuel=4)
                assert kept == fresh
                if kept is not None:
                    assert infer(registry.modules(), available, kept) == goal


def test_case_and_fold_are_planned_as_generic_eliminators() -> None:
    """One ``Case`` and one ``Fold`` serve every type (THEORY §20.7): the
    planner instantiates ``Case`` from the data and the goal, a choice runs
    only the branch it selects, and a fold plan type-checks and runs."""
    calls: list[str] = []

    def double(x: int) -> str:
        calls.append("double")
        return f"2x={2 * x}"

    def report(e: str) -> str:
        calls.append("report")
        return f"bad {e}"

    parse = fn("parse", [TEXT], f"either[{INT},err.v1]",
               lambda s: Choice(0, int(s)) if s.isdigit() else Choice(1, s))
    modules = [Case(), parse, fn("double", [INT], "out.v1", double),
               fn("report", ["err.v1"], "out.v1", report)]
    route = plan(modules, (TEXT,), "out.v1")
    assert isinstance(route, Apply) and route.module is modules[0]
    assert route.binding == (("b", "out.v1"), ("l", INT), ("r", "err.v1"))
    assert infer(modules, (TEXT,), route) == "out.v1"
    for text, expected, branch in (("21", "2x=42", "double"), ("zz", "bad zz", "report")):
        calls.clear()
        workspace = Workspace()
        message = Message(TEXT, text, "input")
        workspace.post(message)
        assert execute(route, {TEXT: message}, workspace, budget=10).payload == expected
        assert calls == [branch]

    total = "total.v1"
    fold, zero, add = (Fold(), fn("zero", [TEXT], total, lambda _: 0),
                       fn("add", [total, INT], total, lambda s, x: s + x))
    route = Apply(fold, (Given(f"seq[{INT}]"), Apply(zero, (Given(TEXT),))),
                  (Apply(add, (Given(total), Given(INT))),), (("a", INT), ("s", total)))
    assert infer([fold, zero, add], (f"seq[{INT}]", TEXT), route) == total
    workspace = Workspace()
    items, text = Message(f"seq[{INT}]", [1, 2, 3], "input"), Message(TEXT, "", "input")
    workspace.post(items)
    workspace.post(text)
    assert execute(route, {f"seq[{INT}]": items, TEXT: text}, workspace, budget=10).payload == 6
