"""Bounded, context-scoped acquisition history over host-provisioned memory.

The host must reserve this producer/type pair for trusted history writers.
Context identifiers version the distribution, loss/agreement, key semantics
and deterministic predictor family; Python cannot verify that meaning.
Eviction may lose optimization, but never resets the backend's spending clock.
SQLite durability and fresh UUIDs are backend/identity assumptions.
"""

from __future__ import annotations

import json
import uuid
from collections import OrderedDict
from dataclasses import asdict
from fractions import Fraction

from nca.abi import Contract, TypeId
from nca.memory import MemoryBackend, MemoryRecord
from nca.objects import Ref, canonical
from nca.retention.screening import ScreenResult


class AcquisitionHistory:
    """Serialized host history with a bounded incremental refusal index.

    Each lookup scans at most ``entries`` new records and caches at most that
    many refusals. A lagging or evicted index can miss a refusal and retry;
    retries always reserve fresh spending positions. No implementation or
    training failure is remembered as an impossible contract. Never restore
    an older database snapshot into the same statistical experiment. All tests
    in one confidence family must share one non-rewinding backend; a new
    database starts a new budget. Contexts also version any implicit slot
    bindings or other inputs affecting the task distribution.
    """

    def __init__(self, memory: MemoryBackend, *, context: str, type_id: TypeId,
                 producer: str, entries: int) -> None:
        if not context or not producer:
            raise ValueError("history needs nonempty context and producer identifiers")
        if isinstance(entries, bool) or not isinstance(entries, int) or entries < 1:
            raise ValueError("history index capacity must be a positive integer")
        self.memory, self.context = memory, context
        self.type_id, self.producer, self.entries = type_id, producer, entries
        self._cursor = 0
        self._index: OrderedDict[bytes, Ref] = OrderedDict()

    def key(self, contract: Contract, tolerance: float, confidence: float,
            screening: Fraction | None) -> bytes:
        return canonical({"version": 1, "context": self.context, "contract": asdict(contract),
                          "tolerance": float(tolerance).hex(),
                          "confidence": float(confidence).hex(), "screening": str(screening)})

    def _index_refusal(self, key: bytes, reference: Ref) -> None:
        self._index[key] = reference
        self._index.move_to_end(key)
        while len(self._index) > self.entries:
            self._index.popitem(last=False)

    def refused(self, key: bytes) -> bool:
        for position, reference in self.memory.scan(after=self._cursor, limit=self.entries):
            self._cursor = position
            try:
                record = self.memory.get(reference)
            except KeyError:  # Concurrent eviction can only lose an optimization.
                continue
            if record.type_id != self.type_id or record.producer != self.producer:
                continue
            data = json.loads(record.payload)
            if data.get("kind") == "refusal":
                self._index_refusal(bytes.fromhex(data["key"]), reference)
        reference = self._index.get(key)
        if reference is None:
            return False
        try:
            self.memory.get(reference)
        except KeyError:
            del self._index[key]
            return False
        self._index.move_to_end(key)
        return True

    def reserve(self, key: bytes) -> tuple[int, Ref]:
        """Commit before sampling: a crash consumes, rather than reuses, a level."""
        payload = canonical({"kind": "attempt", "key": key.hex(), "nonce": uuid.uuid4().hex})
        position, reference = self.memory.append_position(
            MemoryRecord(self.type_id, payload, self.producer, 0.0))
        return position - 1, reference

    def remember(self, key: bytes, ticket: Ref, result: ScreenResult) -> Ref:
        if not result.rejected:
            raise ValueError("only a rejecting screen can establish a refusal")
        payload = canonical({"kind": "refusal", "key": key.hex(), "cases": result.cases,
                             "pairs": result.pairs, "threshold": result.threshold,
                             "level": str(result.level)})
        reference = self.memory.append(MemoryRecord(
            self.type_id, payload, self.producer, 0.0, parents=(ticket,)))
        self._index_refusal(key, reference)
        return reference
