"""A table of hypothesis behaviours on a shared pool of inputs.

One enumeration can serve every goal with the same contract: a goal is identified
by a few labels chosen to split the table, and a goal whose label matches no
remaining class lies outside the table. Identification only proposes a hypothesis.
A proposal must still pass independent fresh cases before admission.
"""

from collections import Counter
from collections.abc import Callable, Hashable, Sequence
from dataclasses import dataclass
from typing import Any, Generic, TypeVar

Hypothesis = TypeVar("Hypothesis")


@dataclass(frozen=True)
class Identification(Generic[Hypothesis]):
    """The hypothesis a goal's labels leave, if one, and the pool positions labelled."""

    hypothesis: Hypothesis | None
    asked: tuple[int, ...]


class BehaviourTable(Generic[Hypothesis]):
    """Behaviour classes in enumeration order, keyed by a hashable form of their outputs."""

    def __init__(self, pool: Sequence[Any], key: Callable[[Any], Hashable]) -> None:
        if not pool:
            raise ValueError("a behaviour table needs a nonempty pool")
        self.pool, self.key = tuple(pool), key
        self.hypotheses: list[Hypothesis] = []
        self.vectors: list[tuple[Hashable, ...]] = []
        self._seen: set[tuple[Hashable, ...]] = set()
        self._questions: dict[tuple[int, ...], int | None] = {}

    def add(self, hypothesis: Hypothesis, outputs: Sequence[Any]) -> bool:
        """Keep a hypothesis if its behaviour is new; the earliest of a class is kept."""
        if len(outputs) != len(self.pool):
            raise ValueError("outputs must cover the pool")
        vector = tuple(self.key(output) for output in outputs)
        if vector in self._seen:
            return False
        self._seen.add(vector)
        self.hypotheses.append(hypothesis)
        self.vectors.append(vector)
        self._questions.clear()
        return True

    def _question(self, remaining: tuple[int, ...]) -> int | None:
        """The position leaving the smallest largest group, or None if none splits them."""
        if remaining not in self._questions:
            best, smallest = None, len(remaining)
            for position in range(len(self.pool)):
                largest = max(Counter(self.vectors[index][position] for index in remaining).values())
                if largest < smallest:
                    best, smallest = position, largest
            self._questions[remaining] = best
        return self._questions[remaining]

    def identify(self, label: Callable[[int], Any]) -> Identification[Hypothesis]:
        """Ask for labels at chosen pool positions until at most one class remains."""
        remaining = tuple(range(len(self.vectors)))
        asked: list[int] = []
        while len(remaining) > 1:
            position = self._question(remaining)
            if position is None:
                break
            answer = self.key(label(position))
            asked.append(position)
            remaining = tuple(index for index in remaining if self.vectors[index][position] == answer)
        return Identification(self.hypotheses[remaining[0]] if remaining else None, tuple(asked))
