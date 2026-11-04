"""Contributor types meeting through a shared hub type (§29.4)."""

from dataclasses import dataclass
from typing import Any

import pytest

from nca.abi import Contract, Manifest, Message
from nca.evidence import route_risk
from nca.planner import Apply, Given, plan
from nca.runtime import execute
from nca.workspace import Workspace

HUB = "hub.latent"  # A contributor-chosen shared type; the core defines none.


@dataclass
class Convert:
    """Converts between one contributor encoding and the hub."""

    name: str
    source: str
    target: str
    forward: dict[Any, Any]

    @property
    def manifest(self) -> Manifest:
        return Manifest(self.name, "1", Contract((self.source,), self.target),
                        effects=frozenset())

    def invoke(self, value: Any) -> Any:
        return self.forward[value]


def contributor(k: int) -> tuple[Convert, Convert]:
    encode = {f"{k}:{(v * (k + 2)) % 11}": v for v in range(11)}
    decode = {v: code for code, v in encode.items()}
    return (Convert(f"enc{k}", f"type{k}", HUB, encode),
            Convert(f"dec{k}", HUB, f"type{k}", decode))


def test_any_pair_routes_through_the_hub_with_two_connectors_each() -> None:
    """``NCA.hub_routes``: encoder then decoder joins every ordered pair."""
    modules = [module for k in range(5) for module in contributor(k)]
    assert len(modules) == 2 * 5
    for i in range(5):
        for j in range(5):
            if i == j:
                continue
            route = plan(modules, (f"type{i}",), f"type{j}")
            assert isinstance(route, Apply) and route.module.name == f"dec{j}"
            assert isinstance(route.args[0], Apply) and route.args[0].module.name == f"enc{i}"
            code = f"{i}:{(4 * (i + 2)) % 11}"
            result = execute(route, (Message(f"type{i}", code, "input"),), Workspace(), 4)
            assert result.payload == f"{j}:{(4 * (j + 2)) % 11}"


def test_adding_a_contributor_keeps_every_existing_route() -> None:
    """``NCA.hubConnectors_mono`` with planning stability (Theorem 3.3)."""
    old = [module for k in range(4) for module in contributor(k)]
    new = old + list(contributor(4))
    for i in range(4):
        for j in range(4):
            if i != j:
                before, after = plan(old, (f"type{i}",), f"type{j}"), plan(new, (f"type{i}",),
                                                                           f"type{j}")
                assert before == after


def test_hub_route_risk_is_encoder_plus_decoder() -> None:
    """``NCA.hub_route_risk`` via the route risk bound of §31."""
    modules = [module for k in range(3) for module in contributor(k)]
    route = plan(modules, ("type0",), "type2")
    rates = {"enc0": 0.01, "dec2": 0.02}
    assert route is not None
    risk = route_risk(route, lambda module: rates.get(module.manifest.module_id))
    assert risk == pytest.approx(0.03)
    assert isinstance(route.args[0], Apply) and isinstance(route.args[0].args[0], Given)
