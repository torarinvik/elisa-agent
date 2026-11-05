from itertools import product

import pytest

from nca.planner.dynamics import plan_actions
from nca.runtime import BudgetExceeded, UnresolvedRequest


def test_supported_plans_match_actual_rollout_over_partial_models() -> None:
    states, actions = ("p", "q", "r"), ("a", "b")
    edges = {(state, action): states[(i + j + 1) % len(states)]
             for i, state in enumerate(states) for j, action in enumerate(actions)}
    pairs = tuple(edges)
    for mask in range(1 << len(pairs)):
        def model(state: str, action: str) -> str:
            pair = (state, action)
            if not mask & (1 << pairs.index(pair)):
                raise UnresolvedRequest("unknown")
            return edges[pair]
        for initial, goal in product(states, repeat=2):
            plan = plan_actions(initial, lambda value: value == goal, actions, model,
                                key=lambda value: value, max_calls=6, max_states=3)
            if plan is None:
                continue
            predicted = actual = initial
            for action in plan:
                predicted = model(predicted, action)
                actual = edges[actual, action]
            assert predicted == actual == goal
            # Differential minimality check against every shorter action list.
            for length in range(len(plan)):
                for candidate in product(actions, repeat=length):
                    state = initial
                    try:
                        for action in candidate:
                            state = model(state, action)
                    except UnresolvedRequest:
                        continue
                    assert state != goal


def test_refused_calls_are_charged_and_exhaustion_is_distinct() -> None:
    calls = []
    def unknown(state: str, action: str) -> str:
        calls.append(action)
        raise UnresolvedRequest("unknown")
    with pytest.raises(BudgetExceeded):
        plan_actions("p", lambda _: False, ("a", "b"), unknown,
                     key=lambda value: value, max_calls=1, max_states=1)
    assert calls == ["a"]
    assert plan_actions("p", lambda _: True, (), unknown,
                        key=lambda value: value, max_calls=0, max_states=1) == ()
