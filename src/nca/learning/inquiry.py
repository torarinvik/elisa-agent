"""A learner that chooses what to look at: its view grows by the probes its judgements call for (THEORY §54).

A situation can be read through any of a pool of probes, each returning one
value. The learner looks only through its view, a list of probes that starts
empty, and learns over the view's readings as ``Relevance`` does (§53). A
judged situation is studied whole: every probe is read once and kept, so a
probe taken up later can be read on the judgements already made.

A set of probes explains the judgements of an action at the cost of the
judgements it gets wrong, one for each judgement outside the majority of its
class, plus ``price`` for each class it uses. Each action is explained by its
own set, and the view's cost is the sum over the actions of the cheapest
(§53.8). A set the target depends on gets none wrong
(``NCA.sufficient_set_consistent``), so judgements no set of the view explains
show that the view lacks a probe (``NCA.disagreeing_probe_outside_view``). The
learner then takes up the probe with which the view would explain them most
cheaply, each action using it or not with at most ``largest - 1`` probes of
the view, as long as that is cheaper than the view explains them. The price of a class keeps a probe from being
bought for splitting classes alone.

With ``sheds`` the view also gives probes up: whenever the actions are joined
anew, it keeps only the probes of each action's cheapest set (§54.9). The cost
of the view is unchanged by that. The view is then a few probes, at the price
of more judgements: the sets a larger view holds besides the cheapest also
carry judgements.

With ``turns`` the learner may find that one action is another turned (§54.8).
A turn puts a probe in each probe's place. An action joins an earlier action
under a turn when the two, read through that turn, are explained more cheaply
together by one probe than apart; they then share their judgements, each read
through its own turn, and a judgement of one teaches the other.

With ``alike`` the learner may also find that a situation and the same
situation turned are judged alike (§54.10). A turn is taken for such a likeness
unless the judgements and their turned copies cost more together than twice
apart, by one probe, beyond what chance allows. A situation is then judged and
decided in one of its alike images, the one that reads first: by one probe,
the pivot, read in every image, and then through the view. A judgement of one
image is so a judgement of all. The pivot is the probe that leaves the
judgements cheapest to explain; with a ``shortlist`` it is sought among the
probes that alone explain them best. Likenesses and pivots are kept for each
action, or each group of actions joined by turns, in that group's frame.

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
                 shortlist: int | None = None, turns: Sequence[Sequence[int]] = (), sheds: bool = False,
                 alike: bool = False) -> None:
        """``read`` gives a probe's value in a situation; the view holds at most ``limit`` probes."""
        if len(set(probes)) != len(probes):
            raise ValueError("the probes are distinct")
        if price < 0 or (limit is not None and limit < 0):
            raise ValueError("the price of a class and the limit of the view are non-negative")
        if shortlist is not None and shortlist < 1:
            raise ValueError("a shortlist holds at least one probe")
        self.probes, self.read = tuple(probes), read
        self.largest, self.keep, self.price, self.limit = largest, keep, price, limit
        self.shortlist, self.sheds, self.alike = shortlist, sheds, alike
        self.same: dict[Hashable, tuple[int, ...]] = {}
        self.pivot: dict[Hashable, int] = {}
        still = tuple(range(len(self.probes)))
        self.turns = (still, *(tuple(turn) for turn in turns if tuple(turn) != still))
        if any(sorted(turn) != list(still) for turn in self.turns):
            raise ValueError("a turn puts each probe in one place")
        self.frames: dict[Hashable, tuple[Hashable, int]] = {}
        self.view: list[int] = []
        self.cases: list[Case] = []
        self.looked = self.studied = 0
        self._relevance = Relevance(0, largest=largest, keep=keep, apart=True)
        self._codes: list[list[int]] = []
        self._good: list[bool] = []
        self._names: dict[Hashable, int] = {}

    def __getstate__(self) -> dict[str, Any]:
        """What is saved: the judgements and the view, from which the learner over the view is made again."""
        return {name: value for name, value in self.__dict__.items() if name != "_relevance"}

    def __setstate__(self, state: dict[str, Any]) -> None:
        self.__dict__.update({"shortlist": None, "frames": {}, "sheds": False, "alike": False, "same": {}, "pivot": {}} | state)
        self.__dict__.setdefault("turns", (tuple(range(len(self.probes))),))
        self._learn()

    @property
    def judgements(self) -> int:
        return len(self.cases)

    @property
    def looking_at(self) -> tuple[Hashable, ...]:
        """The probes of the view, in the order they were taken up."""
        return tuple(self.probes[index] for index in self.view)

    def frame(self, action: Hashable) -> tuple[Hashable, int]:
        """The action whose judgements ``action`` shares, and the turn it is read through."""
        return self.frames.get(action, (action, 0))

    def looking_for(self, action: Hashable) -> tuple[Hashable, ...]:
        """The probes read for ``action``: the view through the action's turn."""
        turn = self.turns[self.frame(action)[1]]
        return tuple(self.probes[turn[index]] for index in self.view)

    def observe(self, situation: Any, action: Hashable = None) -> tuple[Hashable, ...]:
        """The situation as the view shows it for ``action``."""
        images = self._images(action)
        if len(images) == 1:
            self.looked += len(self.view)
            return tuple(self.read(situation, self.probes[index]) for index in images[0])
        readings = {index: self.read(situation, self.probes[index]) for index in dict.fromkeys(sum(images, ()))}
        self.looked += len(readings)
        names = self._names
        first = min(images, key=lambda image: [names.setdefault(readings[index], len(names)) for index in image])
        return tuple(readings[index] for index in first[len(first) - len(self.view):])

    def votes(self, situation: Any, action: Hashable) -> tuple[float, float]:
        """The weight judging ``action`` in ``situation`` good, and the weight judging it bad."""
        return self._relevance.votes(self.observe(situation, action), self.frame(action)[0])

    def choose(self, pairs: Sequence[tuple[Any, Hashable]], guesses: Random) -> int:
        """The index of a pair believed good, or failing any a guess that avoids bad majorities."""
        return self._relevance.choose([(self.observe(situation, action), self.frame(action)[0])
                                       for situation, action in pairs], guesses)

    def judge(self, situation: Any, action: Hashable, good: bool) -> None:
        """Record that ``action`` in ``situation`` is good or bad, and take up probes the judgements now call for."""
        self.studied += len(self.probes)
        readings = tuple(self.read(situation, probe) for probe in self.probes)
        self.cases.append((readings, action, good))
        names = self._names
        self._codes.append([names.setdefault(reading, len(names)) for reading in readings])
        self._good.append(good)
        turned = len(self.turns) > 1 and self._align()
        turned = (self.alike and len(self.turns) > 1 and self._liken()) or turned
        told = bool(self.same or self.pivot) and self._pivot()
        if not (turned or told):
            self._relevance.judge(self._first(readings, self._codes[-1], action), self.frame(action)[0], good)
        if turned and self.sheds:
            self._shed()
        if self._grow() or turned or told:
            self._learn()

    def cost(self, subset: Sequence[int], action: Hashable) -> float:
        """What the set leaves unexplained of the judgements ``action`` shares: those outside their class's majority,
        and ``price`` a class."""
        classes: dict[tuple[int, ...], list[int]] = {}
        codes, actions, verdicts = self._shared()
        groups = self._plain()[3]
        for row, kind, good in zip(codes[:, list(subset)].tolist(), actions.tolist(), verdicts.tolist(), strict=True):
            if groups[kind] == action:
                classes.setdefault(tuple(row), [0, 0])[good] += 1
        return sum(min(counts) for counts in classes.values()) + self.price * len(classes)

    def _single(self, codes: np.ndarray, good: np.ndarray) -> float:
        """The least cost of explaining judgements by one probe or by none."""
        return float(min(self._ranked(codes, good).min(), min(good.sum(), (~good).sum()) + self.price))

    def _align(self) -> bool:
        """Let each action join an earlier one under the turn that explains the two most cheaply together."""
        raw, good = np.array(self._codes), np.array(self._good)
        labels = [action for _, action, _ in self.cases]
        turns = np.array(self.turns)
        frames: dict[Hashable, tuple[Hashable, int]] = {}
        groups: dict[Hashable, tuple[np.ndarray, np.ndarray, float]] = {}
        for action in dict.fromkeys(labels):
            rows = np.array([label == action for label in labels])
            mine, verdicts = raw[rows], good[rows]
            alone = self._single(mine, verdicts)
            saving, group, turn = 0.0, action, 0
            for other, (codes, others, apart) in groups.items():
                for place in range(len(turns)):
                    pooled = self._single(np.vstack((codes, mine[:, turns[place]])), np.concatenate((others, verdicts)))
                    if apart + alone - pooled > saving:
                        saving, group, turn = apart + alone - pooled, other, place
            frames[action] = group, turn
            if group == action:
                groups[action] = mine, verdicts, alone
            else:
                codes, others = np.vstack((groups[group][0], mine[:, turns[turn]])), np.concatenate((groups[group][1], verdicts))
                groups[group] = codes, others, self._single(codes, others)
        changed, self.frames = frames != self.frames, frames
        return changed

    def _images(self, action: Hashable) -> list[tuple[int, ...]]:
        """The probes read for ``action`` in the situation as it stands and in each image judged alike: the pivot in
        every image, by which the images are told apart, and then the view."""
        group, turn = self.frame(action)
        through, places = self.turns[turn], (0, *self.same.get(group, ()))
        told = [self.turns[place][self.pivot[group]] for place in places] if group in self.pivot else []
        return [tuple(through[self.turns[place][index]] for index in (*told, *self.view)) for place in places]

    def _first(self, readings: Sequence[Hashable], codes: Sequence[int], action: Hashable) -> tuple[Hashable, ...]:
        """A judged situation as the view shows the alike image that reads first."""
        first = min(self._images(action), key=lambda image: [codes[index] for index in image])
        return tuple(readings[index] for index in first[len(first) - len(self.view):])

    def _plain(self) -> tuple[np.ndarray, np.ndarray, np.ndarray, list[Hashable]]:
        """The judgements as their actions share them: readings through each action's turn, the action shared, the
        verdict; and the shared actions as numbered."""
        raw, good, turns = np.array(self._codes), np.array(self._good), np.array(self.turns)
        frames = [self.frame(action) for _, action, _ in self.cases]
        names: dict[Hashable, int] = {}
        actions = np.array([names.setdefault(group, len(names)) for group, _ in frames])
        return np.take_along_axis(raw, turns[[turn for _, turn in frames]], axis=1), actions, good, list(names)

    def _shared(self) -> tuple[np.ndarray, np.ndarray, np.ndarray]:
        """The judgements, each in the alike image that reads first."""
        codes, actions, good, groups = self._plain()
        for kind, group in enumerate(groups):
            if self.same.get(group):
                rows = actions == kind
                codes[rows] = self._imaged(codes[rows], self.same[group], self.pivot.get(group))
        return codes, actions, good

    def _imaged(self, codes: np.ndarray, same: Sequence[int], pivot: int | None) -> np.ndarray:
        """Each row in its alike image that reads first: by ``pivot`` in every image, then through the view."""
        turns = np.array(self.turns)[[0, *same]]
        order = np.hstack((turns[:, [] if pivot is None else turns[:, pivot]], turns[:, self.view])).astype(int)
        seen = codes[:, order]
        first = np.ones(seen.shape[:2], dtype=bool)
        for column in range(seen.shape[2]):
            values = np.where(first, seen[:, :, column], np.iinfo(seen.dtype).max)
            first &= values == values.min(axis=1, keepdims=True)
        return np.take_along_axis(codes, turns[first.argmax(axis=1)], axis=1)

    def _ranked(self, codes: np.ndarray, good: np.ndarray) -> np.ndarray:
        """The cost of explaining judgements by each probe alone."""
        values, probes = int(codes.max()) + 1, codes.shape[1]
        keys = codes + np.arange(probes) * values
        counts = [np.bincount(keys[verdict].ravel(), minlength=probes * values).reshape(probes, values)
                  for verdict in (good, ~good)]
        return np.minimum(*counts).sum(axis=1) + self.price * np.count_nonzero(counts[0] + counts[1], axis=1)

    def _pivot(self) -> bool:
        """For each shared action with a likeness, tell the alike images apart by the probe that leaves its
        judgements cheapest to explain by one probe."""
        codes, actions, good, groups = self._plain()
        pivots: dict[Hashable, int] = {}
        for kind, group in enumerate(groups):
            same = self.same.get(group)
            if not same:
                continue
            mine, verdicts = codes[actions == kind], good[actions == kind]
            candidates = (range(len(self.probes)) if self.shortlist is None
                          else np.argsort(self._ranked(mine, verdicts), kind="stable")[:self.shortlist].tolist())
            best = self.pivot.get(group)
            least = self._single(self._imaged(mine, same, best), verdicts)
            for pivot in candidates:
                offer = self._single(self._imaged(mine, same, pivot), verdicts)
                if offer < least:
                    least, best = offer, pivot
            if best is not None:
                pivots[group] = best
        changed, self.pivot = pivots != self.pivot, pivots
        return changed

    def _liken(self) -> bool:
        """For each shared action, take each turn for a likeness unless its judgements and their turned copies cost
        more together than twice apart by more than chance allows (54.10)."""
        codes, actions, good, groups = self._plain()
        likenesses: dict[Hashable, tuple[int, ...]] = {}
        for kind, group in enumerate(groups):
            mine, verdicts = codes[actions == kind], good[actions == kind]
            most = 2 * self._single(mine, verdicts) + len(verdicts) ** 0.5
            same = tuple(place for place in range(1, len(self.turns))
                         if self._single(np.vstack((mine, mine[:, self.turns[place]])), np.tile(verdicts, 2)) < most)
            if same:
                likenesses[group] = same
        changed, self.same = likenesses != self.same, likenesses
        return changed

    def _shed(self) -> None:
        """Keep only the probes of each action's cheapest set of the view; among equals the smallest, then first."""
        codes, actions, good = self._shared()
        kinds = int(actions.max()) + 1
        least, kept = np.full(kinds, np.inf), [()] * kinds
        for size in range(min(self.largest, len(self.view)) + 1):
            for subset in combinations(self.view, size):
                _, classes = np.unique(codes[:, subset], axis=0, return_inverse=True)
                keys = classes.reshape(-1) * kinds + actions
                counts = [np.bincount(keys[verdict], minlength=(int(keys.max()) // kinds + 1) * kinds)
                          .reshape(-1, kinds) for verdict in (good, ~good)]
                costs = np.minimum(*counts).sum(axis=0) + self.price * np.count_nonzero(counts[0] + counts[1], axis=0)
                for kind in np.flatnonzero(costs < least):
                    least[kind], kept[kind] = costs[kind], subset
        used = {index for subset in kept for index in subset}
        self.view = [index for index in self.view if index in used]

    def _offers(self) -> tuple[float, np.ndarray]:
        """The cost the view leaves, and for each probe the cost the view would leave with it."""
        codes, actions, good = self._shared()
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
        """Each action's least cost over sets of at most ``largest``, summed: within the view, and with each probe."""
        view = list(self.view if view is None else view)
        values, probes, kinds = int(codes.max()) + 1, codes.shape[1], int(actions.max()) + 1
        least, offers = np.full(kinds, np.inf), np.full((probes, kinds), np.inf)
        for size in range(min(largest, len(view) + 1)):
            for subset in combinations(view, size):
                _, classes = np.unique(codes[:, subset], axis=0, return_inverse=True)
                classes = classes.reshape(-1) * kinds + actions
                span = (int(classes.max()) // kinds + 1) * kinds
                if not size:
                    counts = [np.bincount(actions[verdict], minlength=kinds) for verdict in (good, ~good)]
                    least = np.minimum(*counts) + self.price * (counts[0] + counts[1] > 0)
                keys = classes[:, None] + span * codes + np.arange(probes) * (span * values)
                counts = [np.bincount(keys[verdict].ravel(), minlength=probes * span * values)
                          .reshape(probes, values, span // kinds, kinds) for verdict in (good, ~good)]
                offers = np.minimum(offers, np.minimum(*counts).sum(axis=(1, 2))
                                    + self.price * np.count_nonzero(counts[0] + counts[1], axis=(1, 2)))
        least = np.minimum(least, offers[view].min(axis=0, initial=np.inf))
        return float(least.sum()), np.minimum(offers, least).sum(axis=1)

    def _grow(self) -> bool:
        if self.largest < 1:
            return False
        grown = False
        while True:
            current, offers = self._offers()
            offers[self.view] = np.inf
            best = int(offers.argmin())
            if (self.limit is not None and len(self.view) >= self.limit) or offers[best] >= current:
                break
            self.view.append(best)
            grown = True
        return grown

    def _learn(self) -> None:
        """Learn over the view afresh from the judgements kept, each read through its action's turn."""
        self._relevance = Relevance(len(self.view), largest=self.largest, keep=self.keep, apart=True)
        for (readings, action, good), codes in zip(self.cases, self._codes, strict=True):
            self._relevance.judge(self._first(readings, codes, action), self.frame(action)[0], good)
