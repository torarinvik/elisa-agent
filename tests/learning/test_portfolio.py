"""Learner selection on training examples only."""

from collections.abc import Callable, Hashable, Sequence
from typing import Any

from nca.abi import Contract, Manifest, Module
from nca.learning.portfolio import Portfolio
from nca.runtime import BudgetExceeded, UnresolvedRequest
import pytest

CONTRACT = Contract(("input",), "output")


class Function:
    def __init__(self, function: Callable[[Any], Any]) -> None:
        self.function = function
        self.manifest = Manifest("sample.function", "1", CONTRACT, effects=frozenset())

    def invoke(self, value: Any) -> Any:
        return self.function(value)


def constantly(function: Callable[[Any], Any]) -> Callable[..., Module]:
    def learner(contract: Contract, keys: Sequence[Hashable], labels: Sequence[Hashable]) -> Module:
        return Function(function)
    return learner


def test_best_selection_score_is_refitted_on_all_examples() -> None:
    sizes: list[int] = []
    def counting(contract: Contract, keys: Sequence[Hashable], labels: Sequence[Hashable]) -> Module:
        sizes.append(len(keys))
        return Function(lambda value: value + 1)
    chosen = Portfolio((("wrong", constantly(lambda value: 0)), ("right", counting)))
    keys = list(range(1, 11))
    module = chosen(CONTRACT, keys, [key + 1 for key in keys])
    assert chosen.chosen == "right" and chosen.last == {"wrong": 0, "right": 2}
    assert sizes == [8, 10] and module is not None and module.invoke(4) == 5


def test_failing_learners_are_skipped_and_all_zero_scores_refuse() -> None:
    def broken(contract: Contract, keys: Sequence[Hashable], labels: Sequence[Hashable]) -> Module:
        raise ValueError("cannot fit")
    chosen = Portfolio((("broken", broken), ("wrong", constantly(lambda value: 0))))
    assert chosen(CONTRACT, [1, 2, 3, 4, 5, 6], [2, 3, 4, 5, 6, 7]) is None
    assert chosen.chosen is None and chosen.last == {"wrong": 0}


def test_refusals_do_not_abort_other_learners_or_hide_budget_exhaustion() -> None:
    def refuse(_: Any) -> Any:
        raise UnresolvedRequest("cannot answer")

    def no_candidate(contract: Contract, keys: Sequence[Hashable], labels: Sequence[Hashable]) -> Module:
        raise UnresolvedRequest("cannot fit")

    selection = Portfolio((("no-candidate", no_candidate), ("refuses", constantly(refuse)),
                           ("answers", constantly(lambda value: value + 1))))
    keys = list(range(10))
    result = selection(CONTRACT, keys, [key + 1 for key in keys])
    assert result is not None and selection.chosen == "answers"
    assert selection.last == {"refuses": 0, "answers": 2}

    def exhausted(_: Any) -> Any:
        raise BudgetExceeded("selection work exhausted")
    with pytest.raises(BudgetExceeded):
        Portfolio((("limited", constantly(exhausted)),))(CONTRACT, keys, keys)
