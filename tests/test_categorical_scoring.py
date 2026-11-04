"""Exact category-count scoring and its optional Elisa interpreter (§36.68)."""

from array import array
from collections import Counter
from itertools import product
import random
from typing import Any

import pytest

from nca.learning import categorical
from nca.native import load


def reference(rows: list[tuple[Any, Any]]) -> int:
    counts = Counter(rows)
    return sum(max(count for (key, _), count in counts.items() if key == group)
               for group in {key for key, _ in rows})


@pytest.mark.parametrize("native", [False, True])
def test_all_small_contingency_tables_and_identifier_permutations(
        monkeypatch: pytest.MonkeyPatch, native: bool) -> None:
    kernel = load("records") if native else None
    if native and getattr(kernel, "modal_score", None) is None:
        pytest.skip("Elisa category scoring is not built/enabled")
    monkeypatch.setattr(categorical, "_NATIVE", kernel)
    alphabet = tuple(product(range(3), range(2)))
    for size in range(5):
        for observations in product(alphabet, repeat=size):
            rows = list(observations)
            keys, labels = [k for k, _ in rows], [l for _, l in rows]
            expected = reference(rows)
            assert categorical.modal_score(keys, labels) == expected
            # Pair permutation and injective relabeling preserve multiplicities.
            assert categorical.modal_score([f"key:{2-k}" for k in reversed(keys)],
                                            [("label", 1-l) for l in reversed(labels)]) == expected


class Colliding:
    def __init__(self, value: int) -> None:
        self.value = value

    def __hash__(self) -> int:
        return 0

    def __eq__(self, other: object) -> bool:
        return isinstance(other, Colliding) and self.value == other.value


@pytest.mark.parametrize("native", [False, True])
def test_hash_collisions_never_merge_distinct_categories(
        monkeypatch: pytest.MonkeyPatch, native: bool) -> None:
    kernel = load("records") if native else None
    if native and getattr(kernel, "modal_score", None) is None:
        pytest.skip("Elisa category scoring is not built/enabled")
    monkeypatch.setattr(categorical, "_NATIVE", kernel)
    keys = [Colliding(k) for k in (0, 0, 1, 1, 2, 2)]
    labels = [Colliding(k) for k in (0, 1, 0, 0, 1, 1)]
    assert categorical.modal_score(keys, labels) == 5
    with pytest.raises(ValueError, match="aligned"):
        categorical.modal_score(keys, labels[:-1])


def test_native_signed_identifiers_and_large_sparse_tables() -> None:
    kernel = load("records")
    if getattr(kernel, "modal_score", None) is None:
        pytest.skip("Elisa category scoring is not built/enabled")
    rng = random.Random(3668)
    for count in (1, 2, 3, 31, 32, 33, 1024):
        rows = [(rng.choice((-2**63, 2**63-1, 7)), rng.randrange(17)) for _ in range(count)]
        packed = array("q", (value for pair in rows for value in pair))
        original = packed.tobytes()
        assert kernel.modal_score(packed) == reference(rows)
        assert packed.tobytes() == original
    assert kernel.modal_score(array("q", [1])) == -1
    assert kernel.modal_score(array("q")) == 0
    assert kernel.modal_score(array("q", (v for i in range(4096) for v in (i, i)))) == 4096
    assert kernel.modal_score(array("q", (v for i in range(4096) for v in (0, i)))) == 1


def test_joint_candidate_order_and_observation_budget_match_reference(
        monkeypatch: pytest.MonkeyPatch) -> None:
    from nca.abi import Contract, Manifest
    from nca.learning.discovery import JointFeature, Proposal
    from nca.learning.interfaces import propose_joint_refinements

    kernel = load("records")
    if getattr(kernel, "modal_score", None) is None:
        pytest.skip("Elisa category scoring is not built/enabled")

    class Coordinate:
        def __init__(self, index: int) -> None:
            self.index, self.calls = index, 0
            self.manifest = Manifest(f"coordinate-{index}", "1", Contract(("input",), f"part-{index}"),
                                     effects=frozenset())

        def invoke(self, value: tuple[int, ...]) -> int:
            self.calls += 1
            return value[self.index]

    def shape(feature: Any) -> tuple[int, ...]:
        if isinstance(feature, JointFeature):
            return (*shape(feature.left), *shape(feature.right))
        return (feature.index,)

    rows = [(value,) for value in product(range(2), repeat=4)]
    labels = [value[0] ^ value[1] ^ value[2] for value, in rows]
    results = []
    for backend in (None, kernel):
        monkeypatch.setattr(categorical, "_NATIVE", backend)
        coordinates = [Coordinate(i) for i in range(4)]
        proposals = propose_joint_refinements(Proposal(coordinates[0]),
            [Proposal(feature) for feature in coordinates[1:]], rows, labels,
            max_candidates=3, limit=6, max_companions=2, max_joint_candidates=6, pair_cost=0)
        assert [feature.calls for feature in coordinates] == [len(rows)] * 4
        results.append([(shape(p.expert), [p.expert.invoke(*row) for row in rows]) for p in proposals])
    assert results[0] == results[1]
    assert results[0][0][0] == (0, 1, 2)


def test_older_native_module_uses_exact_reference(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setattr(categorical, "_NATIVE", object())
    assert categorical.modal_score(["a", "a", "b"], [1, 2, 1]) == 2
