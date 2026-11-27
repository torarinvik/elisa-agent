"""What an asker reads from its own askings and from names: how sure to be, whom to trust, and how far its
record promises too much (§76.16, §76.17, §76.19)."""
from __future__ import annotations

import math
import random
from collections.abc import Callable, Hashable, Mapping, Sequence

import numpy as np


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
