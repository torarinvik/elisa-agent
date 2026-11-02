"""Compiled routes agree with the runtime (THEORY §34)."""

from typing import Any

import pytest

from nca.abi import NOTHING, Contract, Demand, Manifest, Message, Request, SequenceDemand
from nca.compile import NotCompilable, compile_route
from nca.planner import Apply, Given, Map
from nca.runtime import execute
from nca.workspace import Workspace

TEXT, WORD, LENGTH, LENGTHS, TOTAL = "text.v1", "word.v1", "len.v1", "list[len.v1]", "total.v1"


class Expert:
    def __init__(self, name: str, inputs: tuple[str, ...], output: str, function: Any,
                 slots: tuple = ()) -> None:
        self.manifest = Manifest(name, "1.0.0", Contract(inputs, output, slots))
        self.function = function
        self.calls = 0

    def invoke(self, *values: Any) -> Any:
        self.calls += 1
        return self.function(*values)


class Batched(Expert):
    def __init__(self, *args: Any) -> None:
        super().__init__(*args)
        self.batches: list[int] = []

    def invoke_batch(self, column: list[Any]) -> list[Any]:
        self.batches.append(len(column))
        return [self.function(value) for value in column]


class EvenReader(Expert):
    """Sums the lengths at even positions, reading nothing at odd ones."""

    def demand(self, index: int, demand: Demand) -> Demand:
        return SequenceDemand(lambda i, n: None if i % 2 == 0 else NOTHING)


def route(measure: Expert, total: Expert) -> Apply:
    split = Expert("split", (TEXT,), f"list[{WORD}]", str.split)
    mapped = Map(WORD, Apply(measure, (Given(WORD),)), Apply(split, (Given(TEXT),)))
    return Apply(total, (mapped,))


def run(plan: Apply, text: str) -> Any:
    return execute(plan, [Message(TEXT, text, "input")], Workspace(), 100).payload


TEXTS = ["a bc def", "", "gh", "i jk lmn opqr st"]


def test_compiled_route_equals_the_runtime_and_batches_maps() -> None:
    measure = Batched("measure", (WORD,), LENGTH, len)
    plan = route(measure, Expert("total", (LENGTHS,), TOTAL, sum))
    compiled = compile_route(plan, (TEXT,))
    assert compiled([(t,) for t in TEXTS]) == [run(plan, t) for t in TEXTS] == [6, 0, 2, 12]
    assert measure.batches == [9]  # Every row's words in one call.
    assert compiled([]) == []


def test_compiled_route_honors_demand_per_element() -> None:
    measure = Batched("measure", (WORD,), LENGTH, len)
    reader = EvenReader("even", (LENGTHS,), TOTAL,
                        lambda xs: sum(x for i, x in enumerate(xs) if i % 2 == 0))
    plan = route(measure, reader)
    assert compile_route(plan, (TEXT,))([(t,) for t in TEXTS]) == [run(plan, t) for t in TEXTS]
    assert measure.batches == [6]  # Even positions only: 2 + 0 + 1 + 3.


def test_experts_without_batch_forms_are_invoked_per_row() -> None:
    measure = Expert("measure", (WORD,), LENGTH, len)
    plan = route(measure, Expert("total", (LENGTHS,), TOTAL, sum))
    assert compile_route(plan, (TEXT,))([(t,) for t in TEXTS]) == [6, 0, 2, 12]
    assert measure.calls == 9


def test_routes_needing_the_kernel_are_not_compiled() -> None:
    slot = ((WORD,), LENGTH)
    higher = Expert("higher", (TEXT,), TOTAL, lambda f, t: 0, slots=(slot,))
    plan = Apply(higher, (Given(TEXT),), (Apply(Expert("m", (WORD,), LENGTH, len),
                                                (Given(WORD),)),))
    with pytest.raises(NotCompilable, match="slots"):
        compile_route(plan, (TEXT,))
    asking = Expert("ask", (TEXT,), TOTAL, lambda t: Request(TOTAL, ((TEXT, t),)))
    with pytest.raises(NotCompilable, match="kernel"):
        compile_route(Apply(asking, (Given(TEXT),)), (TEXT,))([("x",)])
