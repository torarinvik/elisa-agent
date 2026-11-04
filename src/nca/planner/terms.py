"""Typed plan terms and structural input/output inspection."""
from __future__ import annotations

from collections.abc import Iterator, Sequence
from dataclasses import dataclass
from functools import lru_cache
import itertools
from typing import Union

from nca.abi import Binding, Contract, Module, TypeId, seq_type
from nca.native import load


# The table cache is a resource policy, not a planning limit. Larger tables use
# the same uncached reference enumeration. The cell budget bounds retained tuple
# slots, including empty argument groups, rather than only assignment count.
_ASSIGNMENT_CELLS = 4096
_ASSIGNMENT_NATIVE = load("assignment")


def _reference_choices(size: int, count: int) -> list[tuple[int, ...]]:
    return sorted(itertools.product(range(count), repeat=size),
                  key=lambda choice: (max((choice.count(j) for j in range(count)), default=0),
                                      choice))


@lru_cache(maxsize=64)
def _assignment_table(ordered: tuple[int, ...], count: int) -> tuple[tuple[frozenset[int], ...], ...]:
    if _ASSIGNMENT_NATIVE is None:
        choices = _reference_choices(len(ordered), count)
    else:
        codes = _ASSIGNMENT_NATIVE.order(count, len(ordered), _ASSIGNMENT_CELLS)
        if len(codes) != count ** len(ordered):
            raise RuntimeError("Elisa assignment kernel returned an incomplete table")
        choices = []
        for code in codes:
            digits = [0] * len(ordered)
            for position in range(len(ordered) - 1, -1, -1):
                code, digits[position] = divmod(code, count)
            choices.append(tuple(digits))
    empty: frozenset[int] = frozenset()
    result = []
    for choice in choices:
        groups = [set() for _ in range(count)]
        for position, argument in zip(ordered, choice, strict=True):
            groups[argument].add(position)
        result.append(tuple(frozenset(group) if group else empty for group in groups))
    return tuple(result)


def assignments(required: frozenset[int], count: int) -> Iterator[tuple[frozenset[int], ...]]:
    """Distribute required positions, most evenly first and lexically within ties.

    Small complete tables are built with Elisa when available and cached; larger
    ones use the same uncached reference order. Cached outputs are immutable.
    """
    if not required:
        yield (frozenset(),) * count
        return
    if count <= 0:
        return
    if count == 1:
        yield (required,)
        return
    ordered = tuple(sorted(required))
    choices = 1
    for _ in ordered:
        if choices > _ASSIGNMENT_CELLS // count // count:
            break
        choices *= count
    else:
        yield from _assignment_table(ordered, count)
        return
    for choice in _reference_choices(len(ordered), count):
        yield tuple(frozenset(r for r, c in zip(ordered, choice) if c == j) for j in range(count))


@dataclass(frozen=True)
class Given:
    """An available input: the one at ``position`` among the available types,
    or the first of type ``type_id`` when ``position`` is ``None``."""

    type_id: TypeId
    position: int | None = None


@dataclass(frozen=True)
class Apply:
    module: Module
    args: tuple["Plan", ...]
    slots: tuple["Plan", ...] = ()
    """One plan per slot of the module's contract, each from the slot's inputs."""
    binding: Binding = ()
    """The instance of a polymorphic contract that is applied (THEORY §2.1)."""

    @property
    def contract(self) -> Contract:
        """The applied instance of the module's contract."""
        return self.module.manifest.contract.instance(self.binding)


@dataclass(frozen=True)
class Map:
    """Run ``body`` on each element (of type ``element``) of ``source``."""

    element: TypeId
    body: "Plan"
    source: "Plan"


Plan = Union[Given, Apply, Map]


def uses(node: Plan, available: Sequence[TypeId]) -> frozenset[int]:
    """The positions of the available inputs ``node`` reads (THEORY §20.8). A
    ``map`` body reads only its element, so a ``map`` uses what its source uses."""
    if isinstance(node, Given):
        position = available.index(node.type_id) if node.position is None else node.position
        return frozenset((position,))
    if isinstance(node, Apply):
        return frozenset().union(*(uses(a, available) for a in node.args))
    return uses(node.source, available)


def slot_goals(contract: Contract) -> list[tuple[tuple[TypeId, ...], TypeId, frozenset[int]]]:
    """Each slot of ``contract`` as a sub-goal: its inputs, its output, and the
    positions of the inputs every filling must use."""
    return [(inputs, output, frozenset(contract.relevant[i]) if i < len(contract.relevant)
             else frozenset())
            for i, (inputs, output) in enumerate(contract.slots)]


def output_type(node: Plan) -> TypeId:
    if isinstance(node, Given):
        return node.type_id
    if isinstance(node, Apply):
        return node.contract.output
    return seq_type(output_type(node.body))
