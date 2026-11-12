"""Teach a machine by takeover (THEORY §52).

A learner acts through episodes while a teacher watches. At the first action
the teacher would not have chosen, the teacher takes over: it gives the right
action there and for the rest of the episode. Those are the demonstrated
actions, and they are the teacher's effort.

With a teacher who also answers histories the learner names, each takeover
yields a suffix separating two histories the conjecture merged
(``NCA.takeover_exposes_merged_histories``), which adds a state
(``NCA.takeover_adds_a_state``); the takeovers are then bounded by the states
of the machine taught (``NCA.separated_histories_bound``). Without such answers
the learner merges states on the episodes that were taken over, and only the
counting bound of §52.3 applies.

Given helpers, such as skills taught earlier, a state's action may be a
helper's answer on the history so far (§52.5). A demonstrated action is then
explained by every choice that produces it, and the machine taught can be as
small as the rule that chooses between the helpers.

A teacher may also take over late (§52.6). A wrong action then takes effect and
the episode leaves the teacher's path. The learner cannot tell which of its
latest actions was the wrong one, so it leaves them unjudged and learns from
what the teacher shows from the takeover on.

A teacher may choose freely among several good actions (§52.7). Its choices
then vary and its judgements do not, so the learner keeps the actions known
good and known bad after each history, and two histories may share a state
unless an action is known good at one and known bad at the other
(``NCA.conflicting_judgements_separate``).

The taught machine is a proposal. Admission needs fresh episodes of its own.
"""

from collections import Counter
from collections.abc import Callable, Hashable, Iterable, Sequence
from dataclasses import dataclass, field
from typing import Any, Protocol

from nca.learning.state_machine import UNBOUNDED, Delegate, Helper, Machine, Word

UNLABELLED = ("unlabelled",)
"""The answer of a state for which no action was ever seen."""


class Session(Protocol):
    """One episode: observations arrive in turn and each is answered by an action."""

    def observation(self) -> Hashable | None:
        """The next observation, or ``None`` once the episode is over."""

    def act(self, action: Any) -> None:
        """Apply the action chosen for the latest observation."""


Start = Callable[[], Session]
"""Begins an episode from a fresh starting condition."""
Teacher = Callable[[Word], Any]
"""The right action after a history of observations."""
Episode = tuple[Word, tuple[Any, ...]]
"""The observations of one episode and the right action after each."""


@dataclass(frozen=True)
class Taught:
    """A taught machine and what teaching it cost."""

    machine: Machine
    passed: bool
    """Whether teaching ended on the required run of clean episodes."""
    takeovers: int
    """Episodes the teacher took over, or marked at their end as having gone wrong."""
    demonstrated: int
    """Actions the teacher supplied from each takeover to the end of its episode."""
    questions: int
    """Answers asked for on histories that had not occurred."""
    episodes: int
    mistakes: int = 0
    """Wrong actions of the learner that took effect, which only a late teacher allows."""


def merge_states(episodes: Iterable[Episode]) -> Machine:
    """The machine left by greedily merging the states of the histories given.

    Histories are taken shortest first, and each joins the earliest state whose
    actions never contradict its own on anything seen. A state with no action
    seen answers ``UNLABELLED``; a history leaving what was seen has no transition.
    """
    return _merge((seen, tuple(_Evidence(frozenset((action,))) for action in actions)) for seen, actions in episodes)


Choices = frozenset[Any]
"""The answers that explain one action: the action itself and each helper that gave it."""


@dataclass(frozen=True)
class _Evidence:
    """What is established about the action after one history, or after all the histories of one state.

    ``only`` holds the choices that can still be right when the teacher shows
    the one right action; ``None`` puts no such limit. ``good`` counts the
    choices seen to be good and ``bad`` holds those seen to be bad, for a
    teacher who judges.
    """

    only: Choices | None = None
    good: Counter[Any] = field(default_factory=Counter)
    bad: Choices = frozenset()

    def joined(self, other: "_Evidence") -> "_Evidence | None":
        """The evidence of both, or ``None`` where they cannot belong to one state."""
        only = self.only if other.only is None else other.only if self.only is None else self.only & other.only
        if only is not None and not only:
            return None
        if any(choice in other.bad for choice in self.good) or any(choice in self.bad for choice in other.good):
            return None
        return _Evidence(only, self.good + other.good, self.bad | other.bad)

    def chosen(self) -> Any:
        """One answer: a fixed action before a helper, and among those seen good the one seen most."""
        if self.only is not None:
            fixed = [choice for choice in self.only if not isinstance(choice, Delegate)]
            return fixed[0] if fixed else min(self.only, key=lambda choice: choice.helper)
        if not self.good:
            return UNLABELLED
        return max(self.good, key=lambda choice: (self.good[choice], not isinstance(choice, Delegate),
                                                  -choice.helper if isinstance(choice, Delegate) else 0))


Judged = tuple[Word, tuple[_Evidence | None, ...]]
"""An episode's observations with the evidence about the action after each; ``None`` where it is unjudged."""


def _merge(episodes: Iterable[Judged]) -> Machine:
    """As ``merge_states``, on evidence that may name several choices: histories share a state while it agrees."""
    children: list[dict[Hashable, int]] = [{}]
    label: list[_Evidence | None] = [None]
    rank: list[tuple[int, ...]] = [()]
    for seen, steps in episodes:
        node = 0
        for symbol, evidence in zip(seen, steps, strict=True):
            following = children[node].get(symbol)
            if following is None:
                following = len(children)
                children[node][symbol] = following
                children.append({})
                label.append(None)
                rank.append((*rank[node], len(children[node])))
            node = following
            known = label[node]
            if evidence is not None:
                label[node] = evidence if known is None else known.joined(evidence) or _Evidence(frozenset())

    def fold(kept: int, merged: int, undo: list[tuple[int, Hashable | None, _Evidence | None]]) -> bool:
        mine, theirs = label[kept], label[merged]
        if theirs is not None:
            both = theirs if mine is None else mine.joined(theirs)
            if both is None or both.only == frozenset():
                return False
            undo.append((kept, None, mine))
            label[kept] = both
        for symbol, child in children[merged].items():
            existing = children[kept].get(symbol)
            if existing is None:
                children[kept][symbol] = child
                undo.append((kept, symbol, None))
            elif not fold(existing, child, undo):
                return False
        return True

    states, is_state = [0], {0}
    while True:
        pending = [(len(rank[child]), rank[child], parent, symbol, child) for parent in states
                   for symbol, child in children[parent].items() if child not in is_state]
        if not pending:
            break
        _, _, parent, symbol, candidate = min(pending, key=lambda item: item[:2])
        for state in states:
            undo: list[tuple[int, Hashable | None, _Evidence | None]] = []
            children[parent][symbol] = state
            if fold(state, candidate, undo):
                break
            children[parent][symbol] = candidate
            for node, added, before in reversed(undo):
                if added is None:
                    label[node] = before
                else:
                    del children[node][added]
        else:
            states.append(candidate)
            is_state.add(candidate)
    index = {state: position for position, state in enumerate(states)}

    def answer(state: int) -> Any:
        evidence = label[state]
        return UNLABELLED if evidence is None or evidence.only == frozenset() else evidence.chosen()

    return Machine({(index[state], symbol): index[child] for state in states
                    for symbol, child in children[state].items()}, tuple(answer(state) for state in states))


class _Stopped(Exception):
    """The table reached its state limit or its answers contradict each other."""


class _Table:
    """An observation table filled by a teacher who answers any history."""

    def __init__(self, ask: Teacher, max_states: int) -> None:
        self.ask_teacher, self.max_states = ask, max_states
        self.known: dict[Word, Any] = {(): UNLABELLED}
        self.questions = 0
        self.alphabet: list[Hashable] = []
        self.access: list[Word] = [()]
        self.suffixes: list[Word] = [()]

    def record(self, episode: Episode) -> None:
        seen, actions = episode
        for step, action in enumerate(actions):
            self.known.setdefault(seen[:step + 1], action)
        self.alphabet.extend(symbol for symbol in dict.fromkeys(seen) if symbol not in self.alphabet)

    def ask(self, word: Word) -> Any:
        if word not in self.known:
            self.known[word] = self.ask_teacher(word)
            self.questions += 1
        return self.known[word]

    def row(self, word: Word) -> tuple[Any, ...]:
        return tuple(self.ask(word + suffix) for suffix in self.suffixes)

    def conjecture(self) -> Machine:
        index = {self.row(word): position for position, word in enumerate(self.access)}
        pending = list(self.access)
        while pending:
            word = pending.pop()
            for symbol in self.alphabet:
                extended = (*word, symbol)
                if self.row(extended) not in index:
                    if len(self.access) >= self.max_states:
                        raise _Stopped
                    index[self.row(extended)] = len(self.access)
                    self.access.append(extended)
                    pending.append(extended)
        return Machine({(position, symbol): index[self.row((*word, symbol))]
                        for position, word in enumerate(self.access) for symbol in self.alphabet},
                       tuple(self.ask(word) for word in self.access))

    def repair(self, machine: Machine, word: Word) -> None:
        """Add the suffix of Theorem 52.1, found by bisection over the cuts of a history answered wrongly."""
        states = [0]
        for symbol in word:
            states.append(machine.transitions[states[-1], symbol])
        low, high = 0, len(word)
        first = self.ask(self.access[states[0]] + word)
        while high - low > 1:
            middle = (low + high) // 2
            if self.ask(self.access[states[middle]] + word[middle:]) != first:
                high = middle
            else:
                low = middle
        if word[low + 1:] in self.suffixes:
            raise _Stopped
        self.suffixes.append(word[low + 1:])


_REFUSED = object()


def _helped(helper: Helper, history: Word) -> Any:
    try:
        return helper(history)
    except ValueError:
        return _REFUSED


@dataclass(frozen=True)
class _Watched:
    """One episode as the teacher saw it."""

    seen: Word
    right: tuple[Any, ...]
    """The teacher's action at each step where it gave one; with a judging teacher, only from the takeover on."""
    judged: tuple[_Evidence | None, ...]
    taken: int | None
    """The step from which the teacher acted, if it took over."""
    clean: bool
    mistakes: int


def _watch(start: Start, teacher: Teacher, machine: Machine, helpers: Sequence[Helper],
           delay: Callable[[], int] | None, unjudged: int, accepts: Callable[[Word, Any], bool] | None) -> _Watched:
    """Let the machine act until the teacher takes over, and record what the teacher's actions establish.

    With no delay the teacher corrects the first wrong action before it takes
    effect. With one, wrong actions take effect and the teacher acts from
    ``delay()`` steps after the first. A refusal is a request and is answered
    at once. With ``accepts`` an action is wrong when the teacher does not let
    it stand, and the teacher is asked for an action only once it has taken over.
    """
    session, seen, right, evidence = start(), [], [], []
    state: int | None = 0
    taken = wrong = None
    due = mistakes = 0
    while (symbol := session.observation()) is not None:
        seen.append(symbol)
        history = tuple(seen)
        helped = [_helped(helper, history) for helper in helpers]

        def explains(action: Any, helped: list[Any] = helped) -> Choices:
            return frozenset((action, *(Delegate(position) for position, answer in enumerate(helped)
                                        if answer is not _REFUSED and answer == action)))

        correct = teacher(history) if accepts is None else None
        rejected = None
        if taken is None and wrong is not None and len(seen) - 1 - wrong >= due:
            taken = len(seen) - 1
        if taken is None:
            state = None if state is None else machine.transitions.get((state, symbol))
            mine = UNLABELLED if state is None else machine.outputs[state]
            if isinstance(mine, Delegate):
                mine = helped[mine.helper]
            asked = mine is _REFUSED or mine == UNLABELLED
            stands = not asked and (mine == correct if accepts is None else accepts(history, mine))
            if asked or (not stands and delay is None):
                taken = len(seen) - 1
                rejected = None if asked or accepts is None else mine
            else:
                if not stands:
                    mistakes += 1
                    if wrong is None:
                        wrong, due = len(seen) - 1, delay()  # type: ignore[misc]
                evidence.append(_Evidence(explains(correct)) if accepts is None
                                else _Evidence(good=Counter(explains(mine))))
                right.append(correct)
                session.act(mine)
                continue
        if accepts is None:
            evidence.append(_Evidence(explains(correct)))
        else:
            correct = teacher(history)
            evidence.append(_Evidence(good=Counter(explains(correct)),
                                      bad=frozenset() if rejected is None else explains(rejected)))
        right.append(correct)
        session.act(correct)
    settled = (len(seen) if taken is None else taken) - (unjudged if delay is not None else 0)
    judged = tuple(found if taken is not None and step >= taken or step < settled else None
                   for step, found in enumerate(evidence))
    return _Watched(tuple(seen), tuple(right), judged, taken, taken is None and wrong is None, mistakes)


def teach(start: Start, teacher: Teacher, *, clean: int, max_episodes: int, ask: Teacher | None = None,
          max_states: int = UNBOUNDED, helpers: Sequence[Helper] = (), delay: Callable[[], int] | None = None,
          unjudged: int = 0, max_takeovers: int = UNBOUNDED,
          accepts: Callable[[Word, Any], bool] | None = None) -> Taught:
    """Teach by takeover until ``clean`` episodes in a row need none, or a limit is reached.

    The teacher corrects the first wrong or refused action before it takes
    effect, so every episode follows the teacher's path. With ``ask``, a teacher
    who answers any history, the learner keeps an observation table; without it,
    the learner merges states on the episodes that were taken over. ``helpers``
    apply to merging only: an action of the taught machine may then be a
    ``Delegate`` to one of them.

    ``delay`` makes the teacher late: it gives, for each first wrong action, the
    steps that pass before the teacher takes over, during which the learner's
    actions take effect. The learner's last ``unjudged`` actions before a
    takeover, or before the end of an episode that went wrong, are then
    recorded as neither right nor wrong. ``unjudged`` must be at least the
    longest delay, or a wrong action is recorded as right
    (``NCA.judged_actions_are_right``).

    ``accepts`` says whether the teacher lets an action stand after a history,
    for a teacher who may take any of several good actions. The learner then
    merges on the actions known good and known bad. It needs an immediate
    teacher: a late takeover does not say which action was bad, and with no
    action known bad nothing keeps two histories apart.
    """
    if any(type(limit) is not int or limit < 1 for limit in (clean, max_episodes, max_states, max_takeovers)):
        raise ValueError("positive limits are required")
    if ask is not None and (helpers or delay is not None):
        raise ValueError("helpers and a late teacher apply to teaching by demonstration only")
    if type(unjudged) is not int or unjudged < 0 or (delay is None and unjudged):
        raise ValueError("unjudged actions are a count that applies to a late teacher")
    if accepts is not None and (ask is not None or delay is not None):
        raise ValueError("a judging teacher applies to immediate teaching by demonstration only")
    table = _Table(ask, max_states) if ask is not None else None
    kept: list[Judged] = []
    machine = Machine({}, (UNLABELLED,))
    takeovers = demonstrated = episodes = run = mistakes = 0
    try:
        while run < clean and episodes < max_episodes and takeovers < max_takeovers:
            watched = _watch(start, teacher, machine, helpers, delay, unjudged, accepts)
            episodes += 1
            mistakes += watched.mistakes
            if table is not None:
                fresh = any(symbol not in table.alphabet for symbol in watched.seen)
                table.record((watched.seen, watched.right))
            if watched.clean:
                run += 1
                continue
            run, takeovers = 0, takeovers + 1
            if watched.taken is not None:
                demonstrated += len(watched.seen) - watched.taken
            if table is None:
                kept.append((watched.seen, watched.judged))
                machine = _merge(kept)
                if len(machine.outputs) > max_states:
                    break
            else:
                if not fresh and watched.taken is not None:
                    table.repair(machine, watched.seen[:watched.taken + 1])
                machine = table.conjecture()
    except _Stopped:
        pass
    return Taught(machine, run >= clean, takeovers, demonstrated, 0 if table is None else table.questions, episodes,
                  mistakes)
