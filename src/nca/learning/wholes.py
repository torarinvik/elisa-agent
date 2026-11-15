"""Wholes judged by their parts (THEORY §57).

A situation is split into parts, each of a sort, and a whole is good when
every part is. One learner serves all the parts of a sort, each read at its
own slots, so what is taught of one part holds of the others. The split and
the sorts are the caller's.

``InTurn`` hears several choosers in turn, a later one only where the earlier
leave candidates level (§60.5).
"""

from collections.abc import Callable, Hashable, Mapping, Sequence
from random import Random
from typing import Any, Protocol

SLACK = 1e-9
"""Two grounds within this share of one another are taken as equal."""
Parts = Mapping[Hashable, tuple[Hashable, Any]]
"""What is seen of each named part of a situation, with the part's sort."""


class Learner(Protocol):
    def votes(self, situation: Any, action: Hashable) -> tuple[float, float]: ...

    def judge(self, situation: Any, action: Hashable, good: bool) -> None: ...

    def unmet(self, situation: Any, action: Hashable, together: int = 1) -> int: ...


class Whole:
    """Chooses the whole with the fewest parts judged bad, and is corrected part by part."""

    def __init__(self, parts: Callable[[Any], Parts], learners: Mapping[Hashable, Learner], together: int = 1) -> None:
        """``together`` is how many readings at once may mark a part as showing what no good part has."""
        self.parts, self.learners, self.together = parts, learners, together

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
        """Record a takeover: every part of ``right`` is good, and of the parts ``proposed`` has otherwise, the
        ones the learner has least ground to hold good are bad.

        Some differing part is bad (§57.3). Once the parts of ``right`` are recorded, the differing parts are
        ranked by the learner's votes and, among equals, by how much they show that no good part has shown; only
        the lowest are judged bad. Where nothing tells the differing parts apart, all of them are.
        A part that only one of the two has is not judged: what differs there is that the part is present.
        """
        mine, theirs = self.parts(proposed), self.parts(right)
        for sort, seen in theirs.values():
            self.learners[sort].judge(seen, action, True)
        differing = [part for name, part in mine.items() if name in theirs and theirs[name] != part]
        grounds = []
        for sort, seen in differing:
            good, bad = self.learners[sort].votes(seen, action)
            grounds.append(good - bad)
        least = min(grounds, default=0.0) + SLACK * max(1.0, abs(min(grounds, default=0.0)))
        lowest = [part for part, ground in zip(differing, grounds, strict=True) if ground <= least]
        unmet = [self.learners[sort].unmet(seen, action, self.together) for sort, seen in lowest]
        for (sort, seen), count in zip(lowest, unmet, strict=True):
            if count == max(unmet):
                self.learners[sort].judge(seen, action, False)

    def study(self, wholes: Sequence[Any], right: int, action: Hashable) -> None:
        """Record what every whole offered tells once the right one is known (§57.5).

        Each part has one good value, the rest being as shown: every part of the right whole is good, and a
        part any other whole has otherwise is bad. Only what the votes do not already give is recorded. A
        part that only one of the two has is not judged.
        """
        theirs = self.parts(wholes[right])
        for sort, seen in theirs.values():
            good, bad = self.learners[sort].votes(seen, action)
            if not good > bad:
                self.learners[sort].judge(seen, action, True)
        told: list[tuple[Hashable, Any]] = []
        for place, whole in enumerate(wholes):
            for name, (sort, seen) in self.parts(whole).items() if place != right else ():
                if name not in theirs or theirs[name][1] == seen or (name, seen) in told:
                    continue
                told.append((name, seen))
                good, bad = self.learners[sort].votes(seen, action)
                if not bad > good:
                    self.learners[sort].judge(seen, action, False)


class Chooser(Protocol):
    def against(self, situation: Any, action: Hashable) -> tuple[float, ...]: ...


class InTurn:
    """Choosers heard in turn: what a later one holds against a candidate counts only among the candidates the
    earlier ones hold level (§60.5)."""

    def __init__(self, *choosers: Chooser) -> None:
        self.choosers = choosers

    def against(self, situation: Any, action: Hashable) -> tuple[float, ...]:
        """What each chooser holds against the candidate, the earlier chooser's first."""
        return tuple(held for chooser in self.choosers for held in chooser.against(situation, action))

    def choose(self, pairs: Sequence[tuple[Any, Hashable]], guesses: Random) -> int:
        scores = [self.against(situation, action) for situation, action in pairs]
        return guesses.choice([index for index, score in enumerate(scores) if score == min(scores)])
