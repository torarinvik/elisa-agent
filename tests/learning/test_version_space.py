from itertools import product

import pytest

from nca.learning.version_space import VersionSpace
from nca.planner.dynamics import plan_actions
from nca.runtime import BudgetExceeded, UnresolvedRequest


def test_realizable_versions_generalize_or_refuse_and_plans_agree() -> None:
    states, actions = ("p", "q"), ("a", "b")
    inputs = tuple(product(states, actions))
    tables = [dict(zip(inputs, outputs, strict=True)) for outputs in product(states, repeat=4)]
    for truth in tables:
        for observed in inputs:
            family = [lambda pair, table=table: table[pair] for table in tables]
            model = VersionSpace(family, [(observed, truth[observed])], max_candidates=16)
            assert len(model.hypotheses) == 8
            for pair in inputs:
                try:
                    answer = model.predict(pair)
                except UnresolvedRequest:
                    continue
                assert answer == truth[pair]
            for initial, goal in product(states, repeat=2):
                plan = plan_actions(initial, lambda value: value == goal, actions,
                    lambda state, action: model.predict((state, action)), key=lambda value: value,
                    max_calls=4, max_states=2)
                if plan is not None:
                    actual = initial
                    for action in plan:
                        actual = truth[actual, action]
                    assert actual == goal


def test_missing_truth_can_be_unanimously_wrong_and_is_not_certification() -> None:
    model = VersionSpace([lambda value: "p"], [("observed", "p")], max_candidates=1)
    assert model.predict("unobserved") == "p"  # A true answer of q is not ruled out.
    with pytest.raises(ValueError):
        VersionSpace([lambda value: "p"] * 2, [("observed", "p")], max_candidates=1)
    def expensive(value: str) -> str:
        raise BudgetExceeded("unknown fit outcome")
    with pytest.raises(BudgetExceeded):
        VersionSpace([expensive], [("observed", "p")], max_candidates=1)
