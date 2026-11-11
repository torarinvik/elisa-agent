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

The taught machine is a proposal. Admission needs fresh episodes of its own.
"""

from collections.abc import Callable, Hashable, Iterable
from dataclasses import dataclass
from typing import Any, Protocol

from nca.learning.state_machine import UNBOUNDED, Machine, Word

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
    demonstrated: int
    """Actions the teacher supplied from each takeover to the end of its episode."""
    questions: int
    """Answers asked for on histories that had not occurred."""
    episodes: int


def merge_states(episodes: Iterable[Episode]) -> Machine:
    """The machine left by greedily merging the states of the histories given.

    Histories are taken shortest first, and each joins the earliest state whose
    actions never contradict its own on anything seen. A state with no action
    seen answers ``UNLABELLED``; a history leaving what was seen has no transition.
    """
    children: list[dict[Hashable, int]] = [{}]
    label: list[Any] = [UNLABELLED]
    rank: list[tuple[int, ...]] = [()]
    for seen, actions in episodes:
        node = 0
        for symbol, action in zip(seen, actions, strict=True):
            following = children[node].get(symbol)
            if following is None:
                following = len(children)
                children[node][symbol] = following
                children.append({})
                label.append(UNLABELLED)
                rank.append((*rank[node], len(children[node])))
            node = following
            label[node] = action

    def fold(kept: int, merged: int, undo: list[tuple[int, Hashable | None]]) -> bool:
        if label[merged] != UNLABELLED:
            if label[kept] == UNLABELLED:
                label[kept] = label[merged]
                undo.append((kept, None))
            elif label[kept] != label[merged]:
                return False
        for symbol, child in children[merged].items():
            mine = children[kept].get(symbol)
            if mine is None:
                children[kept][symbol] = child
                undo.append((kept, symbol))
            elif not fold(mine, child, undo):
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
            undo: list[tuple[int, Hashable | None]] = []
            children[parent][symbol] = state
            if fold(state, candidate, undo):
                break
            children[parent][symbol] = candidate
            for node, added in reversed(undo):
                if added is None:
                    label[node] = UNLABELLED
                else:
                    del children[node][added]
        else:
            states.append(candidate)
            is_state.add(candidate)
    index = {state: position for position, state in enumerate(states)}
    return Machine({(index[state], symbol): index[child] for state in states
                    for symbol, child in children[state].items()}, tuple(label[state] for state in states))


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


def _watch(start: Start, teacher: Teacher, machine: Machine) -> tuple[Episode, int | None]:
    """One episode on the teacher's path, and the step of the first action the machine got wrong or refused."""
    session, seen, actions = start(), [], []
    state: int | None = 0
    taken = None
    while (symbol := session.observation()) is not None:
        seen.append(symbol)
        right = teacher(tuple(seen))
        if taken is None:
            state = machine.transitions.get((state, symbol))
            if state is None or machine.outputs[state] != right:
                taken = len(actions)
        actions.append(right)
        session.act(right)
    return (tuple(seen), tuple(actions)), taken


def teach(start: Start, teacher: Teacher, *, clean: int, max_episodes: int, ask: Teacher | None = None,
          max_states: int = UNBOUNDED) -> Taught:
    """Teach by takeover until ``clean`` episodes in a row need none, or a limit is reached.

    The teacher corrects the first wrong or refused action before it takes
    effect, so every episode follows the teacher's path. With ``ask``, a teacher
    who answers any history, the learner keeps an observation table; without it,
    the learner merges states on the episodes that were taken over.
    """
    if any(type(limit) is not int or limit < 1 for limit in (clean, max_episodes, max_states)):
        raise ValueError("positive limits are required")
    table = _Table(ask, max_states) if ask is not None else None
    kept: list[Episode] = []
    machine = Machine({}, (UNLABELLED,))
    takeovers = demonstrated = episodes = run = 0
    try:
        while run < clean and episodes < max_episodes:
            episode, taken = _watch(start, teacher, machine)
            episodes += 1
            if table is not None:
                fresh = any(symbol not in table.alphabet for symbol in episode[0])
                table.record(episode)
            if taken is None:
                run += 1
                continue
            run, takeovers, demonstrated = 0, takeovers + 1, demonstrated + len(episode[0]) - taken
            if table is None:
                kept.append(episode)
                machine = merge_states(kept)
                if len(machine.outputs) > max_states:
                    break
            else:
                if not fresh:
                    table.repair(machine, episode[0][:taken + 1])
                machine = table.conjecture()
    except _Stopped:
        pass
    return Taught(machine, run >= clean, takeovers, demonstrated, 0 if table is None else table.questions, episodes)
