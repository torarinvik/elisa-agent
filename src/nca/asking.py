"""Asking while unsure: what an asking is worth, a record of one's own askings, how sure to be, whom to trust, an
asking made only so often and what an inquiry is promised (§76.13 to §76.19).

What an asking is worth is read from recorded askings: where it was asked, how sure the best answer was there,
where it led and how sure the best answer was then (``Askings``). Under a charge for an asking, a share of what a
right answer is worth, the worth of each asking at each place follows from the last places backwards (``Worth``).
``Unsure`` is the concept that holds an inquiry's answers and, beside them, the open asking worth most with that
worth as its chance, so the frame's own rule decides between answering and asking, and which to ask. Each asking
may be charged its own share, so askings that different experts serve at different costs are weighed in the one
rule (§76.15). The record need not be given: ``Learning`` begins with whatever record it is handed, an empty one
too, and ``Unsure`` keeps it by the askings the frame itself makes, each asking tried a stated number of times
where it stands (§76.14). The same askings say whether the stated chances are right, since a right chance of the
answer held does not drift when more is learned: ``Sureness`` reads from them, with no word on what was right, how
far too sure or too modest the chances are (§76.16). Where an inquiry says what each of its sources said, and one
source is taken as naming what was right, ``Trust`` makes the chances from those words and learns from the names
how far each source is to be believed (§76.17). An asking that may be made only so often is kept to its limit by
a price added to its charge where the rule weighs it (§76.18). ``Promise`` keeps what inquiries were promised
against what they came to hold, which says how far a record promises too much (§76.19).

The frame these are concepts of is ``nca.thinking``. Nothing here says what a place or an asking stands for, who
serves an asking, or what is being found out.
"""
from __future__ import annotations

import math
import random
from collections.abc import Callable, Hashable, Mapping, Sequence
from dataclasses import dataclass, field
from typing import Protocol

import numpy as np

from nca.abi import Request
from nca.memory.working import WorkingMemory
from nca.thinking import Opinion


@dataclass(frozen=True)
class Standing:
    """How an inquiry stands (§76.13): the chance of each of its answers, and what they are (left ``None``, an
    answer is its place among the chances); the place it has come to, which is whatever says what has been asked
    so far; and for each asking still open there, under whatever names it, the request that makes it. ``said``
    is what each source has said so far, a number for every answer, larger for an answer it speaks for: given
    to an asker that holds a ``Trust``, the chances are made from it and ``chances`` is not read (§76.17)."""

    chances: Sequence[float]
    place: Hashable
    open: Mapping[Hashable, Request] = field(default_factory=dict)
    hypotheses: Sequence[object] | None = None
    said: Mapping[Hashable, Sequence[float]] | None = None


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
    kept by stated chances, is valued by those. ``price`` gives, for an asking kept to a limit, what is added
    to its charge where the rule weighs it (§76.18): ``of`` is the worth so weighed, and ``had`` is what
    following that rule is paid at the charges alone.
    A band's chance is taken at its middle. An asking never recorded at a place with the chance in a band has
    no worth there, which is not the same as being worth nothing. Recorded askings that lead back to a place
    they came from have no last place to start from and are refused."""

    def __init__(self, askings: Askings, charge: float | Mapping[Hashable, float],
                 read: Callable[[np.ndarray], np.ndarray] | None = None, price: Mapping[Hashable, float] | None = None) -> None:
        own = dict(charge) if isinstance(charge, Mapping) else None
        if not all(0.0 <= share <= 1.0 for share in ([charge] if own is None else own.values())):
            raise ValueError("the charge for an asking must be a share between nought and one")
        if own is not None and any(asking not in own for _, asking, _ in askings.counts):
            raise ValueError("each recorded asking needs its charge")
        if not all(cost >= 0.0 for cost in (price or {}).values()):
            raise ValueError("the price of an asking is not negative")
        self.bands, self.charge, self.price = askings.bands, float(charge) if own is None else own, dict(price or {})
        self.read = read
        middle = (np.arange(self.bands) + 0.5) / self.bands
        if read is not None:  # the stated chance of a band read as the chance it stands for (§76.16)
            middle = np.asarray(read(middle), dtype=np.float64)
        self._answer = middle
        ways: dict[Hashable, dict[Hashable, list[tuple[Hashable, np.ndarray]]]] = {}
        for (place, asking, then), table in askings.counts.items():
            ways.setdefault(place, {}).setdefault(asking, []).append((then, table))
        self._had: dict[Hashable, np.ndarray] = {}  # what is paid at the charges, following the rule
        self._weighed: dict[Hashable, np.ndarray] = {}  # what the rule weighs: the same with the prices charged too
        self._rows: dict[Hashable, dict[Hashable, np.ndarray]] = {}
        self._paid: dict[Hashable, dict[Hashable, np.ndarray]] = {}
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
                rows, costs, weighed, had = {}, {}, middle.copy(), middle.copy()
                for asking, later in ways.get(place, {}).items():
                    seen = sum(table.sum(1) for _, table in later)
                    share, dearer = 1.0 - self.charged(asking), max(0.0, 1.0 - self.charged(asking) - self.price.get(asking, 0.0))
                    whole = sum(table @ self._weighed[then] for then, table in later)
                    paid = sum(table @ self._had[then] for then, table in later)
                    rows[asking] = np.where(seen > 0, dearer * whole / np.maximum(seen, 1.0), np.nan)
                    costs[asking] = share * paid / np.maximum(seen, 1.0)
                    had = np.where(rows[asking] > weighed, costs[asking], had)
                    weighed = np.fmax(weighed, rows[asking])
                self._rows[place], self._paid[place], self._had[place], self._weighed[place] = rows, costs, had, weighed
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
        """What is had at ``place`` with the best answer at ``chance``: the larger of that chance, as read, and
        what the best asking recorded there is worth; where askings have a price, what is paid at the charges
        by taking whichever of them the rule, weighing the prices too, takes."""
        best = [(worth, asking) for asking in self._rows.get(place, {}) if (worth := self.of(place, chance, asking)) is not None]
        worth, asking = max(best, key=lambda one: one[0], default=(0.0, None))
        answer = float(chance) if self.read is None else float(self.read(np.array(chance)))
        return answer if worth <= answer else float(self._paid[place][asking][self._band(chance)])


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


class Trust:
    """How far each source's word is believed, learned from one source taken as naming what was right (§76.17).

    The chance of an answer is the pool of what the sources said of it, each at its weight: proportional to
    the exponential of the weighted sum. A source begins at the weight ``start``; at nought nobody is trusted
    and every answer is as likely as every other. ``namer`` is the asking, and the source, whose answer names
    what was right; its word is believed to the stated share ``believed`` and its weight is not learned. Each
    name is kept with what the other sources had said at a standing, and the weights are fitted to the names
    by likelihood, pulled toward ``start`` with the strength of ``pull`` names, again after ``every`` further
    names. ``coin`` is the share of inquiries named whatever their chances, tossed apart from everything, so
    that every standing they passed is a fair draw."""

    def __init__(self, namer: Hashable, believed: float, start: float = 0.0, pull: float = 1.0, coin: float = 0.0,
                 every: int = 1, seed: int = 0) -> None:
        if not 0.0 < believed < 1.0:
            raise ValueError("the namer's word is believed to a share strictly between nought and one")
        if not pull > 0.0:
            raise ValueError("the pull toward the starting weight must be positive")
        if not 0.0 <= coin <= 1.0:
            raise ValueError("the coin names a share of inquiries between nought and one")
        if type(every) is not int or every < 1:
            raise ValueError("the weights are fitted again after a positive number of names")
        self.namer, self.believed, self.start, self.pull = namer, float(believed), float(start), float(pull)
        self.coin, self.every, self.learns = float(coin), every, True
        self.weights: dict[Hashable, float] = {}
        self.said: list[dict[Hashable, tuple[float, ...]]] = []
        self.named: list[int] = []
        self._fitted, self._tosses = 0, random.Random(seed)

    def tossed(self) -> bool:
        """Whether the inquiry now beginning is one the coin names."""
        return self.learns and self._tosses.random() < self.coin

    def chances(self, said: Mapping[Hashable, Sequence[float]]) -> list[float]:
        """The chance of each answer, from what each source said."""
        words = [np.asarray(word, dtype=np.float64) for word in said.values()]
        if not words or any(word.shape != words[0].shape or word.ndim != 1 or not len(word) for word in words):
            raise ValueError("each source says one number for each of the same answers")
        score = np.zeros(len(words[0]))
        for source, word in zip(said, words):
            if source == self.namer:
                score += math.log(self.believed * max(1, len(word) - 1) / (1.0 - self.believed)) * word
            else:
                score += self.weights.get(source, self.start) * word
        score = np.exp(score - score.max())
        return [float(chance) for chance in score / score.sum()]

    def note(self, said: Mapping[Hashable, Sequence[float]], named: int) -> None:
        """Keep that where the sources had said ``said``, the answer ``named`` was named as right."""
        if not self.learns:
            return
        self.said.append({source: tuple(float(x) for x in word) for source, word in said.items() if source != self.namer})
        self.named.append(named)
        if len(self.named) - self._fitted >= self.every:
            self.fit()

    def fit(self) -> None:
        """Fit the weights to the names kept."""
        self._fitted = len(self.named)
        sources = sorted({source for said in self.said for source in said}, key=repr)
        if not sources:
            return
        answers = len(next(word for said in self.said for word in said.values()))
        words = np.zeros((len(self.said), len(sources), answers))
        for i, said in enumerate(self.said):
            for s, source in enumerate(sources):
                if source in said:
                    words[i, s] = said[source]
        named = np.array(self.named)
        weights = np.array([self.weights.get(source, self.start) for source in sources])
        for _ in range(25):  # Newton's steps on a likelihood with one summit
            score = np.einsum("s,isk->ik", weights, words)
            chance = np.exp(score - score.max(1, keepdims=True))
            chance /= chance.sum(1, keepdims=True)
            mean = np.einsum("ik,isk->is", chance, words)
            slope = (words[np.arange(len(named)), :, named] - mean).sum(0) - self.pull * (weights - self.start)
            spread = np.einsum("ik,isk,itk->st", chance, words, words) - mean.T @ mean
            step = np.linalg.solve(spread + self.pull * np.eye(len(sources)), slope)
            weights = weights + step
            if np.abs(step).max() < 1e-6:
                break
        self.weights = dict(zip(sources, (float(weight) for weight in weights)))

    def fixed(self) -> Trust:
        """The trust as it stands, as one that keeps no further names and tosses no coin."""
        kept = Trust(self.namer, self.believed, self.start, self.pull)
        kept.weights, kept.learns = dict(self.weights), False
        return kept


class Learning:
    """A record that grows by the askings made from it (§76.14).

    The worth it gives is that of the record as it stands, worked out again once ``every`` further askings
    have been recorded. An asking recorded fewer than ``tries`` times at a place with the best chance in a
    band is tried: made whatever the answers' chances, which by 76.14 gives up at most the charge; ``tries``
    is one number for every asking or gives each asking its own, an asking left out being tried never. Given
    a ``Sureness``, the askings also teach how sure to be (§76.16), and the worth is of the chances so read.

    ``limit`` gives, for an asking that may be made only so often, how many times an inquiry in the mean
    (§76.18). Such an asking has a price, nought to begin with, added to its charge where the record is
    valued; after each inquiry the price moves by ``step`` times the askings made in it less the limit, never
    below nought. With a limit each asking needs its own charge."""

    def __init__(self, askings: Askings, charge: float | Mapping[Hashable, float], tries: int | Mapping[Hashable, int],
                 every: int = 1, sure: Sureness | None = None, limit: Mapping[Hashable, float] | None = None,
                 step: float = 0.02) -> None:
        if any(type(count) is not int or count < 0 for count in (tries.values() if isinstance(tries, Mapping) else [tries])):
            raise ValueError("tries must be a nonnegative number of askings")
        if type(every) is not int or every < 1:
            raise ValueError("the worth is worked out again after a positive number of askings")
        if limit and (not isinstance(charge, Mapping) or any(not rate >= 0.0 or asking not in charge for asking, rate in limit.items())):
            raise ValueError("a limited asking needs its own charge and a limit that is not negative")
        if not step > 0.0:
            raise ValueError("the price moves by a positive step")
        self.askings, self.charge, self.tries, self.every, self.sure = askings, charge, tries, every, sure
        self.limit, self.step = dict(limit or {}), float(step)
        self.price: dict[Hashable, float] = dict.fromkeys(self.limit, 0.0)
        self._made: dict[Hashable, int] = dict.fromkeys(self.limit, 0)
        self._open = False
        self.read: Callable[[np.ndarray], np.ndarray] | None = None
        self._worth, self._at = self._worked(), askings.noted

    def _worked(self) -> Worth:
        self.read = None if self.sure is None else self.sure.reading()  # one reading for the worth and the answers
        return Worth(self.askings, self.charge, self.read, self.price)

    def begun(self) -> None:
        """An inquiry begins: the prices move by what the last one made of each limited asking."""
        if self._open:
            for asking, rate in self.limit.items():
                self.price[asking] = max(0.0, self.price[asking] + self.step * (self._made[asking] - rate))
                self._made[asking] = 0
        self._open = True

    def made(self, asking: Hashable) -> None:
        """An asking was made and served in the inquiry in hand."""
        if asking in self._made:
            self._made[asking] += 1

    @property
    def worth(self) -> Worth:
        if self.askings.noted - self._at >= self.every:
            self._worth, self._at = self._worked(), self.askings.noted
        return self._worth

    def untried(self, place: Hashable, chance: float, asking: Hashable) -> bool:
        """Whether ``asking`` is still to be tried at ``place`` with the best chance at ``chance``."""
        tries = self.tries.get(asking, 0) if isinstance(self.tries, Mapping) else self.tries
        return tries > 0 and self.askings.seen(place, chance, asking) < tries


class Promise:
    """What inquiries were promised against what they came to hold (§76.19).

    At its first place an inquiry is promised what following the rule from there is paid. A promise that is
    right does not drift: in the mean it is what the last place holds, the chance of the answer given there,
    less the charges paid on the way. Both are the asker's own figures, so the mean difference over the
    inquiries made says, with no word on what was right, how far the record promises too much. An inquiry in
    which an asking was made otherwise than by the rule is left out."""

    def __init__(self) -> None:
        self.inquiries, self._over = 0, 0.0
        self._open: tuple[float, float] | None = None

    def begun(self, promised: float) -> None:
        """An inquiry begins, promised ``promised``; the one before it is counted as it last stood."""
        if self._open is not None:
            self.inquiries, self._over = self.inquiries + 1, self._over + self._open[0] - self._open[1]
        self._open = (promised, promised)

    def holds(self, held: float) -> None:
        """The inquiry in hand now holds ``held``: the chance of its best answer less the charges paid so far."""
        if self._open is not None:
            self._open = (self._open[0], held)

    def void(self) -> None:
        """The inquiry in hand is left out."""
        self._open = None

    @property
    def over(self) -> float:
        """By how much, in the mean of the inquiries counted, the promise stood above what was then held."""
        return self._over / self.inquiries if self.inquiries else 0.0

    def of(self, promised: float) -> float:
        """``promised`` less what promises have so far stood too high."""
        return promised - self.over


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
    by the chances as stated.

    Given a ``Trust`` and an inquiry that says what its sources said, the chances are the trust's (§76.17).
    Where the namer was asked and served, its answer is kept as a name for the standing it was asked at, or
    for every standing passed where the trust's coin chose this inquiry; and an inquiry the coin chose is not
    answered before the namer, while open, has been asked.

    Given a ``Promise``, what the worth promises at the inquiry's first place is kept against what each later
    place holds with the charges of the askings served taken off (§76.19); an inquiry in which an asking was
    tried, or which the coin chose, is left out."""

    def __init__(self, inquiry: Inquiry, worth: Worth | Learning, cost: float = 0.0, trust: Trust | None = None,
                 promise: Promise | None = None) -> None:
        self.inquiry, self.worth, self.cost, self.trust, self.promise = inquiry, worth, cost, trust, promise
        self._left: float | None = None  # the share left after the charges of the askings served so far
        self._asked: tuple[Hashable, Request, Hashable, float, int, int] | None = None
        self._tossed = trust is not None and trust.tossed()
        self._passed: list[Mapping[Hashable, Sequence[float]]] = []
        if isinstance(worth, Learning):
            worth.begun()

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
        if self.trust is not None and standing.said is not None:
            if answered is not None and answered[2] == self.trust.namer and self.trust.namer in standing.said:
                named = int(np.argmax(standing.said[self.trust.namer]))
                for said in (self._passed if self._tossed else self._passed[-1:]):
                    self.trust.note(said, named)
            self._passed.append(standing.said)
            chances = self.trust.chances(standing.said)
        hypotheses = list(range(len(chances)) if standing.hypotheses is None else standing.hypotheses)
        if not chances or len(hypotheses) != len(chances):
            raise ValueError("a standing needs one chance for each of at least one answer")
        best = max(chances)
        if learning is not None and answered is not None:
            place, before, asking, held, among = answered
            learning.askings.note(place, before, asking, standing.place, best)
            learning.made(asking)
            if learning.sure is not None and among == len(chances) > 1:
                learning.sure.note(before, chances[held])
        worth = self.worth if learning is None else learning.worth
        offers = [(value, asking) for asking in standing.open if (value := worth.of(standing.place, best, asking)) is not None]
        forced = self._tossed
        if learning is not None:
            untried = [asking for asking in standing.open if learning.untried(standing.place, best, asking)]
            if untried:  # the one recorded least there is tried first
                asking = min(untried, key=lambda one: learning.askings.seen(standing.place, best, one))
                offers, forced = [(1.0, asking)], True
        shown = chances if worth.read is None else [float(chance) for chance in worth.read(np.array(chances))]
        if self._tossed and self.trust.namer in standing.open and all(value <= max(shown) for value, _ in offers):
            offers = [(1.0, self.trust.namer)]  # an inquiry the coin chose is named before it is answered
        if self.promise is not None:
            if self._left is None:
                self._left = 1.0
                self.promise.begun(worth.had(standing.place, best))
            elif answered is not None:
                self._left *= 1.0 - worth.charged(answered[2])
            if forced:
                self.promise.void()
            self.promise.holds(max(shown) * self._left)
        if offers:
            value, asking = max(offers, key=lambda offer: offer[0])
            self._asked = (asking, standing.open[asking], standing.place, best, chances.index(best), len(chances))
        chances = list(shown)
        if offers:
            chances.append(value)
            hypotheses.append(standing.open[asking])
        return Opinion(chances, hypotheses)
