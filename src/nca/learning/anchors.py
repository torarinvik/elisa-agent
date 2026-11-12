"""Probes placed by what a scene holds, for a learner that chooses what to look at (THEORY §54.6).

A scene is values at positions, each position a tuple of integers. A value
whose positions form one solid block, every position of the box around them,
marks a place in the scene, an anchor: the block's least corner. A value at a
single position is the smallest such block. A probe reads the value at a fixed
position, the value at an offset from an anchor, or which way one anchor lies
from another along an axis. Where the anchor's value is absent or does not
form one block, or the position read is outside the scene, the reading is
``None``.

The values and their meanings are the caller's. No value is named as an
anchor: every value may be tried as one, and a learner finds which are worth
looking from.
"""

from collections.abc import Hashable, Mapping, Sequence
from itertools import permutations, product
from math import prod
from typing import Any

Position = tuple[int, ...]
Probe = tuple[Hashable, ...]


class Scene:
    """Values at positions, and where each value that forms one solid block is."""

    def __init__(self, cells: Mapping[Position, Hashable]) -> None:
        self.cells = cells
        self._blocks: dict[Hashable, Position | None] | None = None

    def where(self, value: Hashable) -> Position | None:
        """The least corner of the solid block ``value`` forms, or ``None`` if it is absent or forms none."""
        if self._blocks is None:
            boxes: dict[Hashable, list[Any]] = {}
            for position, held in self.cells.items():
                box = boxes.get(held)
                if box is None:
                    boxes[held] = [1, position, position]
                else:
                    box[0] += 1
                    box[1] = tuple(map(min, box[1], position))
                    box[2] = tuple(map(max, box[2], position))
            self._blocks = {held: least if count == prod(high - low + 1 for low, high in zip(least, most, strict=True))
                            else None for held, (count, least, most) in boxes.items()}
        return self._blocks.get(value)


def at(position: Position) -> Probe:
    """The value at a fixed position."""
    return ("at", position)


def beside(value: Hashable, offset: Position) -> Probe:
    """The value at ``offset`` from the corner of the block ``value`` forms."""
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
