"""Share one budget among resumable attempts in doubling rounds (THEORY §49.2–49.3).

Each round doubles the amount every unfinished attempt may have spent in total, so
cheap attempts finish before costly ones receive more, and no cap has to be chosen:
the rounds stop where the budget stops (``NCA.capped_work_monotone``,
``NCA.uniform_cap_minimax``, ``NCA.doubling_rounds``). An attempt must resume at no
cost, reporting its total spending so far. One that stops below its allowance has
failed for a reason more budget cannot fix, and is dropped.
"""

from collections.abc import Callable, Sequence
from typing import TypeVar

Result = TypeVar("Result")
Attempt = Callable[[int], tuple[Result | None, int]]
"""Given a limit on total spending, the result if reached and the total spent so far."""


def doubling_rounds(attempts: Sequence[Attempt[Result]], budget: int) -> tuple[list[Result | None], int]:
    """Results in the order of the attempts, and the budget spent."""
    if type(budget) is not int or budget < 0:
        raise ValueError("the budget must be a nonnegative integer")
    results: list[Result | None] = [None] * len(attempts)
    spent = [0] * len(attempts)
    active = list(range(len(attempts)))
    cap = 1
    while active and sum(spent) < budget:
        for position in list(active):
            allowed = min(cap, spent[position] + budget - sum(spent))
            if allowed <= spent[position]:
                continue
            result, used = attempts[position](allowed)
            if not spent[position] <= used <= allowed:
                raise ValueError("an attempt must report spending between its last report and its limit")
            if result is not None or used < allowed:
                active.remove(position)
            results[position], spent[position] = result, used
        cap *= 2
    return results, sum(spent)
