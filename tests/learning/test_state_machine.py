from itertools import product
from random import Random

import pytest

from nca.abi import Contract
from nca.learning.state_machine import (DifferenceLearner, MachineExpert, MachineLearner, SummingExpert, Word,
                                        composed, learn_machine)

SEQUENCE, ANSWER = "seq[sha256:" + "0" * 64 + "]", "sha256:" + "1" * 64
CONTRACT = Contract((SEQUENCE,), ANSWER)


def parity(word: Word) -> int:
    return sum(word) % 2  # type: ignore[arg-type]


def two_or_more(word: Word) -> int:
    return int(sum(word) >= 2)  # type: ignore[arg-type]


def words(count: int, seed: int = 0) -> list[Word]:
    rng = Random(seed)
    return [tuple(rng.randint(0, 1) for _ in range(rng.randint(1, 8))) for _ in range(count)]


@pytest.mark.parametrize(("target", "states"), [(parity, 2), (two_or_more, 3)])
def test_finite_targets_are_learned_with_minimal_states(target: object, states: int) -> None:
    """``NCA.distinguished_prefixes_need_states``: the table never exceeds the smallest machine."""
    sample = [(word, target(word)) for word in words(16)]  # type: ignore[operator]
    answers: dict[Word, object] = {}
    machine = learn_machine(target, (0, 1), sample, rng=Random(1), max_length=8, max_queries=500,  # type: ignore[arg-type]
                            max_states=20, answers=answers)
    assert machine is not None and len(machine.outputs) == states
    assert all(machine.run(word) == target(word) for word in words(200, seed=5))  # type: ignore[operator]
    assert 0 < len(answers) <= 500


def test_unbounded_counting_is_refused_early() -> None:
    """``NCA.distinct_answers_need_states``: a count has no finite machine, and few labels show it."""
    sample = [(word, sum(word)) for word in words(16)]  # type: ignore[arg-type]
    answers: dict[Word, object] = {}
    machine = learn_machine(lambda word: sum(word), (0, 1), sample, rng=Random(1), max_length=8,  # type: ignore[arg-type]
                            max_queries=5000, max_states=100, answers=answers)
    assert machine is None
    assert len(answers) < 100


def test_query_limit_returns_nothing() -> None:
    sample = [(word, parity(word)) for word in words(16)]
    assert learn_machine(parity, (0, 1), sample, rng=Random(1), max_length=8, max_queries=3, max_states=20) is None


def test_learner_proposes_an_expert_that_refuses_what_it_cannot_answer() -> None:
    undefined = ("undefined",)

    def query(word: Word) -> object:
        return parity(word) if word else undefined

    keys = words(16)
    learner = MachineLearner(query, max_queries=500, max_states=20, undefined=undefined)
    expert = learner(CONTRACT, keys, [parity(word) for word in keys])
    assert isinstance(expert, MachineExpert) and expert.manifest.contract == CONTRACT
    assert expert.invoke((1, 0, 1, 1)) == 1
    with pytest.raises(ValueError, match="no answer"):
        expert.invoke(())
    with pytest.raises(ValueError, match="never saw"):
        expert.invoke((1, 7))
    used = len(learner.answers)
    assert learner(CONTRACT, keys, [parity(word) for word in keys]) is not None and len(learner.answers) == used
    assert learner(Contract((SEQUENCE, SEQUENCE), ANSWER), keys, [0] * len(keys)) is None


def count_twos(word: Word) -> int:
    return sum(symbol == 2 for symbol in word)


def ternary(count: int, seed: int = 0) -> list[Word]:
    rng = Random(seed)
    return [tuple(rng.randint(0, 2) for _ in range(rng.randint(1, 8))) for _ in range(count)]


def test_a_count_is_learned_from_its_differences_and_holds_on_longer_sequences() -> None:
    """``NCA.differences_rebuild`` and ``NCA.counter_differences_follow_control``."""
    keys = ternary(16)
    labels = [count_twos(word) for word in keys]
    answers: dict[Word, object] = {}
    finite = MachineLearner(count_twos, max_queries=2000, max_states=50, answers=answers)
    assert finite(CONTRACT, keys, labels) is None
    learner = DifferenceLearner(count_twos, max_queries=2000, max_states=50, answers=answers,
                                add=lambda left, right: left + right, subtract=lambda left, right: left - right)
    expert = learner(CONTRACT, keys, labels)
    assert isinstance(expert, SummingExpert) and len(expert.machine.outputs) == 2
    assert all(expert.invoke(word) == count_twos(word) for word in ternary(100, seed=3))
    assert expert.invoke((2,) * 40) == 40
    assert len(answers) == finite.paid + learner.paid and 0 < learner.paid < 400
    with pytest.raises(ValueError, match="never saw"):
        expert.invoke((2, 9))


def test_answers_without_a_difference_are_declined_before_any_query() -> None:
    def subtract(left: object, right: object) -> object:
        raise TypeError

    keys = ternary(8)
    learner = DifferenceLearner(lambda word: word, max_queries=100, max_states=10, add=lambda left, right: left,
                                subtract=subtract)
    assert learner(CONTRACT, keys, list(keys)) is None and learner.paid == 0


def test_a_count_with_no_answer_on_the_empty_sequence_is_declined_after_one_query() -> None:
    undefined = ("undefined",)

    def query(word: Word) -> object:
        return count_twos(word) if word else undefined

    keys = ternary(8)
    learner = DifferenceLearner(query, max_queries=100, max_states=10, undefined=undefined,
                                add=lambda left, right: left + right, subtract=lambda left, right: left - right)
    assert learner(CONTRACT, keys, [count_twos(word) for word in keys]) is None and learner.paid == 1


def _parity(word: tuple[str, ...]) -> str:
    return "odd" if sum(symbol == "turn" for symbol in word) % 2 else "even"


def test_answers_composed_along_short_sequences_hold_on_long_ones() -> None:
    short = [word for length in (1, 2) for word in product(("keep", "turn"), repeat=length)]
    machine = composed([(word, _parity(word)) for word in short])
    assert machine is not None
    assert all(machine.run(word) == _parity(word) for word in product(("keep", "turn"), repeat=9))


def _ordered(word: tuple[str, ...]) -> str:
    return word[0] if len(set(word)) == 1 else "open"


def test_an_answer_that_absorbs_is_composed_and_an_unmet_move_is_not_guessed() -> None:
    paid = [(("up",), "up"), (("down",), "down"), (("up", "up"), "up"), (("up", "down"), "open"),
            (("down", "down"), "down"), (("up", "down", "up"), "open")]
    machine = composed(paid)
    assert machine is not None
    assert machine.run(("up", "up", "up", "down", "up")) == "open"
    with pytest.raises(KeyError):
        machine.run(("down", "up"))
    full = composed([*paid, (("down", "up"), "open"), (("up", "down", "down"), "open")])
    assert full is not None
    assert all(full.run(word) == _ordered(word) for length in range(1, 7) for word in product(("up", "down"), repeat=length))


def test_a_refused_answer_is_not_composed() -> None:
    paid = [(("a",), "x"), (("b",), "y"), (("a", "b", "a"), "x")]
    free = composed(paid)
    assert free is not None and free.run(("a", "b")) == "x"
    held = composed(paid, refused=[(("a", "b"), "x")])
    assert held is not None and held.run(("a", "b")) == "y" and held.run(("a", "b", "a")) == "x"


def test_no_machine_is_composed_where_a_longer_sequence_takes_answers_apart() -> None:
    def side(word: tuple[int, ...]) -> int:
        return (sum(word) > 0) - (sum(word) < 0)

    paid = [(word, side(word)) for length in (1, 2, 3) for word in product((1, -1), repeat=length)]
    assert composed(paid) is None
    assert composed([(("turn",), "odd"), (("keep",), "even"), (("turn", "turn"), "even")], budget=1) is None
