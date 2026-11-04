"""Risk-account replay across direct, erased-reference and declared lazy calls.

The erased wrapper models the former boundary for comparison only; fixed lazy
loaders reject a declaration that differs from the loaded implementation.
"""

from __future__ import annotations

import json
import math
from fractions import Fraction
from time import process_time
from typing import Any

from nca.abi import Contract, Manifest, Message, Module
from nca.cache import ResultCache
from nca.compile import compile_route
from nca.loader import ExpertStore, LazyExpert
from nca.planner import Apply, Given
from nca.runtime import RiskLedger, execute
from nca.runtime import ledger as accounting
from nca.native import load
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


def numeric_trial(policy: str, repeats: int = 100) -> dict[str, Any]:
    """Compare admission arithmetic with identical report-record bookkeeping."""
    tight = (0.01,) * 50
    tight_sum = sum(map(Fraction, tight), Fraction())
    tight_budget = float(tight_sum)
    if Fraction(tight_budget) < tight_sum:
        tight_budget = math.nextafter(tight_budget, math.inf)
    cases = [((0.5, 2.0 ** -54), 0.5), ((0.5, *((2.0 ** -60,) * 64)), 0.5),
             ((0.25, 0.25), 0.5), (tight, tight_budget),
             ((-0.5,), 0.0), ((math.nan,), 0.0), ((math.inf,), 0.0)]
    cases = [(tuple(Reported(r) for r in values), budget,
              all(math.isfinite(r) and r >= 0 for r in values),
              sum(map(Fraction, values), Fraction()) if all(math.isfinite(r) for r in values) else None)
             for values, budget in cases]
    report_fn, add_fn, kernel = accounting._report_upper, accounting._add_upper, accounting._ADD_UPPER
    requested = getattr(load("stats"), "nonnegative_add_upper", None)
    if policy == "elisa" and requested is None:
        raise RuntimeError("native upward adder is unavailable")
    started = process_time()
    rejected = undercounts = bad_grants = extra_abstentions = requests = 0
    try:
        if policy == "legacy-reference":
            accounting._report_upper = lambda value, **kwargs: value
            accounting._add_upper = lambda a, b: a + b
        else:
            accounting._ADD_UPPER = requested if policy == "elisa" else None
        for _ in range(repeats):
            for modules, budget, valid, exact in cases:
                ledger = RiskLedger()
                try:
                    for module in modules:
                        requests += 1
                        accounting.charge(ledger, module, 7, None, [7])
                except ValueError:
                    assert not valid
                    rejected += 1
                    continue
                granted = ledger.certified and ledger.charge <= budget
                if not valid:
                    bad_grants += granted
                    continue
                undercounts += Fraction(ledger.charge) < exact
                bad_grants += granted and exact > Fraction(budget)
                extra_abstentions += not granted and exact <= Fraction(budget)
    finally:
        accounting._report_upper, accounting._add_upper, accounting._ADD_UPPER = report_fn, add_fn, kernel
    return {"policy": policy, "cases": repeats * len(cases), "report_requests": requests,
            "invalid_rejected": rejected, "understated_valid_cases": undercounts,
            "invalid_or_understated_grants": bad_grants, "extra_abstentions": extra_abstentions,
            "labels": 0, "acquisition_requests": 0, "cpu_seconds": process_time() - started}


if __name__ == "__main__":
    for compiled in (False, True):
        for policy in ("direct", "erased-reference", "declared-lazy"):
            print(json.dumps(trial(policy, compiled)), flush=True)
    for policy in ("legacy-reference", "python", "elisa"):
        if policy != "elisa" or getattr(load("stats"), "nonnegative_add_upper", None) is not None:
            print(json.dumps(numeric_trial(policy)), flush=True)
