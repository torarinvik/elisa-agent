"""Valid risk reports and exact-rational links to conservative ledger folds."""

import math
import random
import struct
from fractions import Fraction
from itertools import product
from typing import Any

import numpy as np
import pytest

from nca.abi import Contract, Manifest, Message
from nca.compile import compile_route
from nca.evidence import answer_within
from nca.native import load
from nca.planner import Apply, Given
from nca.runtime import RiskLedger, execute
from nca.runtime import ledger as accounting
from nca.workspace import Workspace


class Reported:
    manifest = Manifest("numeric-report", "1", Contract(("source",), "source"), effects=frozenset())

    def __init__(self, report: Any) -> None:
        self.report = report

    def invoke(self, value: int) -> int:
        return value

    def risk(self, output: int, *values: int) -> Any:
        return self.report


@pytest.mark.parametrize("native", [False, True])
def test_upper_add_matches_exact_binary64_sums(native: bool, monkeypatch: pytest.MonkeyPatch) -> None:
    kernel = getattr(load("stats"), "nonnegative_add_upper", None)
    if native and kernel is None:
        pytest.skip("native upward adder unavailable or disabled")
    monkeypatch.setattr(accounting, "_ADD_UPPER", kernel if native else None)
    edges = [0.0, math.ulp(0.0), 2.0 ** -1022, 2.0 ** -54, 0.5, 1.0,
             math.nextafter(math.inf, 0.0)]
    rng = random.Random(3716)
    values = list(edges)
    while len(values) < 2050:
        value = struct.unpack(">d", (rng.getrandbits(64) & ((1 << 63) - 1)).to_bytes(8, "big"))[0]
        if math.isfinite(value):
            values.append(value)
    pairs = [*product(edges, repeat=2), *zip(values, reversed(values), strict=True)]
    for a, b in pairs:
        total = accounting._add_upper(a, b)
        exact = Fraction(a) + Fraction(b)
        assert total >= max(a, b)
        if math.isinf(total):
            assert Fraction(math.nextafter(total, 0.0)) < exact
        else:
            assert Fraction(total) >= exact
            if total:
                assert Fraction(math.nextafter(total, -math.inf)) < exact
    # ledger_fold_upper: each stored prefix bounds all exact binary reports.
    charge, exact = 0.0, Fraction()
    for report in [0.5, *([2.0 ** -54] * 100), math.ulp(0.0)]:
        charge = accounting._add_upper(charge, report)
        exact += Fraction(report)
        assert Fraction(charge) >= exact
    assert accounting._add_upper(0.25, 0.25) == 0.5  # No gratuitous padding.


@pytest.mark.parametrize("report", [-0.5, float("nan"), float("inf"), -float("inf"),
                                    True, "0.25", [0.25], 1j])
@pytest.mark.parametrize("compiled", [False, True])
def test_invalid_reports_cannot_return_a_certified_answer(report: Any, compiled: bool) -> None:
    route = Apply(Reported(report), (Given("source"),))
    ledger = RiskLedger()
    with pytest.raises(ValueError, match="risk report"):
        if compiled:
            compile_route(route, ("source",))([(7,)], ledgers=[ledger])
        else:
            execute(route, (Message("source", 7, "input"),), Workspace(), 2, ledger=ledger)
    assert ledger.charge == 0 and ledger.entries == []


def test_report_conversion_is_outward_and_missing_is_uncertified() -> None:
    for value in (Fraction(1, 3), Fraction(1, 10 ** 400), 2 ** 53 + 1, np.float32(0.125)):
        converted = accounting._report_upper(value)
        assert Fraction(converted) >= value
    with pytest.raises(ValueError, match="risk report"):
        accounting._report_upper(-Fraction(1, 10 ** 400))
    ledger = RiskLedger()
    execute(Apply(Reported(None), (Given("source"),)), (Message("source", 7, "input"),),
            Workspace(), 2, ledger=ledger)
    assert not ledger.certified
    assert Fraction(RiskLedger(charge=Fraction(1, 3)).charge) >= Fraction(1, 3)
    assert RiskLedger(charge=math.inf).charge == math.inf  # An exhausted upper bound.


@pytest.mark.parametrize("initial", [-1.0, math.nan, -math.inf, True])
def test_invalid_initial_ledger_charge_is_rejected(initial: Any) -> None:
    with pytest.raises(ValueError, match="risk report"):
        RiskLedger(charge=initial)


def test_budget_boundary_cannot_hide_a_positive_report() -> None:
    route = Apply(Reported(2.0 ** -54), (Apply(Reported(0.5), (Given("source"),)),))
    answer, ledger = answer_within(route, (Message("source", 7, "input"),), 0.5)
    assert answer is None and ledger.certified and ledger.charge == math.nextafter(0.5, math.inf)
    compiled = RiskLedger()
    assert compile_route(route, ("source",))([(7,)], ledgers=[compiled]) == [7]
    assert compiled.charge == ledger.charge
