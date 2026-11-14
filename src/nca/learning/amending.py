"""Teach by takeover a machine whose parts are shown more where they are used (THEORY §52.13).

A part taught and admitted on its own episodes may err on the episodes of
the machine that uses it: its certificate is for the histories it was drawn
on (``NCA.certificate_does_not_travel``). Where the machine delegated to a
part and the teacher took over, either the choice of the part was wrong or
the part was. The demonstrated action cannot say which.

An ``Amendable`` keeps the episodes it was shown beside the machine merged
from them, so that it can be shown one more. At a takeover the learner
weighs both readings: the episode shown to the machine alone, and the
action also shown to the part the machine delegated to, as the part's own
right action after that history. It keeps the reading that leaves the
fewest states in the machine and all its parts together, and the first on
a tie. A part amended this way is the user's copy; the part as installed
is untouched, and the whole still needs admission on fresh episodes.

Where the parts err only where the teacher's rule delegates to them, the
second reading is consistent with a machine no larger than the rule
(``NCA.amended_parts_keep_the_rule``); the first forces the machine to tell
apart the histories at which a part errs (``NCA.erring_part_is_not_the_choice``).
"""

from collections.abc import Sequence
from dataclasses import dataclass, field, replace
from typing import Any

from nca.learning.state_machine import UNBOUNDED, Delegate, Helper, Machine, Word
from nca.learning.takeover import UNLABELLED, Judged, Start, Taught, Teacher, _Evidence, _merge, _watch

UNJUDGED = ("unjudged",)
"""Stands for the right action at a step about which nothing was shown."""
Shown = tuple[Word, tuple[Any, ...]]
"""The observations of one episode and the right action after each, or ``UNJUDGED``."""


@dataclass(frozen=True, eq=False)
class Amendable:
    """A machine merged from the episodes it was shown, answering histories as a helper does."""

    shown: tuple[Shown, ...] = ()
    helpers: tuple[Helper, ...] = ()
    machine: Machine = field(init=False)
    _answers: dict[Word, Any] = field(init=False, default_factory=dict)

    def __post_init__(self) -> None:
        object.__setattr__(self, "machine", _merge(map(self._judged, self.shown)))

    def _helped(self, history: Word) -> list[Any]:
        answers = []
        for helper in self.helpers:
            try:
                answers.append(helper(history))
            except ValueError:
                answers.append(UNJUDGED)
        return answers

    def _judged(self, episode: Shown) -> Judged:
        seen, right = episode
        evidence: list[_Evidence | None] = []
        for step, action in enumerate(right):
            if action == UNJUDGED:
                evidence.append(None)
                continue
            helped = self._helped(seen[:step + 1])
            evidence.append(_Evidence(frozenset((action, *(Delegate(position) for position, answer in enumerate(helped)
                                                           if answer == action)))))
        return seen, tuple(evidence)

    def choice(self, history: Word) -> Any:
        """What the state after a history holds: a fixed action, a ``Delegate``, or ``UNLABELLED``."""
        state: int | None = 0
        for symbol in history:
            state = self.machine.transitions.get((state, symbol))
            if state is None:
                return UNLABELLED
        return self.machine.outputs[state]

    def __call__(self, history: Word) -> Any:
        if history not in self._answers:
            answer = self.choice(history)
            if answer == UNLABELLED:
                raise ValueError("the machine has no answer for this history")
            self._answers[history] = self.helpers[answer.helper](history) if isinstance(answer, Delegate) else answer
        return self._answers[history]

    @property
    def states(self) -> int:
        """The states of the machine and of every amendable part beneath it."""
        return len(self.machine.outputs) + sum(helper.states for helper in self.helpers
                                               if isinstance(helper, Amendable))

    def amended(self, episode: Shown) -> "Amendable":
        """This machine shown one more episode, with its parts shown what leaves the whole smallest.

        At each judged step where the machine delegates to an amendable part
        that does not give the right action, the part is shown that action
        if the whole then has fewer states than when it is not.
        """
        seen, right = episode
        current = replace(self, shown=(*self.shown, episode))
        for step, action in enumerate(right):
            history = seen[:step + 1]
            choice = self.choice(history)
            if action == UNJUDGED or not isinstance(choice, Delegate):
                continue
            part = current.helpers[choice.helper]
            if not isinstance(part, Amendable) or current._helped(history)[choice.helper] == action:
                continue
            below = part.amended((history, (*(UNJUDGED,) * step, action)))
            passed = replace(current, helpers=(*current.helpers[:choice.helper], below,
                                               *current.helpers[choice.helper + 1:]))
            if passed.states < current.states:
                current = passed
        return current


def teach_amendable(start: Start, teacher: Teacher, *, clean: int, max_episodes: int,
                    helpers: Sequence[Helper] = (), max_takeovers: int = UNBOUNDED) -> tuple[Amendable, Taught]:
    """Teach by demonstration until ``clean`` episodes in a row need no takeover, or a limit is reached.

    As ``takeover.teach`` with an immediate teacher who shows the one right
    action, except that the episodes shown are kept and a helper that is an
    ``Amendable`` may be shown the teacher's action where the machine
    delegated to it. A helper that is any other callable is left as it is.
    """
    if any(type(limit) is not int or limit < 1 for limit in (clean, max_episodes, max_takeovers)):
        raise ValueError("positive limits are required")
    learner = Amendable(helpers=tuple(helpers))
    takeovers = demonstrated = episodes = run = 0
    while run < clean and episodes < max_episodes and takeovers < max_takeovers:
        watched = _watch(start, teacher, learner.machine, learner.helpers, None, 0, None)
        episodes += 1
        if watched.clean:
            run += 1
            continue
        run, takeovers = 0, takeovers + 1
        demonstrated += len(watched.seen) - (watched.taken or 0)
        learner = learner.amended((watched.seen, watched.right))
    return learner, Taught(learner.machine, run >= clean, takeovers, demonstrated, 0, episodes)
