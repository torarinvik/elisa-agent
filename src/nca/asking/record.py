"""The record of askings and what it says each is worth (§76.13, §76.15, §76.18, §76.20, §76.21)."""
from __future__ import annotations

import math
from collections.abc import Callable, Hashable, Iterable, Mapping, Sequence
from dataclasses import dataclass, field
from typing import Protocol

import numpy as np

from nca.abi import Request


class _Over:
    def __repr__(self) -> str:
        return "OVER"


OVER = _Over()
WITHIN = 1e-9
"""How far two amounts may lie apart and count as the same where a record is valued."""
"""The place an inquiry is recorded as led to when it ended while an asking was being served (§76.21)."""


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
    a column for each band after; it may be given whole, as a record made elsewhere. ``answers`` holds, for
    each place and band, how many answers given there were judged and what share they were paid (§76.20)."""

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
        self.answers: dict[Hashable, np.ndarray] = {}
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

    def judged(self, place: Hashable, chance: float, paid: float) -> None:
        """Record that an answer given at ``place`` with the best chance ``chance`` was paid the share ``paid``."""
        if not 0.0 <= paid <= 1.0:
            raise ValueError("an answer is paid a share between nought and one")
        self.answers.setdefault(place, np.zeros((self.bands, 2)))[int(self.band(chance))] += (1.0, paid)
        self.noted += 1

    def seen(self, place: Hashable, chance: float, asking: Hashable) -> float:
        """How many times ``asking`` was recorded at ``place`` with the best chance in the band of ``chance``."""
        band = int(self.band(chance))
        return float(sum(table[band].sum() for (at, asked, _), table in self.counts.items() if at == place and asked == asking))

    def visits(self, place: Hashable, chance: float) -> float:
        """How many times an inquiry stood at ``place`` with the best chance in the band of ``chance`` and
        asked or gave an answer that was judged."""
        band = int(self.band(chance))
        given = float(self.answers[place][band, 0]) if place in self.answers else 0.0
        return given + float(sum(table[band].sum() for (at, _, _), table in self.counts.items() if at == place))

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
    following that rule is paid at the charges alone. Where answers given at a place were judged, answering
    there is had at the share they were paid, pulled toward the chance with the weight of ``pull`` answers
    (§76.20).
    A band's chance is taken at its middle. An asking never recorded at a place with the chance in a band has
    no worth there, which is not the same as being worth nothing. Recorded askings may lead back to a place
    they came from (§76.22): every place begins at what answering there is had and the step of §76.13 is
    swept, at most ``sweeps`` times, until nothing moves by more than ``WITHIN``, which gives what is had by
    asking any finite number of times. An asking the record values no higher than answering in its band is
    never worth more than the answer at the chance in hand, so one that leads back to where the inquiry
    stood and shows nothing new is not taken.

    Given ``told``, an option that takes more must be told apart to be taken (§76.23): ``offer`` walks the
    answer and then the open askings in the order given, the plainer first, and leaves the one it holds for
    the next only where that is worth more by over ``told`` standard errors of the difference, each counted
    from the scatter of what was had where the asking led, or of what the answers judged were paid."""

    def __init__(self, askings: Askings, charge: float | Mapping[Hashable, float],
                 read: Callable[[np.ndarray], np.ndarray] | None = None, price: Mapping[Hashable, float] | None = None,
                 pull: float = 8.0, sweeps: int = 1000, told: float | None = None) -> None:
        own = dict(charge) if isinstance(charge, Mapping) else None
        if not all(0.0 <= share <= 1.0 for share in ([charge] if own is None else own.values())):
            raise ValueError("the charge for an asking must be a share between nought and one")
        if own is not None and any(asking not in own for _, asking, _ in askings.counts):
            raise ValueError("each recorded asking needs its charge")
        if not all(cost >= 0.0 for cost in (price or {}).values()):
            raise ValueError("the price of an asking is not negative")
        if not pull > 0.0:
            raise ValueError("judged answers are pulled toward the chance with a positive weight")
        if type(sweeps) is not int or sweeps < 1:
            raise ValueError("the record is swept a positive number of times")
        if told is not None and not told >= 0.0:
            raise ValueError("options are told apart by a number of standard errors that is not negative")
        self.told = told
        self.bands, self.charge, self.price = askings.bands, float(charge) if own is None else own, dict(price or {})
        self.read, self.pull, self._judged = read, float(pull), askings.answers
        middle = (np.arange(self.bands) + 0.5) / self.bands
        if read is not None:  # the stated chance of a band read as the chance it stands for (§76.16)
            middle = np.asarray(read(middle), dtype=np.float64)
        self._middle = middle
        self._leaves = {place: (table[:, 1] + pull * middle) / (table[:, 0] + pull) for place, table in askings.answers.items()}
        ways: dict[Hashable, dict[Hashable, tuple[np.ndarray, list[tuple[Hashable, np.ndarray]]]]] = {}
        for (place, asking, then), table in askings.counts.items():
            ways.setdefault(place, {}).setdefault(asking, (np.zeros(self.bands), []))[1].append((then, table))
        for asked in ways.values():  # the counts of each asking as the shares of where it led
            for asking, (seen, later) in asked.items():
                seen += sum(table.sum(1) for _, table in later)
                asked[asking] = (seen, [(then, table / np.maximum(seen, 1.0)[:, None]) for then, table in later])
        order, met = [], set()  # each place after the places its askings lead to, as far as none leads back
        for start in ways:
            path = [] if start in met else [(start, iter([then for _, later in ways[start].values() for then, _ in later]))]
            met.add(start)
            while path:
                place, ahead = path[-1]
                then = next((then for then in ahead if then in ways and then not in met), None)
                if then is None:
                    order.append(path.pop()[0])
                else:
                    met.add(then)
                    path.append((then, iter([further for _, later in ways[then].values() for further, _ in later])))
        rank = {place: at for at, place in enumerate(order)}
        back = any(rank.get(then, -1) >= rank[place] for place in order for _, later in ways[place].values() for then, _ in later)
        shares = {asking: 1.0 - self.charged(asking) for asked in ways.values() for asking in asked}
        dearer = {asking: max(0.0, share - self.price.get(asking, 0.0)) for asking, share in shares.items()}
        self._weighed: dict[Hashable, np.ndarray] = {}  # what the rule weighs: the charges and the prices taken off
        self._had: dict[Hashable, np.ndarray] = {}  # what is paid at the charges alone, following that rule
        self._rows: dict[Hashable, dict[Hashable, np.ndarray]] = {place: {} for place in order}
        self._paid: dict[Hashable, dict[Hashable, np.ndarray]] = {place: {} for place in order}
        taken: dict[Hashable, np.ndarray] = {}

        def swept(held: dict[Hashable, np.ndarray], rows: dict[Hashable, dict[Hashable, np.ndarray]], share: dict[Hashable, float],
                  unseen: float, one: Callable[[Hashable], np.ndarray]) -> None:
            for _ in range(sweeps if back else 1):
                moved = 0.0
                for place in order:
                    for asking, (seen, later) in ways[place].items():
                        whole = share[asking] * sum(table @ held.get(then, self._leaf(then)) for then, table in later)
                        rows[place][asking] = np.where(seen > 0, whole, unseen)
                    new = one(place)
                    moved = max(moved, float(np.abs(new - held.get(place, new + 1.0)).max()))
                    held[place] = new
                if moved <= WITHIN:
                    break

        def largest(place: Hashable) -> np.ndarray:
            best, which = self._leaf(place).copy(), np.full(self.bands, -1)
            for at, row in enumerate(self._rows[place].values()):
                which = np.where(row > best, at, which)
                best = np.fmax(best, row)
            taken[place] = which
            return best

        def following(place: Hashable) -> np.ndarray:
            paid = self._leaf(place).copy()
            for at, cost in enumerate(self._paid[place].values()):
                paid = np.where(taken[place] == at, cost, paid)
            return paid

        swept(self._weighed, self._rows, dearer, math.nan, largest)
        swept(self._had, self._paid, shares, 0.0, following)
        self._wide: dict[Hashable, dict[Hashable, np.ndarray]] = {place: {} for place in order}
        for place in order if told is not None else ():  # the squared standard error of each asking's worth
            for asking, (seen, later) in ways[place].items():
                mean = np.nan_to_num(self._rows[place][asking])
                square = dearer[asking] ** 2 * sum(table @ self._weighed.get(then, self._leaf(then)) ** 2 for then, table in later)
                among = np.clip(mean, 0.0, 1.0)  # with few counts the scatter is pulled toward the widest there is
                scatter = (seen * np.maximum(square - mean ** 2, 0.0) + pull * among * (1.0 - among)) / (seen + pull)
                self._wide[place][asking] = scatter / np.maximum(seen, 1.0)

    def _leaf(self, place: Hashable) -> np.ndarray:
        return self._leaves.get(place, self._middle)

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
        row, band = self._rows.get(place, {}).get(asking), self._band(chance)
        worth = math.nan if row is None else float(row[band])
        if math.isnan(worth):
            return None
        return min(worth, self.answer(place, chance)) if worth <= self._leaf(place)[band] + WITHIN else worth

    def answer(self, place: Hashable, chance: float) -> float:
        """What answering at ``place`` with the best answer at ``chance`` is had: the chance as read, or where
        answers given there were judged, the share they were paid pulled toward it."""
        stated = float(chance) if self.read is None else float(self.read(np.array(chance)))
        given, paid = self._judged[place][self._band(chance)] if place in self._judged else (0.0, 0.0)
        return float((paid + self.pull * stated) / (given + self.pull))

    def had(self, place: Hashable, chance: float) -> float:
        """What is had at ``place`` with the best answer at ``chance``: the larger of that chance, as read, and
        what the best asking recorded there is worth; where askings have a price, what is paid at the charges
        by taking whichever of them the rule, weighing the prices too, takes."""
        offer, answer = self.offer(place, chance, self._rows.get(place, ())), self.answer(place, chance)
        return answer if offer is None or offer[0] <= answer else float(self._paid[place][offer[1]][self._band(chance)])

    def offer(self, place: Hashable, chance: float, open: Iterable[Hashable]) -> tuple[float, Hashable] | None:  # noqa: A002
        """The asking among ``open`` to set beside the answers at ``place`` with the best answer at ``chance``,
        with its worth: the one worth most, the first of equals; or, where options must be told apart, the
        last in the order given that was told apart from the one held before it, the answer first. ``None``
        where no asking open was recorded there or none was told apart."""
        known = [(worth, asking) for asking in open if (worth := self.of(place, chance, asking)) is not None]
        if self.told is None or not known:
            return max(known, key=lambda one: one[0], default=None)
        band, held = self._band(chance), self.answer(place, chance)
        given = float(self._judged[place][band, 0]) if place in self._judged else 0.0
        wide, taken = held * (1.0 - held) / (given + self.pull), None
        for worth, asking in known:
            if worth - held > self.told * math.sqrt(wide + self._wide[place][asking][band]):
                held, wide, taken = worth, float(self._wide[place][asking][band]), asking
        return None if taken is None else (held, taken)
