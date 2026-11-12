"""Learn a machine from a teacher whose takeovers are sometimes later than assumed (THEORY §52.9).

A takeover marks the learner's last action as bad. When the teacher reacted a
step later than assumed, that mark is wrong, and a single wrong mark kept for
good splits a state that should stay whole. So no mark is kept for good. After
every takeover each mark is judged again where the current machine puts it: on
its transition, the state before with the observation read. A mark is believed
while that transition holds enough marks against the action and they outweigh
the times the action stood there (``NCA.believed_mark_outweighs``), or while the
same mark was made repeatedly after exactly the same history. Believed marks
separate histories as in §52.7; the others are ignored until they are repeated.

The learner is fed episodes as they happen, so the teacher may be a person.
The machine is a proposal. Admission needs fresh episodes of its own.
"""

from collections import Counter
from collections.abc import Hashable, Iterator, Sequence
from typing import Any

from nca.learning.state_machine import Machine, Word
from nca.learning.takeover import UNLABELLED, Judged, _Evidence, _merge

Marks = dict[Word, frozenset[Any]]


class Apprentice:
    """A machine taught by takeovers, with every mark of a bad action judged again after each one."""

    def __init__(self, *, unjudged: int = 2, needed: int = 2, share: float = 0.25, rounds: int = 4) -> None:
        """``unjudged`` is how many of the learner's actions, up to the one marked, are not recorded as good.

        A mark is believed once its transition holds ``needed`` marks against
        the action, making up more than ``share`` of the judgements of it
        there. ``rounds`` bounds the judging and merging after one takeover.
        """
        if any(type(count) is not int or count < 1 for count in (unjudged, needed, rounds)) or not 0 <= share < 1:
            raise ValueError("positive counts and a share below one are required")
        self.unjudged, self.needed, self.share, self.rounds = unjudged, needed, share, rounds
        self.machine = Machine({}, (UNLABELLED,))
        self.takeovers = 0
        self._episodes: list[Word] = []
        self._good: dict[Word, Counter[Any]] = {}
        self._marks: dict[Word, Counter[Any]] = {}
        self._believed: Marks = {}

    def action(self, seen: Word) -> Any:
        """The machine's action after the observations so far, or ``UNLABELLED`` where it has none."""
        state: int | None = 0
        for symbol in seen:
            state = self.machine.transitions.get((state, symbol))
            if state is None:
                return UNLABELLED
        return self.machine.outputs[state]

    def taken_over(self, seen: Word, played: Sequence[Any], shown: Sequence[Any], *, asked: bool = False,
                   late: int = 0) -> None:
        """Learn from an episode the teacher took over.

        The learner's actions ``played`` answered the first observations of
        ``seen`` and the teacher's actions ``shown`` the rest. With ``asked``
        the learner had no action and requested the takeover, so nothing is
        marked bad. Otherwise the action marked is the one ``late`` actions
        before the learner's last: the teacher's reaction time, in steps.
        """
        if len(played) + len(shown) != len(seen) or type(late) is not int or late < 0:
            raise ValueError("every observation is answered once, and the teacher's lateness is a count")
        self.takeovers += 1
        self._episodes.append(seen)
        blamed = len(played) - 1 - late
        for step in range(blamed + 1 - self.unjudged):
            self._good.setdefault(seen[:step + 1], Counter())[played[step]] += 1
        for offset, action in enumerate(shown):
            self._good.setdefault(seen[:len(played) + offset + 1], Counter())[action] += 1
        if blamed >= 0 and not asked:
            self._marks.setdefault(seen[:blamed + 1], Counter())[played[blamed]] += 1
        for history, marks in self._marks.items():
            for action in set(marks) & set(self._good.get(history, ())):
                del marks[action]
        for attempt in range(self.rounds):
            believed = self._judge()
            if attempt and believed == self._believed:
                break
            self._believed = believed
            self.machine = _merge(self._judged())

    def _judge(self) -> Marks:
        """The marks believed on the current machine."""
        good: Counter[tuple[int, Hashable, Any]] = Counter()
        bad: Counter[tuple[int, Hashable, Any]] = Counter()
        placed: list[tuple[Word, Any, tuple[int, Hashable, Any]]] = []
        visited: set[Word] = set()
        for seen in self._episodes:
            state: int | None = 0
            for step, symbol in enumerate(seen):
                history, before = seen[:step + 1], state
                state = self.machine.transitions.get((before, symbol))
                if history not in visited:
                    visited.add(history)
                    for action, count in self._good.get(history, {}).items():
                        good[before, symbol, action] += count
                    for action, count in self._marks.get(history, {}).items():
                        bad[before, symbol, action] += count
                        placed.append((history, action, (before, symbol, action)))
                if state is None:
                    break
        believed: dict[Word, set[Any]] = {}
        for history, action, key in placed:
            if self._marks[history][action] >= self.needed or (
                    bad[key] >= self.needed and bad[key] > self.share * (bad[key] + good[key])):
                believed.setdefault(history, set()).add(action)
        return {history: frozenset(actions) for history, actions in believed.items()}

    def _judged(self) -> Iterator[Judged]:
        """The episodes with what is known after each history, each history given once."""
        visited: set[Word] = set()
        for seen in self._episodes:
            steps: list[_Evidence | None] = []
            for step in range(len(seen)):
                history = seen[:step + 1]
                known, marked = self._good.get(history), self._believed.get(history, frozenset())
                fresh = history not in visited and (known is not None or bool(marked))
                visited.add(history)
                steps.append(_Evidence(good=Counter(known or ()), bad=marked) if fresh else None)
            yield seen, tuple(steps)
