"""Probes placed by what a scene holds, for a learner that chooses what to look at (THEORY §54.6).

A scene is values at positions, each position a tuple of integers. A value
that stands at exactly one position of a scene marks a place in it, an anchor.
A probe reads the value at a fixed position, the value at an offset from an
anchor, or which way one anchor lies from another along an axis. Where the
anchor's value is absent or stands at several positions, or the position read
is outside the scene, the reading is ``None``.

The values and their meanings are the caller's. No value is named as an
anchor: every value may be tried as one, and a learner finds which are worth
looking from.
"""

from collections.abc import Hashable, Mapping, Sequence
from itertools import permutations, product

Position = tuple[int, ...]
Probe = tuple[Hashable, ...]


class Scene:
    """Values at positions, and where each value that stands alone is."""

    def __init__(self, cells: Mapping[Position, Hashable]) -> None:
        self.cells = cells
        self._alone: dict[Hashable, Position | None] | None = None

    def where(self, value: Hashable) -> Position | None:
        """The one position holding ``value``, or ``None`` if none or several do."""
        if self._alone is None:
            self._alone = {}
            for position, held in self.cells.items():
                self._alone[held] = None if held in self._alone else position
        return self._alone.get(value)


def at(position: Position) -> Probe:
    """The value at a fixed position."""
    return ("at", position)


def beside(value: Hashable, offset: Position) -> Probe:
    """The value at ``offset`` from where ``value`` stands alone."""
    return ("beside", value, offset)


def toward(origin: Hashable, goal: Hashable, axis: int) -> Probe:
    """Which way ``goal`` lies from ``origin`` along ``axis``: -1, 0 or 1."""
    return ("toward", origin, goal, axis)


def pool(values: Sequence[Hashable], reach: int, dimensions: int) -> tuple[Probe, ...]:
    """Every offset within ``reach`` of every value, and every way from one value to another."""
    offsets = [offset for offset in product(range(-reach, reach + 1), repeat=dimensions) if any(offset)]
    return (*(beside(value, offset) for value in values for offset in offsets),
            *(toward(origin, goal, axis) for origin, goal in permutations(values, 2) if values.index(origin)
              < values.index(goal) for axis in range(dimensions)))


def read(scene: Scene, probe: Probe) -> Hashable:
    """One probe's reading of a scene."""
    if probe[0] == "at":
        return scene.cells.get(probe[1])
    origin = scene.where(probe[1])
    if origin is None:
        return None
    if probe[0] == "beside":
        return scene.cells.get(tuple(place + step for place, step in zip(origin, probe[2], strict=True)))
    goal = scene.where(probe[2])
    if goal is None:
        return None
    return (goal[probe[3]] > origin[probe[3]]) - (goal[probe[3]] < origin[probe[3]])
