"""A table of hypothesis behaviours on a shared pool of inputs.

One enumeration can serve every goal with the same contract, needing no labels: a
goal narrows the table on a few of its own cases, and a goal whose label matches no
remaining class lies outside the table. Narrowing only proposes a hypothesis, which
must still pass independent fresh cases before admission.
"""

from collections.abc import Callable, Hashable, Sequence
from dataclasses import dataclass
from typing import Any, Generic, TypeVar

Hypothesis = TypeVar("Hypothesis")


@dataclass(frozen=True)
class Narrowing(Generic[Hypothesis]):
    """The hypothesis a goal's own cases leave, if one, with what finding it cost."""

    hypothesis: Hypothesis | None
    labels: int
    evaluations: int


class BehaviourTable(Generic[Hypothesis]):
    """Behaviour classes in enumeration order, keyed by a hashable form of their outputs."""

    def __init__(self, pool: Sequence[Any], key: Callable[[Any], Hashable]) -> None:
        if not pool:
            raise ValueError("a behaviour table needs a nonempty pool")
        self.pool, self.key = tuple(pool), key
        self.hypotheses: list[Hypothesis] = []
        self.vectors: list[tuple[Hashable, ...]] = []
        self._seen: set[tuple[Hashable, ...]] = set()

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
        return True

    def narrow(self, cases: Sequence[tuple[Any, Any]], run: Callable[[Hypothesis, Any], Any]) -> Narrowing[Hypothesis]:
        """Read a goal's labelled cases in turn until at most one class agrees.

        This needs no chosen inputs. A failing ``run`` should return a value no label equals.
        """
        remaining = list(self.hypotheses)
        labels = evaluations = 0
        for item, label in cases:
            if len(remaining) <= 1 and labels:
                break
            answer = self.key(label)
            labels += 1
            evaluations += len(remaining)
            remaining = [hypothesis for hypothesis in remaining if self.key(run(hypothesis, item)) == answer]
        return Narrowing(remaining[0] if remaining else None, labels, evaluations)
