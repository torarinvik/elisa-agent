"""Stable positional assignment order across native and reference backends."""

from itertools import product

import pytest

from nca.planner import assignments
from nca.planner import terms


def reference(required: frozenset[int], count: int) -> list[tuple[frozenset[int], ...]]:
    if not required:
        return [(frozenset(),) * count]
    ordered = sorted(required)
    choices = sorted(product(range(count), repeat=len(ordered)),
                     key=lambda c: (max((c.count(j) for j in range(count)), default=0), c))
    return [tuple(frozenset(r for r, c in zip(ordered, choice, strict=True) if c == j)
                  for j in range(count)) for choice in choices]


@pytest.mark.parametrize("use_native", [False, True])
def test_every_small_assignment_preserves_reference_order(
        monkeypatch: pytest.MonkeyPatch, use_native: bool) -> None:
    if use_native and terms._ASSIGNMENT_NATIVE is None:
        pytest.skip("native assignment kernel unavailable or disabled")
    if not use_native:
        monkeypatch.setattr(terms, "_ASSIGNMENT_NATIVE", None)
    terms._assignment_table.cache_clear()
    try:
        for count in range(6):
            for size in range(6):
                required = frozenset(2*i+1 for i in range(size))
                assert list(assignments(required, count)) == reference(required, count)
    finally:
        terms._assignment_table.cache_clear()


def test_large_and_single_argument_cases_keep_unbounded_semantics() -> None:
    terms._assignment_table.cache_clear()
    required = frozenset({3})
    assert list(assignments(required, 65)) == reference(required, 65)
    assert terms._assignment_table.cache_info().currsize == 0
    many = frozenset(range(10000))
    assert list(assignments(many, 1)) == [(many,)]
