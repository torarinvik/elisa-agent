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


def test_retained_actions_check_the_observation_and_recover_after_displacement() -> None:
    from nca.planner.dynamics import PlanFollower

    calls = []
    edges = {(0, "a"): 1, (1, "b"): 2, (2, "a"): 3, (4, "b"): 2}

    def predict(state: int, action: str) -> int:
        calls.append((state, action))
        if (state, action) not in edges:
            raise UnresolvedRequest("missing edge")
        return edges[state, action]

    follow = PlanFollower(lambda state: state == 3, ("a", "b"), predict, key=int, max_calls=12, max_states=6)
    assert follow.propose(0).action == "a"
    effort = len(calls)
    assert follow.propose(0).action == "a" and follow.propose(1).action == "b"
    assert len(calls) == effort
    assert follow.propose(4).action == "b" and len(calls) > effort
    effort = len(calls)
    assert follow.propose(2).action == "a" and follow.propose(3) is None
    assert len(calls) == effort
    with pytest.raises(UnresolvedRequest):
        follow.propose(5)
    assert follow.propose(0).action == "a"
    del edges[1, "b"]
    follow.invalidate()
    with pytest.raises(UnresolvedRequest):
        follow.propose(1)


def test_retained_planner_discards_old_proposals_before_a_budget_failure() -> None:
    from nca.planner.dynamics import PlanFollower

    follower = PlanFollower(lambda n: n == 3, (None,), lambda n, _: n + 1, key=int,
                            max_calls=2, max_states=2)
    assert follower.propose(1).action is None
    with pytest.raises(BudgetExceeded):
        follower.propose(0)
    assert follower.propose(2).state_key == 2
