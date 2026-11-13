"""Judgements that carry across observations agreeing on the components that matter (THEORY §53).

An observation is a sequence of components. A judgement says that an action at
an observation is good or bad. The learner keeps every set of at most
``largest`` components and, for each, the judgements in each of its classes:
the observations that agree on the set. A set predicts the verdict its
judgements of an action in a class lean to, and a new judgement the other way
contradicts it. Each set votes with weight ``keep`` raised to its
contradictions (§53.5). With ``keep`` zero a contradicted set is dropped: a set
the target depends on is never contradicted by a correct teacher
(``NCA.sufficient_set_consistent``), and takeovers are bounded by the classes of
that set and the number of sets, not by the number of observations (§53.3–53.4).
With ``keep`` above zero a teacher who contradicts themselves loses no set, and
one contradicted less often outweighs one contradicted more often
(``NCA.weight_le_pow``). A set whose weight falls below ``negligible`` times
the best in its context is dropped.

Components named ``ordered`` have comparable values (§53.7). They are left out
of the sets, and each carries two hypotheses instead: that larger values are
preferred, and that smaller ones are. A choice of one candidate over the others
counts against each by the share of them it would have ranked above the choice.
Among the pairs it believes good, the learner chooses the one furthest along
the ordered components, each weighed by its two hypotheses
(``NCA.fewer_contradictions_weigh_more``). It is not told the direction.

Components named ``always`` split the problem instead: each of their values is
a context with its own family of sets. With ``apart`` each action is a context
too: the components one action's verdict depends on need not be another's
(§53.8). The components and their meanings are the caller's; the learner only
finds which of them matter.
"""

from collections.abc import Callable, Hashable, Sequence
from itertools import combinations
from operator import itemgetter
from random import Random
from typing import Any

Observation = Sequence[Hashable]
Judgement = tuple[tuple[Hashable, ...], Hashable, bool]


def _nothing(_: Observation) -> Hashable:
    return ()


def _reader(subset: tuple[int, ...]) -> Callable[[Observation], Hashable]:
    """What an observation shows on ``subset``, the key of its class."""
    return itemgetter(*subset) if subset else _nothing


class _Context:
    """The sets of one context, the counts of good and bad judgements in their classes, and their contradictions."""

    def __init__(self, family: tuple[tuple[int, ...], ...]) -> None:
        self.tables: dict[tuple[int, ...], dict[tuple[Hashable, Hashable], list[int]]] = {
            subset: {} for subset in family}
        self.contradicted = dict.fromkeys(family, 0)
        self.weight = dict.fromkeys(family, 1.0)
        self.predicted: set[tuple[int, ...]] = set()
        """The sets that have predicted a verdict: a judgement fell in a class of theirs that leaned one way."""
        self.votes: dict[tuple[tuple[Hashable, ...], Hashable], tuple[float, float]] = {}

    def __setstate__(self, state: dict[str, Any]) -> None:
        """Take up a saved context; one saved before predictions were kept counts every set as having predicted."""
        self.__dict__.update({"predicted": set(state["tables"])} | state)


class Relevance:
    """Judged actions, carried to every observation that agrees on a set of components, weighted by its record."""

    def __init__(self, components: int, *, largest: int, always: Sequence[int] = (), keep: float = 0.0,
                 negligible: float = 1e-9, ordered: Sequence[int] = (), apart: bool = False) -> None:
        """``components`` per observation, sets of at most ``largest`` of them, ``always`` read as the context.

        The values of the ``ordered`` components can be compared with one another.
        """
        if type(components) is not int or type(largest) is not int or components < 0 or largest < 0:
            raise ValueError("counts of components are non-negative integers")
        if any(index not in range(components) for index in always) or len(set(always)) != len(always):
            raise ValueError("the context components are distinct components")
        if any(index not in range(components) for index in ordered) or len(set(ordered)) != len(ordered):
            raise ValueError("the ordered components are distinct components")
        if not 0 <= keep < 1 or not 0 < negligible < 1:
            raise ValueError("a contradicted set keeps a share below one, and a negligible share is below one")
        self.components, self.largest, self.always = components, largest, tuple(always)
        self.keep, self.negligible, self.apart = keep, negligible, apart
        free = [index for index in range(components) if index not in self.always and index not in ordered]
        self.family = tuple(subset for size in range(min(largest, len(free)) + 1)
                            for subset in combinations(free, size))
        self.readers = {subset: _reader(subset) for subset in self.family}
        self.ordered = tuple(ordered)
        self.preferences = 0
        self._against = {(index, larger): 0.0 for index in self.ordered for larger in (True, False)}
        self.history: list[Judgement] = []
        self._contexts: dict[tuple[Hashable, ...], _Context] = {}

    def __setstate__(self, state: dict[str, Any]) -> None:
        """Take up a saved learner; one saved before actions could be kept apart keeps them together."""
        self.__dict__.update({"apart": False} | state)

    @property
    def judgements(self) -> int:
        """Verdicts and preferences recorded so far."""
        return len(self.history) + self.preferences

    def prefer(self, better: Observation, others: Sequence[Observation], action: Hashable) -> None:
        """Record that the teacher chose ``action`` at ``better`` over it at each of ``others``.

        Each direction of an ordered component loses the share of the others,
        among those not believed bad that differ from ``better`` on the
        component, that it would have ranked above the teacher's choice.
        """
        rivals = [other for other in others if (lambda good, bad: bad <= good)(*self.votes(other, action))]
        self.preferences += 1
        for index in self.ordered:
            beyond = sum(other[index] > better[index] for other in rivals)
            short = sum(other[index] < better[index] for other in rivals)
            if beyond + short:
                self._against[index, True] += beyond / (beyond + short)
                self._against[index, False] += short / (beyond + short)

    def direction(self, index: int) -> float:
        """The weight that larger values of an ordered component are preferred, minus the weight that smaller are."""
        larger, smaller = self._against[index, True], self._against[index, False]
        least = min(larger, smaller)
        return self.keep ** (larger - least) - self.keep ** (smaller - least)

    def _context(self, observation: Observation, action: Hashable = None) -> _Context:
        if len(observation) != self.components:
            raise ValueError(f"an observation has {self.components} components")
        key = (*(observation[index] for index in self.always), *((action,) if self.apart else ()))
        context = self._contexts.get(key)
        if context is None:
            context = self._contexts[key] = _Context(self.family)
        return context

    def judge(self, observation: Observation, action: Hashable, good: bool) -> None:
        """Record that ``action`` at ``observation`` is good or bad, counting it against every set it contradicts.

        A set is dropped once its weight is a negligible share of the best set's
        among those that have predicted. A set that has never predicted, as one
        over components whose values never recur, is contradicted by nothing and
        votes on nothing; it is not a measure of the others.
        """
        context = self._context(observation, action)
        self.history.append((tuple(observation), action, good))
        context.votes.clear()
        readers = self.readers
        for subset, table in context.tables.items():
            counts = table.setdefault((readers[subset](observation), action), [0, 0])
            if counts[0] != counts[1]:
                context.predicted.add(subset)
                if (counts[0] > counts[1]) != good:
                    context.contradicted[subset] += 1
                    context.weight[subset] = self.keep ** context.contradicted[subset]
            counts[not good] += 1
        least = min(map(context.contradicted.__getitem__, context.predicted), default=0)
        for subset, misses in list(context.contradicted.items()):
            if misses and (self.keep == 0 or self.keep ** (misses - least) < self.negligible):
                del context.tables[subset], context.contradicted[subset], context.weight[subset]
                context.predicted.discard(subset)

    def votes(self, observation: Observation, action: Hashable) -> tuple[float, float]:
        """The weight of the sets that judge ``action`` at ``observation`` good, and of those that judge it bad."""
        context = self._context(observation, action)
        remembered = context.votes.get((tuple(observation), action))
        if remembered is not None:
            return remembered
        good = bad = 0.0
        readers, weights = self.readers, context.weight
        for subset, table in context.tables.items():
            counts = table.get((readers[subset](observation), action))
            if counts is not None and counts[0] != counts[1]:
                if counts[0] > counts[1]:
                    good += weights[subset]
                else:
                    bad += weights[subset]
        context.votes[tuple(observation), action] = good, bad
        return good, bad

    def surviving(self, observation: Observation, action: Hashable = None) -> int:
        """The sets of the observation's context still voting."""
        return len(self._context(observation, action).tables)

    def choose(self, pairs: Sequence[tuple[Observation, Hashable]], guesses: Random) -> int:
        """The index of a pair believed good, or failing any a guess that avoids bad majorities.

        Among those pairs the one furthest along the ordered components is
        taken, by the directions learned; with no direction learned, the widest
        good majority, or any of the guesses.
        """
        if not pairs:
            raise ValueError("there is nothing to choose from")
        tallies = [self.votes(observation, action) for observation, action in pairs]
        believed = [index for index, (good, bad) in enumerate(tallies) if good > bad]
        kept = believed or [index for index, (good, bad) in enumerate(tallies) if bad <= good] or range(len(pairs))
        along = dict.fromkeys(kept, 0.0)
        for component in self.ordered:
            direction = self.direction(component)
            if direction:
                places = {value: place for place, value in enumerate(sorted({pairs[index][0][component]
                                                                             for index in kept}))}
                for index in kept:
                    along[index] += direction * places[pairs[index][0][component]]
        furthest = max(along.values())
        kept = [index for index in kept if along[index] == furthest]
        if believed:
            return max(kept, key=lambda index: (tallies[index][0] - tallies[index][1], -index))
        return guesses.choice(kept)
