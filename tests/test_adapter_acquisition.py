"""Typed bridge search learns which supplied consumer completes a useful route."""

import random
from collections.abc import Sequence
from pathlib import Path
from typing import Any

import pytest

from nca.abi import Contract, Manifest, Module
from nca.acquisition_objects import store_acquired_model
from nca.affine_learning import fit_affine
from nca.discovery import Proposal, discover
from nca.interface_learning import propose_adapters
from nca.objects import Constructor, Primitive, Store
from nca.packages import install, install_scopes
from nca.planner import plan_stable


class Reading:
    def __init__(self, scale: float, offset: float, output: str) -> None:
        self.scale, self.offset = scale, offset
        self.calls: list[float] = []
        self.manifest = Manifest(f"reading-{scale}-{offset}-{output}", "1",
                                 Contract(("input",), output), cost=1)

    def invoke(self, value: float) -> float:
        self.calls.append(value)
        return self.scale * value + self.offset


class Consumer:
    def __init__(self, input_type: str, offset: float) -> None:
        self.offset = offset
        self.manifest = Manifest(f"consumer-{input_type}-{offset}", "1",
                                 Contract((input_type,), "goal"), cost=1, effects=frozenset())

    def invoke(self, value: float) -> float:
        return value * value + self.offset


class Baseline:
    manifest = Manifest("baseline", "1", Contract(("input",), "goal"))

    def invoke(self, value: float) -> float:
        return 0.0


def test_adapter_search_filters_contracts_and_selects_the_useful_consumer() -> None:
    new = Constructor("new-interface", "1", 0, "hypothetical new observation")
    old = Constructor("old-interface", "1", 0, "hypothetical old observation")
    source, teacher = Reading(2.0, 1.0, new.type()), Reading(1.0, 0.0, old.type())
    bad, good = Consumer(old.type(), 1.0), Consumer(old.type(), 0.0)
    assert plan_stable([source, good], ("input",), "goal") is None
    rng = random.Random(3659)
    rows = [(rng.uniform(-1, 1),) for _ in range(400)]
    labels = [x * x for x, in rows]

    def propose(train: Sequence[tuple[Any, ...]], targets: Sequence[Any]) -> list[Proposal]:
        return propose_adapters(Baseline(), [Proposal(source, (new,))],
                    [Proposal(teacher, (old,))], [Consumer("incompatible", 0.0), bad, good],
                    train, max_candidates=2, decoder_cost=1, fit=fit_affine)

    result = discover(Baseline(), propose, rows, labels, lambda a, b: abs(a - b) < 1e-9)
    assert [sum(t.outcomes) for t in result.trials] == [0, 200]
    assert result.chosen is not None and result.chosen.expert.decoder is good
    assert result.chosen.constructors == (new, old)
    bridge = result.chosen.expert.feature.decoder
    assert bridge.manifest.contract == Contract((new.type(),), old.type())
    assert teacher.calls == [row[0] for row in rows[:200]] * 2
    assert result.chosen.expert.invoke(0.37) == pytest.approx(0.37**2)
    assert len(teacher.calls) == 400
    assert plan_stable([source, good, result.chosen.expert], ("input",), "goal") is not None


def test_adapter_candidate_budget_and_retention_exclude_teacher_code(tmp_path: Path) -> None:
    store = Store()
    new, old = Constructor("new", "1", 0, "new observation"), Constructor("old", "1", 0, "old observation")
    for constructor in (new, old):
        store.put(constructor)
    refs = []
    for scale, offset, output in [(2.0, 1.0, new.type()), (1.0, 0.0, old.type())]:
        model = Reading(scale, offset, output)
        refs.append(store.put(Primitive(model.manifest, f"{__name__}:Reading",
                    {"scale": scale, "offset": offset, "output": output}, size=8)))
    for offset in [1.0, 0.0]:
        model = Consumer(old.type(), offset)
        refs.append(store.put(Primitive(model.manifest, f"{__name__}:Consumer",
                    {"input_type": old.type(), "offset": offset}, size=8)))
    scopes = install_scopes(store, refs)
    source, teacher, bad, good = (scope[0] for scope in scopes)
    rows = [(-1.0,), (-0.5,), (0.5,), (1.0,)]
    candidates = propose_adapters(Baseline(), [Proposal(source)], [Proposal(teacher)],
                    [bad, good], rows, max_candidates=1, decoder_cost=1, fit=fit_affine)
    assert len(candidates) == 1 and candidates[0].expert.decoder is bad
    selected = propose_adapters(Baseline(), [Proposal(source)], [Proposal(teacher)],
                    [good], rows, max_candidates=1, decoder_cost=1, fit=fit_affine)[0]
    bound = []

    def bind(module: Module) -> tuple[str, int]:
        bound.append(module.identity)
        return module.identity, 0

    root, index = store_acquired_model(store, selected.expert, bind, size=lambda m: 16)
    assert set(bound) == {source.identity, good.identity} and len(bound) == 2
    assert teacher.identity not in set(store.walk(root))
    store.save(tmp_path)
    restored = install(Store.open(tmp_path), root)[index]
    assert [restored.invoke(x) for x in (-0.7, 0.0, 0.9)] == [
        selected.expert.invoke(x) for x in (-0.7, 0.0, 0.9)]
    with pytest.raises(ValueError, match="candidate budget"):
        propose_adapters(Baseline(), [], [], [], rows, max_candidates=0, decoder_cost=1)
