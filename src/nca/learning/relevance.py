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

Components named ``always`` split the problem instead: each of their values is
a context with its own family of sets. The components and their meanings are
the caller's; the learner only finds which of them matter.
"""

from collections.abc import Callable, Hashable, Sequence
from itertools import combinations
from operator import itemgetter
from random import Random

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
        self.votes: dict[tuple[tuple[Hashable, ...], Hashable], tuple[float, float]] = {}


class Relevance:
    """Judged actions, carried to every observation that agrees on a set of components, weighted by its record."""

    def __init__(self, components: int, *, largest: int, always: Sequence[int] = (), keep: float = 0.0,
                 negligible: float = 1e-9) -> None:
        """``components`` per observation, sets of at most ``largest`` of them, ``always`` read as the context."""
        if type(components) is not int or type(largest) is not int or components < 0 or largest < 0:
            raise ValueError("counts of components are non-negative integers")
        if any(index not in range(components) for index in always) or len(set(always)) != len(always):
            raise ValueError("the context components are distinct components")
        if not 0 <= keep < 1 or not 0 < negligible < 1:
            raise ValueError("a contradicted set keeps a share below one, and a negligible share is below one")
        self.components, self.largest, self.always = components, largest, tuple(always)
        self.keep, self.negligible = keep, negligible
        free = [index for index in range(components) if index not in self.always]
        self.family = tuple(subset for size in range(min(largest, len(free)) + 1)
                            for subset in combinations(free, size))
        self.readers = {subset: _reader(subset) for subset in self.family}
        self.history: list[Judgement] = []
        self._contexts: dict[tuple[Hashable, ...], _Context] = {}

    @property
    def judgements(self) -> int:
        return len(self.history)

    def _context(self, observation: Observation) -> _Context:
        if len(observation) != self.components:
            raise ValueError(f"an observation has {self.components} components")
        key = tuple(observation[index] for index in self.always)
        context = self._contexts.get(key)
        if context is None:
            context = self._contexts[key] = _Context(self.family)
        return context

    def judge(self, observation: Observation, action: Hashable, good: bool) -> None:
        """Record that ``action`` at ``observation`` is good or bad, counting it against every set it contradicts."""
        context = self._context(observation)
        self.history.append((tuple(observation), action, good))
        context.votes.clear()
        readers = self.readers
        for subset, table in context.tables.items():
            counts = table.setdefault((readers[subset](observation), action), [0, 0])
            if counts[0] != counts[1] and (counts[0] > counts[1]) != good:
                context.contradicted[subset] += 1
                context.weight[subset] = self.keep ** context.contradicted[subset]
            counts[not good] += 1
        least = min(context.contradicted.values(), default=0)
        for subset, misses in list(context.contradicted.items()):
            if misses and (self.keep == 0 or self.keep ** (misses - least) < self.negligible):
                del context.tables[subset], context.contradicted[subset], context.weight[subset]

    def votes(self, observation: Observation, action: Hashable) -> tuple[float, float]:
        """The weight of the sets that judge ``action`` at ``observation`` good, and of those that judge it bad."""
        context = self._context(observation)
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

    def surviving(self, observation: Observation) -> int:
        """The sets of the observation's context still voting."""
        return len(self._context(observation).tables)

    def choose(self, pairs: Sequence[tuple[Observation, Hashable]], guesses: Random) -> int:
        """The index of a pair with a good majority, the widest first; else a guess, avoiding bad majorities."""
        if not pairs:
            raise ValueError("there is nothing to choose from")
        tallies = [self.votes(observation, action) for observation, action in pairs]
        margin, best = max((good - bad, -index) for index, (good, bad) in enumerate(tallies))
        if margin > 0:
            return -best
        open_pairs = [index for index, (good, bad) in enumerate(tallies) if bad <= good]
        return guesses.choice(open_pairs or range(len(pairs)))
