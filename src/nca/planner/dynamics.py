"""Bounded goal-directed planning over contributor-supplied predictions."""

from collections import deque
from collections.abc import Callable, Hashable, Sequence
from dataclasses import dataclass
from typing import Generic, TypeVar

from nca.runtime import BudgetExceeded, UnresolvedRequest

S = TypeVar("S")
A = TypeVar("A")
T = TypeVar("T")


@dataclass(frozen=True, slots=True)
class PlannedAction(Generic[A]):
    """An action and the observable state key from which it was planned."""

    state_key: Hashable
    action: A


def _check_bounds(max_calls: int, max_states: int) -> None:
    if type(max_calls) is not int or max_calls < 0 or type(max_states) is not int or max_states < 1:
        raise ValueError("nonnegative calls and positive retained states required")


def _search(initial: S, root: Hashable, goal: Callable[[S], bool], actions: Sequence[A],
            predict: Callable[[S, A], S], key: Callable[[S], Hashable],
            max_calls: int, max_states: int, step: Callable[[Hashable, A], T]) -> deque[T] | None:
    pending = deque([(initial, root)])
    parents: dict[Hashable, tuple[Hashable, A] | None] = {root: None}
    calls = 0
    while pending:
        state, current = pending.popleft()
        for action in actions:
            if calls >= max_calls:
                raise BudgetExceeded("prediction-call budget exhausted")
            calls += 1
            try:
                successor = predict(state, action)
            except UnresolvedRequest:
                continue
            if goal(successor):
                path = deque([step(current, action)])
                while (edge := parents[current]) is not None:
                    current, previous_action = edge
                    path.appendleft(step(current, previous_action))
                return path
            identity = key(successor)
            if identity in parents:
                continue
            if len(parents) >= max_states:
                raise BudgetExceeded("retained-state budget exhausted")
            parents[identity] = (current, action)
            pending.append((successor, identity))
    return None


def plan_actions(initial: S, goal: Callable[[S], bool], actions: Sequence[A],
                 predict: Callable[[S, A], S], *, key: Callable[[S], Hashable],
                 max_calls: int, max_states: int) -> tuple[A, ...] | None:
    """Find a shortest supported plan, or refuse within explicit resource bounds.

    State identities must be faithful for the supplied stationary model and
    goal. Unknown predictions raise UnresolvedRequest and create no edge.
    Budget exhaustion raises BudgetExceeded, rather than proving no plan.
    This function assigns no confidence to a model or its selected trajectory.
    """
    _check_bounds(max_calls, max_states)
    if goal(initial):
        return ()
    path = _search(initial, key(initial), goal, actions, predict, key, max_calls, max_states, lambda _, action: action)
    return None if path is None else tuple(path)


class PlanFollower(Generic[S, A]):
    """Reuse a supported shortest path while observations match its predicted state keys.

    Bind one goal, ordered action set, stationary predictor and faithful key
    function per follower. Invalidate after changing the goal or model.
    Each new search has its own call and state limits.
    """

    def __init__(self, goal: Callable[[S], bool], actions: Sequence[A], predict: Callable[[S, A], S], *,
                 key: Callable[[S], Hashable], max_calls: int, max_states: int) -> None:
        _check_bounds(max_calls, max_states)
        self._goal, self._actions, self._predict, self._key = goal, tuple(actions), predict, key
        self._max_calls, self._max_states = max_calls, max_states
        self._steps: deque[PlannedAction[A]] = deque()

    def invalidate(self) -> None:
        self._steps.clear()

    def _match_key(self, identity: Hashable) -> PlannedAction[A] | None:
        if self._steps:
            if self._steps[0].state_key == identity:
                return self._steps[0]
            self._steps.popleft()
            if self._steps and self._steps[0].state_key == identity:
                return self._steps[0]
            self.invalidate()
        return None

    def match(self, observed: S) -> PlannedAction[A] | None:
        """Check a retained step without making prediction calls. Discard a mismatched plan."""
        if self._goal(observed):
            self.invalidate()
            return None
        return self._match_key(self._key(observed))

    def propose(self, observed: S) -> PlannedAction[A] | None:
        """Return the next proposal, or None at the goal. An unsupported path raises UnresolvedRequest."""
        if self._goal(observed):
            self.invalidate()
            return None
        identity = self._key(observed)
        matched = self._match_key(identity)
        if matched is not None:
            return matched
        path = _search(observed, identity, self._goal, self._actions, self._predict, self._key,
                       self._max_calls, self._max_states, PlannedAction)
        if path is None:
            raise UnresolvedRequest("no supported path to the goal")
        self._steps = path
        return self._steps[0]
