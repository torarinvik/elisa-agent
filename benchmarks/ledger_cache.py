"""Risk-account replay across direct, erased-reference and declared lazy calls.

The erased wrapper models the former boundary for comparison only; fixed lazy
loaders reject a declaration that differs from the loaded implementation.
"""

from __future__ import annotations

import json
from time import process_time
from typing import Any

from nca.abi import Contract, Manifest, Message, Module
from nca.cache import ResultCache
from nca.compile import compile_route
from nca.loader import ExpertStore, LazyExpert
from nca.planner import Apply, Given
from nca.runtime import RiskLedger, execute
from nca.workspace import Workspace


class Reported:
    manifest = Manifest("benchmark.reported", "1", Contract(("source",), "result"),
                        effects=frozenset())

    def __init__(self, report: float) -> None:
        self.report = report

    def invoke(self, value: int) -> int:
        return value

    def risk(self, output: int, *values: int) -> float:
        return self.report


class Inside:
    accounts_inside = True
    manifest = Manifest("benchmark.inside", "1", Reported.manifest.contract, effects=frozenset())

    def __init__(self, report: float) -> None:
        self.child, self.calls = Reported(report), 0

    def invoke(self, value: int) -> int:
        self.calls += 1
        return execute(Apply(self.child, (Given("source"),)),
                       (Message("source", value, "input"),), Workspace(), 2).payload


class ErasedReference:
    """An intentionally unfaithful projection, never a production loader mode."""

    def __init__(self, nested: Inside) -> None:
        self.nested, self.manifest, self.identity = nested, nested.manifest, "benchmark.erased"

    def invoke(self, value: int) -> int:
        return self.nested.invoke(value)

    def risk(self, output: int, *values: int) -> float:
        return 0.0


def trial(policy: str, compiled: bool, calls: int = 100, report: float = 0.25) -> dict[str, Any]:
    started = process_time()
    nested = Inside(report)
    module: Module
    if policy == "direct":
        module = nested
    elif policy == "erased-reference":
        module = ErasedReference(nested)
    else:
        module = LazyExpert(nested.manifest, lambda: nested, 0, ExpertStore(),
                            identity="benchmark.declared", accounts_inside=True)
    route = Apply(module, (Given("source"),))
    cache = ResultCache()
    inputs = (Message("source", 7, "input"),)
    execute(route, inputs, Workspace(), 3, cache=cache)  # Warm value cache without a ledger.
    ledgers = [RiskLedger() for _ in range(calls)]
    if compiled:
        assert compile_route(route, ("source",))([(7,)] * calls, cache, ledgers) == [7] * calls
    else:
        for ledger in ledgers:
            assert execute(route, inputs, Workspace(), 3, cache=cache, ledger=ledger).payload == 7
    return {"policy": policy, "compiled": compiled, "requests": calls,
            "expected_charge": calls * report, "actual_charge": sum(l.charge for l in ledgers),
            "underreports": sum(l.charge < report for l in ledgers),
            "certified": sum(l.certified for l in ledgers), "body_calls": nested.calls,
            "cache_hits": cache.stats.hits, "labels": 0, "acquisition_requests": 0,
            "cpu_seconds": process_time() - started}


if __name__ == "__main__":
    for compiled in (False, True):
        for policy in ("direct", "erased-reference", "declared-lazy"):
            print(json.dumps(trial(policy, compiled)), flush=True)
