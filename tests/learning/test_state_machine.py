from random import Random

import pytest

from nca.abi import Contract
from nca.learning.state_machine import MachineExpert, MachineLearner, Word, learn_machine

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
