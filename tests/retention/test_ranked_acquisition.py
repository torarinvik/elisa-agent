"""Ranked candidates share one request's level and are tested in order."""

from collections.abc import Callable, Hashable, Sequence
from random import Random

import pytest

from nca.abi import Contract, Manifest, Module
from nca.retention.acquisition import CertifiedAcquirer, Ranked
from nca.retention.certification import validation_plan
from nca.retention.sampled import decision_level, required_cases
from nca.stats import family_audit_alpha

CONTRACT = Contract(("input",), "output")
CONFIDENCE = 0.1


def truth(value: int) -> int:
    return value + 1


def level(candidates: int, confidence: float = CONFIDENCE) -> float:
    return family_audit_alpha(decision_level(confidence, 0), candidates)


class Function:
    def __init__(self, name: str, function: Callable[[int], int], contract: Contract = CONTRACT) -> None:
        self.function = function
        self.manifest = Manifest(name, "1", contract, effects=frozenset())

    def invoke(self, value: int) -> int:
        return self.function(value)


def cases(seed: int = 0) -> Callable[[Contract, int], list[tuple[int, int]]]:
    rng = Random(seed)
    def sample(contract: Contract, count: int) -> list[tuple[int, int]]:
        return [(value, truth(value)) for value in (rng.randrange(1000) for _ in range(count))]
    return sample


def ranking(*modules: Module | None) -> tuple[Callable[..., Ranked], list[int]]:
    built: list[int] = []
    def builder(index: int) -> Callable[[], Module | None]:
        def build() -> Module | None:
            built.append(index)
            return modules[index]
        return build
    def fit(contract: Contract, keys: Sequence[Hashable], labels: Sequence[Hashable]) -> Ranked:
        return Ranked(tuple(builder(index) for index in range(len(modules))))
    return fit, built


def test_a_rejected_candidate_gives_way_to_the_next_at_a_split_level() -> None:
    wrong = Function("sample.wrong", lambda value: 0)
    right = Function("sample.right", truth)
    fit, built = ranking(wrong, right)
    acquirer = CertifiedAcquirer(fit, cases(), train=4, tolerance=0.05, confidence=CONFIDENCE)
    assert acquirer(CONTRACT) is right and built == [0, 1]
    needed = required_cases(0.05, level(2))
    assert 4 + needed < acquirer.labels <= 4 + 2 * needed
    assert acquirer.rate(right) == 0.05 and acquirer.rate(wrong) is None


def test_later_candidates_are_not_built_after_an_admission() -> None:
    right = Function("sample.right", truth)
    fit, built = ranking(right, Function("sample.unused", truth))
    acquirer = CertifiedAcquirer(fit, cases(), train=4, tolerance=0.05, confidence=CONFIDENCE)
    assert acquirer(CONTRACT) is right and built == [0]
    assert acquirer.labels == 4 + required_cases(0.05, level(2))


def test_a_sole_ranked_candidate_keeps_the_whole_level() -> None:
    right = Function("sample.right", truth)
    fit, _ = ranking(right)
    ranked = CertifiedAcquirer(fit, cases(), train=4, tolerance=0.05, confidence=CONFIDENCE)
    plain = CertifiedAcquirer(lambda contract, keys, labels: right, cases(), train=4, tolerance=0.05, confidence=CONFIDENCE)
    assert ranked(CONTRACT) is right and plain(CONTRACT) is right and ranked.labels == plain.labels


def test_positive_error_allowance_tightens_with_the_candidate_count() -> None:
    allowed = validation_plan(0.06, level(1, 0.5), 1000)[1]
    assert validation_plan(0.06, level(10, 0.5), 1000)[1] < allowed

    def nearly(value: int) -> int:
        return 0 if value % 1000 < allowed else truth(value)

    def stream() -> Callable[[Contract, int], list[tuple[int, int]]]:
        position = [0]
        def sample(contract: Contract, count: int) -> list[tuple[int, int]]:
            start = position[0]
            position[0] += count
            return [(value, truth(value)) for value in range(start, start + count)]
        return sample

    candidate = Function("sample.nearly", nearly)
    sole, _ = ranking(candidate)
    split, _ = ranking(candidate, *(None for _ in range(9)))
    assert CertifiedAcquirer(sole, stream(), train=1, tolerance=0.06, confidence=0.5,
                             validation_cases=1000)(CONTRACT) is candidate
    assert CertifiedAcquirer(split, stream(), train=1, tolerance=0.06, confidence=0.5,
                             validation_cases=1000)(CONTRACT) is None


def test_a_builder_without_a_candidate_is_skipped_and_empty_rankings_refuse() -> None:
    right = Function("sample.right", truth)
    fit, built = ranking(None, right)
    assert CertifiedAcquirer(fit, cases(), train=4, tolerance=0.05, confidence=CONFIDENCE)(CONTRACT) is right
    assert built == [0, 1]
    empty, _ = ranking()
    assert CertifiedAcquirer(empty, cases(), train=4, tolerance=0.05, confidence=CONFIDENCE)(CONTRACT) is None


def test_a_ranked_candidate_with_another_contract_is_an_error() -> None:
    fit, _ = ranking(Function("sample.other", truth, Contract(("other",), "output")))
    with pytest.raises(ValueError, match="requested contract"):
        CertifiedAcquirer(fit, cases(), train=4, tolerance=0.05, confidence=CONFIDENCE)(CONTRACT)


def test_wrong_candidates_are_admitted_within_the_requested_confidence() -> None:
    rng = Random(20261105)
    def faulty(name: str, stream: Random) -> Module:
        return Function(name, lambda value: 0 if stream.random() < 0.06 else truth(value))
    runs, admitted = 400, 0
    for seed in range(runs):
        fit, _ = ranking(faulty("sample.first", rng), faulty("sample.second", rng), faulty("sample.third", rng))
        admitted += CertifiedAcquirer(fit, cases(seed), train=1, tolerance=0.05,
                                      confidence=CONFIDENCE)(CONTRACT) is not None
    assert admitted / runs <= 0.1
