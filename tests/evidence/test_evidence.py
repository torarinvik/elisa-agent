"""Promotion among substitutes by attested evaluations (§30)."""

from typing import Any

import pytest

from nca.abi import Contract, Manifest
from nca.evidence import benchmark, evaluation, outcomes, promote
from nca.objects import Composite, Primitive, Store
from nca.packages import install
from nca.planner import Apply, plan_stable

ENTRY = f"{__name__}:make"
IMAGE, LABEL, ANSWER = "image.v1", "label.v1", "answer.v1"


class Expert:
    def __init__(self, name: str, inputs: list[str], output: str) -> None:
        self.manifest = Manifest(name, "1.0.0", Contract(tuple(inputs), output),
                                 effects=frozenset())

    def invoke(self, *values: Any) -> Any:
        return values[0]


def make(name: str, inputs: list[str], output: str) -> Expert:
    return Expert(name, inputs, output)


def primitive(name: str, inputs: list[str], output: str) -> Primitive:
    arguments = {"name": name, "inputs": inputs, "output": output}
    return Primitive(make(**arguments).manifest, ENTRY, arguments)


BENCH = benchmark([("sample", i) for i in range(40)])


def library(store: Store, readers: int) -> list:
    refs = [store.put(primitive(f"reader-{i}", [IMAGE], LABEL)) for i in range(readers)]
    refs.append(store.put(primitive("answer", [LABEL], ANSWER)))
    return install(store, store.put(Composite("world", "1", tuple(refs))))


def attest(store: Store, module: Any, right: int, issuer: str = "lab", total: int = 40) -> None:
    store.put(evaluation(module.identity, BENCH, [i < right for i in range(total)], issuer))


def test_evaluations_are_read_from_trusted_issuers_only() -> None:
    store = Store()
    reader = library(store, 1)[0]
    attest(store, reader, 30, issuer="lab")
    attest(store, reader, 40, issuer="vendor")
    assert outcomes(store, reader.identity, BENCH, {"lab"}) == tuple(i < 30 for i in range(40))
    assert outcomes(store, reader.identity, BENCH, {"nobody"}) is None
    with pytest.raises(ValueError, match="disagree"):
        outcomes(store, reader.identity, BENCH, {"lab", "vendor"})
    with pytest.raises(ValueError, match="canonical"):
        benchmark([object()])


def test_a_better_challenger_takes_the_incumbents_place_in_every_route() -> None:
    store = Store()
    modules = library(store, 2)
    incumbent, challenger, answer = modules
    attest(store, incumbent, 20)
    attest(store, challenger, 35)  # Discordant: 15 wins, no losses.
    before = plan_stable(modules, (IMAGE,), ANSWER)
    promoted, promotions = promote(modules, store, BENCH, {"lab"})
    assert promoted == [challenger, incumbent, answer]
    (promotion,) = promotions
    assert (promotion.wins, promotion.losses) == (15, 0)
    assert promotion.p_value == pytest.approx(2.0 ** -15)
    after = plan_stable(promoted, (IMAGE,), ANSWER)
    assert isinstance(before, Apply) and isinstance(after, Apply)
    assert after.module is before.module is answer
    assert before.args[0].module is incumbent and after.args[0].module is challenger
    # The same evidence promotes nothing further, and exchanging back
    # restores the original route exactly.
    assert promote(promoted, store, BENCH, {"lab"}) == (promoted, [])
    assert plan_stable([incumbent, challenger, answer], (IMAGE,), ANSWER) == before


def test_weak_or_untrusted_evidence_promotes_nothing() -> None:
    store = Store()
    modules = library(store, 2)
    attest(store, modules[0], 20)
    attest(store, modules[1], 23)  # Three wins: p = 1/8.
    assert promote(modules, store, BENCH, {"lab"}) == (modules, [])
    attest(store, modules[1], 40, issuer="vendor")
    assert promote(modules, store, BENCH, {"lab"})[1] == []
    assert promote(modules, store, BENCH, {"vendor"})[1] == []  # No evidence on the incumbent.


def test_the_level_is_shared_among_challengers() -> None:
    # Five wins and no losses give p = 1/32: enough at α = 0.05 for one
    # challenger, not at α / 2 for two.
    store = Store()
    modules = library(store, 2)
    attest(store, modules[0], 20)
    attest(store, modules[1], 25)
    assert len(promote(modules, store, BENCH, {"lab"})[1]) == 1
    store = Store()
    modules = library(store, 3)
    attest(store, modules[0], 20)
    attest(store, modules[1], 25)
    attest(store, modules[2], 21)
    assert promote(modules, store, BENCH, {"lab"})[1] == []
