"""Cognitive ABI: typed contracts, module manifests, and the message envelope."""

from __future__ import annotations

import itertools
from collections.abc import Callable, Mapping
from dataclasses import dataclass, field
from typing import Any

TypeId = str
"""Versioned semantic type, e.g. ``"digit.distribution.v1"``.

Two values are compatible only if their type ids are equal; byte shape alone
never implies compatibility.
"""


def seq_type(element: TypeId) -> TypeId:
    """The type of finite sequences of ``element``."""
    return f"seq[{element}]"


def elem_type(type_id: TypeId) -> TypeId | None:
    """The element type if ``type_id`` is a sequence type, else ``None``."""
    if type_id.startswith("seq[") and type_id.endswith("]"):
        return type_id[4:-1]
    return None


@dataclass(frozen=True)
class Contract:
    inputs: tuple[TypeId, ...]
    output: TypeId


@dataclass(frozen=True)
class Manifest:
    module_id: str
    version: str
    contract: Contract
    cost: float = 1.0
    """Cost of one invocation (for example, floating-point operations)."""

    @property
    def ref(self) -> str:
        return f"{self.module_id}@{self.version}"


@dataclass(frozen=True)
class SequenceDemand:
    """Demand on a sequence: what is read of element ``i`` of a length-``n`` sequence."""

    element: Callable[[int, int], "Demand"]


Demand = frozenset[str] | SequenceDemand | None
"""What a consumer reads of a value: ``None`` everything, a set of named fields,
or a per-element demand for sequences. The empty set means nothing is read."""

NOTHING: frozenset[str] = frozenset()


@dataclass(frozen=True)
class Request:
    """Asks the kernel: "produce a value of ``type_id`` from these inputs, without
    me". Returned by a module to delegate its output, or yielded by a module's
    generator to obtain a sub-result and continue."""

    type_id: TypeId
    inputs: Mapping[TypeId, Any]
    provisional: Any = None
    """The requester's own best answer, used if the request turns out irrelevant."""


_message_ids = itertools.count()


@dataclass(frozen=True)
class Message:
    type_id: TypeId
    payload: Any
    producer: str
    """Manifest ref of the producing module, or ``"input"`` for task inputs."""
    parents: tuple[str, ...] = ()
    message_id: str = field(default_factory=lambda: f"msg:{next(_message_ids)}")
