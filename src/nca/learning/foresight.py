"""Looking ahead through what follows an action (THEORY §56).

A learner taught by takeover judges an action in the situation before it. What
an action leads to is not in that situation. Given what follows an action, a
choice can be carried forward: an action **lasts** ``d`` steps if it is not
ruled out and, for ``d > 1``, some action lasts ``d - 1`` steps in what
follows it.

What is ruled out, the actions open in a situation and what follows an action
are the caller's. Ruling out only what truly fails never sets aside an action
that could have been carried through (§56.2). An action a teacher judged bad
has not thereby failed (§56.3). Where what follows is not known, nothing is
held against the action.
"""

from collections.abc import Callable, Hashable, Sequence
from typing import Any

Bad = Callable[[Any, Hashable], bool]
Follow = Callable[[Any, Hashable], Any]
Options = Callable[[Any], Sequence[Hashable]]


def lasts(situation: Any, action: Hashable, depth: int, *, bad: Bad, follow: Follow, options: Options) -> int:
    """How many steps ``action`` can be carried forward by actions not ruled out, up to ``depth``.

    ``follow`` gives the situation after an action, or ``None`` where it
    cannot say; a situation with no options ends the run.
    """
    if depth <= 0 or bad(situation, action):
        return 0
    if depth == 1:
        return 1
    after = follow(situation, action)
    if after is None:
        return depth
    return 1 + max((lasts(after, further, depth - 1, bad=bad, follow=follow, options=options)
                    for further in options(after)), default=0)


def furthest(situation: Any, actions: Sequence[Hashable], depth: int, *, bad: Bad, follow: Follow,
             options: Options) -> list[Hashable]:
    """The actions that last longest, in the order given: those lasting ``depth`` steps if any does."""
    reach, kept = -1, []
    for action in actions:
        steps = lasts(situation, action, depth, bad=bad, follow=follow, options=options)
        if steps > reach:
            reach, kept = steps, [action]
        elif steps == reach:
            kept.append(action)
    return kept
