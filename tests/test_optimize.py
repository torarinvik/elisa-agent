import random
from dataclasses import dataclass

import pytest

from nca.abi import Contract, Manifest, TypeId, elem_type, seq_type
from nca.optimize import Option, cheapest_within, plan_min, plan_pareto
from nca.planner import Apply, Given, Map, elem_candidates
from nca.router import infer


@dataclass
class Stub:
    manifest: Manifest

    def invoke(self) -> None:
        raise AssertionError("not executed")


def all_plans(modules: list[Stub], avail: tuple[TypeId, ...], t: TypeId, n: int,
              length: int, errors: dict[str, float]) -> list[Option]:
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
        choices = [all_plans(modules, avail, i, n - 1, length, errors) for i in contract.inputs]

        def combine(k: int, picked: list[Option]) -> None:
            if k == len(choices):
                found.append(Option(Apply(module, tuple(o.plan for o in picked)),
                                    module.manifest.cost + sum(o.cost for o in picked),
                                    errors.get(module.manifest.ref, 0.0)
                                    + sum(o.error for o in picked)))
                return
            for option in choices[k]:
                combine(k + 1, [*picked, option])

        combine(0, [])
    element_goal = elem_type(t)
    if element_goal is not None:
        for a in elem_candidates(modules, avail):
            for body in all_plans(modules, (a,), element_goal, n - 1, length, errors):
                for source in all_plans(modules, avail, seq_type(a), n - 1, length, errors):
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
