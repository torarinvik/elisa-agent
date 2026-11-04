import random
from dataclasses import dataclass

import pytest

from nca.abi import Calls, Contract, Manifest, TypeId, elem_type, seq_type
from nca.optimize import Option, cheapest_within, plan_min, plan_pareto, slot_calls
from nca.planner import Apply, Given, Map, elem_candidates, plan
from nca.router import infer


@dataclass
class Stub:
    manifest: Manifest

    def invoke(self) -> None:
        raise AssertionError("not executed")


def all_plans(modules: list[Stub], avail: tuple[TypeId, ...], t: TypeId, n: int,
              length: int, errors: dict[str, float], expected: bool = False) -> list[Option]:
    """Every searchable plan within fuel ``n``, by exhaustive enumeration."""
    if n == 0:
        return []
    if t in avail:
        return [Option(Given(t), 0.0, 0.0)]
    found: list[Option] = []
    for module in modules:
        contract = module.manifest.contract
        if contract.output != t:
            continue
        choices = [all_plans(modules, avail, i, n - 1, length, errors, expected)
                   for i in contract.inputs]
        fills = [all_plans(modules, inputs, out, n - 1, length, errors, expected)
                 for inputs, out in contract.slots]
        calls = slot_calls(module.manifest, length, expected)

        def combine(k: int, picked: list[Option]) -> None:
            if k == len(choices) + len(fills):
                args, slots = picked[:len(choices)], picked[len(choices):]
                found.append(Option(
                    Apply(module, tuple(o.plan for o in args), tuple(o.plan for o in slots)),
                    module.manifest.cost + sum(o.cost for o in args)
                    + sum(c * o.cost for c, o in zip(calls, slots)),
                    errors.get(module.manifest.ref, 0.0) + sum(o.error for o in args)
                    + sum(c * o.error for c, o in zip(calls, slots))))
                return
            for option in (choices + fills)[k]:
                combine(k + 1, [*picked, option])

        combine(0, [])
    element_goal = elem_type(t)
    if element_goal is not None:
        for a in elem_candidates(modules, avail):
            for body in all_plans(modules, (a,), element_goal, n - 1, length, errors, expected):
                for source in all_plans(modules, avail, seq_type(a), n - 1, length, errors,
                                        expected):
                    found.append(Option(Map(a, body.plan, source.plan),
                                        length * body.cost + source.cost,
                                        length * body.error + source.error))
    return found


def random_library(rng: random.Random) -> list[Stub]:
    types = ["a", "b", "c", "d"]
    modules = []
    for i in range(rng.randint(1, 7)):
        inputs = tuple(rng.sample(types + ["seq[a]"], rng.randint(0, 2)))
        output = rng.choice(types + ["seq[a]", "seq[b]"])
        modules.append(Stub(Manifest(f"m{i}", "1.0.0", Contract(inputs, output),
                                     cost=float(rng.randint(1, 9)))))
    return modules


def test_cost_planners_preserve_order_between_exact_and_generic_producers() -> None:
    exact = Stub(Manifest("exact", "1.0.0", Contract(("a",), "box[a]")))
    generic = Stub(Manifest("generic", "1.0.0", Contract(("?x",), "box[?x]")))
    for modules in ([exact, generic], [generic, exact]):
        result = plan_min(modules, ("a",), "box[a]", length=1, fuel=2)
        assert result is not None and isinstance(result[0], Apply)
        assert result[0].module is modules[0]
        frontier = plan_pareto(modules, ("a",), "box[a]", length=1, errors={}, fuel=2)
        assert frontier and isinstance(frontier[0].plan, Apply)
        assert frontier[0].plan.module is modules[0]


def test_plan_min_is_sound_and_optimal_against_exhaustive_search() -> None:
    rng = random.Random(0)
    for _ in range(400):
        modules = random_library(rng)
        goal = rng.choice(["b", "c", "d", "seq[b]"])
        everything = all_plans(modules, ("a",), goal, 4, 3, {})
        result = plan_min(modules, ("a",), goal, length=3, fuel=4)
        if not everything:
            assert result is None
            continue
        assert result is not None
        best, cost = result
        assert cost == min(o.cost for o in everything)
        assert infer(modules, ("a",), best) == goal
        assert any(o.plan == best and o.cost == cost for o in everything)


def test_pareto_selects_cheapest_plan_meeting_error_target() -> None:
    rng = random.Random(1)
    for _ in range(300):
        modules = random_library(rng)
        errors = {m.manifest.ref: rng.choice([0.0, 0.01, 0.05, 0.2]) for m in modules}
        goal = rng.choice(["b", "c", "seq[b]"])
        everything = all_plans(modules, ("a",), goal, 4, 3, errors)
        frontier = plan_pareto(modules, ("a",), goal, 3, errors, fuel=4)
        for target in (0.0, 0.05, 0.3, float("inf")):
            feasible = [o for o in everything if o.error <= target + 1e-12]
            chosen = cheapest_within(frontier, target + 1e-12)
            if not feasible:
                assert chosen is None
            else:
                assert chosen is not None
                assert chosen.cost == pytest.approx(min(o.cost for o in feasible))


def test_pareto_is_sound_and_covers_exhaustive_search() -> None:
    """``NCA.planPareto_sound`` and ``NCA.planPareto_cover`` on random libraries."""
    rng = random.Random(2)
    for _ in range(300):
        modules = random_library(rng)
        errors = {m.manifest.ref: rng.choice([0.0, 0.01, 0.05, 0.2]) for m in modules}
        goal = rng.choice(["b", "c", "seq[b]"])
        everything = all_plans(modules, ("a",), goal, 4, 3, errors)
        frontier = plan_pareto(modules, ("a",), goal, 3, errors, fuel=4)
        for option in frontier:
            assert infer(modules, ("a",), option.plan) == goal
            assert any(o.plan == option.plan and o.cost == pytest.approx(option.cost)
                       and o.error == pytest.approx(option.error) for o in everything)
        for option in everything:
            assert any(f.cost <= option.cost + 1e-9 and f.error <= option.error + 1e-9
                       for f in frontier)


def higher_order_library(rng: random.Random) -> list[Stub]:
    """Random libraries in which some experts have slots with call bounds."""
    types = ["a", "b", "c", "d"]
    modules = random_library(rng)
    for i in range(rng.randint(1, 3)):
        slots = tuple(((rng.choice(types),), rng.choice(types))
                      for _ in range(rng.randint(1, 2)))
        calls = tuple(Calls(rng.choice([0.5, 1.0, 2.0]), rng.choice([0.0, 1.0])) for _ in slots)
        expected = tuple(Calls(c.fixed / 2, c.per_element / 2) for c in calls)
        inputs = tuple(rng.sample(types, rng.randint(0, 1)))
        modules.insert(rng.randint(0, len(modules)), Stub(Manifest(
            f"h{i}", "1.0.0", Contract(inputs, rng.choice(types), slots),
            cost=float(rng.randint(1, 9)), calls=calls,
            expected_calls=expected if rng.random() < 0.5 else None)))
    return modules


def test_slot_planners_match_exhaustive_search() -> None:
    """``plan_min`` (worst-case and expected calls) and ``plan_pareto`` with
    higher-order experts, against enumeration (``NCA.HPlan.cost_mono``)."""
    rng = random.Random(3)
    used = 0
    for _ in range(300):
        modules = higher_order_library(rng)
        errors = {m.manifest.ref: rng.choice([0.0, 0.01, 0.05, 0.2]) for m in modules}
        goal = rng.choice(["b", "c", "d"])
        for expected in (False, True):
            everything = all_plans(modules, ("a",), goal, 4, 3, errors, expected)
            result = plan_min(modules, ("a",), goal, length=3, fuel=4, expected=expected)
            if not everything:
                assert result is None
                continue
            assert result is not None
            best, cost = result
            assert cost == pytest.approx(min(o.cost for o in everything))
            assert infer(modules, ("a",), best) == goal
            used += isinstance(best, Apply) and bool(best.slots)
            frontier = plan_pareto(modules, ("a",), goal, 3, errors, fuel=4, expected=expected)
            for option in frontier:
                assert infer(modules, ("a",), option.plan) == goal
            for option in everything:
                assert any(f.cost <= option.cost + 1e-9 and f.error <= option.error + 1e-9
                           for f in frontier)
        stable = plan(modules, ("a",), goal, fuel=4)
        assert (stable is None) == (not all_plans(modules, ("a",), goal, 4, 3, errors))
        if stable is not None:
            assert infer(modules, ("a",), stable) == goal
    assert used > 20
