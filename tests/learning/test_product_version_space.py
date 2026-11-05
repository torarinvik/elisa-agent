"""Differential evidence for explicitly declared product hypothesis families."""

from itertools import product

import pytest

from nca.learning.product_version_space import ProductVersionSpace
from nca.learning.version_space import VersionSpace
from nca.runtime import BudgetExceeded, UnresolvedRequest


def test_product_matches_explicit_enumeration_on_small_families() -> None:
    states = tuple(product(('p', 'q'), repeat=2))
    fields = (lambda state: state[0], lambda state: state[1], lambda state: state[0])
    # Repeated predictors are distinct choices and must retain their weights.
    for arity in range(4):
        factors = (fields,) * arity
        family = tuple(lambda state, selected=selected: tuple(predict(state) for predict in selected)
                       for selected in product(*factors))
        for sample, truth in product(states, family):
            observations = [(sample, truth(sample))]
            explicit = VersionSpace(family, observations, max_candidates=len(family))
            factored = ProductVersionSpace(factors, observations, max_candidates=len(family))
            assert factored.hypothesis_count == explicit.hypothesis_count
            for state in states:
                try:
                    expected = explicit.predict(state)
                except UnresolvedRequest:
                    with pytest.raises(UnresolvedRequest):
                        factored.predict(state)
                else:
                    assert factored.predict(state) == expected
            assert factored.choose_disagreement(states, max_inputs=4) == explicit.choose_disagreement(states, max_inputs=4)
            for state in states:
                more = [(state, truth(state))]
                left, right = explicit.refine(more), factored.refine(more)
                assert right.hypothesis_count == left.hypothesis_count
                assert right.choose_disagreement(states, max_inputs=4) == left.choose_disagreement(states, max_inputs=4)
                for probe in states:
                    try:
                        expected = left.predict(probe)
                    except UnresolvedRequest:
                        with pytest.raises(UnresolvedRequest):
                            right.predict(probe)
                    else:
                        assert right.predict(probe) == expected


def test_product_refuses_incomplete_families_and_propagates_budget_failure() -> None:
    def field(value: int) -> int:
        return value
    with pytest.raises(ValueError):
        ProductVersionSpace(((field, field), (field, field)), [(1, (1, 1))], max_candidates=3)
    with pytest.raises(ValueError):
        ProductVersionSpace(((field,),), [(1, ())], max_candidates=1)
    with pytest.raises(ValueError):
        ProductVersionSpace(((),), [(1, (1,))], max_candidates=1)
    def expensive(value: int) -> int:
        raise BudgetExceeded('unknown candidate outcome')
    with pytest.raises(BudgetExceeded):
        ProductVersionSpace(((expensive,),), [(1, (1,))], max_candidates=1)
    empty = ProductVersionSpace((), [(1, ())], max_candidates=1)
    assert empty.hypothesis_count == 1 and empty.component_count == 0
    assert empty.predict(2) == () and empty.choose_disagreement((1, 2), max_inputs=2) is None


def test_partial_candidate_refusal_matches_explicit_family() -> None:
    def stable(value: int) -> int:
        return value
    def partial(value: int) -> int:
        if value == 2:
            raise UnresolvedRequest("outside domain")
        return value
    factors = ((stable, partial), (stable,))
    family = tuple(lambda value, pair=pair: tuple(fn(value) for fn in pair)
                   for pair in product(*factors))
    explicit = VersionSpace(family, [(1, (1, 1))], max_candidates=2)
    factored = ProductVersionSpace(factors, [(1, (1, 1))], max_candidates=2)
    with pytest.raises(UnresolvedRequest):
        explicit.predict(2)
    with pytest.raises(UnresolvedRequest):
        factored.predict(2)
    with pytest.raises(UnresolvedRequest):
        explicit.choose_disagreement((2,), max_inputs=1)
    with pytest.raises(UnresolvedRequest):
        factored.choose_disagreement((2,), max_inputs=1)
