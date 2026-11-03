"""Immutable typed episodic records and canonical transport encoding."""
from __future__ import annotations

import hashlib
import json
import math
from dataclasses import dataclass

from nca.abi import TypeId, canonical_type
from nca.objects import Ref, canonical


class MemoryFull(RuntimeError):
    """Appending would exceed the persistent logical-byte capacity."""


@dataclass(frozen=True)
class MemoryRecord:
    type_id: TypeId
    payload: bytes
    producer: str
    observed_at: float
    parents: tuple[Ref, ...] = ()
    confidence: float | None = None
    supersedes: Ref | None = None

    def __post_init__(self) -> None:
        if canonical_type(self.type_id) != self.type_id:
            raise ValueError("memory type identifier must be canonical")
        if type(self.payload) is not bytes:
            raise TypeError("memory payload must be immutable bytes")
        if not isinstance(self.producer, str) or not self.producer:
            raise ValueError("memory producer identity must be nonempty")
        if not math.isfinite(self.observed_at):
            raise ValueError("observation time must be finite")
        if self.confidence is not None and not (
            math.isfinite(self.confidence) and 0 <= self.confidence <= 1
        ):
            raise ValueError("confidence must be absent or finite in [0, 1]")
        object.__setattr__(self, "parents", tuple(self.parents))
        if any(not isinstance(parent, str) for parent in self.parents):
            raise TypeError("parent references must be strings")
        if self.supersedes is not None and self.supersedes not in self.parents:
            raise ValueError("superseded record must be a parent")

    def encode(self) -> bytes:
        """Canonical transport encoding; no interpretation of payload contents."""
        return canonical({"type": self.type_id, "payload": self.payload.hex(),
                          "producer": self.producer, "observed_at": self.observed_at,
                          "parents": self.parents, "confidence": self.confidence,
                          "supersedes": self.supersedes})

    @property
    def ref(self) -> Ref:
        return "sha256:" + hashlib.sha256(self.encode()).hexdigest()


def _decode(encoded: bytes) -> MemoryRecord:
    data = json.loads(encoded)
    record = MemoryRecord(data["type"], bytes.fromhex(data["payload"]), data["producer"],
                          data["observed_at"], tuple(data["parents"]), data["confidence"],
                          data["supersedes"])
    if record.encode() != encoded:
        raise ValueError("memory record encoding is not canonical")
    return record
