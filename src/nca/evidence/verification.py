"""Verified answers (THEORY §41).

A verifier is any callable ``verify(*inputs, answer) -> bool`` checking a
route's answer against the route's inputs, with a miss rate ``m`` and a
false-rejection rate ``f``. ``answer_verified`` answers only accepted
answers, each with the bound ``m c / ((1 − c)(1 − f))`` of Theorem 41.1 in
place of the route's charge ``c``; ``verifier_rates`` estimates ``m`` and
``f`` on labeled answers.
"""

from __future__ import annotations

from collections.abc import Callable, Sequence
from typing import Any

from nca.abi import Module, TypeId
from nca.evidence.alternatives import Choice
from nca.cache import ResultCache
from nca.compile import compile_route
from nca.planner import Plan
from nca.runtime import RiskLedger
from nca.stats import clopper_pearson_upper


def verified_bound(charge: float, miss: float, false_reject: float) -> float:
    """Theorem 41.1's bound on an accepted answer's error given the route's
    charge; 0 for an exact verifier (``miss == 0``), 1 when ``charge`` is
    not below 1."""
    if miss == 0.0:
        return 0.0
    if charge >= 1.0 or false_reject >= 1.0:
        return 1.0
    return min(1.0, miss * charge / ((1.0 - charge) * (1.0 - false_reject)))


def verifier_rates(accepted: Sequence[bool], correct: Sequence[bool],
                   beta: float) -> tuple[float, float]:
    """Clopper–Pearson upper bounds on the miss rate (accepted among wrong
    answers) and the false-rejection rate (rejected among right answers),
    holding together with probability at least ``1 − beta`` (§41.2)."""
    if len(accepted) != len(correct):
        raise ValueError("rates need one correctness flag per verdict")
    wrong = [a for a, c in zip(accepted, correct) if not c]
    right = [a for a, c in zip(accepted, correct) if c]
    miss = clopper_pearson_upper(sum(wrong), len(wrong), beta / 2) if wrong else 1.0
    false_reject = (clopper_pearson_upper(len(right) - sum(right), len(right), beta / 2)
                    if right else 1.0)
    return miss, false_reject


def answer_verified(plan: Plan, available: Sequence[TypeId], rows: Sequence[tuple[Any, ...]],
                    delta: float, verify: Callable[..., bool], miss: float,
                    false_reject: float, exact: Callable[[Module], bool] | None = None,
                    cache: ResultCache | None = None) -> list[Choice]:
    """Answer each row with the route's answer if ``verify(*row, answer)``
    accepts it and its verified bound is at most ``delta``; an uncertified
    ledger counts as charge 1."""
    ledgers = [RiskLedger() if exact is None else RiskLedger(exact) for _ in rows]
    answers = compile_route(plan, available)(rows, cache=cache, ledgers=ledgers)
    choices = []
    for row, answer, ledger in zip(rows, answers, ledgers, strict=True):
        if not verify(*row, answer):
            choices.append(Choice(None, 1.0, 1))
            continue
        charge = min(1.0, ledger.charge) if ledger.certified else 1.0
        bound = verified_bound(charge, miss, false_reject)
        choices.append(Choice(answer if bound <= delta else None, bound, 1))
    return choices
