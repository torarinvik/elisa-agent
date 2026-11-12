"""Judgements that carry across observations agreeing on the components that matter (THEORY §53).

An observation is a sequence of components. A judgement says that an action at
an observation is good or bad. The learner keeps every set of at most
``largest`` components that no two judgements contradict: two judgements on
observations agreeing on the set, about one action, with opposite verdicts. A
set the teacher's target depends on is never contradicted by a correct teacher
(``NCA.sufficient_set_consistent``), and a contradicted set stays contradicted
(``NCA.consistent_of_subset_judgements``). Each surviving set votes on a pair of
an observation and an action with the verdict its class holds, or abstains.
Takeovers are then bounded by the classes of the set that matters and the
number of sets, not by the number of observations (§53.3–53.4).

Components named ``always`` split the problem instead: each of their values is
a context with its own family of sets. The components and their meanings are
the caller's; the learner only finds which of them matter.
"""

from collections.abc import Hashable, Sequence
from itertools import combinations
from random import Random
from typing import Any

Observation = Sequence[Hashable]


class Relevance:
    """Judged actions, carried to every observation that agrees on a surviving set of components."""

    def __init__(self, components: int, *, largest: int, always: Sequence[int] = ()) -> None:
        """``components`` per observation, sets of at most ``largest`` of them, ``always`` read as the context."""
        if type(components) is not int or type(largest) is not int or components < 0 or largest < 0:
            raise ValueError("counts of components are non-negative integers")
        if any(index not in range(components) for index in always) or len(set(always)) != len(always):
            raise ValueError("the context components are distinct components")
        self.components, self.largest, self.always = components, largest, tuple(always)
        free = [index for index in range(components) if index not in self.always]
        self.family = tuple(subset for size in range(min(largest, len(free)) + 1)
                            for subset in combinations(free, size))
        self.judgements = 0
        self._contexts: dict[tuple[Hashable, ...], dict[tuple[int, ...], dict[Any, bool]]] = {}

    def _sets(self, observation: Observation) -> dict[tuple[int, ...], dict[Any, bool]]:
        if len(observation) != self.components:
            raise ValueError(f"an observation has {self.components} components")
        context = tuple(observation[index] for index in self.always)
        return self._contexts.setdefault(context, {subset: {} for subset in self.family})

    def judge(self, observation: Observation, action: Hashable, good: bool) -> None:
        """Record that ``action`` at ``observation`` is good or bad, and drop every set it contradicts."""
        sets = self._sets(observation)
        self.judgements += 1
        for subset in list(sets):
            key = (tuple(observation[index] for index in subset), action)
            verdict = sets[subset].setdefault(key, good)
            if verdict != good:
                del sets[subset]

    def votes(self, observation: Observation, action: Hashable) -> tuple[int, int]:
        """How many surviving sets judge ``action`` at ``observation`` good, and how many bad."""
        good = bad = 0
        for subset, table in self._sets(observation).items():
            verdict = table.get((tuple(observation[index] for index in subset), action))
            good += verdict is True
            bad += verdict is False
        return good, bad

    def surviving(self, observation: Observation) -> int:
        """The sets of the observation's context that no judgement has contradicted."""
        return len(self._sets(observation))

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
