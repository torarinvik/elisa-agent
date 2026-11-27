"""Asking while unsure as a concept of the thinking frame, and the record that grows by it (§76.13, §76.14)."""
from __future__ import annotations

from collections.abc import Callable, Hashable, Mapping, Sequence

import numpy as np

from nca.abi import Request
from nca.asking.readings import Promise, Sureness, Trust
from nca.asking.record import OVER, Askings, Inquiry, Worth
from nca.memory.working import WorkingMemory
from nca.thinking import Opinion


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
    tried, or which the coin chose, is left out.

    A host that learns what the answer given was paid says so with ``judged``, and one whose inquiry ended
    while an asking was being served with ``over``; a learning keeps both (§76.20, §76.21)."""

    def __init__(self, inquiry: Inquiry, worth: Worth | Learning, cost: float = 0.0, trust: Trust | None = None,
                 promise: Promise | None = None) -> None:
        self.inquiry, self.worth, self.cost, self.trust, self.promise = inquiry, worth, cost, trust, promise
        self._left: float | None = None  # the share left after the charges of the askings served so far
        self._stood: tuple[Hashable, float] | None = None  # where the inquiry last stood, and its best chance
        self._asked: tuple[Hashable, Request, Hashable, float, int, int] | None = None
        self._tossed = trust is not None and trust.tossed()
        self._passed: list[Mapping[Hashable, Sequence[float]]] = []
        if isinstance(worth, Learning):
            worth.begun()

    def judged(self, paid: float) -> None:
        """The answer given where the inquiry last stood was paid the share ``paid``."""
        if isinstance(self.worth, Learning) and self._stood is not None:
            self.worth.askings.judged(*self._stood, paid)

    def over(self, paid: float = 0.0) -> None:
        """The inquiry ended while an asking was being served, with the share ``paid`` had."""
        if isinstance(self.worth, Learning) and self._asked is not None:
            self.worth.askings.note(self._asked[2], self._asked[3], self._asked[0], OVER, paid)
            self.worth.askings.judged(OVER, paid, paid)
            self.worth.made(self._asked[0])
        self._asked = None

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
        self._stood = (standing.place, best)
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
        held = worth.answer(standing.place, best)  # the best answer at what answering here is had (§76.20)
        shown = [min(chance, held) for chance in shown]
        shown[chances.index(best)] = held
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
