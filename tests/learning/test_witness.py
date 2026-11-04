"""Witness suggestions are typed proposals, never admission decisions."""

from dataclasses import replace

import pytest

from nca.abi import Contract, Manifest
from nca.learning.witness import Decomposition, Example, Need, QuerySession, Request, Specification, decompositions
from nca.objects import Primitive, manifest_data, manifest_from


def test_manifest_witness_roundtrip_preserves_existing_references() -> None:
    manifest = Manifest("sample.expert", "1", Contract(("a",), "b"), effects=frozenset())
    data = manifest_data(manifest)
    assert "witness" not in data
    assert manifest_from(data) == manifest
    assert Primitive(manifest_from(data), "sample:expert").ref == Primitive(manifest, "sample:expert").ref
    described = replace(manifest, witness="sample:witness")
    assert manifest_from(manifest_data(described)) == described
    assert Primitive(described, "sample:expert").ref != Primitive(manifest, "sample:expert").ref
    query_described = replace(described, witness_queries=True)
    assert manifest_from(manifest_data(query_described)) == query_described
    assert "witness_queries" not in manifest_data(described)
    with pytest.raises(ValueError):
        replace(manifest, witness="")
    with pytest.raises(ValueError):
        replace(manifest, witness_queries=True)


def test_witness_checks_input_and_slot_scopes(monkeypatch: pytest.MonkeyPatch) -> None:
    from nca.learning import witness

    target = Specification(Contract(("source",), "result"), (Example((1,), 2),))
    expert = Contract(("source",), "result", ((("item",), "result"),))
    request = Request(target, expert, ((1,),))
    source = Specification(Contract(("source",), "source"), (Example((1,), 1),))
    slot = Specification(Contract(("item",), "result"), (Example((1,), 2),))
    manifest = Manifest("sample.expert", "1", expert, witness="sample:witness")
    monkeypatch.setattr(witness.loaders, "resolve", lambda name: lambda req: (Decomposition((source,), (slot,)),))
    assert list(decompositions(manifest, request)) == [Decomposition((source,), (slot,))]
    assert list(decompositions(replace(manifest, witness=None), request)) == []
    wrong = Specification(Contract(("source",), "result"), (Example((1,), 2),))
    monkeypatch.setattr(witness.loaders, "resolve", lambda name: lambda req: (Decomposition((source,), (wrong,)),))
    with pytest.raises(ValueError, match="subgoals"):
        list(decompositions(manifest, request))
    with pytest.raises(ValueError, match="argument"):
        Request(target, expert, ())
    unrelated = Request(target, Contract(("other",), "result"))
    with pytest.raises(ValueError, match="not an instance"):
        list(decompositions(manifest, unrelated))


def test_witness_slots_do_not_require_parameters_even_for_legacy_metadata(monkeypatch: pytest.MonkeyPatch) -> None:
    from nca.learning import witness

    target = Specification(Contract(("source",), "result"), (Example((1,), 2),))
    expert = Contract(("source",), "result", ((("item",), "result"),), ((0,),))
    source = Specification(Contract(("source",), "source"), (Example((1,), 1),))
    slot = Specification(Contract(("item",), "result"), (Example((1,), 2),))
    manifest = Manifest("sample.expert", "1", expert, witness="sample:witness")
    monkeypatch.setattr(witness.loaders, "resolve", lambda name: lambda req: (Decomposition((source,), (slot,)),))
    assert list(decompositions(manifest, Request(target, expert))) == [Decomposition((source,), (slot,))]
    restricted = Specification(slot.contract, slot.examples, frozenset({0}))
    monkeypatch.setattr(witness.loaders, "resolve",
                        lambda name: lambda req: (Decomposition((source,), (restricted,)),))
    with pytest.raises(ValueError, match="cannot require"):
        list(decompositions(manifest, Request(target, expert)))


def test_witness_query_labels_are_budgeted_and_returned_as_proposals(monkeypatch: pytest.MonkeyPatch) -> None:
    from collections.abc import Generator
    from nca.learning import witness

    target = Specification(Contract(("source",), "result"), (Example((3,), 6),))
    expert = Contract(("source",), "result")
    manifest = Manifest("sample.expert", "1", expert, witness="sample:witness")
    def provider(request: Request) -> Generator[Need | Decomposition, tuple[object, ...] | None, None]:
        answers = yield Need(((2,), (4,)))
        if answers is not None:
            goal = Specification(Contract(("source",), "source"),
                                 (Example((answers[0],), answers[1]),))
            yield Decomposition((goal,), ())
    monkeypatch.setattr(witness.loaders, "resolve", lambda name: provider)
    queries = QuerySession(lambda inputs: inputs[0] * 2, limit=2)
    result, = decompositions(manifest, Request(target, expert), queries)
    assert result.inputs[0].examples == (Example((4,), 8),)
    assert queries.labels == 2
    denied = QuerySession(lambda inputs: pytest.fail("denied query must not call oracle"), limit=1)
    assert not list(decompositions(manifest, Request(target, expert), denied))
    assert denied.labels == 0
    assert not list(decompositions(manifest, Request(target, expert)))
    with pytest.raises(ValueError, match="scope"):
        queries.ask(Need(((1, 2),)), target)
    assert queries.ask(Need(((2,),)), Specification(Contract(("other",), "result"), ())) is None
    assert queries.ask(Need(((2,),)), Specification(Contract(("source",), "other"), ())) is None
    assert queries.ask(Need(((2,),)), Specification(target.contract, target.examples)) is None
    assert queries.labels == 2


def test_query_oracle_failure_still_charges_the_attempt() -> None:
    def unavailable(inputs: tuple[object, ...]) -> object:
        raise RuntimeError("oracle unavailable")
    session = QuerySession(unavailable, 1)
    with pytest.raises(RuntimeError, match="oracle unavailable"):
        session.ask(Need(((1,),)), Specification(Contract(("source",), "result"), ()))
    assert session.labels == 1


def test_query_steps_reserve_batches_and_release_cancelled_capacity() -> None:
    calls = []
    target = Specification(Contract(("source",), "result"), ())
    session = QuerySession(lambda values: calls.append(values) or values[0], 3)
    steps = session.ask_steps(Need(((1,), (2,))), target)
    assert next(steps) is None and calls == [(1,)]
    assert session.labels == 1 and session.reserved == 1
    assert session.ask(Need(((3,), (4,))), target) is None
    assert session.ask(Need(((3,),)), target) == (3,)
    assert calls == [(1,), (3,)]
    steps.close()
    assert session.labels == 2 and session.reserved == 0
    assert session.ask(Need(((4,),)), target) == (4,)


def test_query_steps_release_reserved_capacity_when_oracle_raises() -> None:
    def oracle(values: tuple[object, ...]) -> object:
        if values == (2,):
            raise RuntimeError("unavailable")
        return values[0]
    target = Specification(Contract(("source",), "result"), ())
    session = QuerySession(oracle, 3)
    steps = session.ask_steps(Need(((1,), (2,), (3,))), target)
    assert next(steps) is None and session.labels == 1 and session.reserved == 2
    with pytest.raises(RuntimeError, match="unavailable"):
        next(steps)
    assert session.labels == 2 and session.reserved == 0


def test_decomposition_steps_issue_at_most_one_query_per_step(monkeypatch: pytest.MonkeyPatch) -> None:
    from collections.abc import Generator
    from nca.learning import witness

    target = Specification(Contract(("source",), "result"), ())
    manifest = Manifest("sample.expert", "1", target.contract, witness="sample:witness")
    def provider(request: Request) -> Generator[Need | Decomposition, tuple[object, ...] | None, None]:
        answers = yield Need(((1,), (2,), (3,)))
        if answers is not None:
            goal = Specification(Contract(("source",), "source"), ())
            yield Decomposition((goal,), ())
    monkeypatch.setattr(witness.loaders, "resolve", lambda name: provider)
    session = QuerySession(lambda values: values[0], 3)
    steps = witness.decomposition_steps(manifest, Request(target, target.contract), session)
    for expected in (1, 2, 3):
        assert next(steps) is None and session.labels == expected
    assert isinstance(next(steps), Decomposition)
    assert session.reserved == 0


def test_identical_recursive_subgoal_does_not_starve_enumeration(monkeypatch: pytest.MonkeyPatch) -> None:
    from nca.learning import witness
    from nca.planner import Apply, Given

    class Loop:
        manifest = Manifest("sample.loop", "1", Contract(("goal",), "goal"),
                            effects=frozenset(), witness="sample:loop")
        def invoke(self, value: int) -> int:
            return value
    class First:
        manifest = Manifest("sample.first", "1", Contract(("source",), "middle"), effects=frozenset())
        def invoke(self, value: int) -> int:
            return value + 1
    class Second:
        manifest = Manifest("sample.second", "1", Contract(("middle",), "goal"), effects=frozenset())
        def invoke(self, value: int) -> int:
            return value + 1
    loop, first, second = Loop(), First(), Second()
    target = Specification(Contract(("source",), "goal"), (Example((1,), 3),))
    monkeypatch.setattr(witness.loaders, "resolve",
                        lambda name: lambda request: (Decomposition((request.target,), ()),))
    def fallback(goal: Specification, fuel: int) -> Apply | None:
        return Apply(second, (Apply(first, (Given("source", 0),)),)) if goal == target else None
    result = witness.propose((loop, first, second), target, types=("source", "middle", "goal"),
                             depth=100, expansions=10, execution_budget=10, fallback=fallback)
    assert result == Apply(second, (Apply(first, (Given("source", 0),)),))
