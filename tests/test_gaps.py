"""Capability gaps and kernel-mediated acquisition (§20.9)."""

from collections.abc import Generator
from itertools import combinations, product
import random
from typing import Any

import pytest

from nca.abi import Contract, Manifest, Message, Module, Request
from nca.kernel import Kernel
from nca.planner import plan
from nca.planner.gaps import fewest_missing, gaps, repair
from nca.runtime import execute
from nca.workspace import Workspace


class Step:
    """Adds ``delta`` to its inputs; with ``requests``, it asks the kernel for a
    value of that type from its input and continues with the answer."""

    def __init__(self, inputs: tuple[str, ...], output: str, delta: int = 1,
                 requests: str | None = None) -> None:
        self.delta, self.requests = delta, requests
        name = f"{'+'.join(inputs)}->{output}"
        self.manifest = Manifest(name, "1", Contract(inputs, output), effects=frozenset())

    def invoke(self, *values: Any) -> Any:
        if self.requests is not None:
            return self.ask(values[0])
        return sum(values) + self.delta

    def ask(self, value: int) -> Generator[Request, object, object]:
        answer = yield Request(str(self.requests), (("s", value),))
        return answer


LIBRARY = [Step(("s",), "x"), Step(("x",), "y"), Step(("z",), "g"), Step(("y", "s"), "w"),
           Step(("w",), "v")]
TYPES = ["s", "x", "y", "z", "g", "w", "v", "u"]


def test_gaps_are_exactly_the_single_connector_repairs() -> None:
    """``NCA.gap_iff``, differentially against the planner over every pair."""
    found = {gap.contract for gap in gaps(LIBRARY, ("s",), "g")}
    for source, target in product(TYPES, TYPES):
        if source == target:
            continue
        repaired = plan([*LIBRARY, Step((source,), target)], ("s",), "g") is not None
        assert repaired == (Contract((source,), target) in found), (source, target)
    assert Contract(("w",), "z") in found and Contract(("u",), "g") not in found


def test_no_gaps_when_a_route_exists() -> None:
    assert gaps(LIBRARY, ("s",), "v") == []


def test_repair_avoids_refused_connectors_and_keeps_acquisitions() -> None:
    asked: list[Contract] = []

    def acquire(contract: Contract) -> Module | None:
        asked.append(contract)
        return Step(contract.inputs, contract.output, 10) if contract == Contract(
            ("y",), "z") else None

    repaired = repair(LIBRARY, ("s",), "g", acquire, attempts=100)
    assert repaired is not None and repaired.requests == len(asked) == len(set(asked))
    assert [m.manifest.contract for m in repaired.acquired] == [Contract(("y",), "z")]
    result = execute(repaired.route, (Message("s", 0, "input"),), Workspace(), 10)
    assert result.payload == 13
    assert repair(LIBRARY, ("s",), "g", lambda contract: None, attempts=5) is None


def test_repair_rejects_an_expert_with_another_contract() -> None:
    with pytest.raises(ValueError, match="contract"):
        repair(LIBRARY, ("s",), "g", lambda contract: Step(("s",), "u"), attempts=1)


def test_repair_falls_back_to_longer_routes_around_refusals() -> None:
    """``NCA.repair_sound``: with direct jumps refused, two acquired connectors
    complete the route."""
    library = [Step(("s",), "x"), Step(("y",), "z"), Step(("w",), "g")]
    allowed = {Contract(("x",), "y"), Contract(("z",), "w")}

    def acquire(contract: Contract) -> Module | None:
        return Step(contract.inputs, contract.output, 0) if contract in allowed else None

    assert repair(library, ("s",), "g", acquire, attempts=100) is None
    repaired = repair(library, ("s",), "g", acquire, attempts=100, missing=2)
    assert repaired is not None
    assert {m.manifest.contract for m in repaired.acquired} == allowed
    result = execute(repaired.route, (Message("s", 0, "input"),), Workspace(), 10)
    assert result.payload == 3


def test_fewest_missing_is_minimal_against_brute_force() -> None:
    """``NCA.repair_complete``: no smaller set of allowed connectors reaches the goal."""
    rng = random.Random(7)
    types = [f"t{k}" for k in range(6)]
    pairs = [(a, b) for a, b in product(types, types) if a != b]
    sizes = set()
    for _ in range(60):
        library = [Step((a,), b) for a, b in (rng.sample(types, 2) for _ in range(4))]
        allowed = rng.sample(pairs, 6)
        refused = frozenset(set(pairs) - set(allowed))
        source, goal = rng.sample(types, 2)
        least = None
        for size in range(4):
            if any(plan([*library, *(Step((a,), b) for a, b in added)], (source,), goal)
                   for added in combinations(allowed, size)):
                least = size
                break
        path = fewest_missing(library, (source,), goal, 3, refused)
        assert (None if path is None else len(path)) == least
        assert path is None or set(path) <= set(allowed)
        sizes.add(least)
    assert {2, 3} & sizes


def test_the_kernel_serves_an_unservable_request_by_acquisition() -> None:
    asker = Step(("s",), "answer", requests="g")
    route = plan([asker], ("s",), "answer")
    assert route is not None
    with pytest.raises(Exception, match="no route"):
        execute(route, (Message("s", 0, "input"),), Workspace(), 10, Kernel(LIBRARY))

    def acquire(contract: Contract) -> Module | None:
        return Step(contract.inputs, contract.output, 100) if contract.output == "z" else None

    kernel = Kernel(LIBRARY, acquire=acquire)
    result = execute(route, (Message("s", 0, "input"),), Workspace(), 10, kernel)
    assert len(kernel.acquired) == 1 and kernel.acquired[0].manifest.contract.output == "z"
    assert result.payload == {"s": 101, "x": 102, "y": 103}[
        kernel.acquired[0].manifest.contract.inputs[0]]
    again = execute(route, (Message("s", 0, "input"),), Workspace(), 10, kernel)
    assert again.payload == result.payload and len(kernel.acquired) == 1
