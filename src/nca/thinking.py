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

Asking while unsure (§76.13). What an asking is worth is read from recorded askings: where it was asked, how
sure the best answer was there, where it led and how sure the best answer was then (``Askings``). Under a
charge for an asking, a share of what a right answer is worth, the worth of each asking at each place follows
from the last places backwards (``Worth``). ``Unsure`` is the concept that holds an inquiry's answers and,
beside them, the open asking worth most with that worth as its chance, so the frame's own rule decides between
answering and asking, and which to ask. Each asking may be charged its own share, so askings that different
experts serve at different costs are weighed in the one rule (§76.15). The record need not be given: ``Learning`` begins with whatever
record it is handed, an empty one too, and ``Unsure`` keeps it by the askings the frame itself makes, each
asking tried a stated number of times where it stands (§76.14). The same askings say whether the stated
chances are right, since a right chance of the answer held does not drift when more is learned: ``Sureness``
reads from them, with no word on what was right, how far too sure or too modest the chances are (§76.16).

Nothing here says what a hypothesis is, how a chance is come by, what a risk is the risk of, what a place or
an asking stands for, or what is asked about.
"""
from __future__ import annotations

import math
from collections.abc import Callable, Generator, Hashable, Mapping, Sequence
from dataclasses import dataclass, field, replace
from typing import Literal, Protocol

import numpy as np

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


@dataclass(frozen=True)
class Standing:
    """How an inquiry stands (§76.13): the chance of each of its answers, and what they are (left ``None``, an
    answer is its place among the chances); the place it has come to, which is whatever says what has been asked
    so far; and for each asking still open there, under whatever names it, the request that makes it."""

    chances: Sequence[float]
    place: Hashable
    open: Mapping[Hashable, Request] = field(default_factory=dict)
    hypotheses: Sequence[object] | None = None


class Inquiry(Protocol):
    """Whatever is being found out: it says how it stands, and takes what an asking gave (``None`` where the
    kernel could give nothing), after which it stands at a later place."""

    def standing(self) -> Standing: ...

    def take(self, asking: Hashable, answer: object) -> None: ...


class Askings:
    """Recorded askings (§76.13): how often, at a place with the best chance in one band, an asking led to a
    later place with the best chance in another band. ``bands`` equal bands divide the chances from nought to
    one. ``counts`` holds, for each place, asking and later place, a table with a row for each band before and
    a column for each band after; it may be given whole, as a record made elsewhere."""

    def __init__(self, bands: int = 50,
                 counts: Mapping[tuple[Hashable, Hashable, Hashable], np.ndarray] | None = None) -> None:
        if type(bands) is not int or bands < 1:
            raise ValueError("the chances must be divided into a positive number of bands")
        self.bands = bands
        self.counts: dict[tuple[Hashable, Hashable, Hashable], np.ndarray] = {}
        for key, table in (counts or {}).items():
            table = np.array(table, dtype=np.float64)
            if len(key) != 3 or table.shape != (bands, bands) or not np.isfinite(table).all() or (table < 0).any():
                raise ValueError("a record of askings needs a square table of counts for a place, an asking and a later place")
            self.counts[key] = table
        self.noted = 0

    def band(self, chance: float | np.ndarray) -> np.ndarray:
        """The band a chance falls in; of several chances, each one's."""
        chance = np.asarray(chance, dtype=np.float64)
        if not ((chance >= 0.0) & (chance <= 1.0)).all():
            raise ValueError("a chance must lie between nought and one")
        return np.minimum((chance * self.bands).astype(np.int64), self.bands - 1)

    def note(self, place: Hashable, chance: float | np.ndarray, asking: Hashable, then: Hashable,
             after: float | np.ndarray) -> None:
        """Record that at ``place``, with the best chance ``chance``, ``asking`` was asked and led to the place
        ``then`` with the best chance ``after``; or as many such askings as there are chances given."""
        before, later = np.atleast_1d(self.band(chance)), np.atleast_1d(self.band(after))
        if before.shape != later.shape or before.ndim != 1:
            raise ValueError("each asking recorded needs one chance before and one after")
        table = self.counts.setdefault((place, asking, then), np.zeros((self.bands, self.bands)))
        np.add.at(table, (before, later), 1.0)
        self.noted += len(before)

    def seen(self, place: Hashable, chance: float, asking: Hashable) -> float:
        """How many times ``asking`` was recorded at ``place`` with the best chance in the band of ``chance``."""
        band = int(self.band(chance))
        return float(sum(table[band].sum() for (at, asked, _), table in self.counts.items() if at == place and asked == asking))

    def worth(self, charge: float | Mapping[Hashable, float]) -> Worth:
        """What the askings recorded so far are worth where each is charged the share ``charge``, or each its
        own share where ``charge`` gives one for each asking."""
        return Worth(self, charge)


class Worth:
    """What each recorded asking is worth at each place, under a charge for each asking (§76.13, §76.15).

    An asking is charged a share of what is to be had (§76.11) and is worth, less that, what is had at the place
    it leads to: there the larger of the best answer's chance and what the best asking is worth. ``charge`` is
    one share for every asking, or gives each recorded asking its own, whoever serves it. Where the stated
    chances are known to be off, ``read`` gives for a stated chance the chance it stands for, and the record,
    kept by stated chances, is valued by those.
    A band's chance is taken at its middle. An asking never recorded at a place with the chance in a band has
    no worth there, which is not the same as being worth nothing. Recorded askings that lead back to a place
    they came from have no last place to start from and are refused."""

    def __init__(self, askings: Askings, charge: float | Mapping[Hashable, float],
                 read: Callable[[np.ndarray], np.ndarray] | None = None) -> None:
        own = dict(charge) if isinstance(charge, Mapping) else None
        if not all(0.0 <= share <= 1.0 for share in ([charge] if own is None else own.values())):
            raise ValueError("the charge for an asking must be a share between nought and one")
        if own is not None and any(asking not in own for _, asking, _ in askings.counts):
            raise ValueError("each recorded asking needs its charge")
        self.bands, self.charge = askings.bands, float(charge) if own is None else own
        middle = (np.arange(self.bands) + 0.5) / self.bands
        if read is not None:  # the stated chance of a band read as the chance it stands for (§76.16)
            middle = np.asarray(read(middle), dtype=np.float64)
        self._answer = middle
        ways: dict[Hashable, dict[Hashable, list[tuple[Hashable, np.ndarray]]]] = {}
        for (place, asking, then), table in askings.counts.items():
            ways.setdefault(place, {}).setdefault(asking, []).append((then, table))
        self._had: dict[Hashable, np.ndarray] = {}
        self._rows: dict[Hashable, dict[Hashable, np.ndarray]] = {}
        for start in ways:
            if start in self._had:
                continue
            path, onward = [start], {start}
            while path:
                place = path[-1]
                ahead = [then for later in ways.get(place, {}).values() for then, _ in later if then not in self._had]
                if any(then in onward for then in ahead):
                    raise ValueError("recorded askings lead back to a place they came from")
                if ahead:
                    path.append(ahead[0])
                    onward.add(ahead[0])
                    continue
                rows, had = {}, middle.copy()
                for asking, later in ways.get(place, {}).items():
                    seen = sum(table.sum(1) for _, table in later)
                    whole = sum(table @ self._had[then] for then, table in later)
                    rows[asking] = np.where(seen > 0, (1.0 - self.charged(asking)) * whole / np.maximum(seen, 1.0), np.nan)
                    had = np.fmax(had, rows[asking])
                self._rows[place], self._had[place] = rows, had
                onward.discard(path.pop())

    def charged(self, asking: Hashable) -> float:
        """The share ``asking`` is charged."""
        return self.charge[asking] if isinstance(self.charge, dict) else self.charge

    def _band(self, chance: float) -> int:
        if not 0.0 <= chance <= 1.0:
            raise ValueError("a chance must lie between nought and one")
        return min(int(chance * self.bands), self.bands - 1)

    def of(self, place: Hashable, chance: float, asking: Hashable) -> float | None:
        """What ``asking`` is worth at ``place`` where the best answer has the chance ``chance``; ``None`` where
        it was never recorded there with such a chance."""
        row = self._rows.get(place, {}).get(asking)
        worth = math.nan if row is None else float(row[self._band(chance)])
        return None if math.isnan(worth) else worth

    def had(self, place: Hashable, chance: float) -> float:
        """What is had at ``place`` with the best answer at ``chance``: the larger of that chance and what the
        best asking recorded there is worth."""
        best = [worth for asking in self._rows.get(place, {}) if (worth := self.of(place, chance, asking)) is not None]
        return max([float(chance), *best])


class Sureness:
    """How sure to be, learned from one's own askings with no word on what was right (§76.16).

    It keeps, for each asking served, the stated chance of the answer held before and the stated chance of
    that same answer after. A chance that is right does not drift. Read as σ(logit(c) / t), the chances drift
    by some mean with some standard error under each power t. The power used is the one nearest one, between
    a half and two, under which that mean is within ``errors`` standard errors of nought: one while the
    askings do not contradict the chances as stated, then only as far out as they force, and the root itself
    as the askings grow. ``shrink`` takes that power to an exponent, for a host that found even the root to
    lie too far out."""

    GRID = np.geomspace(1.0, 2.0, 41)

    def __init__(self, shrink: float = 1.0, errors: float = 2.0) -> None:
        if not 0.0 <= shrink <= 1.0:
            raise ValueError("the shrink must lie between nought and one")
        if not errors >= 0.0:
            raise ValueError("a drift is held against a number of standard errors that is not negative")
        self.shrink, self.errors = float(shrink), float(errors)
        self.before: list[float] = []
        self.after: list[float] = []

    def note(self, before: float, after: float) -> None:
        """Keep that the answer held at the chance ``before`` stood at ``after`` once an asking was answered."""
        if not (0.0 <= before <= 1.0 and 0.0 <= after <= 1.0):
            raise ValueError("a chance must lie between nought and one")
        self.before.append(before)
        self.after.append(after)

    @staticmethod
    def _read(chance: np.ndarray, power: float) -> np.ndarray:
        odds = np.log(np.clip(chance, 1e-9, 1.0 - 1e-9) / np.clip(1.0 - chance, 1e-9, 1.0))
        return 1.0 / (1.0 + np.exp(-odds / power))

    def drift(self, power: float = 1.0) -> tuple[float, float]:
        """The mean change of the kept chances over an asking, read through ``power``, and its standard error."""
        change = self._read(np.array(self.after), power) - self._read(np.array(self.before), power)
        return float(change.mean()), float(change.std() / math.sqrt(len(change)))

    def power(self) -> float:
        """The power nearest one that the askings kept do not contradict; one where fewer than two are kept."""
        if len(self.before) < 2:
            return 1.0
        first, error = self.drift()
        if abs(first) <= self.errors * error:
            return 1.0
        last, power = first, 1.0
        for step in self.GRID[1:]:  # a rising chance is too modest: the power lies below one
            before, power = power, float(1.0 / step if first > 0.0 else step)
            mean, error = self.drift(power)
            if mean * first <= 0.0:  # past the root: the root itself, and no further
                return float(before * (power / before) ** (last / (last - mean)))
            if abs(mean) <= self.errors * error:
                return power
            last = mean
        return power

    def reading(self) -> Callable[[np.ndarray], np.ndarray]:
        """The reading of stated chances as things stand: each chance read, as that of one answer against the
        rest, through the shrunk power."""
        power = self.power() ** self.shrink
        return lambda chance: self._read(np.asarray(chance, dtype=np.float64), power)


class Learning:
    """A record that grows by the askings made from it (§76.14).

    The worth it gives is that of the record as it stands, worked out again once ``every`` further askings
    have been recorded. An asking recorded fewer than ``tries`` times at a place with the best chance in a
    band is tried: made whatever the answers' chances, which by 76.14 gives up at most the charge. Given a
    ``Sureness``, the askings also teach how sure to be (§76.16), and the worth is of the chances so read."""

    def __init__(self, askings: Askings, charge: float | Mapping[Hashable, float], tries: int, every: int = 1,
                 sure: Sureness | None = None) -> None:
        if type(tries) is not int or tries < 0:
            raise ValueError("tries must be a nonnegative number of askings")
        if type(every) is not int or every < 1:
            raise ValueError("the worth is worked out again after a positive number of askings")
        self.askings, self.charge, self.tries, self.every, self.sure = askings, charge, tries, every, sure
        self.read: Callable[[np.ndarray], np.ndarray] | None = None
        self._worth, self._at = self._worked(), askings.noted

    def _worked(self) -> Worth:
        self.read = None if self.sure is None else self.sure.reading()  # one reading for the worth and the answers
        return Worth(self.askings, self.charge, self.read)

    @property
    def worth(self) -> Worth:
        if self.askings.noted - self._at >= self.every:
            self._worth, self._at = self._worked(), self.askings.noted
        return self._worth

    def untried(self, place: Hashable, chance: float, asking: Hashable) -> bool:
        """Whether ``asking`` is still to be tried at ``place`` with the best chance at ``chance``."""
        return self.askings.seen(place, chance, asking) < self.tries


class Unsure:
    """Asking while unsure, as a concept (§76.13).

    Asked, it gives the inquiry's answers with their chances and, beside them, the open asking worth most where
    the best answer stands, as one more hypothesis with that worth as its chance. The frame's rule then takes
    an answer or the asking, whichever has the greater chance, and an answer where they tie. Where the asking
    was taken and served, its answer is on the scratchpad under the type asked for when the concept is next
    asked: the concept hands it to the inquiry and lets go of the note.

    Given a ``Learning`` in place of a worth, the concept also keeps the record (§76.14): each asking served
    is recorded with how the inquiry stood before it and after, unless the kernel gave nothing; and an open
    asking still to be tried is offered with the chance one, so that it is made. Where the learning holds a
    ``Sureness`` and the inquiry says the chance of each of at least two answers, the chance of the answer held
    is followed over each asking, and the answers are given at the chances so read (§76.16); the record is kept
    by the chances as stated."""

    def __init__(self, inquiry: Inquiry, worth: Worth | Learning, cost: float = 0.0) -> None:
        self.inquiry, self.worth, self.cost = inquiry, worth, cost
        self._asked: tuple[Hashable, Request, Hashable, float, int, int] | None = None

    def think(self, memory: WorkingMemory) -> Opinion:
        learning = self.worth if isinstance(self.worth, Learning) else None
        answered = None
        if self._asked is not None and self._asked[1].type_id in memory.scratch:
            asking, request, place, before, held, among = self._asked
            answer = memory.scratch.read(request.type_id)
            self.inquiry.take(asking, answer)
            memory.scratch.drop(request.type_id)
            answered = (place, before, asking, held, among) if answer is not None else None
        self._asked = None
        standing = self.inquiry.standing()
        chances = [float(chance) for chance in standing.chances]
        hypotheses = list(range(len(chances)) if standing.hypotheses is None else standing.hypotheses)
        if not chances or len(hypotheses) != len(chances):
            raise ValueError("a standing needs one chance for each of at least one answer")
        best = max(chances)
        if learning is not None and answered is not None:
            place, before, asking, held, among = answered
            learning.askings.note(place, before, asking, standing.place, best)
            if learning.sure is not None and among == len(chances) > 1:
                learning.sure.note(before, chances[held])
        worth = self.worth if learning is None else learning.worth
        offers = [(value, asking) for asking in standing.open if (value := worth.of(standing.place, best, asking)) is not None]
        if learning is not None:
            untried = [asking for asking in standing.open if learning.untried(standing.place, best, asking)]
            if untried:  # the one recorded least there is tried first
                asking = min(untried, key=lambda one: learning.askings.seen(standing.place, best, one))
                offers = [(1.0, asking)]
        if offers:
            value, asking = max(offers, key=lambda offer: offer[0])
            self._asked = (asking, standing.open[asking], standing.place, best, chances.index(best), len(chances))
        if learning is not None and learning.read is not None:
            chances = [float(chance) for chance in learning.read(np.array(chances))]
        if offers:
            chances.append(value)
            hypotheses.append(standing.open[asking])
        return Opinion(chances, hypotheses)
