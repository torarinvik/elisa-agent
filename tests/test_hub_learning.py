"""Learning hub connectors by attachment, without hub labels (§29.5)."""

from functools import partial

import pytest

from nca.abi import Contract, Message, Module
from nca.learning.discovery import fit_decoder
from nca.learning.hub import attach
from nca.planner import plan
from nca.runtime import execute
from nca.workspace import Workspace

HUB = "hub.learned"
fit = partial(fit_decoder, cost=1.0)


def code(k: int, value: int) -> str:
    return f"{k}:{(value * (2 * k + 3)) % 17}"


def test_attached_types_translate_through_a_hub_none_observed() -> None:
    values = list(range(17))
    founder = fit(Contract(("type0",), HUB), [code(0, v) for v in values],
                  [code(0, v) for v in values])
    modules = [founder, fit(Contract((HUB,), "type0"), [code(0, v) for v in values],
                            [code(0, v) for v in values])]
    encoders = {0: founder}
    for k in range(1, 4):
        partner = k - 1
        pairs = [(code(k, v), code(partner, v)) for v in values]
        encoder, decoder = attach(f"type{k}", HUB, encoders[partner], pairs, fit)
        encoders[k] = encoder
        modules += [encoder, decoder]
    route = plan(modules, ("type3",), "type1")
    assert route is not None
    for v in values:
        out = execute(route, (Message("type3", code(3, v), "input"),), Workspace(), 4)
        assert out.payload == code(1, v)


def test_attachment_requires_a_partner_encoder_into_the_hub() -> None:
    other = fit(Contract(("type0",), "elsewhere"), ["a"], ["b"])
    with pytest.raises(ValueError, match="partner encoder"):
        attach("type1", HUB, other, [("x", "a")], fit)
    founder = fit(Contract(("type0",), HUB), ["a"], ["a"])
    with pytest.raises(ValueError, match="paired"):
        attach("type1", HUB, founder, [], fit)



def hub_version(hub: str, members: range) -> tuple[list[Module], Module]:
    """A hub founded by its first member, every other member attached to it."""
    values = list(range(17))
    first = members[0]
    exact = [code(first, v) for v in values]
    founder = fit(Contract((f"type{first}",), hub), exact, exact)
    modules = [founder, fit(Contract((hub,), f"type{first}"), exact, exact)]
    for k in members[1:]:
        modules += attach(f"type{k}", hub, founder,
                          [(code(k, v), code(first, v)) for v in values], fit)
    return modules, founder


def test_a_bridge_joins_hub_versions_and_keeps_old_routes() -> None:
    """``NCA.bridged_keeps`` and ``NCA.bridged_routes``: the new hub attaches
    to the old one once, through the old founder."""
    old, old_founder = hub_version(HUB, range(0, 3))
    new, _ = hub_version("hub.next", range(3, 6))
    pairs = [(code(3, v), code(0, v)) for v in range(17)]
    bridged = [*old, *new, *attach("hub.next", HUB, old_founder, pairs, fit)]
    for version, i, j in ((old, 0, 2), (new, 4, 5)):
        assert plan(bridged, (f"type{i}",), f"type{j}") == plan(version, (f"type{i}",),
                                                                f"type{j}")
    for i, j in ((1, 5), (4, 2)):
        route = plan(bridged, (f"type{i}",), f"type{j}")
        assert route is not None
        for v in range(17):
            out = execute(route, (Message(f"type{i}", code(i, v), "input"),), Workspace(), 4)
            assert out.payload == code(j, v)
