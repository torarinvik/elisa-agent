"""Continuous bridge fitting generalizes to unseen measurements without type aliasing."""

from collections.abc import Sequence
from pathlib import Path
from typing import Any

import pytest

from nca.abi import Contract, Manifest
from nca.affine_learning import affine_object, fit_affine
from nca.discovery import Proposal, discover
from nca.interface_learning import propose_adapter
from nca.objects import Store
from nca.packages import install


class Source:
    manifest = Manifest("source", "1", Contract(("input",), "a"), effects=frozenset())

    def invoke(self, value: float) -> float:
        return 2 * value - 0.7


class Teacher:
    manifest = Manifest("teacher", "1", Contract(("input",), "b"), effects=frozenset())

    def __init__(self) -> None:
        self.calls = 0

    def invoke(self, value: float) -> float:
        self.calls += 1
        return 3 * value + 0.4


class Consumer:
    manifest = Manifest("consumer", "1", Contract(("b",), "output"), effects=frozenset())

    def invoke(self, value: float) -> str:
        return "upper" if value >= 0 else "lower"


class Baseline:
    manifest = Manifest("baseline", "1", Contract(("input",), "output"))

    def invoke(self, value: float) -> str:
        return "upper"


def test_continuous_fitter_generalizes_without_teacher_calls() -> None:
    source, teacher, consumer = Source(), Teacher(), Consumer()
    xs = [i / 100 - 1.0 for i in range(200)]
    rows = [(x,) for x in xs[::2] + xs[1::2]]
    labels = ["upper" if 3 * row[0] + 0.4 >= 0 else "lower" for row in rows]

    def propose(train: Sequence[tuple[Any, ...]], targets: Sequence[Any]) -> list[Proposal]:
        return [propose_adapter(Baseline(), source, teacher, consumer, train,
                                decoder_cost=1, fit=fit_affine)]

    result = discover(Baseline(), propose, rows, labels, lambda a, b: a == b)
    assert result.chosen is not None and teacher.calls == 100
    assert sum(result.trials[0].outcomes) == 100


def test_affine_parameters_round_trip_and_numeric_limits(tmp_path: Path) -> None:
    contract = Contract(("a",), "b")
    model = fit_affine(contract, [-1.0, 0.0, 1.0], [-0.05, 1.45, 2.95], cost=1)
    assert model.slope == pytest.approx(1.5) and model.offset == pytest.approx(1.45)
    store = Store()
    obj = affine_object(model, size=32)
    ref = store.put(obj)
    store.save(tmp_path)
    restored = install(Store.open(tmp_path), ref)[0]
    assert restored.invoke(0.123) == model.invoke(0.123)
    constant = fit_affine(contract, [2.0, 2.0], [1.0, 3.0], cost=1)
    assert constant.invoke(99.0) == 2.0
    with pytest.raises(ValueError, match="variance"):
        fit_affine(contract, [1e-300, 2e-300], [1.0, 2.0], cost=1)
    with pytest.raises(ValueError, match="finite floats"):
        fit_affine(contract, [float("nan")], [1.0], cost=1)


def test_fitter_cannot_change_the_requested_adapter_contract() -> None:
    from nca.abi import Module

    def wrong(contract: Contract, keys: Sequence[Any], labels: Sequence[Any], *,
              cost: float) -> Module:
        return Source()

    with pytest.raises(ValueError, match="requested interface contract"):
        propose_adapter(Baseline(), Source(), Teacher(), Consumer(), [(0.0,), (1.0,)],
                         decoder_cost=1, fit=wrong)
