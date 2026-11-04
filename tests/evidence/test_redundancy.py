"""Majority over redundant routes (§31.7)."""

import random
from itertools import combinations, product
from math import prod
from typing import Any

import pytest

from nca.abi import Contract, Manifest, Message, Module
from nca.evidence.redundancy import disjoint_routes, threshold, vote, vote_risk


class Shift:
    """Adds ``delta``; corrupts the value when ``wrong`` holds for it."""

    def __init__(self, name: str, source: str, target: str, delta: int = 1,
                 wrong: frozenset[int] = frozenset()) -> None:
        self.delta, self.wrong = delta, wrong
        self.manifest = Manifest(name, "1", Contract((source,), target), effects=frozenset())

    def invoke(self, value: int) -> int:
        return -1000 - value if value in self.wrong else value + self.delta


def paths(count: int, wrong: dict[int, frozenset[int]] | None = None) -> list[Module]:
    """``count`` parallel two-step paths from ``s`` to ``g`` through ``m{i}``."""
    wrong = wrong or {}
    return [m for i in range(count) for m in (
        Shift(f"in{i}", "s", f"m{i}", wrong=wrong.get(i, frozenset())),
        Shift(f"out{i}", f"m{i}", "g"))]


def test_disjoint_routes_share_no_expert() -> None:
    routes = disjoint_routes(paths(4), ("s",), "g", 3)
    assert len(routes) == 3
    names = [{route.module.manifest.module_id, route.args[0].module.manifest.module_id}
             for route in routes]
    assert all(a.isdisjoint(b) for a, b in combinations(names, 2))
    assert len(disjoint_routes(paths(2), ("s",), "g", 5)) == 2


def test_a_shared_expert_may_appear_in_every_route() -> None:
    hub = Shift("hub", "g", "h")
    routes = disjoint_routes([*paths(3), hub], ("s",), "h", 3,
                             shared=lambda m: m.manifest.module_id == "hub")
    assert len(routes) == 3


def test_vote_corrects_a_minority_and_abstains_without_a_majority() -> None:
    """``NCA.vote_correct``: fewer than ``t`` failing routes leave the answer correct."""
    one = disjoint_routes(paths(3, {0: frozenset({5})}), ("s",), "g", 3)
    result = vote(one, (Message("s", 5, "input"),), 10)
    assert result.answer == 7 and result.agreeing == 2
    two = disjoint_routes(paths(4, {0: frozenset({5}), 1: frozenset({5})}), ("s",), "g", 4)
    assert vote(two, (Message("s", 5, "input"),), 10).answer is None
    assert threshold(3) == 2 and threshold(4) == 2 and threshold(5) == 3


def test_exhausted_routes_abstain_without_lowering_the_majority_threshold() -> None:
    from nca.planner import Apply, Given
    from nca.retention.ensembles import EnsembleSearch

    long = Apply(Shift("second", "m", "g"), (Apply(Shift("first", "s", "m"), (Given("s"),)),))
    short = Apply(Shift("short", "s", "g", delta=2), (Given("s"),))
    inputs = (Message("s", 5, "input"),)
    assert vote((short, long), inputs, 1).agreeing == 0
    result = vote((short, short, long), inputs, 1)
    assert result.answer == 7 and result.agreeing == 2 and result.routes == 3
    gate = EnsembleSearch(counts=(1,), tolerance=.1, confidence=.05, budget=1)
    assert gate.revise(Contract(("s",), "g"), lambda cap, failures: (long,),
                       lambda count: [(inputs, 7)] * count) is None


def exact_failure(risks: list[float]) -> float:
    t = threshold(len(risks))
    total = 0.0
    for outcome in product((False, True), repeat=len(risks)):
        if sum(outcome) >= t:
            total += prod(r if f else 1 - r for r, f in zip(risks, outcome, strict=True))
    return total


def test_vote_risk_bounds_the_exact_failure_probability() -> None:
    """``NCA.vote_risk``: ``e_t`` bounds the chance that ``t`` independent routes fail."""
    assert vote_risk([0.1, 0.1, 0.1]) == pytest.approx(3 * 0.01)
    rng = random.Random(5)
    for _ in range(200):
        risks = [rng.random() * 0.4 for _ in range(rng.randrange(1, 8))]
        assert exact_failure(risks) <= vote_risk(risks) + 1e-12
    assert vote_risk([0.05] * 7) < vote_risk([0.05] * 3) < 0.05


def test_simulated_independent_routes_stay_within_the_bound() -> None:
    rng = random.Random(9)
    risk, trials, failures = 0.15, 4000, 0
    for _ in range(trials):
        broken = {i: frozenset({0}) for i in range(5) if rng.random() < risk}
        routes = disjoint_routes(paths(5, broken), ("s",), "g", 5)
        answer: Any = vote(routes, (Message("s", 0, "input"),), 10).answer
        failures += answer != 2
    assert failures / trials <= vote_risk([risk] * 5)
