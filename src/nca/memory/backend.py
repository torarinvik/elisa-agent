"""Structural interface for host-provisioned episodic storage backends."""
from __future__ import annotations

from typing import Protocol

from nca.memory.records import MemoryRecord
from nca.objects import Ref


class MemoryBackend(Protocol):
    """Episodic storage contract, independent of database implementation.

    Implementations must mediate reads and writes through the configured effects,
    verify record identities, enforce provenance and persistent byte admission,
    and serialize append transactions. Duplicate appends are idempotent. Missing
    references raise KeyError; invalid records or inconsistent identities fail.
    These semantic obligations require backend validation: structural typing alone
    does not establish them. The host trusts and provisions the backend.
    """

    @property
    def read_effect(self) -> str:
        """Host-selected authority required for get, scan and usage."""
        ...

    @property
    def write_effect(self) -> str:
        """Host-selected authority required for append."""
        ...

    def get(self, reference: Ref) -> MemoryRecord:
        """Return the exact immutable record bound to a verified reference."""
        ...

    def append(self, record: MemoryRecord) -> Ref:
        """Atomically admit a record and its logical byte charge, or change nothing."""
        ...

    def remove(self, reference: Ref) -> int:
        """Atomically delete a record that no record names as a parent, freeing
        and returning its logical byte charge."""
        ...

    def usage(self) -> tuple[int, int]:
        """Return logical encoded bytes and record count in one snapshot."""
        ...

    def scan(self, *, after: int = 0, limit: int) -> tuple[tuple[int, Ref], ...]:
        """Bounded append-order enumeration with strictly increasing positions.

        Positions start above zero. Later commits receive higher positions;
        nonnegative after/limit arguments follow the SQLite backend contract.
        """
        ...

    def close(self) -> None:
        """Host lifecycle operation, after outstanding calls finish."""
        ...
