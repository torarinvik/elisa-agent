"""Compiled routes agree with the runtime (THEORY §34)."""

from typing import Any

import pytest

from nca.abi import NOTHING, Contract, Demand, Manifest, Message, Request, SequenceDemand
from nca.cache import ResultCache
from nca.compile import NotCompilable, compile_route
from nca.planner import Apply, Given, Map
from nca.runtime import RiskLedger, execute
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


class Reporting(Batched):
    """Reports a risk that depends on its output, and is pure and identified."""

    def __init__(self, *args: Any) -> None:
        super().__init__(*args)
        self.manifest = Manifest(self.manifest.module_id, "1.0.0", self.manifest.contract,
                                 effects=frozenset())
        self.identity = "measure-ref"

    def risk(self, output: int) -> float:
        return 0.01 * output


def ledger_of(plan: Apply, text: str) -> RiskLedger:
    ledger = RiskLedger()
    execute(plan, [Message(TEXT, text, "input")], Workspace(), 100, ledger=ledger)
    return ledger


def test_compiled_ledgers_charge_each_row_as_the_runtime_does() -> None:
    reader = EvenReader("even", (LENGTHS,), TOTAL,
                        lambda xs: sum(x for i, x in enumerate(xs) if i % 2 == 0))
    plan = route(Reporting("measure", (WORD,), LENGTH, len), reader)
    ledgers = [RiskLedger() for _ in TEXTS]
    compile_route(plan, (TEXT,))([(t,) for t in TEXTS], ledgers=ledgers)
    for text, ledger in zip(TEXTS, ledgers):
        expected = ledger_of(plan, text)
        assert ledger.charge == pytest.approx(expected.charge)
        assert ledger.uncertified == expected.uncertified
        assert [(m, v) for m, v, _ in ledger.entries] == [(m, v) for m, v, _ in expected.entries]
    # Only even-position words are charged; split and even report nothing.
    assert ledgers[0].charge == pytest.approx(0.04)
    assert ledgers[0].uncertified == ["split", "even"]
    with pytest.raises(ValueError, match="ledgers"):
        compile_route(plan, (TEXT,))([("a",)], ledgers=[])


def test_compiled_routes_read_and_fill_the_cache_once_per_distinct_input() -> None:
    measure = Reporting("measure", (WORD,), LENGTH, len)
    plan = route(measure, Expert("total", (LENGTHS,), TOTAL, sum))
    compiled, cache = compile_route(plan, (TEXT,)), ResultCache()
    rows = [("a bb a",), ("bb ccc",)]
    assert compiled(rows, cache=cache) == [4, 5]
    assert measure.batches == [3]  # "a", "bb", "ccc": duplicates evaluated once.
    assert compiled(rows, cache=cache) == [4, 5]
    assert measure.batches == [3]  # Every word served by the cache.
    checked = ResultCache(check_rate=1.0)
    compiled(rows, cache=checked)
    compiled(rows, cache=checked)
    assert measure.batches == [3, 3, 3] and checked.checks["measure-ref"].checked == 3
