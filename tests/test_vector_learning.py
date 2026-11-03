"""Vector bridges preserve nominal interfaces and generalize coordinate mixing."""

from pathlib import Path

import pytest

from nca.abi import Contract
from nca.objects import Store
from nca.packages import install
from nca.vector_learning import fit_vector_affine, vector_affine_object


@pytest.mark.parametrize("inputs,outputs", [(0, 1), (1, 1), (2, 3), (4, 2), (2, 0)])
def test_dimensions_and_artifact_round_trip(tmp_path: Path, inputs: int, outputs: int) -> None:
    xs = [tuple(0.0 for _ in range(inputs))]
    xs += [tuple(float(i == j) for j in range(inputs)) for i in range(inputs)]

    def target(x: tuple[float, ...]) -> tuple[float, ...]:
        return tuple(sum((i + j + 1) * v for i, v in enumerate(x)) + j + 0.25
                     for j in range(outputs))

    model = fit_vector_affine(Contract(("source",), "target"), xs, list(map(target, xs)), cost=1)
    fresh = tuple(0.37 * (i + 1) for i in range(inputs))
    assert model.invoke(fresh) == pytest.approx(target(fresh))
    store = Store()
    obj = vector_affine_object(model, size=64)
    ref = store.put(obj)
    store.save(tmp_path)
    restored = install(Store.open(tmp_path), ref)[0]
    assert restored.invoke(fresh) == model.invoke(fresh)
    assert not obj.dependencies
    assert restored.manifest.contract == Contract(("source",), "target")
    with pytest.raises(ValueError, match="dimension"):
        model.invoke(fresh + (1.0,))


def test_invalid_data_and_rank_deficiency() -> None:
    contract = Contract(("source",), "target")
    for xs, ys in [([], []), ([(0.0,)], []), ([(0.0,), (1.0, 2.0)], [(0.0,), (1.0,)]),
                   ([(0.0,)], [(float("inf"),)]), ([[0.0]], [(1.0,)]),
                   ([(1,)], [(1.0,)])]:
        with pytest.raises(ValueError):
            fit_vector_affine(contract, xs, ys, cost=1)
    model = fit_vector_affine(contract, [(2.0,), (2.0,)], [(1.0,), (3.0,)], cost=1)
    assert model.invoke((2.0,)) == pytest.approx((2.0,))


def test_typed_bridge_uses_teacher_only_during_training() -> None:
    from nca.abi import Manifest
    from nca.learning.interfaces import propose_adapter

    class Source:
        manifest = Manifest("source", "1", Contract(("input",), "source"), effects=frozenset())

        def invoke(self, x: tuple[float, ...]) -> tuple[float, ...]:
            return x

    class Teacher:
        manifest = Manifest("teacher", "1", Contract(("input",), "target"), effects=frozenset())
        calls = 0

        def invoke(self, x: tuple[float, ...]) -> tuple[float, ...]:
            self.calls += 1
            return (x[0] + 2 * x[1], x[0] - x[1], 0.5 + x[1])

    class Consumer:
        manifest = Manifest("head", "1", Contract(("target",), "output"), effects=frozenset())

        def invoke(self, x: tuple[float, ...]) -> bool:
            return x[0] + x[2] > x[1]

    class Baseline:
        manifest = Manifest("baseline", "1", Contract(("input",), "output"))

        def invoke(self, x: tuple[float, ...]) -> bool:
            return True

    teacher = Teacher()
    proposal = propose_adapter(Baseline(), Source(), teacher, Consumer(),
                               [((0.0, 0.0),), ((1.0, 0.0),), ((0.0, 1.0),)],
                               decoder_cost=1, fit=fit_vector_affine)
    assert proposal.expert.invoke((0.3, 0.7)) is True
    assert proposal.expert.invoke((0.3, -0.7)) is False
    assert teacher.calls == 3
