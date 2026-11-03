"""Plasticity signals from runtime ledgers, audits and dependents (§43.9)."""

from collections.abc import Hashable
from dataclasses import dataclass
from typing import Any

import pytest

from nca.abi import Contract, Manifest, Message
from nca.evidence import audit
from nca.planner import Apply, Given
from nca.retention.plasticity import PlasticityField, Smoothing
from nca.retention.routes import ProtectedRoute, RouteCatalog
from nca.retention.signals import identity, observe, stability, surprise
from nca.runtime import Invocation, RiskLedger, execute
from nca.workspace import Workspace


@dataclass
class Reporter:
    """Echoes its input and reports a fixed risk per input region."""

    name: str
    risks: dict[str, float]

    @property
    def identity(self) -> str:
        return f"{self.name}@1"

    @property
    def manifest(self) -> Manifest:
        return Manifest(self.name, "1", Contract(("input",), "output"), effects=frozenset())

    def invoke(self, value: str) -> str:
        return value

    def risk(self, output: Any, value: str) -> float:
        return self.risks[value[0]]


def run(expert: Reporter, values: list[str]) -> list[RiskLedger]:
    plan = Apply(expert, (Given("input", 0),))
    ledgers = []
    for value in values:
        ledger = RiskLedger()
        execute(plan, (Message("input", value, "input"),), Workspace(), 4, ledger=ledger)
        ledgers.append(ledger)
    return ledgers


def region(invocation: Invocation) -> Hashable:
    return identity(invocation), invocation.values[0][0]


def test_surprise_is_mean_reported_risk_per_key() -> None:
    expert = Reporter("reader", {"a": 0.1, "b": 0.7})
    ledgers = run(expert, ["a1", "a2", "b1", "a3"])
    assert surprise(ledgers) == {"reader@1": pytest.approx((0.1 * 3 + 0.7) / 4)}
    assert surprise(ledgers, region) == {("reader@1", "a"): pytest.approx(0.1),
                                         ("reader@1", "b"): pytest.approx(0.7)}
    skipped = surprise(ledgers, lambda invocation: None)
    assert skipped == {}


def test_refuting_audits_raise_silent_failures_to_full_surprise() -> None:
    expert = Reporter("reader", {"a": 0.01})
    ledgers = run(expert, ["a1"] * 20)
    silent = audit([0.01] * 20, [True] * 10 + [False] * 10)
    calm = audit([0.01] * 20, [False] * 20)
    signals = surprise(ledgers, audits={"reader@1": silent, "other@1": calm})
    assert signals == {"reader@1": 1.0, "other@1": 0.0}
    with pytest.raises(ValueError, match="alpha"):
        surprise(ledgers, alpha=0.0)


def test_stability_counts_protected_dependents() -> None:
    shared, lone = Reporter("shared", {"a": 0.0}), Reporter("lone", {"a": 0.0})

    def route(anchor: str, expert: Reporter) -> ProtectedRoute:
        return ProtectedRoute(anchor, ("input",), Apply(expert, (Given("input", 0),)),
                              lambda record: ((), None), lambda output, label: True)

    catalog = RouteCatalog((route("x", shared), route("y", shared), route("z", lone)), ())
    assert stability(catalog, shared) == pytest.approx(2 / 3)
    assert stability(catalog, lone) == pytest.approx(1 / 2)
    assert stability(catalog, Reporter("unused", {})) == 0.0
    with pytest.raises(ValueError, match="half"):
        stability(catalog, shared, half=0.0)


def test_ledger_windows_drive_the_field() -> None:
    expert = Reporter("reader", {"a": 0.05, "b": 0.9})
    field = PlasticityField(Smoothing(0.5), open_at=0.4, close_at=0.15)
    for _ in range(3):
        observe(field, surprise(run(expert, ["a1", "b1", "a2", "b2"]), region),
                lambda key: 0.0)
    assert field.is_open(("reader@1", "b")) and not field.is_open(("reader@1", "a"))
