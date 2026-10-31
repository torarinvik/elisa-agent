"""Cognitive ABI: typed contracts, module manifests, and the message envelope."""

from __future__ import annotations

import itertools
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

    @property
    def ref(self) -> str:
        return f"{self.module_id}@{self.version}"


_message_ids = itertools.count()


@dataclass(frozen=True)
class Message:
    type_id: TypeId
    payload: Any
    producer: str
    """Manifest ref of the producing module, or ``"input"`` for task inputs."""
    parents: tuple[str, ...] = ()
    message_id: str = field(default_factory=lambda: f"msg:{next(_message_ids)}")
