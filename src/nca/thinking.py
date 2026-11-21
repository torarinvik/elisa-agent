"""Thinking: concepts that hold hypotheses, and the decision to put out now or to go on (§76).

A concept is whatever the host makes of what the memory holds. The frame gives it a cost and no meaning, and
never looks inside. Asked at a step, a concept gives an opinion: hypotheses, each with the chance that taking
it now is right, and, where it reads them, the risk of going on and the risk of putting out now. A hypothesis
is anything that could be done now; the frame reads none, except that one kind is its own: an asking of the
kernel (``nca.abi.Request``). The concepts are asked in the order the host gives them, the cheaper first,
each free to read what those before it left on the memory's scratchpad. After each the step is summed up
(§76.1): the best hypothesis and its chance, and the two risks. The hypothesis is taken where its chance
reaches a threshold and going on risks at least a threshold times what putting out does (§76.2). Otherwise
the next concept is asked; when none is left, the budget is spent or a concept says the step is settled,
nothing is put out, and thinking goes on with what the next step brings (§76.5).

A hypothesis taken is put out, unless it is an asking of the kernel and the host gave a way to ask: then the
kernel serves it within the step, its answer is left on the scratchpad under the type asked for, and the
concepts are asked again, at most a stated number of times a step (§76.6).

Nothing here says what a hypothesis is, how a chance is come by, or what a risk is the risk of.
"""
from __future__ import annotations

import math
from collections.abc import Callable, Sequence
from dataclasses import dataclass
from typing import Protocol

from nca.abi import Message, Request
from nca.memory.working import WorkingMemory
from nca.runtime import Resolver, UnresolvedRequest, attempt
from nca.workspace import Workspace


@dataclass(frozen=True)
class Opinion:
    """What a concept holds at a step. ``chances`` gives each hypothesis the chance that taking it now is
    right, and ``hypotheses`` says what they are; left ``None``, a hypothesis is its place among the chances.
    ``wait`` is the risk of going on and ``act`` the risk of putting out now. A concept says what it reads
    and leaves the rest ``None``, which keeps what the concepts before it said. ``settled`` says that no
    later concept would change what is done at this step."""

    chances: Sequence[float] | None = None
    hypotheses: Sequence[object] | None = None
    wait: float | None = None
    act: float | None = None
    settled: bool = False


class Concept(Protocol):
    """Whatever gives an opinion of a step from what the memory holds, at a stated cost."""

    cost: float

    def think(self, memory: WorkingMemory) -> Opinion: ...


@dataclass(frozen=True)
class Thresholds:
    """The least chance the best hypothesis must have, and the least quotient of the risk of going on over the
    risk of putting out now, for it to be taken (§76.2)."""

    prob: float = 0.0
    ratio: float = 1.0


@dataclass(frozen=True)
class Thought:
    """How a step stood when thinking stopped: what is put out, if anything; the place of the best hypothesis
    and its chance; the risk of going on and of putting out now; how many times a concept was asked, what the
    concepts and the kernel cost, and how many askings the kernel served."""

    out: object | None
    best: int | None
    chance: float
    wait: float
    act: float
    asked: int
    cost: float
    asks: int = 0

    @property
    def ratio(self) -> float:
        """The risk of going on over the risk of putting out now; infinite where putting out risks nothing."""
        return self.wait / self.act if self.act > 0 else math.inf

    @property
    def tilt(self) -> float:
        """Where the risk lies, as one number: the share of the two risks that is in putting out now. Nought
        where all the risk is in going on, one where all is in putting out, a half where there is none. With
        a threshold ``ratio`` on the quotient, a hypothesis is taken where this is at most ``1 / (1 + ratio)``
        (§76.1)."""
        whole = self.wait + self.act
        return self.act / whole if whole > 0 else 0.5


@dataclass(frozen=True)
class Answer:
    """What an asking of the kernel gave: the value, ``None`` where it could give none, and what it cost."""

    value: object | None
    cost: float = 0.0


Adapting = Callable[[Thought], Thresholds]
"""Thresholds that turn on how the step stands: given the summing up so far, the thresholds to hold it to."""

Asking = Callable[[Request], Answer]
"""A way to ask the kernel."""


def through(kernel: Resolver, workspace: Workspace, *, budget: int, cost_budget: float | None = None) -> Asking:
    """Askings served by a kernel: it plans a route to the type asked for from the inputs given and runs it
    under the budgets of each asking. No route, or a budget that does not reach, gives no value; a refusal is
    never a wrong answer (§20)."""

    def ask(request: Request) -> Answer:
        before = workspace.spent
        route = kernel.resolve(request, ())
        if route is None:
            return Answer(None)
        inputs = [Message(type_id, value, "input") for type_id, value in request.inputs]
        try:
            result = attempt(route, inputs, workspace, budget, kernel, cost_budget)
        except UnresolvedRequest:
            result = None
        return Answer(None if result is None else result.payload, workspace.spent - before)

    return ask


def decides(chance: float, wait: float, act: float, thresholds: Thresholds) -> bool:
    """Whether to take the best hypothesis: it is likely enough, and going on risks at least ``ratio`` times
    what putting out now does. With the thresholds nought and one this takes the smaller risk (§76.1)."""
    return chance >= thresholds.prob and wait >= thresholds.ratio * act


def _risk(value: float, name: str) -> float:
    if not 0.0 <= value <= 1.0:
        raise ValueError(f"{name} must lie between nought and one")
    return float(value)


def think(concepts: Sequence[Concept], memory: WorkingMemory, thresholds: Thresholds | Adapting = Thresholds(), *,
          wait: float = 1.0, budget: float = math.inf, ask: Asking | None = None, rounds: int = 4) -> Thought:
    """Ask the concepts in turn until a hypothesis is put out, the step is settled, or the budget would be passed.

    ``wait`` is the risk of going on where no concept reads it; with the default nothing is gained by going on,
    so the best hypothesis is taken as soon as its chance reaches the threshold. Where no concept gives a risk
    of putting out now it is one less the best chance. A concept whose cost would pass ``budget`` is not asked,
    nor any after it. With ``ask``, a hypothesis taken that is an asking of the kernel is served, its answer
    noted for this step under the type asked for, and the concepts asked again from the first; after ``rounds``
    askings in a step a further one is not served and nothing is put out.
    """
    risk, asked, spent, asks = _risk(wait, "the risk of going on"), 0, 0.0, 0
    best: int | None = None
    chance, acting = 0.0, 1.0
    while True:
        best, chance, acting, given, taken = None, 0.0, 1.0, None, None
        hypotheses: Sequence[object] | None = None
        for concept in concepts:
            if concept.cost < 0 or math.isnan(concept.cost):
                raise ValueError("a concept's cost must not be below nought")
            if spent + concept.cost > budget:
                break
            opinion = concept.think(memory)
            asked, spent = asked + 1, spent + concept.cost
            if opinion.wait is not None:
                risk = _risk(opinion.wait, "the risk of going on")
            if opinion.act is not None:
                given = _risk(opinion.act, "the risk of putting out now")
            if opinion.chances is not None:
                if len(opinion.chances) == 0 or (opinion.hypotheses is not None and len(opinion.hypotheses) != len(opinion.chances)):
                    raise ValueError("an opinion needs one chance for each of at least one hypothesis")
                hypotheses = opinion.hypotheses
                best = max(range(len(opinion.chances)), key=opinion.chances.__getitem__)
                chance = _risk(opinion.chances[best], "a hypothesis's chance")
            if best is not None:
                acting = 1.0 - chance if given is None else given
                so_far = Thought(None, best, chance, risk, acting, asked, spent, asks)
                if decides(chance, risk, acting, thresholds(so_far) if callable(thresholds) else thresholds):
                    taken = best if hypotheses is None else hypotheses[best]
                    break
            if opinion.settled:
                break
        if given is not None:
            acting = given
        if not isinstance(taken, Request) or ask is None:
            return Thought(taken, best, chance, risk, acting, asked, spent, asks)
        if asks == rounds:
            return Thought(None, best, chance, risk, acting, asked, spent, asks)
        answer = ask(taken)
        memory.scratch.note(taken.type_id, answer.value, life=1)
        spent, asks = spent + answer.cost, asks + 1
