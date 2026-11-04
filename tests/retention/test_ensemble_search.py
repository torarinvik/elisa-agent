"""Fresh end-to-end certification rather than route independence (§31.9)."""

from itertools import product
from pathlib import Path
from typing import Any
import pytest

from nca.abi import Contract, Manifest, Message
from nca.evidence.redundancy import disjoint_routes
from nca.planner import Apply, Given, Plan
from nca.retention.certification import zero_loss_test
from nca.retention.ensembles import EnsembleSearch, VoteCase
from test_acquisition_history import history
from test_memory import authority
from test_redundancy import paths


def sample(count: int) -> list[VoteCase]:
    return [((Message("s", 5, "input"),), 7)] * count


def test_grow_until_the_actual_vote_passes_then_stop_acquiring() -> None:
    available = disjoint_routes(paths(5, {0: frozenset({5})}), ("s",), "g", 5)

    def acquire(existing: tuple[Plan, ...]) -> Plan:
        return available[len(existing)]

    search = EnsembleSearch(counts=(1, 3, 5), tolerance=0.1, confidence=0.05, budget=10)
    result = search(Contract(("s",), "g"), acquire, sample)
    assert result is not None and len(result.routes) == search.requests == 3
    assert search.tests == 2
    assert search.labels == search.evaluations == 1 + result.cases
    assert result.tolerance == 0.1


def test_common_mode_failure_refuses_instead_of_claiming_amplification() -> None:
    available = disjoint_routes(paths(3, {i: frozenset({5}) for i in range(3)}), ("s",), "g", 3)
    search = EnsembleSearch(counts=(1, 3), tolerance=0.1, confidence=0.05, budget=10)
    assert search(Contract(("s",), "g"), lambda old: available[len(old)], sample) is None
    assert search.requests == 3 and search.tests == search.labels == 2


def test_abstention_is_failure_even_when_none_would_agree_with_the_label() -> None:
    available = disjoint_routes(paths(2, {0: frozenset({5})}), ("s",), "g", 2)
    search = EnsembleSearch(counts=(2,), tolerance=0.1, confidence=0.05, budget=10)
    assert search(Contract(("s",), "g"), lambda old: available[len(old)],
                  lambda n: [((Message("s", 5, "input"),), None)] * n,
                  agree=lambda a, b: True) is None


def test_unanimous_none_payload_is_an_answer_rather_than_abstention() -> None:
    class Null:
        manifest = Manifest("null", "1", Contract(("s",), "g"), effects=frozenset())

        def invoke(self, value: Any) -> None:
            return None

    route = Apply(Null(), (Given("s"),))
    search = EnsembleSearch(counts=(2,), tolerance=0.1, confidence=0.05, budget=10)
    assert search(Contract(("s",), "g"), lambda old: route,
                  lambda n: [((Message("s", 5, "input"),), None)] * n) is not None


@pytest.mark.parametrize("limit", [None, 1, 2, 3, 5, 100])
def test_shared_test_matches_all_boolean_histories_and_retention_bounds(limit: int | None) -> None:
    """Brute-force link to earlyTest_admits/earlyTest_reads: batching changes
    draw cost, not admission, and retained observations are only a prefix."""
    for size in range(1, 9):
        for bits in product((False, True), repeat=size):
            cursor = 0
            evaluated = 0
            draws: list[int] = []

            def draw(count: int) -> tuple[bool, ...]:
                nonlocal cursor
                draws.append(count)
                batch = bits[cursor:cursor + count]
                cursor += len(batch)
                return batch

            def agree(bit: bool) -> bool:
                nonlocal evaluated
                evaluated += 1
                return bit

            result = zero_loss_test(draw, agree, cases=size, retain=2, batch_limit=limit)
            assert result.passed == all(bits)
            assert result.drawn == cursor <= size
            assert result.retained == bits[:min(cursor, 2)]
            if result.passed:
                assert cursor == size
            assert evaluated == (size if all(bits) else bits.index(False) + 1)
            if limit is not None:
                assert max(draws) <= limit
                # batchedTest_excess: exact-size replies, first failing batch.
                assert cursor < evaluated + limit


@pytest.mark.parametrize("limit", [False, True, 0, -1, 1.5, "2"])
def test_batch_limit_validation_precedes_sampling(limit: Any) -> None:
    def forbidden(count: int) -> None:
        pytest.fail("invalid configuration must not sample")

    with pytest.raises(ValueError, match="batch limit"):
        zero_loss_test(forbidden, bool, cases=4, batch_limit=limit)
    with pytest.raises(ValueError, match="batch limit"):
        EnsembleSearch(counts=(1,), tolerance=0.1, confidence=0.05,
                       budget=10, batch_limit=limit)


@pytest.mark.parametrize("reply", [(), (True, True, True)])
def test_capped_test_charges_malformed_reply_without_admitting(reply: tuple[bool, ...]) -> None:
    result = zero_loss_test(lambda count: reply, bool, cases=8, batch_limit=1)
    assert result.passed is None and result.drawn == len(reply)
    assert result.retained == ()


@pytest.mark.parametrize("limit", [1, 3, None])
def test_ensemble_batch_cap_reaches_sampler_without_changing_admission(limit: int | None) -> None:
    route = disjoint_routes(paths(1), ("s",), "g", 1)[0]
    draws: list[int] = []

    def draw(count: int) -> list[VoteCase]:
        draws.append(count)
        return sample(count)

    search = EnsembleSearch(counts=(1,), tolerance=0.1, confidence=0.05,
                            budget=10, batch_limit=limit)
    result = search(Contract(("s",), "g"), lambda old: route, draw)
    assert result is not None
    assert result.cases == search.labels == search.evaluations == sum(draws)
    if limit is not None:
        assert max(draws) <= limit


def test_resumption_preserves_ensemble_confidence_without_refusal_caching(tmp_path: Path) -> None:
    path = tmp_path / "history.sqlite"
    route = disjoint_routes(paths(1), ("s",), "g", 1)[0]
    levels = []
    with authority():
        for _ in range(2):
            log = history(path)
            search = EnsembleSearch(counts=(1,), tolerance=0.1, confidence=0.05,
                                    budget=10, history=log)
            result = search(Contract(("s",), "g"), lambda old: route, sample)
            assert result is not None
            levels.append(result.level)
            log.memory.close()
    assert levels[1] < levels[0]


def test_incomplete_test_draw_is_inconclusive_and_charged() -> None:
    calls = 0

    def draw(count: int) -> tuple[bool, ...]:
        nonlocal calls
        calls += 1
        return (True,)  # First request is one; second requests two.

    result = zero_loss_test(draw, lambda bit: bit, cases=7, retain=7)
    assert result.passed is None and result.drawn == 2
    assert result.retained == (True,) and calls == 2


def test_scoring_exception_preserves_label_accounting() -> None:
    route = disjoint_routes(paths(1), ("s",), "g", 1)[0]
    search = EnsembleSearch(counts=(1,), tolerance=0.1, confidence=0.05, budget=10)

    def broken(answer: Any, target: Any) -> bool:
        raise RuntimeError("scoring failed")

    with pytest.raises(RuntimeError, match="scoring failed"):
        search(Contract(("s",), "g"), lambda old: route, sample, agree=broken)
    assert search.labels == search.evaluations == 1


def test_unavailable_or_wrongly_typed_route_cannot_be_certified() -> None:
    search = EnsembleSearch(counts=(1,), tolerance=0.1, confidence=0.05, budget=10)
    assert search(Contract(("s",), "g"), lambda old: None, sample) is None
    with pytest.raises(ValueError, match="output type"):
        search(Contract(("s",), "g"), lambda old: Given("s"), sample)
    assert search.labels == search.tests == 0 and search.requests == 2


def test_undeclared_test_inputs_cannot_leak_into_a_certificate() -> None:
    route = disjoint_routes(paths(1), ("s",), "g", 1)[0]
    search = EnsembleSearch(counts=(1,), tolerance=0.1, confidence=0.05, budget=10)

    def extra(count: int) -> list[VoteCase]:
        return [((Message("s", 5, "input"), Message("extra", 7, "input")), 7)] * count

    with pytest.raises(ValueError, match="inputs do not match"):
        search(Contract(("s",), "g"), lambda old: route, extra)
    assert search.labels == 1
