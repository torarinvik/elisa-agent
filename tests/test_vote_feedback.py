"""Failure transport and monotonic-repair links (§31.10)."""

from itertools import combinations
from typing import Any

import pytest

from nca.abi import Contract, Manifest, Message
from nca.evidence.redundancy import disjoint_routes
from nca.planner import Apply, Given, Plan
from nca.retention.ensembles import EnsembleSearch, VoteCase, VoteFailure
from test_redundancy import paths


class Lookup:
    manifest = Manifest("lookup", "1", Contract(("s",), "g"), effects=frozenset())

    def __init__(self, table: dict[int, int]) -> None:
        self.table = dict(table)

    def invoke(self, key: int) -> Any:
        return self.table.get(key, "unlearned")


def test_feedback_can_train_later_candidates_without_reusing_draws() -> None:
    table: dict[int, int] = {}
    cursor = 0
    feedback_ids: list[int] = []
    drawn_ids: list[int] = []

    def sample(count: int) -> list[VoteCase]:
        nonlocal cursor
        batch = []
        for _ in range(count):
            index = cursor
            cursor += 1
            drawn_ids.append(index)
            batch.append(((Message("s", index % 2, "input", message_id=str(index)),), index % 2))
        return batch

    def learn(failure: VoteFailure) -> None:
        inputs, label = failure.case
        assert not isinstance(inputs, dict)
        feedback_ids.append(int(inputs[0].message_id))
        assert failure.vote.answer != label and failure.drawn == 1
        table[inputs[0].payload] = label

    def acquire(old: tuple[Plan, ...]) -> Plan:
        return Apply(Lookup(table), (Given("s"),))

    search = EnsembleSearch(counts=(1,), tolerance=0.1, confidence=0.05, budget=2)
    result = None
    for _ in range(3):
        result = search(Contract(("s",), "g"), acquire, sample, feedback=learn)
        if result is not None:
            break
    assert result is not None and table == {0: 0, 1: 1}
    assert feedback_ids == [0, 1]
    assert len(set(drawn_ids)) == len(drawn_ids)
    assert search.labels == result.cases + 2


def test_feedback_is_after_scoring_and_before_the_next_acquisition() -> None:
    events: list[str] = []
    available = disjoint_routes(paths(3, {0: frozenset({5})}), ("s",), "g", 3)

    def acquire(old: tuple[Plan, ...]) -> Plan:
        events.append("acquire")
        return available[len(old)]

    def agree(answer: Any, target: Any) -> bool:
        events.append("score")
        return bool(answer == target)

    def feedback(failure: VoteFailure) -> None:
        assert events == ["acquire", "score"]
        assert len(failure.routes) == 1
        events.append("feedback")

    search = EnsembleSearch(counts=(1, 3), tolerance=0.1, confidence=0.05, budget=10)
    result = search(Contract(("s",), "g"), acquire,
                    lambda n: [((Message("s", 5, "input"),), 7)] * n,
                    agree=agree, feedback=feedback)
    assert result is not None and events[:5] == ["acquire", "score", "feedback", "acquire", "acquire"]
    assert events.count("feedback") == 1


def test_admission_and_missing_data_emit_no_failure() -> None:
    route = Apply(Lookup({0: 0}), (Given("s"),))
    seen: list[VoteFailure] = []
    search = EnsembleSearch(counts=(1,), tolerance=0.1, confidence=0.05, budget=2)
    assert search(Contract(("s",), "g"), lambda old: route,
                  lambda n: [((Message("s", 0, "input"),), 0)] * n, feedback=seen.append)
    assert search(Contract(("s",), "g"), lambda old: route,
                  lambda n: None, feedback=seen.append) is None
    assert seen == []


def test_feedback_exception_is_not_an_admission_and_keeps_costs() -> None:
    search = EnsembleSearch(counts=(1,), tolerance=0.1, confidence=0.05, budget=2)

    def broken(failure: VoteFailure) -> None:
        raise RuntimeError("repair unavailable")

    with pytest.raises(RuntimeError, match="repair unavailable"):
        search(Contract(("s",), "g"), lambda old: Apply(Lookup({}), (Given("s"),)),
               lambda n: [((Message("s", 0, "input"),), 0)] * n, feedback=broken)
    assert search.labels == search.evaluations == search.tests == 1


def test_feedback_names_the_first_scored_failure_inside_a_larger_batch() -> None:
    cursor = 0
    seen: list[VoteFailure] = []

    def sample(count: int) -> list[VoteCase]:
        nonlocal cursor
        cases = [((Message("s", i, "input"),), i) for i in range(cursor, cursor + count)]
        cursor += count
        return cases

    search = EnsembleSearch(counts=(1,), tolerance=0.1, confidence=0.05, budget=2)
    assert search(Contract(("s",), "g"),
                  lambda old: Apply(Lookup({0: 0, 1: 1}), (Given("s"),)),
                  sample, feedback=seen.append) is None
    assert len(seen) == 1 and seen[0].case[1] == 2
    assert seen[0].drawn == search.labels == cursor == 3


def test_all_finite_monotonic_repairs_strictly_reduce_error_count() -> None:
    """Brute-force link to feedback_repair_progress and feedback_chain_bound;
    these are learner hypotheses, not properties of arbitrary callbacks."""
    domain = range(6)
    for size in range(7):
        for elements in combinations(domain, size):
            errors = set(elements)
            for failed in errors:
                remainder = errors - {failed}
                for kept in range(len(remainder) + 1):
                    for repaired in combinations(remainder, kept):
                        assert len(repaired) < len(errors)
            current = errors.copy()
            for steps, failed in enumerate(elements, 1):
                current.remove(failed)
                assert len(current) + steps <= len(errors)
