"""Witness suggestions are typed proposals, never admission decisions."""

from dataclasses import replace

import pytest

from nca.abi import Contract, Manifest
from nca.learning.witness import Decomposition, Example, Request, Specification, decompositions
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
    with pytest.raises(ValueError):
        replace(manifest, witness="")


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
