from collections.abc import Hashable
from random import Random
from typing import Any

import pytest

from nca.learning.amending import UNJUDGED, Amendable, teach_amendable
from nca.learning.state_machine import Delegate, Word
from nca.learning.takeover import teach

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

    def __init__(self, rng: Random, length: int) -> None:
        self.rng, self.left, self.position = rng, length, rng.randrange(7)

    def observation(self) -> Hashable | None:
        if self.left == 0:
            return None
        self.left -= 1
        return self.position % 3

    def act(self, action: Any) -> None:
        self.position = (self.position + ACTION.index(action) + self.rng.randrange(3)) % 7


def starts(seed: int, length: int) -> Any:
    rng = Random(seed)
    return lambda: Loop(rng, length)


def errs(part: Any, history: Word) -> bool:
    try:
        return part(history) != right(history)
    except ValueError:
        return True


def test_a_part_that_errs_where_it_is_used_is_shown_the_action_and_the_rule_stays_small() -> None:
    """Section 52.13: the takeover is read as the part's error where that leaves the whole smaller."""
    part, taught = teach_amendable(starts(0, 3), right, clean=3, max_episodes=200)
    assert taught.passed
    longer = [tuple(Random(seed).randrange(3) for _ in range(12)) for seed in range(40)]
    assert any(errs(part, history) for history in longer)

    def fixed(history: Word) -> Any:
        return part(history)

    plain, alone = teach_amendable(starts(1, 12), right, clean=60, max_episodes=3000, helpers=(fixed,))
    learner, amended = teach_amendable(starts(1, 12), right, clean=60, max_episodes=3000, helpers=(part,))
    assert alone.passed and amended.passed
    assert learner.machine.outputs == (Delegate(0),) and len(plain.machine.outputs) > 1
    assert plain.helpers == (fixed,) and learner.helpers[0] is not part
    assert not any(errs(learner, history) for history in longer)
    assert any(errs(part, history) for history in longer)
    assert learner.states == 1 + learner.helpers[0].states  # type: ignore[union-attr]


def test_with_parts_left_as_they_are_the_teaching_is_that_of_takeover() -> None:
    """Helpers that cannot be shown more are used as in section 52.5, and unjudged steps say nothing."""
    learner, taught = teach_amendable(starts(2, 12), right, clean=60, max_episodes=3000)
    same = teach(starts(2, 12), right, clean=60, max_episodes=3000)
    assert (taught.takeovers, taught.demonstrated, taught.machine) == (same.takeovers, same.demonstrated, same.machine)
    assert Amendable((((0, 1), (UNJUDGED, "left")),)).machine.outputs == ("left",)
    with pytest.raises(ValueError):
        learner((0, 1, 2, "unseen"))
    with pytest.raises(ValueError):
        teach_amendable(starts(2, 12), right, clean=0, max_episodes=1)
