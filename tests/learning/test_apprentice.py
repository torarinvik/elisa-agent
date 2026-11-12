from collections.abc import Hashable
from random import Random
from typing import Any

import pytest

from nca.learning.apprentice import Apprentice
from nca.learning.state_machine import Word
from nca.learning.takeover import UNLABELLED

STEP = ((1, 2, 0), (2, 0, 1), (0, 0, 2))
GOOD = (frozenset({"stay", "left"}), frozenset({"left"}), frozenset({"right"}))
ACTION = ("stay", "left", "right")


def good(history: Word) -> frozenset[str]:
    """A three-state rule with two good actions in its first state."""
    state = 0
    for symbol in history:
        state = STEP[state][symbol]  # type: ignore[index]
    return GOOD[state]


class Loop:
    def __init__(self, rng: Random, length: int = 12) -> None:
        self.rng, self.left, self.position = rng, length, rng.randrange(7)

    def observation(self) -> Hashable | None:
        if self.left == 0:
            return None
        self.left -= 1
        return self.position % 3

    def act(self, action: Any) -> None:
        self.position = (self.position + ACTION.index(action) + self.rng.randrange(3)) % 7


def teach(apprentice: Apprentice, late: float, seed: int, clean: int = 60, limit: int = 400) -> bool:
    """A teacher one step late, or two with chance ``late``, who then takes any good action."""
    rng = Random(seed)
    run = 0
    while run < clean and apprentice.takeovers < limit:
        session, seen, played, shown = Loop(rng), [], [], []
        wrong = due = None
        asked = False
        while (symbol := session.observation()) is not None:
            seen.append(symbol)
            history = tuple(seen)
            if not shown and not asked and (wrong is None or len(seen) - 1 - wrong < due):
                mine = apprentice.action(history)
                if mine != UNLABELLED:
                    if wrong is None and mine not in good(history):
                        wrong, due = len(seen) - 1, 2 if rng.random() < late else 1
                    played.append(mine)
                    session.act(mine)
                    continue
                asked = True
            shown.append(rng.choice(sorted(good(history))))
            session.act(shown[-1])
        if wrong is None and not asked:
            run += 1
            continue
        run = 0
        apprentice.taken_over(tuple(seen), played, shown, asked=asked)
    return run >= clean


def plays_well(apprentice: Apprentice) -> bool:
    rng = Random(99)
    histories = [tuple(rng.randrange(3) for _ in range(rng.randint(1, 12))) for _ in range(200)]
    return all(apprentice.action(history) in good(history) for history in histories)


def test_a_punctual_teacher_is_learned_exactly() -> None:
    apprentice = Apprentice()
    assert apprentice.action((0,)) == UNLABELLED
    assert teach(apprentice, 0.0, 1) and plays_well(apprentice)
    assert len(apprentice.machine.outputs) == 3


def test_late_reactions_do_not_split_states() -> None:
    """One reaction in five is a step late; the wrong marks are not believed and the machine stays small."""
    apprentice = Apprentice()
    assert teach(apprentice, 0.2, 2) and plays_well(apprentice)
    assert len(apprentice.machine.outputs) == 3


def test_believing_every_mark_splits_states() -> None:
    """With one mark enough, the same late teacher leaves a larger machine."""
    apprentice = Apprentice(needed=1, share=0.0)
    teach(apprentice, 0.2, 2)
    assert len(apprentice.machine.outputs) > 3


def test_a_known_reaction_time_moves_the_mark() -> None:
    """With the teacher one action late, the action before the last is marked and the last is left unjudged."""
    apprentice = Apprentice(unjudged=1)
    apprentice.taken_over((2, 0, 1), [], ["left", "left", "left"], asked=True)
    assert apprentice.action((0, 1)) == "left"
    for _ in range(2):
        apprentice.taken_over((0, 1, 2), ["left", "left", "left"], [], late=1)
    assert apprentice.action((0,)) == "left" and apprentice.action((0, 1)) != "left"


def test_arguments_are_checked() -> None:
    with pytest.raises(ValueError):
        Apprentice(needed=0)
    with pytest.raises(ValueError):
        Apprentice(share=1.0)
    with pytest.raises(ValueError):
        Apprentice().taken_over((0, 1), ["stay"], [])
    with pytest.raises(ValueError):
        Apprentice().taken_over((0,), ["stay"], [], late=-1)
