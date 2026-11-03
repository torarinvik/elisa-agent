"""Typed episodic storage interfaces and the default durable SQLite backend (§43).

Payload codecs and retrieval strategies belong to external experts. Capacity
counts logical encoded bytes, not database pages/indexes or resident memory.
The host provisions/closes the store; this is not an OS isolation boundary.
"""
from nca.memory.records import (
    MemoryFull as MemoryFull,
    MemoryRecord as MemoryRecord,
    _decode as _decode,
)
from nca.memory.backend import MemoryBackend as MemoryBackend
from nca.memory.sqlite import MemoryStore as MemoryStore
