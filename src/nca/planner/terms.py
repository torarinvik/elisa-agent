"""Typed plan terms and structural input/output inspection."""
from __future__ import annotations

from collections.abc import Sequence
from dataclasses import dataclass
from typing import Union

from nca.abi import Binding, Contract, Module, TypeId, seq_type


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
