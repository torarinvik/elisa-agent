"""Looking at a scene within a budget, remembering where things were (THEORY §54.7).

A scene is read one position at a time, and a frame may be read at no more
than ``budget`` positions. A ``Gaze`` spends a frame's looks in three parts.
It first looks again for each block it remembers: where the block would be had
it moved as it last did, or as far along another axis or the other way, then
where it was, and then in widening rings around that place. It keeps back the
looks its caller will ask for. The rest are scattered over positions in a
fixed shuffled order that carries on from frame to frame, and a look that
lands on a value is followed back along each axis to the block's least corner.
Once the scatter has been through the whole scene, it is cut to a share
``idle`` of the budget in frames where every block found before is found
again: there is then nothing known to be missing.

The side of a block is measured when it is first found, and is not given. A
block of side ``w`` holds a position whose coordinates are all multiples of
``w``, so the rings step by ``w``, and a block that is missing is looked for
at those positions of the scene before the scatter (THEORY §54.11). A pass
over them that does not find it forgets the side.

A value found as one block no larger than ``reach`` is an anchor, as in
``anchors.Scene``. A value found at two corners in one frame, or running
further than ``reach``, is not looked for again. Nothing checks that a block is
solid or the only one beyond what the looks happened to show.

The ``Glimpse`` of a frame answers the readings of ``anchors.read``: a position
looked at before in the frame is free, a new one costs a look, and none is
answered once the budget is spent. A frame that is studied is read whole,
beyond the budget, and its anchors are then those of the whole scene: what is
learned from the frame does not depend on what the looks had found in it.
"""

from collections.abc import Callable, Hashable, Sequence
from itertools import permutations, product
from random import Random

from .anchors import Scene

Position = tuple[int, ...]
Look = Callable[[Position], Hashable]


class _Spent(Exception):
    """The frame's looks for finding things are used up."""


class Glimpse:
    """What one frame has shown so far, and the places of the anchors found in it."""

    def __init__(self, look: Look, budget: int, positions: Sequence[Position] = ()) -> None:
        self._look, self.budget, self._positions = look, budget, positions
        self._whole: Scene | None = None
        self.seen: dict[Position, Hashable] = {}
        self.places: dict[Hashable, Position] = {}
        self.looks = self.studied = 0
        self.studying = False

    def study(self) -> None:
        """Read the whole frame, beyond the budget; its anchors are from then on the whole scene's."""
        self.studying = True
        self._whole = Scene({position: self.get(position) for position in self._positions})
        self.studying = False

    @property
    def cells(self) -> "Glimpse":
        return self

    def get(self, position: Position, default: Hashable = None) -> Hashable:
        """The value at ``position``, looking if it was not looked at and a look is left."""
        if position in self.seen:
            return self.seen[position]
        if self.studying or self._whole is not None:
            self.studied += 1
        elif self.looks >= self.budget:
            return default
        else:
            self.looks += 1
        value = self.seen[position] = self._look(position)
        return value

    def where(self, value: Hashable) -> Position | None:
        """The least corner of the block ``value`` was found to form, or ``None``."""
        return self.places.get(value) if self._whole is None else self._whole.where(value)


class Gaze:
    """Where to look in each frame of a scene of the given shape, and what is remembered between frames."""

    def __init__(self, shape: Sequence[int], budget: int, *, reach: int, idle: float = 0.1,
                 seed: int | str = 0) -> None:
        if budget < 0 or reach < 1 or any(side < 1 for side in shape) or not 0 <= idle <= 1:
            raise ValueError("a budget is non-negative, a reach and the sides of a scene positive, a share within one")
        self.shape, self.budget, self.reach, self.idle = tuple(shape), budget, reach, idle
        self._order = list(product(*(range(side) for side in shape)))
        Random(f"gaze:{seed}").shuffle(self._order)
        self._rings: dict[int, list[Position]] = {}
        self._lattices: dict[int, list[Position]] = {}
        self._cursor = self._scattered = self._swept = self._passed = 0
        self.sides: dict[Hashable, int] = {}
        self.anchored: set[Hashable] = set()
        self.known: dict[Hashable, Position] = {}
        self.moved: dict[Hashable, Position] = {}
        self.ignored: set[Hashable] = set()
        self.frames = self.looks = 0

    def frame(self, look: Look, reserve: int = 0) -> Glimpse:
        """Look at a new frame, keeping ``reserve`` looks back for the caller's own readings."""
        glimpse = Glimpse(look, self.budget, self._order)
        spare = self.budget - reserve

        def see(position: Position) -> Hashable:
            if position not in glimpse.seen and glimpse.looks >= spare:
                raise _Spent
            return glimpse.get(position)

        remembered, self.known = self.known, {}
        try:
            for value, corner in remembered.items():
                found = self._again(see, value, corner)
                if found is not None:
                    self._measure(see, value, found)
                    self.moved[value] = tuple(new - old for new, old in zip(found, corner, strict=True))
                    self.known[value] = glimpse.places[value] = found
                else:
                    self.moved.pop(value, None)
            self._sweep(see, glimpse)
            settled = self._scattered >= len(self._order) and not self._missing()
            for _ in range(int(self.idle * self.budget) if settled else len(self._order)):
                position = self._order[self._cursor]
                self._cursor = (self._cursor + 1) % len(self._order)
                self._scattered += 1
                self._meet(see, glimpse, position)
        except _Spent:
            for value in remembered.keys() - self.known.keys():
                self.moved.pop(value, None)
        self.frames += 1
        return glimpse

    def spent(self) -> float:
        """Looks a frame so far, counting the caller's readings of frames already handed over."""
        return self.looks / self.frames if self.frames else 0.0

    def close(self, glimpse: Glimpse) -> None:
        """Count a frame's looks once its readings are done."""
        self.looks += glimpse.looks

    def _missing(self) -> set[Hashable]:
        """The anchors found before that this frame has not shown."""
        return self.anchored - self.ignored - self.known.keys()

    def _sweep(self, see: Callable[[Position], Hashable], glimpse: Glimpse) -> None:
        """Look for missing blocks of known side at the positions one of that side must hold."""
        missing = self._missing()
        if not missing:
            self._passed = 0
        if not missing or not missing <= self.sides.keys():
            return
        side = min(self.sides[value] for value in missing)
        if side not in self._lattices:
            self._lattices[side] = [position for position in self._order if not any(part % side for part in position)]
        lattice = self._lattices[side]
        for _ in lattice:
            if not self._missing():
                return
            self._meet(see, glimpse, lattice[self._swept % len(lattice)])
            self._swept += 1
            self._passed += 1
        if self._passed >= len(lattice):
            self._passed = 0
            for value in self._missing():
                self.sides.pop(value, None)

    def _meet(self, see: Callable[[Position], Hashable], glimpse: Glimpse, position: Position) -> None:
        """Look at a position and follow a value found there to its block."""
        value = see(position)
        if value is None or value in self.ignored:
            return
        corner = self._corner(see, position, value)
        if corner is None or self.known.get(value, corner) != corner:
            self.ignored.add(value)
            self.known.pop(value, None)
            glimpse.places.pop(value, None)
        else:
            self.known[value] = glimpse.places[value] = corner
            self.anchored.add(value)
            self._measure(see, value, corner)

    def _measure(self, see: Callable[[Position], Hashable], value: Hashable, corner: Position) -> None:
        """Note the least run of a block from its corner along an axis, once."""
        if value in self.sides:
            return
        runs = []
        for axis in range(len(corner)):
            place = list(corner)
            while place[axis] - corner[axis] <= self.reach and see(tuple(place)) == value:
                place[axis] += 1
            runs.append(place[axis] - corner[axis])
        self.sides[value] = min(runs)

    def _near(self, side: int) -> list[Position]:
        """The offsets, nearest first, at which a block of ``side`` that moved no further than the reach is met."""
        if side not in self._rings:
            steps = range(-(self.reach // side) * side, self.reach + side, side)
            self._rings[side] = sorted((offset for offset in product(steps, repeat=len(self.shape)) if any(offset)),
                                       key=lambda offset: (max(map(abs, offset)), sum(map(abs, offset)), offset))
        return self._rings[side]

    def _again(self, see: Callable[[Position], Hashable], value: Hashable, corner: Position) -> Position | None:
        """Where a remembered block is now, or ``None`` if it is not near where it was."""
        if value in self.ignored:
            return None
        moved = self.moved.get(value, ())
        turned = dict.fromkeys(tuple(sign * step for step in turn) for turn in (moved, *permutations(moved))
                               for sign in (1, -1))
        guesses = [tuple(place + step for place, step in zip(corner, offset, strict=True))
                   for offset in (*(turned if any(moved) else ()), (0,) * len(corner),
                                  *self._near(self.sides.get(value, 1)))]
        for position in guesses:
            if see(position) == value:
                found = self._corner(see, position, value)
                if found is None:
                    self.ignored.add(value)
                return found
        return None

    def _corner(self, see: Callable[[Position], Hashable], position: Position, value: Hashable) -> Position | None:
        """The least corner of the run of ``value`` through ``position``, or ``None`` if it runs past the reach."""
        corner = list(position)
        for axis in range(len(corner)):
            for _ in range(self.reach + 1):
                corner[axis] -= 1
                if see(tuple(corner)) != value:
                    corner[axis] += 1
                    break
            else:
                return None
        return tuple(corner)
