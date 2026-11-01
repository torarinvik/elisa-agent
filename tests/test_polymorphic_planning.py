"""Planning with polymorphic contracts (THEORY §2), its pruning oracles
(THEORY §12), and eliminators (THEORY §20.7)."""

import itertools
from dataclasses import dataclass, field
from typing import Any, Callable

import numpy as np
import pytest

from nca.abi import (App, Calls, Choice, Contract, Manifest, Message, ScopedName, Var,
                     format_type, parse_type, type_variables)
from nca.index import ProducerIndex
from nca.modules.combinators import Case, Fold
from nca.optimize import plan_min, plan_pareto
from nca.planner import Apply, Given, Map, Plan, plan, plan_stable, uses
from nca.router import infer
from nca.runtime import execute
from nca.workspace import Workspace

TEXT = "text.v1"
INT = "int.v1"


@dataclass
class Fn:
    manifest: Manifest
    fn: Callable[..., Any] = field(repr=False)

    def invoke(self, *inputs: Any) -> Any:
        return self.fn(*inputs)


def fn(module_id: str, inputs: list[str], output: str, f: Callable[..., Any]) -> Fn:
    return Fn(Manifest(module_id, "1.0.0", Contract(tuple(inputs), output)), f)


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
    (Theorem 12.17) the closure oracle rejects, pattern-goal candidates with
    another output root (Theorem 2.6) or an underivable input, and
    eliminators whose output lies outside the closure (Theorem 12.19), returns
    exactly the unpruned plan."""
    rng = np.random.default_rng(3)
    names = [f"t{i}.v1" for i in range(6)]
    types = [*names, *(f"seq[{t}]" for t in names), *(f"seq[seq[{t}]]" for t in names[:2]),
             "either[t0.v1,t1.v1]", "either[t2.v1,seq[t3.v1]]"]
    generic = [Case(), Fold(), fn("inl", ["?l"], "either[?l,?r]", lambda x: Choice(0, x)),
               fn("unwrap", ["either[?a,?a]"], "?a", lambda c: c.value),
               fn("first", ["seq[?a]"], "?a", lambda x: x[0])]
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
        for module in generic:
            if rng.random() < 0.2:
                modules.insert(int(rng.integers(len(modules) + 1)), module)
        available = tuple(str(t) for t in rng.choice(types, size=int(rng.integers(1, 3))))
        cases += [(modules, available, str(goal)) for goal in rng.choice(types, size=6)]
    pruned = [plan(m, a, g, fuel=4) for m, a, g in cases]
    monkeypatch.setattr(ProducerIndex, "may_derive", lambda *_: True)
    monkeypatch.setattr(ProducerIndex, "sources", lambda *_: None)
    monkeypatch.setattr(ProducerIndex, "seq_elements", lambda *_: None)
    monkeypatch.setattr(ProducerIndex, "pattern_candidates",
                        lambda self, available, goal, limit: list(range(limit)))
    monkeypatch.setattr(ProducerIndex, "total", lambda *_: True)
    unpruned = [plan(m, a, g, fuel=4) for m, a, g in cases]
    assert pruned == unpruned
    assert sum(isinstance(p, Map) for p in pruned) > 20


def test_case_and_fold_are_planned_as_generic_eliminators() -> None:
    """One ``Case`` and one ``Fold`` serve every type (THEORY §20.7): the
    planner instantiates ``Case`` from the data and the goal, its closure
    contribution is what its branches make (Theorem 12.19), a choice runs
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
    index = ProducerIndex(modules)
    assert not index.total((TEXT,), len(modules))
    assert "out.v1" in index.reachable((TEXT,), len(modules))
    assert plan(modules, (TEXT,), "missing.v1") is None
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


def test_slot_inputs_are_addressed_by_position_and_relevant_ones_are_used() -> None:
    """A fold whose state and elements share a type sums correctly: its step
    reads each input by position (THEORY §20.8). The step must use both
    inputs, so a step reading one of them twice is rejected and the planner
    finds ``add(state, element)``; a task may require its own inputs too."""
    fold, zero = Fold(), fn("zero", [TEXT], INT, lambda _: 0)
    add = fn("add", [INT, INT], INT, lambda a, b: a + b)
    modules, available = [zero, fold, add], (f"seq[{INT}]", TEXT)

    def run(route: Plan) -> Any:
        workspace = Workspace()
        inputs = {f"seq[{INT}]": Message(f"seq[{INT}]", [1, 2, 4], "input"),
                  TEXT: Message(TEXT, "", "input")}
        for message in inputs.values():
            workspace.post(message)
        return execute(route, inputs, workspace, budget=20).payload

    by_type = Apply(fold, (Given(f"seq[{INT}]"), Apply(zero, (Given(TEXT),))),
                    (Apply(add, (Given(INT), Given(INT))),), (("a", INT), ("s", INT)))
    assert infer(modules, available, by_type) is None
    step = Apply(add, (Given(INT), Given(INT, 1)))
    assert uses(step, (INT, INT)) == {0, 1}
    route = plan(modules, available, INT, fuel=5, required=frozenset({0}))
    assert route == Apply(fold, by_type.args, (step,), by_type.binding)
    assert infer(modules, available, route) == INT and run(route) == 7
    assert plan(modules, available, INT, fuel=5) == Apply(zero, (Given(TEXT),))
    cheapest = plan_min(modules, available, INT, 3, fuel=5, required=frozenset({0}))
    assert cheapest is not None and cheapest[0] == route and run(cheapest[0]) == 7

    # Earlier generic producers must not wrap a valid fold in redundant adds.
    reordered = [add, zero, fold]
    shallow = plan(reordered, available, INT, fuel=5, required=frozenset({0}))
    assert shallow == route and run(shallow) == 7


def test_map_sources_made_by_polymorphic_producers_are_found() -> None:
    """A sequence that only a polymorphic producer makes is a ``map`` source:
    its element is found by solving ``seq[?a]`` as a pattern goal (THEORY
    §2.2). Planning succeeds exactly when planning over the instances does."""
    unbox = fn("unbox", ["box[?a]"], "?a", lambda x: x)
    f = fn("f", ["c0.v1"], "c1.v1", str)
    route = plan([unbox, f], ("box[seq[c0.v1]]",), "seq[c1.v1]")
    assert isinstance(route, Map) and isinstance(route.source, Apply)
    assert route.source.module is unbox
    assert infer([unbox, f], ("box[seq[c0.v1]]",), route) == "seq[c1.v1]"

    rng = np.random.default_rng(7)
    base = ["c0.v1", "c1.v1", "c2.v1"]
    universe = [*base, *(f"seq[{c}]" for c in base), *(f"box[{c}]" for c in base),
                *(f"box[seq[{c}]]" for c in base)]
    wide = [*universe, *(f"seq[box[{c}]]" for c in base), *(f"seq[seq[{c}]]" for c in base),
            *(f"box[box[{c}]]" for c in base)]
    goals = [t for t in wide if t.startswith("seq[")]
    generic = [("unbox", ["box[?a]"], "?a"), ("first", ["seq[?a]"], "?a"),
               ("wrap", ["?a"], "box[?a]")]
    planned = 0
    for trial in range(150):
        specs = [(f"m{k}", [str(rng.choice(universe))], str(rng.choice(universe)))
                 for k in range(int(rng.integers(1, 4)))]
        specs += [generic[i] for i in rng.permutation(len(generic))[:int(rng.integers(1, 4))]]
        modules = [fn(f"{specs[i][0]}-{trial}", specs[i][1], specs[i][2], lambda *x: x)
                   for i in rng.permutation(len(specs))]
        instances = [Fn(Manifest(m.manifest.module_id, "1.0.0",
                                 m.manifest.contract.instance((("a", t),))), m.fn)
                     if m.manifest.contract.variables else m
                     for m in modules
                     for t in (wide if m.manifest.contract.variables else [""])]
        available = (str(rng.choice(universe)),)
        for goal in rng.choice(goals, size=6):
            found = plan(modules, available, str(goal), fuel=4)
            expected = plan(instances, available, str(goal), fuel=4)
            assert (found is None) == (expected is None), (goal, specs, available)
            if found is not None:
                planned += 1
                assert infer(modules, available, found) == goal
    assert planned > 80


def test_cost_planners_price_every_instance_of_free_variables() -> None:
    """``plan_min`` and ``plan_pareto`` cost a contract with free variables at
    every instance pattern search determines, so they agree with the same
    planners over the expanded instances."""
    forget = Fn(Manifest("forget", "1.0.0", Contract(("box[?a]",), "c1.v1"), cost=1.0),
                lambda x: x)
    dear = Fn(Manifest("dear", "1.0.0", Contract(("c0.v1",), "box[c0.v1]"), cost=5.0), lambda x: x)
    cheap = Fn(Manifest("cheap", "1.0.0", Contract(("c0.v1",), "box[c2.v1]"), cost=1.0),
               lambda x: x)
    best = plan_min([forget, dear, cheap], ("c0.v1",), "c1.v1", length=1)
    assert best is not None and best[1] == 2.0
    assert isinstance(best[0], Apply) and best[0].binding == (("a", "c2.v1"),)

    rng = np.random.default_rng(5)
    universe, wide = _ground_terms(1), _ground_terms(2)
    generic = [("forget", ["box[?a]"], "c1.v1"), ("size", ["box[?a]", "c0.v1"], "c2.v1"),
               ("box", ["?a"], "box[?a]"), ("unbox", ["box[?a]"], "?a"),
               ("dup", ["?a"], "pair[?a,?a]")]
    compared = 0
    for trial in range(70):
        specs = [(f"m{k}", [str(rng.choice(universe))], str(rng.choice(universe)))
                 for k in range(int(rng.integers(1, 4)))]
        specs += [generic[i] for i in rng.permutation(len(generic))[:int(rng.integers(1, 5))]]
        modules = [Fn(Manifest(f"{name}-{trial}", "1.0.0", Contract(tuple(inputs), output),
                               cost=float(rng.integers(1, 5))), lambda *x: x)
                   for name, inputs, output in (specs[i] for i in rng.permutation(len(specs)))]
        errors = {m.manifest.ref: float(rng.integers(0, 3)) / 10 for m in modules}
        instances = [Fn(Manifest(m.manifest.module_id, "1.0.0",
                                 m.manifest.contract.instance((("a", t),)),
                                 cost=m.manifest.cost), m.fn)
                     if m.manifest.contract.variables else m
                     for m in modules
                     for t in (wide if m.manifest.contract.variables else [""])]
        available = (str(rng.choice(universe)), "c0.v1")
        for goal in [*rng.choice(wide, size=6), "c1.v1", "c2.v1"]:
            found = plan_min(modules, available, str(goal), length=1, fuel=3)
            expected = plan_min(instances, available, str(goal), length=1, fuel=3)
            assert (found is None) == (expected is None)
            if found is not None and expected is not None:
                compared += 1
                assert found[1] == expected[1]
                assert infer(modules, available, found[0]) == goal
                frontier = plan_pareto(modules, available, str(goal), 1, errors, fuel=3)
                reference = plan_pareto(instances, available, str(goal), 1, errors, fuel=3)
                assert [(o.cost, o.error) for o in frontier] == [
                    (o.cost, o.error) for o in reference]
    assert compared > 45


def test_free_bindings_skip_duplicate_plan_closures(monkeypatch: pytest.MonkeyPatch) -> None:
    from nca import planner
    from nca.index import ProducerIndex

    add = fn("add", [INT, INT], INT, lambda a, b: a + b)
    zero = fn("zero", [TEXT], INT, lambda _: 0)
    fold = Fold()
    modules, available = [add, zero, fold], (f"seq[{INT}]", TEXT)
    binding = fold.manifest.contract.producing(INT)
    assert binding is not None
    original = planner._close
    calls = 0
    def close(*args: Any, **kwargs: Any) -> Plan | None:
        nonlocal calls
        calls += 1
        return original(*args, **kwargs)
    monkeypatch.setattr(planner, "_close", close)
    index = ProducerIndex(modules)
    expected = list(dict.fromkeys(full for _, full in planner._free_instances(
        index, index.size, available, fold, binding, 5, index.memo(index.size))))
    before = calls
    calls = 0
    actual = planner.free_bindings(ProducerIndex(modules), available, fold, binding, 5)
    assert actual == expected
    assert calls < before


def test_free_bindings_retry_after_failed_closure(monkeypatch: pytest.MonkeyPatch) -> None:
    from nca import planner
    from nca.index import ProducerIndex

    expert = fn("forget", ["box[?a]"], INT, lambda value: value)
    index = ProducerIndex([expert])
    monkeypatch.setattr(planner, "rename_apart",
                        lambda contract, binding: ({"a": "fresh"}, tuple(map(parse_type, contract.inputs)),
                                                   parse_type(contract.output)))
    def solutions(*args: Any) -> Any:
        solved = {"fresh": parse_type(TEXT)}
        yield (Given("bad"),), solved
        yield (Given("good"),), solved
    monkeypatch.setattr(planner, "_solve_inputs", solutions)
    monkeypatch.setattr(planner, "_close",
                        lambda index, limit, node, binding, memo: None if node.type_id == "bad" else node)
    assert planner.free_bindings(index, (), expert, (), 3) == [(("a", TEXT),)]


def test_free_binding_rejects_unusable_required_input() -> None:
    add = fn("add", [INT, INT], INT, lambda a, b: a + b)
    zero = fn("zero", [TEXT], INT, lambda _: 0)
    available = (f"seq[{INT}]", TEXT, "unused.v1")
    assert plan([add, zero, Fold()], available, INT, fuel=5, required=frozenset({2})) is None


def test_free_binding_checks_ground_inputs_without_losing_dependent_inputs() -> None:
    add = fn("add", [INT, INT], INT, lambda a, b: a + b)
    zero = fn("zero", [TEXT], INT, lambda _: 0)
    blocked = fn("blocked", ["seq[?a]", "missing.v1"], "out.v1", lambda a, b: None)
    modules, available = [add, zero, Fold(), blocked], (f"seq[{INT}]", TEXT)
    assert plan_min(modules, available, "out.v1", length=1, fuel=5) is None
    assert plan_pareto(modules, available, "out.v1", length=1, errors={}, fuel=5) == []
    missing = fn("missing", [TEXT], "missing.v1", lambda _: None)
    result = plan_min([*modules, missing], available, "out.v1", length=1, fuel=5)
    assert result is not None and infer([*modules, missing], available, result[0]) == "out.v1"

    dependent = fn("dependent", ["box[?a]", "?a"], "out.v1", lambda a, b: None)
    boxing = fn("boxing", [INT], "box[int.v1]", lambda value: value)
    result = plan_min([dependent, boxing], (INT,), "out.v1", length=1, fuel=4)
    assert result is not None and infer([dependent, boxing], (INT,), result[0]) == "out.v1"


def test_pattern_search_checks_later_input_after_binding_without_losing_alternatives() -> None:
    gate = fn("gate", ["trigger[?a]", "seq[?b]", "required[?a]"],
              "out.v1", lambda *args: None)
    needed = fn("needed", [TEXT], "required[text.v1]", lambda _: None)
    available = (f"seq[{INT}]", TEXT, "trigger[int.v1]", "trigger[text.v1]")
    assert plan_min([gate], available, "out.v1", length=1, fuel=4) is None
    modules = [gate, needed]
    result = plan_min(modules, available, "out.v1", length=1, fuel=4)
    assert result is not None and infer(modules, available, result[0]) == "out.v1"
    assert isinstance(result[0], Apply) and ("a", TEXT) in result[0].binding
    frontier = plan_pareto(modules, available, "out.v1", length=1, errors={}, fuel=4)
    assert frontier and frontier[0].cost == result[1]


def test_free_expert_ground_slot_pruning_keeps_solvable_instances() -> None:
    gate = Fn(Manifest("gate", "1.0.0", Contract(
        ("seq[?a]",), "out.v1", (((TEXT,), "missing.v1"),), ((0,),)),
        calls=(Calls(1, 0),)), lambda *args: None)
    wrap = fn("wrap", ["?a"], "seq[?a]", lambda value: [value])
    provider = fn("provider", [TEXT], "missing.v1", lambda value: value)
    available = (f"seq[{INT}]", INT)
    modules = [gate, wrap]
    assert plan(modules, available, "out.v1", fuel=5) is None
    assert plan_min(modules, available, "out.v1", 1, fuel=5) is None
    assert not plan_pareto(modules, available, "out.v1", 1, errors={}, fuel=5)
    modules.append(provider)
    route = plan(modules, available, "out.v1", fuel=5)
    cheapest = plan_min(modules, available, "out.v1", 1, fuel=5)
    frontier = plan_pareto(modules, available, "out.v1", 1, errors={}, fuel=5)
    assert route is not None and infer(modules, available, route) == "out.v1"
    assert cheapest is not None and infer(modules, available, cheapest[0]) == "out.v1"
    assert frontier and infer(modules, available, frontier[0].plan) == "out.v1"

    open_slot = Fn(Manifest("open-slot", "1.0.0", Contract(
        ("seq[?a]",), "out.v1", ((("?a",), "?a"),)), calls=(Calls(1, 0),)),
        lambda *args: None)
    assert plan([open_slot], available, "out.v1", fuel=3) is not None
    assert plan_min([open_slot], available, "out.v1", 1, fuel=3) is not None


def test_nested_pattern_prunes_only_unfillable_ground_slots() -> None:
    from nca import planner

    nested = Fn(Manifest("nested", "1.0.0", Contract(
        ("seq[?b]",), "seq[?b]", (((TEXT,), "missing.v1"),), ((0,),)),
        calls=(Calls(1, 0),)), lambda *args: None)
    provider = fn("provider", [TEXT], "missing.v1", lambda value: value)
    pattern = App("seq", (Var("x"),))
    for modules, expected in (([nested], False), ([nested, provider], True)):
        index = ProducerIndex(modules)
        solutions = planner._solutions(index, index.size, (f"seq[{INT}]",), pattern,
                                       {}, 3, index.memo(index.size))
        assert any(isinstance(partial, planner._Open) and partial.module is nested
                   for partial, _ in solutions) is expected


def test_nested_slot_grounded_by_output_unification() -> None:
    from nca import planner

    nested = Fn(Manifest("nested", "1.0.0", Contract(
        ("seq[?c]",), "pair[?a,?b]", ((("?a",), "missing.v1"),), ((0,),)),
        calls=(Calls(1, 0),)), lambda *args: None)
    provider = fn("provider", [INT], "missing.v1", lambda value: value)
    pattern = App("pair", (parse_type(INT), Var("x")))
    for modules, expected in (([nested], False), ([nested, provider], True)):
        index = ProducerIndex(modules)
        answers = planner._solutions(index, index.size, (f"seq[{TEXT}]",), pattern,
                                     {}, 3, index.memo(index.size))
        assert any(isinstance(partial, planner._Open) and partial.module is nested
                   for partial, _ in answers) is expected
    unresolved = Fn(Manifest("unresolved", "1.0.0", Contract(
        ("seq[?c]",), "pair[?a,?b]", ((("?b",), "missing.v1"),)),
        calls=(Calls(1, 0),)), lambda *args: None)
    index = ProducerIndex([unresolved])
    answers = planner._solutions(index, index.size, (f"seq[{TEXT}]",), pattern,
                                 {}, 3, index.memo(index.size))
    assert any(isinstance(partial, planner._Open) and partial.module is unresolved
               for partial, _ in answers)


def test_resolved_slot_follows_variable_aliases() -> None:
    from nca import planner

    nested = Fn(Manifest("nested-alias", "1.0.0", Contract(
        (), "pair[?a,?b]", ((("?a",), "missing.v1"),)), calls=(Calls(1, 0),)),
        lambda: None)
    scoped = ScopedName("a", 100)
    renaming = {"a": scoped}
    index = ProducerIndex([nested])
    memo = index.memo(index.size)
    assert planner._resolved_slots_possible(index, index.size, nested, renaming, {}, 3, memo)
    alias = {scoped: Var("link"), "link": parse_type(INT)}
    assert not planner._resolved_slots_possible(index, index.size, nested, renaming, alias, 3, memo)
    provider = fn("provider", [INT], "missing.v1", lambda value: value)
    index = ProducerIndex([nested, provider])
    assert planner._resolved_slots_possible(index, index.size, nested, renaming, alias, 3,
                                            index.memo(index.size))


def test_pattern_search_at_one_depth_keeps_zero_input_producers() -> None:
    from nca import planner

    needs = fn("needs", [TEXT], INT, lambda value: 1)
    seed = fn("seed", [], INT, lambda: 2)
    index = ProducerIndex([needs, seed])
    memo = index.memo(index.size)
    results = list(planner._solutions(index, index.size, (), Var("goal"), {}, 1, memo))
    closed = [planner._close(index, index.size, partial, binding, memo)
              for partial, binding in results]
    assert closed == [Apply(seed, ())]
    available = list(planner._solutions(index, index.size, (TEXT,), Var("goal"), {}, 1, memo))
    assert any(partial == Given(TEXT) for partial, _ in available)


def test_single_pattern_input_preserves_answers_and_order() -> None:
    from nca import planner

    seed = fn("seed", [], INT, lambda: 1)
    index = ProducerIndex([seed])
    memo = index.memo(index.size)
    answers = list(planner._solve_inputs(index, index.size, (TEXT,), (Var("x"),), {}, 2, memo))
    closed = [(planner._close(index, index.size, args[0], binding, memo),
               format_type(planner.resolve(Var("x"), binding)))
              for args, binding in answers]
    assert closed == [(Given(TEXT), TEXT), (Apply(seed, ()), INT)]
    assert list(planner._solve_inputs(index, index.size, (), (Var("x"),), {}, 1, memo)) == []


def test_pattern_sequence_at_one_depth_needs_no_map_candidates(monkeypatch) -> None:
    from nca import planner

    seed = fn("seed-sequence", [], f"seq[{INT}]", lambda: [])
    index = ProducerIndex([seed])
    memo = index.memo(index.size)

    def unexpected(*args):
        raise AssertionError("a map cannot be planned at depth one")

    monkeypatch.setattr(index, "element_candidates", unexpected)
    results = list(planner._solutions(index, index.size, (f"seq[{TEXT}]",),
                                      App("seq", (Var("element"),)), {}, 1, memo))
    closed = [planner._close(index, index.size, partial, binding, memo)
              for partial, binding in results]
    assert closed == [Given(f"seq[{TEXT}]"), Apply(seed, ())]


def test_pattern_helpers_stop_at_nonpositive_depth() -> None:
    from nca import planner

    loop = fn("loop", ["?a"], "seq[?a]", lambda value: [value])
    index = ProducerIndex([loop])
    memo = index.memo(index.size)
    assert planner._plan(index, index.size, (INT,), f"seq[{INT}]", -1) is None
    assert list(planner._solutions(index, index.size, (INT,), Var("goal"), {}, -1, memo)) == []
    assert planner.map_candidates(index, (), 0) == []


def test_renaming_preserves_inputs_output_and_slot_only_variables() -> None:
    from nca.index import rename_apart

    contract = Contract(("box[?a]", "?b"), "?b", ((("?c", "?a"), "?b"),))
    binding = (("b", INT),)
    first, inputs, output = rename_apart(contract, binding)
    second, _, _ = rename_apart(contract, binding)
    assert inputs == (App("box", (Var(first["a"]),)), parse_type(INT))
    assert format_type(output) == INT
    assert set(first) == {"a", "c"}
    assert set(first.values()).isdisjoint(second.values())
    with pytest.raises(ValueError, match="unresolved scoped variable"):
        format_type(inputs[0])


def test_generated_variable_cannot_collide_with_user_name(monkeypatch: pytest.MonkeyPatch) -> None:
    from nca import index as index_module

    producer = fn("nested", [], "box[seq[?a]]", lambda: None)
    index = ProducerIndex([producer])
    index.reachable((), index.size)
    monkeypatch.setattr(index_module, "_fresh", itertools.count(0))
    assert index.may_derive((), parse_type("box[?a_0]"), index.size)

    from nca import planner
    producer = fn("wrap", ["?a"], "box[seq[?a]]", lambda value: value)
    index = ProducerIndex([producer])
    monkeypatch.setattr(index, "pattern_candidates", lambda *args: [0])
    monkeypatch.setattr(index_module, "_fresh", itertools.count(0))
    memo = index.memo(index.size)
    partial, solved = next(planner._solutions(index, index.size, (INT,),
                                              parse_type("box[?a_0]"), {}, 3, memo))
    result = planner._close(index, index.size, partial, solved, memo)
    assert result is not None and infer([producer], (INT,), result) == f"box[seq[{INT}]]"
