"""Charging experts fed refined values through upcasts (§29.7)."""

from typing import Any

import pytest

from nca.abi import Contract, Manifest, Module, TypeId
from nca.evidence import route_risk
from nca.objects import Constructor
from nca.packages import Upcast
from nca.planner import Apply, Given, Plan

GENERAL = Constructor("record", "1.0.0", 0, "A hypothetical general value.")
REFINED = Constructor("narrow-record", "1.0.0", 0, "A hypothetical narrower value.",
                      (GENERAL.ref,))
RATES = {"produce": 0.01, "consume": 0.02, "other": 0.04}


class Expert:
    def __init__(self, name: str, inputs: tuple[str, ...], output: str) -> None:
        self.manifest = Manifest(name, "1.0.0", Contract(inputs, output), effects=frozenset())

    def invoke(self, *values: Any) -> Any:
        return values[0]


def rate(module: Module) -> float | None:
    return RATES.get(module.manifest.module_id)


def fed_route() -> Plan:
    produced = Apply(Expert("produce", ("source",), REFINED.type()), (Given("source"),))
    upcast = Apply(Upcast(REFINED, 0), (produced,))
    return Apply(Expert("consume", (GENERAL.type(),), "answer"), (upcast,))


def test_without_a_certificate_rates_are_taken_in_situ() -> None:
    assert route_risk(fed_route(), rate) == pytest.approx(0.03)


def test_a_certificate_scales_the_fed_expert_only() -> None:
    """``NCA.slot_risk_transfer``: charged ``c`` times its measured rate."""
    seen: list[tuple[str, tuple[TypeId, ...]]] = []

    def shift(module: Module, types: tuple[TypeId, ...]) -> float | None:
        seen.append((module.manifest.module_id, types))
        return 3.0

    assert route_risk(fed_route(), rate, shift=shift) == pytest.approx(0.01 + 3 * 0.02)
    assert seen == [("consume", (REFINED.type(),))]
    assert route_risk(fed_route(), rate, shift=shift, relevant=True) == pytest.approx(0.07)
    assert route_risk(fed_route(), rate, shift=lambda m, t: 1000.0) == pytest.approx(1.01)


def test_a_missing_certificate_leaves_the_risk_unknown() -> None:
    """``NCA.slot_risk_unbounded``: a general rate bounds nothing on refined inputs."""
    assert route_risk(fed_route(), rate, shift=lambda m, t: None) is None
    direct = Apply(Expert("other", (GENERAL.type(),), "answer"), (Given(GENERAL.type()),))
    assert route_risk(direct, rate, shift=lambda m, t: None) == pytest.approx(0.04)
