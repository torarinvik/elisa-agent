"""Share one budget among resumable attempts in doubling rounds (THEORY §49.2–49.3).

Each round doubles the amount every unfinished attempt may have spent in total, so
cheap attempts finish before costly ones receive more, and no cap has to be chosen:
the rounds stop where the budget stops (``NCA.capped_work_monotone``,
``NCA.uniform_cap_minimax``, ``NCA.doubling_rounds``). An attempt must resume at no
cost, reporting its total spending so far. One that stops below its allowance has
failed for a reason more budget cannot fix, and is dropped. ``first_of`` joins
several attempts at one goal into one attempt that shares its allowance among them.
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


def first_of(attempts: Sequence[Attempt[Result]]) -> Attempt[Result]:
    """One attempt from several at the same goal, returning the first result found.

    Each allowance is divided equally among the attempts still running; one that
    stops below its share is finished, and what it left passes to the others.
    """
    spent = [0] * len(attempts)
    running = list(range(len(attempts)))

    def attempt(allowed: int) -> tuple[Result | None, int]:
        while running and sum(spent) < allowed:
            order = list(running)
            for index, position in enumerate(order):
                share = -(-(allowed - sum(spent)) // (len(order) - index))
                if share <= 0:
                    continue
                limit = spent[position] + share
                result, used = attempts[position](limit)
                if not spent[position] <= used <= limit:
                    raise ValueError("an attempt must report spending between its last report and its limit")
                spent[position] = used
                if result is not None:
                    return result, sum(spent)
                if used < limit:
                    running.remove(position)
        return None, sum(spent)
    return attempt
