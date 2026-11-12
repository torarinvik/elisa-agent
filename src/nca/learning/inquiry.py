"""A learner that chooses what to look at: its view grows by the probes its judgements call for (THEORY §54).

A situation can be read through any of a pool of probes, each returning one
value. The learner looks only through its view, a list of probes that starts
empty, and learns over the view's readings as ``Relevance`` does (§53). A
judged situation is studied whole: every probe is read once and kept, so a
probe taken up later can be read on the judgements already made.

A set of probes explains the judgements at the cost of the judgements it gets
wrong, one for each judgement outside the majority of its class, plus ``price``
for each class it uses. A set the target depends on gets none wrong
(``NCA.sufficient_set_consistent``), so judgements no set of the view explains
show that the view lacks a probe (``NCA.disagreeing_probe_outside_view``). The
learner then takes up the probe that, joined to at most ``largest - 1`` probes
of the view, explains the judgements most cheaply, as long as that is cheaper
than the view explains them. The price of a class keeps a probe from being
bought for splitting classes alone.

The probes and their meanings are the caller's; the learner only finds which
of them to look through.
"""

from collections.abc import Callable, Hashable, Sequence
from itertools import combinations
from random import Random
from typing import Any

from .relevance import Relevance

Case = tuple[tuple[Hashable, ...], Hashable, bool]


class Inquiry:
    """Judged actions over a view that grows by the probes the judgements call for."""

    def __init__(self, probes: Sequence[Hashable], read: Callable[[Any, Hashable], Hashable], *, largest: int,
                 keep: float = 0.0, price: float = 1.0, limit: int | None = None) -> None:
        """``read`` gives a probe's value in a situation; the view holds at most ``limit`` probes."""
        if len(set(probes)) != len(probes):
            raise ValueError("the probes are distinct")
        if price < 0 or (limit is not None and limit < 0):
            raise ValueError("the price of a class and the limit of the view are non-negative")
        self.probes, self.read = tuple(probes), read
        self.largest, self.keep, self.price, self.limit = largest, keep, price, limit
        self.view: list[int] = []
        self.cases: list[Case] = []
        self.looked = self.studied = 0
        self._relevance = Relevance(0, largest=largest, keep=keep)
        self._settled = 0

    @property
    def judgements(self) -> int:
        return len(self.cases)

    @property
    def looking_at(self) -> tuple[Hashable, ...]:
        """The probes of the view, in the order they were taken up."""
        return tuple(self.probes[index] for index in self.view)

    def observe(self, situation: Any) -> tuple[Hashable, ...]:
        """The situation as the view shows it."""
        self.looked += len(self.view)
        return tuple(self.read(situation, self.probes[index]) for index in self.view)

    def votes(self, situation: Any, action: Hashable) -> tuple[float, float]:
        """The weight judging ``action`` in ``situation`` good, and the weight judging it bad."""
        return self._relevance.votes(self.observe(situation), action)

    def choose(self, pairs: Sequence[tuple[Any, Hashable]], guesses: Random) -> int:
        """The index of a pair believed good, or failing any a guess that avoids bad majorities."""
        return self._relevance.choose([(self.observe(situation), action) for situation, action in pairs], guesses)

    def judge(self, situation: Any, action: Hashable, good: bool) -> None:
        """Record that ``action`` in ``situation`` is good or bad, and take up probes the judgements now call for."""
        self.studied += len(self.probes)
        readings = tuple(self.read(situation, probe) for probe in self.probes)
        self.cases.append((readings, action, good))
        self._relevance.judge(tuple(readings[index] for index in self.view), action, good)
        self._grow()

    def cost(self, subset: Sequence[int]) -> float:
        """What the set leaves unexplained: judgements outside their class's majority, and ``price`` a class."""
        classes: dict[tuple[Hashable, ...], list[int]] = {}
        for readings, action, good in self.cases:
            classes.setdefault((action, *(readings[index] for index in subset)), [0, 0])[good] += 1
        return sum(min(counts) for counts in classes.values()) + self.price * len(classes)

    def _least(self, having: tuple[int, ...] = ()) -> float:
        """The least cost of a set of the view, of at most ``largest`` probes, that includes ``having``."""
        room = self.largest - len(having)
        return min(self.cost((*subset, *having)) for size in range(min(room, len(self.view)) + 1)
                   for subset in combinations(self.view, size))

    def _grow(self) -> None:
        if self.largest < 1:
            return
        current, grown = self._least(), False
        if current <= self._settled:
            return
        while self.limit is None or len(self.view) < self.limit:
            offers = {index: self._least((index,)) for index in range(len(self.probes)) if index not in self.view}
            best = min(offers, key=lambda index: (offers[index], index), default=None)
            if best is None or offers[best] >= current:
                break
            self.view.append(best)
            current, grown = offers[best], True
        self._settled = current
        if grown:
            self._relevance = Relevance(len(self.view), largest=self.largest, keep=self.keep)
            for readings, action, good in self.cases:
                self._relevance.judge(tuple(readings[index] for index in self.view), action, good)
