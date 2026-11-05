"""Bounded goal-directed planning over contributor-supplied predictions."""

from collections import deque
from collections.abc import Callable, Hashable, Sequence
from typing import TypeVar

from nca.runtime import BudgetExceeded, UnresolvedRequest

S = TypeVar("S")
A = TypeVar("A")


def plan_actions(initial: S, goal: Callable[[S], bool], actions: Sequence[A],
                 predict: Callable[[S, A], S], *, key: Callable[[S], Hashable],
                 max_calls: int, max_states: int) -> tuple[A, ...] | None:
    """Find a shortest supported plan, or refuse within explicit resource bounds.

    State identities must be faithful for the supplied stationary model and
    goal. Unknown predictions raise UnresolvedRequest and create no edge.
    Budget exhaustion raises BudgetExceeded, rather than proving no plan.
    This function assigns no confidence to a model or its selected trajectory.
    """
    if type(max_calls) is not int or max_calls < 0 or type(max_states) is not int or max_states < 1:
        raise ValueError("nonnegative calls and positive retained states required")
    if goal(initial):
        return ()
    pending = deque([(initial, ())])
    seen = {key(initial)}
    calls = 0
    while pending:
        state, prefix = pending.popleft()
        for action in actions:
            if calls >= max_calls:
                raise BudgetExceeded("prediction-call budget exhausted")
            calls += 1
            try:
                successor = predict(state, action)
            except UnresolvedRequest:
                continue
            plan = (*prefix, action)
            if goal(successor):
                return plan
            identity = key(successor)
            if identity in seen:
                continue
            if len(seen) >= max_states:
                raise BudgetExceeded("retained-state budget exhausted")
            seen.add(identity)
            pending.append((successor, plan))
    return None
