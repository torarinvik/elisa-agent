"""Learn a finite-state machine from answers to chosen sequences (THEORY §51).

A machine reads a sequence one symbol at a time, and the state it ends in fixes
the answer. The learner keeps an observation table: prefixes whose answers differ
after some suffix must lie in different states (``NCA.distinguished_prefixes_need_states``),
so it never builds more states than the smallest machine for the target. It
conjectures a machine, looks for a sequence the machine gets wrong among the
labelled cases and among random sequences, and adds the suffix that exposes the
error. Every distinct query is a label and is kept in ``answers`` for accounting.

A target with unboundedly many distinct answers has no finite machine
(``NCA.distinct_answers_need_states``); the learner then stops at its limits and
returns nothing. A counter is still within reach: where each symbol changes the
answer by an amount fixed by a finite control, that one-step difference is a
finite-state function (``NCA.counter_differences_follow_control``), so the same
learner learns the difference and the answer is rebuilt by adding differences
along the sequence (``NCA.differences_rebuild``).

A learned machine is a proposal: it has been compared with finitely many
sequences and must still pass independent fresh cases.
"""

from collections.abc import Callable, Hashable, Mapping, Sequence
from dataclasses import dataclass, field
from random import Random
from typing import Any

from nca.abi import Contract, Manifest, Module

Word = tuple[Hashable, ...]


@dataclass(frozen=True)
class Machine:
    """Transitions from state zero and the answer held by each state."""

    transitions: dict[tuple[int, Hashable], int]
    outputs: tuple[Any, ...]

    def state(self, word: Sequence[Hashable]) -> int:
        """The state after reading a sequence; an unknown symbol raises ``KeyError``."""
        current = 0
        for symbol in word:
            current = self.transitions[current, symbol]
        return current

    def run(self, word: Sequence[Hashable]) -> Any:
        return self.outputs[self.state(word)]


class _Exhausted(Exception):
    """A query or state limit was reached, or the answers contradict each other."""


def learn_machine(query: Callable[[Word], Any], alphabet: Sequence[Hashable], sample: Sequence[tuple[Word, Any]], *,
                  rng: Random, max_length: int, max_queries: int, max_states: int, checks: int = 100,
                  answers: dict[Word, Any] | None = None) -> Machine | None:
    """A machine agreeing with the sample and with ``checks`` random sequences, or ``None`` at a limit.

    The first closure also stops once it holds more states than the sample has
    distinct labels plus one: with no suffix yet, states are distinct answers,
    and more of them than the evidence shows marks a target outside the class.
    This saves labels and can only lose a task, never admit one.
    """
    if not alphabet or any(type(limit) is not int or limit < 1 for limit in (max_queries, max_states)):
        raise ValueError("an alphabet and positive limits are required")
    known = answers if answers is not None else {}

    def ask(word: Word) -> Any:
        if word not in known:
            if len(known) >= max_queries:
                raise _Exhausted
            known[word] = query(word)
        return known[word]

    suffixes: list[Word] = [()]
    prefixes: list[Word] = [()]
    first_limit = len({label for _, label in sample}) + 1

    def row(word: Word) -> tuple[Any, ...]:
        return tuple(ask(word + suffix) for suffix in suffixes)

    try:
        while True:
            limit = min(max_states, first_limit) if len(suffixes) == 1 else max_states
            index = {row(prefix): position for position, prefix in enumerate(prefixes)}
            pending = list(prefixes)
            while pending:
                prefix = pending.pop()
                for symbol in alphabet:
                    extended = (*prefix, symbol)
                    if row(extended) not in index:
                        if len(prefixes) >= limit:
                            raise _Exhausted
                        index[row(extended)] = len(prefixes)
                        prefixes.append(extended)
                        pending.append(extended)
            machine = Machine({(position, symbol): index[row((*prefix, symbol))]
                               for position, prefix in enumerate(prefixes) for symbol in alphabet},
                              tuple(ask(prefix) for prefix in prefixes))
            known_symbols = set(alphabet)
            wrong = next((word for word, label in sample
                          if known_symbols.issuperset(word) and machine.run(word) != label), None)
            if wrong is None:
                for _ in range(checks):
                    word = tuple(rng.choice(alphabet) for _ in range(rng.randint(0, max_length)))
                    if machine.run(word) != ask(word):
                        wrong = word
                        break
            if wrong is None:
                return machine
            previous = ask(wrong)
            for cut in range(1, len(wrong) + 1):
                answer = ask(prefixes[machine.state(wrong[:cut])] + wrong[cut:])
                if answer != previous:
                    if wrong[cut:] in suffixes:
                        raise _Exhausted
                    suffixes.append(wrong[cut:])
                    break
                previous = answer
            else:
                raise _Exhausted
    except _Exhausted:
        return None


UNBOUNDED = 1 << 62
NO_DIFFERENCE = ("no difference",)


class MachineExpert:
    """A learned machine over one sequence input; unknown symbols and marked answers are refused."""

    def __init__(self, contract: Contract, machine: Machine, undefined: Any = None) -> None:
        self.machine, self.undefined = machine, undefined
        self.manifest = Manifest("learned.machine", "1", contract, effects=frozenset())

    def invoke(self, values: Sequence[Hashable]) -> Any:
        try:
            answer = self.machine.run(values)
        except KeyError as error:
            raise ValueError("the sequence has a symbol the machine never saw") from error
        if self.undefined is not None and answer == self.undefined:
            raise ValueError("the machine has no answer for this sequence")
        return answer


class SummingExpert:
    """A machine of one-step differences; the answer adds them to the answer on the empty sequence."""

    def __init__(self, contract: Contract, machine: Machine, add: Callable[[Any, Any], Any], undefined: Any) -> None:
        self.machine, self.add, self.undefined = machine, add, undefined
        self.manifest = Manifest("learned.counter", "1", contract, effects=frozenset())

    def invoke(self, values: Sequence[Hashable]) -> Any:
        state, total = 0, self.machine.outputs[0]
        if total == self.undefined:
            raise ValueError("the machine has no answer for this sequence")
        for symbol in values:
            state = self.machine.transitions.get((state, symbol), -1)
            if state < 0:
                raise ValueError("the sequence has a symbol the machine never saw")
            step = self.machine.outputs[state]
            if step == self.undefined:
                raise ValueError("the machine has no answer for this sequence")
            total = self.add(total, step)
        return total


@dataclass
class _Asking:
    """Answers to chosen inputs, paid for once: ``answers`` may be shared between learners of one task."""

    query: Callable[[Word], Any]
    max_queries: int
    max_states: int
    undefined: Any = None
    seed: str = ""
    answers: dict[Word, Any] = field(default_factory=dict)
    paid: int = 0
    """Answers this learner asked for itself; ``max_queries`` bounds it over all calls."""

    def _ask(self, word: Word, labelled: Mapping[Word, Any]) -> Any:
        if word in labelled:
            return labelled[word]
        if word not in self.answers:
            if self.paid >= self.max_queries:
                raise _Exhausted
            self.answers[word] = self.query(word)
            self.paid += 1
        return self.answers[word]

    @staticmethod
    def _sample(contract: Contract, keys: Sequence[Hashable], labels: Sequence[Hashable]
                ) -> tuple[list[tuple[Word, Any]], list[Hashable]] | None:
        if len(contract.inputs) != 1 or not keys:
            return None
        sample = [(tuple(key), label) for key, label in zip(keys, labels, strict=True)]  # type: ignore[arg-type]
        symbols = {symbol for word, _ in sample for symbol in word}
        if not symbols:
            return None
        try:
            return sample, sorted(symbols)  # type: ignore[type-var]
        except TypeError:
            return sample, sorted(symbols, key=repr)


@dataclass
class MachineLearner(_Asking):
    """A portfolio learner for contracts with one sequence input, given answers to chosen inputs.

    ``query`` answers any sequence, with ``undefined`` where the task has no
    answer. Training labels are not asked again. The alphabet is the symbols of
    the supplied keys.
    """

    def __call__(self, contract: Contract, keys: Sequence[Hashable], labels: Sequence[Hashable]) -> Module | None:
        prepared = self._sample(contract, keys, labels)
        if prepared is None:
            return None
        sample, alphabet = prepared
        labelled = dict(sample)
        machine = learn_machine(lambda word: self._ask(word, labelled), alphabet, sample, rng=Random(self.seed),
                                max_length=max(len(word) for word, _ in sample), max_queries=UNBOUNDED,
                                max_states=self.max_states)
        return None if machine is None else MachineExpert(contract, machine, self.undefined)


@dataclass
class DifferenceLearner(_Asking):
    """As ``MachineLearner``, for answers that count: it learns how one more symbol changes the answer.

    ``subtract`` and ``add`` give the answers' group; a ``TypeError`` from
    ``subtract`` marks a pair with no difference, and labels that cannot be
    subtracted at all make the learner decline before any query. A rebuilt answer
    that misses a training case adds that case's prefixes as cases and learning
    repeats, until no new case is added or the queries run out.
    """

    add: Callable[[Any, Any], Any] | None = None
    subtract: Callable[[Any, Any], Any] | None = None

    def __call__(self, contract: Contract, keys: Sequence[Hashable], labels: Sequence[Hashable]) -> Module | None:
        prepared = self._sample(contract, keys, labels)
        if prepared is None or self.add is None or self.subtract is None:
            return None
        sample, alphabet = prepared
        labelled = dict(sample)
        mark = NO_DIFFERENCE if self.undefined is None else self.undefined
        try:
            self.subtract(sample[0][1], sample[0][1])
        except TypeError:
            return None

        def difference(word: Word) -> Any:
            if not word:
                return self._ask(word, labelled)
            try:
                return self.subtract(self._ask(word, labelled), self._ask(word[:-1], labelled))  # type: ignore[misc]
            except TypeError:
                return mark

        try:
            cases = {word: difference(word) for word, _ in sample}
            while True:
                machine = learn_machine(difference, alphabet, list(cases.items()), rng=Random(self.seed),
                                        max_length=max(len(word) for word, _ in sample), max_queries=UNBOUNDED,
                                        max_states=self.max_states)
                if machine is None:
                    return None
                expert = SummingExpert(contract, machine, self.add, mark)
                wrong = next((word for word, label in sample if self._answer(expert, word) != label), None)
                if wrong is None:
                    return expert
                prefixes = [wrong[:cut] for cut in range(len(wrong) + 1) if wrong[:cut] not in cases]
                if not prefixes:
                    return None
                cases.update({prefix: difference(prefix) for prefix in prefixes})
        except _Exhausted:
            return None

    @staticmethod
    def _answer(expert: SummingExpert, word: Word) -> Any:
        try:
            return expert.invoke(word)
        except ValueError:
            return NO_DIFFERENCE
