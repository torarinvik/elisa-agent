"""Permutation safety and exact acquisition-exchange checks (§20.19)."""

from fractions import Fraction
from itertools import product

import pytest

from nca.abi import Contract, Module, Request
from nca.kernel import Kernel
from nca.planner.gaps import gaps, repair
from test_gaps import LIBRARY, Step


def test_priorities_preserve_all_candidates_and_ties() -> None:
    original = gaps(LIBRARY, ("s",), "g", arity=2)
    tied = gaps(LIBRARY, ("s",), "g", arity=2, priority=lambda c: 0.0)
    assert [g.contract for g in tied] == [g.contract for g in original]
    for seed in range(20):
        priorities = {g.contract: float((i * 7 + seed) % 11) for i, g in enumerate(original)}
        ranked = gaps(LIBRARY, ("s",), "g", arity=2, priority=priorities.__getitem__)
        assert {g.contract for g in ranked} == {g.contract for g in original}
        assert len(ranked) == len(original)
        assert [g.contract for g in ranked] == sorted(
            [g.contract for g in original], key=priorities.__getitem__, reverse=True)


def test_ranked_repair_tries_preferred_candidate_without_weakening_validation() -> None:
    preferred = Contract(("y",), "z")
    asked: list[Contract] = []

    def acquire(contract: Contract) -> Module | None:
        asked.append(contract)
        return Step(contract.inputs, contract.output) if contract == preferred else None

    result = repair(LIBRARY, ("s",), "g", acquire, attempts=1,
                    priority=lambda c: float(c == preferred))
    assert result is not None and asked == [preferred]


def test_negative_priorities_do_not_prune_or_repeat_refused_candidates() -> None:
    asked: list[Contract] = []

    def refuse(contract: Contract) -> Module | None:
        asked.append(contract)
        return None

    original = gaps(LIBRARY, ("s",), "g", arity=2)
    assert repair(LIBRARY, ("s",), "g", refuse, attempts=len(original), arity=2,
                  priority=lambda c: -float(len(c.inputs))) is None
    assert len(asked) == len(original) == len(set(asked))
    assert set(asked) == {gap.contract for gap in original}


@pytest.mark.parametrize("score", [float("nan"), float("inf"), -float("inf")])
def test_nonfinite_scores_are_rejected_before_acquisition(score: float) -> None:
    with pytest.raises(ValueError, match="finite"):
        gaps(LIBRARY, ("s",), "g", priority=lambda c: score)


def test_exchange_rule_matches_exact_expected_cost() -> None:
    chances = [Fraction(i, 4) for i in range(5)]
    for ca, cb, qa, qb, tail in product(range(1, 4), range(1, 4), chances, chances, range(4)):
        ab = ca + (1 - qa) * cb + (1 - qa) * (1 - qb) * tail
        ba = cb + (1 - qb) * ca + (1 - qb) * (1 - qa) * tail
        assert ab - ba == ca * qb - cb * qa
        assert (ab <= ba) == (ca * qb <= cb * qa)


def test_kernel_can_prioritize_a_multi_input_acquisition() -> None:
    preferred = Contract(("a", "b"), "g")
    asked: list[Contract] = []

    def acquire(contract: Contract) -> Module | None:
        asked.append(contract)
        return Step(contract.inputs, contract.output) if contract == preferred else None

    kernel = Kernel([], acquire=acquire, attempts=1, arity=2,
                    priority=lambda c: float(c == preferred))
    assert kernel.resolve(Request("g", (("a", 1), ("b", 2))), ()) is not None
    assert asked == [preferred]
    assert [m.manifest.contract for m in kernel.acquired] == [preferred]
