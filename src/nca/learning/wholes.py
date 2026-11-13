"""Wholes judged by their parts (THEORY §57).

A situation is split into parts, each of a sort, and a whole is good when
every part is. One learner serves all the parts of a sort, each read at its
own slots, so what is taught of one part holds of the others. The split and
the sorts are the caller's.
"""

from collections.abc import Callable, Hashable, Mapping, Sequence
from random import Random
from typing import Any, Protocol

Parts = Mapping[Hashable, tuple[Hashable, Any]]
"""What is seen of each named part of a situation, with the part's sort."""


class Learner(Protocol):
    def votes(self, situation: Any, action: Hashable) -> tuple[float, float]: ...

    def judge(self, situation: Any, action: Hashable, good: bool) -> None: ...


class Whole:
    """Chooses the whole with the fewest parts judged bad, and is corrected part by part."""

    def __init__(self, parts: Callable[[Any], Parts], learners: Mapping[Hashable, Learner]) -> None:
        self.parts, self.learners = parts, learners

    def against(self, situation: Any, action: Hashable) -> tuple[int, float]:
        """The parts judged bad, and how far the votes against all the parts outweigh those for them."""
        count, weight = 0, 0.0
        for sort, seen in self.parts(situation).values():
            good, bad = self.learners[sort].votes(seen, action)
            count, weight = count + (bad > good), weight + bad - good
        return count, weight

    def choose(self, pairs: Sequence[tuple[Any, Hashable]], guesses: Random) -> int:
        scores = [self.against(situation, action) for situation, action in pairs]
        return guesses.choice([index for index, score in enumerate(scores) if score == min(scores)])

    def correct(self, proposed: Any, right: Any, action: Hashable) -> None:
        """Record a takeover: every part of ``right`` is good, and each part ``proposed`` has otherwise is bad.

        That each differing part is bad holds where a part has one good value, the rest being as shown (§57.3).
        A part that only one of the two has is not judged: what differs there is that the part is present.
        """
        mine, theirs = self.parts(proposed), self.parts(right)
        for name, part in mine.items():
            if name in theirs and theirs[name] != part:
                self.learners[part[0]].judge(part[1], action, False)
        for sort, seen in theirs.values():
            self.learners[sort].judge(seen, action, True)
