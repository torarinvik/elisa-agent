"""Thinking: concepts that hold hypotheses, and the decision to put out now or to go on (§76).

A concept is whatever the host makes of what the memory holds. The frame gives it a cost and no meaning, and
never looks inside. Asked at a step, a concept gives an opinion: hypotheses, each with the chance that taking
it now is right, and, where it reads them, the risk of going on and the risk of putting out now. A hypothesis
is anything that could be done now; the frame reads none, except that one kind is its own: an asking of the
kernel (``nca.abi.Request``). The concepts are asked in the order the host gives them, the cheaper first,
each free to read what those before it left on the memory's scratchpad. After each the step is summed up
(§76.1): the best hypothesis and its chance, and the two risks. The hypothesis is taken where its chance
reaches its threshold and the risk ratio meets its bound (by default the lower bound of §76.2). Otherwise
the next concept is asked; when none is left, the budget is spent or a concept says the step is settled,
nothing is put out, and thinking goes on with what the next step brings (§76.5).

A hypothesis taken is put out, unless it is an asking of the kernel and the host gave a way to ask: then the
kernel serves it within the step, its answer is left on the scratchpad under the type asked for, and the
concepts are asked again, at most a stated number of times a step (§76.6). An expert the kernel is itself
running has no kernel to ask; ``thinking`` is ``think`` for it, handing each asking to whoever runs the expert.

Asking while unsure, what an asking is worth and how sure to be (§76.13 to §76.16) are in ``nca.asking``.

Nothing here says what a hypothesis is, how a chance is come by, what a risk is the risk of, or what is asked
about.
"""
from __future__ import annotations

import math
from collections.abc import Callable, Generator, Sequence
from dataclasses import dataclass, replace
from typing import Literal, Protocol

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
    """Minimum confidence and a bound on waiting risk divided by acting risk.

    The minimum ratio follows §76.2. A maximum ratio expresses the upper-bound
    decision rule printed in the cognitive-model diagram. At zero acting risk
    the reported ratio is infinite, including when both risks are zero.
    """

    prob: float = 0.0
    ratio: float = 1.0
    ratio_bound: Literal["minimum", "maximum"] = "minimum"

    def __post_init__(self) -> None:
        if not 0. <= self.prob <= 1.:
            raise ValueError("confidence threshold must be between zero and one")
        if not math.isfinite(self.ratio) or self.ratio < 0:
            raise ValueError("risk ratio threshold must be finite and nonnegative")
        if self.ratio_bound not in ("minimum", "maximum"):
            raise ValueError("risk ratio bound must be minimum or maximum")


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
        positive total risk, a lower bound ``ratio`` on the quotient holds where this is at most ``1 / (1 + ratio)``
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


@dataclass(frozen=True)
class KernelAsking:
    """A callable kernel adapter that can also admit a request against a remaining step budget."""

    kernel: Resolver
    workspace: Workspace
    budget: int
    cost_budget: float | None

    def __call__(self, request: Request) -> Answer:
        return self._serve(request, self.cost_budget)

    def ask_with_budget(self, request: Request, remaining: float) -> Answer:
        limit = remaining if self.cost_budget is None else min(self.cost_budget, remaining)
        return self._serve(request, limit)

    def _serve(self, request: Request, limit: float | None) -> Answer:
        before = self.workspace.spent
        route = self.kernel.resolve(request, ())
        if route is None:
            return Answer(None)
        inputs = [Message(type_id, value, "input") for type_id, value in request.inputs]
        try:
            result = attempt(route, inputs, self.workspace, self.budget, self.kernel, limit)
        except UnresolvedRequest:
            result = None
        return Answer(None if result is None else result.payload, self.workspace.spent - before)


def through(kernel: Resolver, workspace: Workspace, *, budget: int, cost_budget: float | None = None) -> KernelAsking:
    """Serve a request under its invocation and cost caps, further limited by a finite thinking budget."""
    if cost_budget is not None and (not math.isfinite(cost_budget) or cost_budget < 0):
        raise ValueError("cost_budget must be finite and nonnegative")
    return KernelAsking(kernel, workspace, budget, cost_budget)


def decides(chance: float, wait: float, act: float, thresholds: Thresholds) -> bool:
    """Apply the confidence and risk bounds to one candidate."""
    return _meets(_risk(chance, "a hypothesis's chance"), _risk(wait, "the risk of going on"),
                  _risk(act, "the risk of putting out now"), thresholds)


def _meets(chance: float, wait: float, act: float, thresholds: Thresholds) -> bool:
    if chance < thresholds.prob:
        return False
    if thresholds.ratio_bound == "maximum":
        return act > 0 and wait <= thresholds.ratio * act
    return wait >= thresholds.ratio * act


def _risk(value: float, name: str) -> float:
    if not 0.0 <= value <= 1.0:
        raise ValueError(f"{name} must lie between nought and one")
    return float(value)


def think(concepts: Sequence[Concept], memory: WorkingMemory, thresholds: Thresholds | Adapting = Thresholds(), *,
          wait: float = 1.0, budget: float = math.inf, ask: Asking | None = None, rounds: int = 4,
          passes: int = 1) -> Thought:
    """Ask the concepts in turn until a hypothesis is put out, the step is settled, or the budget would be passed.

    ``wait`` is the risk of going on where no concept reads it; with the default nothing is gained by going on,
    so the best hypothesis is taken as soon as its chance reaches the threshold. Where no concept gives a risk
    of putting out now it is one less the best chance. A concept whose cost would pass ``budget`` is not asked,
    nor any after it. With ``ask``, a hypothesis taken that is an asking of the kernel is served, its answer
    noted for this step under the type asked for, and the concepts asked again from the first; after ``rounds``
    askings in a step a further one is not served and nothing is put out.
    ``passes`` permits additional traversals of the concepts on the same input. A completed
    traversal carries its latest opinion and scratchpad into the next. Settlement, output and
    the cost budget stop refinement immediately. Kernel answers restart the opinion independently
    under ``rounds`` and share the same budget and remaining extra traversals.
    A service exposing ``ask_with_budget(request, remaining)``, including ``through``, receives the
    remaining finite budget before execution. A one-argument callback reports its cost after execution.
    """
    if type(rounds) is not int or rounds < 0:
        raise ValueError("rounds must be a nonnegative integer")
    if type(passes) is not int or passes < 1:
        raise ValueError("passes must be a positive integer")
    if math.isnan(budget) or budget < 0:
        raise ValueError("thinking budget must be nonnegative")
    risk, asked, spent, asks = _risk(wait, "the risk of going on"), 0, 0.0, 0
    best: int | None = None
    chance, acting = 0.0, 1.0
    hypotheses: Sequence[object] | None = None
    given = taken = None
    while True:
        for concept in concepts:
            cost = concept.cost
            if cost < 0 or math.isnan(cost):
                raise ValueError("a concept's cost must not be below nought")
            if spent + cost > budget:
                break
            opinion = concept.think(memory)
            asked, spent = asked + 1, spent + cost
            if opinion.wait is not None:
                risk = _risk(opinion.wait, "the risk of going on")
            if opinion.act is not None:
                given = _risk(opinion.act, "the risk of putting out now")
            if opinion.hypotheses is not None and opinion.chances is None:
                raise ValueError("replacement hypotheses need corresponding chances")
            if opinion.chances is not None:
                if len(opinion.chances) == 0 or (opinion.hypotheses is not None and len(opinion.hypotheses) != len(opinion.chances)):
                    raise ValueError("an opinion needs one chance for each of at least one hypothesis")
                hypotheses = opinion.hypotheses
                chance = -1.0
                for index, value in enumerate(opinion.chances):
                    if not 0.0 <= value <= 1.0:
                        raise ValueError("a hypothesis's chance must lie between nought and one")
                    if value > chance:
                        best, chance = index, float(value)
            if best is not None:
                acting = 1.0 - chance if given is None else given
                bounds = thresholds
                if callable(bounds):
                    bounds = bounds(Thought(None, best, chance, risk, acting, asked, spent, asks))
                if _meets(chance, risk, acting, bounds):
                    taken = best if hypotheses is None else hypotheses[best]
                    break
            if opinion.settled:
                break
        else:
            if passes > 1 and concepts:
                passes -= 1
                continue
        if given is not None:
            acting = given
        if not isinstance(taken, Request) or ask is None:
            return Thought(taken, best, chance, risk, acting, asked, spent, asks)
        if asks == rounds:
            return Thought(None, best, chance, risk, acting, asked, spent, asks)
        budgeted = getattr(ask, "ask_with_budget", None) if math.isfinite(budget) else None
        answer = ask(taken) if budgeted is None else budgeted(taken, budget - spent)
        if not math.isfinite(answer.cost) or answer.cost < 0:
            raise ValueError("request cost must be finite and nonnegative")
        memory.scratch.note(taken.type_id, answer.value, life=1)
        spent, asks = spent + answer.cost, asks + 1
        best, chance, acting, given, taken = None, 0.0, 1.0, None, None
        hypotheses = None


def thinking(concepts: Sequence[Concept], memory: WorkingMemory, thresholds: Thresholds | Adapting = Thresholds(), *,
             wait: float = 1.0, budget: float = math.inf, rounds: int = 4,
             passes: int = 1) -> Generator[Request, object, Thought]:
    """``think`` for an expert the kernel is itself running, which has no kernel to ask (§76.6).

    An asking taken is yielded to whoever runs the expert; what is sent back is noted for this step under the
    type asked for and the concepts are asked again from the first, as ``think`` does with a way to ask. After
    ``rounds`` askings a further one is not yielded and nothing is put out. The thought returned counts every
    time a concept was asked, what the concepts cost and how many askings were yielded; what serving them cost
    is the runner's to count. Each asking of the concepts has its own ``passes``.
    """
    if type(rounds) is not int or rounds < 0:
        raise ValueError("rounds must be a nonnegative integer")
    asked, spent, asks = 0, 0.0, 0
    while True:
        thought = think(concepts, memory, thresholds, wait=wait, budget=budget - spent, passes=passes)
        asked, spent = asked + thought.asked, spent + thought.cost
        out = thought.out
        if not isinstance(out, Request) or asks == rounds:
            return replace(thought, out=None if isinstance(out, Request) else out, asked=asked, cost=spent, asks=asks)
        memory.scratch.note(out.type_id, (yield out), life=1)
        asks += 1
