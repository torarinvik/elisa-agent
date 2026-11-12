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

With ``shortlist`` the search is cut short for large pools: every probe is first
joined to at most one probe of the view, and only the ``shortlist`` cheapest are
then compared in full. A probe that explains the judgements only together with
two probes of the view can then be missed.

The probes and their meanings are the caller's; the learner only finds which
of them to look through.
"""

from collections.abc import Callable, Hashable, Sequence
from itertools import combinations
from random import Random
from typing import Any

import numpy as np

from .relevance import Relevance

Case = tuple[tuple[Hashable, ...], Hashable, bool]


class Inquiry:
    """Judged actions over a view that grows by the probes the judgements call for."""

    def __init__(self, probes: Sequence[Hashable], read: Callable[[Any, Hashable], Hashable], *, largest: int,
                 keep: float = 0.0, price: float = 1.0, limit: int | None = None,
                 shortlist: int | None = None) -> None:
        """``read`` gives a probe's value in a situation; the view holds at most ``limit`` probes."""
        if len(set(probes)) != len(probes):
            raise ValueError("the probes are distinct")
        if price < 0 or (limit is not None and limit < 0):
            raise ValueError("the price of a class and the limit of the view are non-negative")
        if shortlist is not None and shortlist < 1:
            raise ValueError("a shortlist holds at least one probe")
        self.probes, self.read = tuple(probes), read
        self.largest, self.keep, self.price, self.limit = largest, keep, price, limit
        self.shortlist = shortlist
        self.view: list[int] = []
        self.cases: list[Case] = []
        self.looked = self.studied = 0
        self._relevance = Relevance(0, largest=largest, keep=keep)
        self._codes: list[list[int]] = []
        self._actions: list[int] = []
        self._good: list[bool] = []
        self._names: dict[Hashable, int] = {}

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
        names = self._names
        self._codes.append([names.setdefault(reading, len(names)) for reading in readings])
        self._actions.append(names.setdefault((Inquiry, action), len(names)))
        self._good.append(good)
        self._relevance.judge(tuple(readings[index] for index in self.view), action, good)
        self._grow()

    def cost(self, subset: Sequence[int]) -> float:
        """What the set leaves unexplained: judgements outside their class's majority, and ``price`` a class."""
        classes: dict[tuple[Hashable, ...], list[int]] = {}
        for readings, action, good in self.cases:
            classes.setdefault((action, *(readings[index] for index in subset)), [0, 0])[good] += 1
        return sum(min(counts) for counts in classes.values()) + self.price * len(classes)

    def _offers(self) -> tuple[float, np.ndarray]:
        """The least cost of a set of the view, and for each probe the least cost of a set of it and the view."""
        codes, actions, good = np.array(self._codes), np.array(self._actions), np.array(self._good)
        if self.shortlist is None or self.largest <= 2 or codes.shape[1] <= self.shortlist + len(self.view):
            return self._costs(codes, actions, good, self.largest)
        _, rough = self._costs(codes, actions, good, 2)
        rough[self.view] = np.inf
        listed = np.array([*self.view, *np.argsort(rough, kind="stable")[:self.shortlist]])
        least, exact = self._costs(codes[:, listed], actions, good, self.largest, range(len(self.view)))
        offers = np.full(codes.shape[1], np.inf)
        offers[listed] = exact
        return least, offers

    def _costs(self, codes: np.ndarray, actions: np.ndarray, good: np.ndarray, largest: int,
               view: Sequence[int] | None = None) -> tuple[float, np.ndarray]:
        """The least cost within the view, and each probe's with the view, over sets of at most ``largest``."""
        view = self.view if view is None else view
        values, probes = int(codes.max()) + 1, codes.shape[1]
        least, offers = float("inf"), np.full(probes, np.inf)
        for size in range(min(largest, len(view) + 1)):
            for subset in combinations(view, size):
                _, classes = np.unique(np.column_stack((actions, codes[:, subset])), axis=0, return_inverse=True)
                classes = classes.reshape(-1)
                span = (int(classes.max()) + 1) * values
                if not size:
                    counts = [np.bincount(classes[verdict], minlength=span) for verdict in (good, ~good)]
                    least = float(np.minimum(*counts).sum() + self.price * np.count_nonzero(counts[0] + counts[1]))
                keys = (classes[:, None] * values + codes + np.arange(probes) * span)
                counts = [np.bincount(keys[verdict].ravel(), minlength=probes * span).reshape(probes, span)
                          for verdict in (good, ~good)]
                offers = np.minimum(offers, np.minimum(*counts).sum(axis=1)
                                    + self.price * np.count_nonzero(counts[0] + counts[1], axis=1))
        return min(least, float(offers[list(view)].min(initial=np.inf))), offers

    def _grow(self) -> None:
        if self.largest < 1:
            return
        grown = False
        while True:
            current, offers = self._offers()
            offers[self.view] = np.inf
            best = int(offers.argmin())
            if (self.limit is not None and len(self.view) >= self.limit) or offers[best] >= current:
                break
            self.view.append(best)
            grown = True
        if grown:
            self._relevance = Relevance(len(self.view), largest=self.largest, keep=self.keep)
            for readings, action, good in self.cases:
                self._relevance.judge(tuple(readings[index] for index in self.view), action, good)
