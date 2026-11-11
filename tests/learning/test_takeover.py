from collections.abc import Hashable
from random import Random
from typing import Any

import pytest

from nca.abi import Contract
from nca.learning.state_machine import Delegate, StepwiseExpert, Word
from nca.learning.takeover import UNLABELLED, merge_states, teach

SEQUENCE, ANSWERS = "seq[sha256:" + "0" * 64 + "]", "seq[sha256:" + "1" * 64 + "]"
STEP = ((1, 2, 0), (2, 0, 1), (0, 0, 2))
ACTION = ("stay", "left", "right")


def right(history: Word) -> str:
    """A three-state rule: the action depends on the state the observations lead to."""
    state = 0
    for symbol in history:
        state = STEP[state][symbol]  # type: ignore[index]
    return ACTION[state]


class Loop:
    """Each action moves the position, and with a chance outcome fixes the next observation."""

    def __init__(self, rng: Random, length: int = 12) -> None:
        self.rng, self.left, self.position = rng, length, rng.randrange(7)

    def observation(self) -> Hashable | None:
        if self.left == 0:
            return None
        self.left -= 1
        return self.position % 3

    def act(self, action: Any) -> None:
        self.position = (self.position + ACTION.index(action) + self.rng.randrange(3)) % 7


def starts(seed: int) -> Any:
    rng = Random(seed)
    return lambda: Loop(rng)


def test_a_teacher_who_answers_any_history_needs_few_takeovers() -> None:
    """``NCA.separated_histories_bound``: one takeover per state, the unlabelled start included."""
    taught = teach(starts(0), right, clean=60, max_episodes=1000, ask=right)
    assert taught.passed and taught.takeovers <= 3 and len(taught.machine.outputs) == 4
    assert taught.machine.outputs[0] == UNLABELLED and taught.questions > 0
    rng = Random(9)
    for _ in range(100):
        history = tuple(rng.randrange(3) for _ in range(rng.randint(1, 20)))
        assert taught.machine.run(history) == right(history)


def test_demonstrations_alone_teach_the_rule_on_what_occurs() -> None:
    taught = teach(starts(0), right, clean=60, max_episodes=2000)
    assert taught.passed and taught.questions == 0 and 0 < taught.takeovers
    assert taught.demonstrated <= 12 * taught.takeovers
    expert = StepwiseExpert(Contract((SEQUENCE,), ANSWERS), taught.machine, UNLABELLED)
    fresh = starts(5)
    for _ in range(50):
        session, seen = fresh(), []
        while (symbol := session.observation()) is not None:
            seen.append(symbol)
            session.act(right(tuple(seen)))
        assert expert.invoke(tuple(seen)) == tuple(right(tuple(seen[:cut + 1])) for cut in range(len(seen)))


def test_merging_keeps_separate_what_the_actions_separate_and_refuses_the_unseen() -> None:
    machine = merge_states([((0, 0, 0, 0), ("a", "b", "a", "b")), ((1, 0), ("a", "b"))])
    assert len(machine.outputs) == 2 and machine.run((0, 0, 0, 0, 0)) == "a" and machine.run((1, 0, 0)) == "a"
    expert = StepwiseExpert(Contract((SEQUENCE,), ANSWERS), machine, UNLABELLED)
    assert expert.invoke((0, 0)) == ("a", "b")
    with pytest.raises(ValueError, match="leaves"):
        expert.invoke((0, 2))


def test_limits_stop_teaching_without_a_pass() -> None:
    assert not teach(starts(0), right, clean=60, max_episodes=3).passed
    assert not teach(starts(0), right, clean=60, max_episodes=1000, ask=right, max_states=2).passed
    with pytest.raises(ValueError, match="positive"):
        teach(starts(0), right, clean=0, max_episodes=10)


def other(history: Word) -> str:
    return ACTION[sum(history) % 3]  # type: ignore[arg-type]


def switching(history: Word) -> str:
    """Follows one rule after an even number of zeros and the other after an odd number."""
    return right(history) if history.count(0) % 2 == 0 else other(history)


def test_a_rule_that_chooses_between_helpers_is_taught_as_the_choice() -> None:
    """Section 52.5: the machine taught is the rule that chooses, with the helpers as its actions."""
    alone = teach(starts(0), switching, clean=60, max_episodes=3000)
    helped = teach(starts(0), switching, clean=60, max_episodes=3000, helpers=(right, other))
    assert helped.passed and len(helped.machine.outputs) == 2
    assert set(helped.machine.outputs) == {Delegate(0), Delegate(1)}
    assert helped.takeovers * 3 <= alone.takeovers
    expert = StepwiseExpert(Contract((SEQUENCE,), ANSWERS), helped.machine, UNLABELLED, helpers=(right, other))
    rng = Random(4)
    for _ in range(50):
        history = tuple(rng.randrange(3) for _ in range(rng.randint(1, 25)))
        assert expert.invoke(history) == tuple(switching(history[:cut + 1]) for cut in range(len(history)))


def test_a_refusing_helper_explains_nothing_and_helpers_exclude_questions() -> None:
    def refusing(history: Word) -> str:
        raise ValueError("no answer")

    taught = teach(starts(0), right, clean=60, max_episodes=2000, helpers=(refusing,))
    assert taught.passed and not any(isinstance(answer, Delegate) for answer in taught.machine.outputs)
    with pytest.raises(ValueError, match="demonstration only"):
        teach(starts(0), right, clean=60, max_episodes=10, ask=right, helpers=(other,))
