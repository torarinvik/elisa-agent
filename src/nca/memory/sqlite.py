"""Durable SQLite backend for permission-checked episodic memory with removal."""
from __future__ import annotations

import hashlib
import sqlite3
from pathlib import Path

from nca.effects import require_effect
from nca.memory.records import MemoryFull, MemoryRecord, _decode
from nca.objects import Ref


class MemoryStore:
    """A host-provisioned SQLite store. Reads/appends require configured effects.

    Independent handles serialize append and remove transactions. Records are
    never updated; ``remove`` deletes one record and frees its charge, refusing
    records other records name as parents, and choosing what to remove is an
    eviction policy's job (§43.11). Opening an existing store requires the same capacity;
    provision a dedicated database path. Effect names are host policy, not saved
    in the database, so reopening cannot silently grant an expert authority.
    """

    def __init__(self, path: str | Path, *, capacity_bytes: int,
                 read_effect: str, write_effect: str) -> None:
        if (isinstance(capacity_bytes, bool) or not isinstance(capacity_bytes, int)
                or capacity_bytes < 0):
            raise ValueError("capacity_bytes must be a nonnegative integer")
        if not read_effect or not write_effect:
            raise ValueError("memory effect identifiers must be nonempty")
        self.read_effect = read_effect
        self.write_effect = write_effect
        self._db = sqlite3.connect(path)
        try:
            mode = self._db.execute("PRAGMA journal_mode=WAL").fetchone()[0]
            if mode != "wal":
                raise ValueError("episodic memory requires a file-backed WAL database")
            self._db.execute("PRAGMA synchronous=FULL")
            with self._db:
                self._db.execute("BEGIN IMMEDIATE")
                self._db.execute("CREATE TABLE IF NOT EXISTS memory_meta "
                                 "(id INTEGER PRIMARY KEY CHECK(id=1), version INTEGER, "
                                 "capacity INTEGER, used INTEGER, records INTEGER)")
                self._db.execute("CREATE TABLE IF NOT EXISTS memory_records "
                                 "(ref TEXT PRIMARY KEY, encoded BLOB NOT NULL, "
                                 "position INTEGER UNIQUE NOT NULL) WITHOUT ROWID")
                self._db.execute("INSERT OR IGNORE INTO memory_meta VALUES (1, 1, ?, 0, 0)",
                                 (capacity_bytes,))
                indexed = self._db.execute(
                    "SELECT 1 FROM sqlite_master WHERE name='memory_parents'").fetchone()
                self._db.execute("CREATE TABLE IF NOT EXISTS memory_parents "
                                 "(parent TEXT NOT NULL, child TEXT NOT NULL, "
                                 "PRIMARY KEY (parent, child)) WITHOUT ROWID")
                if indexed is None:
                    # Stores created before removal existed get their parent index once.
                    for child, encoded in self._db.execute(
                            "SELECT ref, encoded FROM memory_records").fetchall():
                        self._db.executemany("INSERT INTO memory_parents VALUES (?, ?)",
                                             [(parent, child) for parent in _decode(encoded).parents])
                version, capacity = self._db.execute(
                    "SELECT version, capacity FROM memory_meta WHERE id=1").fetchone()
                if version != 1 or capacity != capacity_bytes:
                    raise ValueError("memory schema version or capacity does not match")
        except Exception:
            self._db.close()
            raise

    def close(self) -> None:
        """Host lifecycle operation; close after outstanding calls finish."""
        self._db.close()

    def usage(self) -> tuple[int, int]:
        """Charged logical bytes and record count, from one metadata snapshot."""
        require_effect(self.read_effect)
        return self._db.execute("SELECT used, records FROM memory_meta WHERE id=1").fetchone()

    def scan(self, *, after: int = 0, limit: int) -> tuple[tuple[int, Ref], ...]:
        """Bounded append-order references for external index rebuilding.

        Continue after the last returned position. Concurrent appends get higher
        positions, so advancing a cursor cannot skip a later committed append.
        This is enumeration, not a semantic recall strategy.
        """
        require_effect(self.read_effect)
        if any(isinstance(value, bool) or not isinstance(value, int) or value < 0
               for value in (after, limit)):
            raise ValueError("scan cursor and limit must be nonnegative integers")
        return tuple(self._db.execute(
            "SELECT position, ref FROM memory_records WHERE position>? "
            "ORDER BY position LIMIT ?", (after, limit)).fetchall())

    def get(self, reference: Ref) -> MemoryRecord:
        require_effect(self.read_effect)
        row = self._db.execute("SELECT encoded FROM memory_records WHERE ref=?",
                               (reference,)).fetchone()
        if row is None:
            raise KeyError(reference)
        encoded = row[0]
        if "sha256:" + hashlib.sha256(encoded).hexdigest() != reference:
            raise ValueError("memory record digest mismatch")
        return _decode(encoded)

    def append(self, record: MemoryRecord) -> Ref:
        require_effect(self.write_effect)
        encoded = record.encode()
        reference = "sha256:" + hashlib.sha256(encoded).hexdigest()
        charge = len(encoded) + len(reference.encode())
        with self._db:
            self._db.execute("BEGIN IMMEDIATE")
            existing = self._db.execute("SELECT encoded FROM memory_records WHERE ref=?",
                                        (reference,)).fetchone()
            if existing is not None:
                if existing[0] != encoded:
                    raise ValueError("memory identity collision or corruption")
                return reference
            capacity, used, _ = self._db.execute(
                "SELECT capacity, used, records FROM memory_meta WHERE id=1").fetchone()
            if charge > capacity - used:
                raise MemoryFull("memory logical-byte capacity exhausted")
            for parent in record.parents:
                row = self._db.execute("SELECT encoded FROM memory_records WHERE ref=?",
                                       (parent,)).fetchone()
                if row is None:
                    raise ValueError("memory parent does not exist")
                if parent == record.supersedes:
                    if "sha256:" + hashlib.sha256(row[0]).hexdigest() != parent:
                        raise ValueError("superseded memory digest mismatch")
                    if _decode(row[0]).type_id != record.type_id:
                        raise ValueError("superseded record has a different type")
            position = self._db.execute(
                "SELECT COALESCE(MAX(position), 0) + 1 FROM memory_records").fetchone()[0]
            self._db.execute("INSERT INTO memory_records VALUES (?, ?, ?)",
                             (reference, encoded, position))
            self._db.executemany("INSERT INTO memory_parents VALUES (?, ?)",
                                 [(parent, reference) for parent in dict.fromkeys(record.parents)])
            self._db.execute("UPDATE memory_meta SET used=used+?, records=records+1 WHERE id=1",
                             (charge,))
        return reference

    def remove(self, reference: Ref) -> int:
        """Delete one record and free its logical charge, which is returned.

        Missing references raise KeyError; a record still named as a parent by
        another record is refused, so provenance never dangles.
        """
        require_effect(self.write_effect)
        with self._db:
            self._db.execute("BEGIN IMMEDIATE")
            row = self._db.execute("SELECT encoded FROM memory_records WHERE ref=?",
                                   (reference,)).fetchone()
            if row is None:
                raise KeyError(reference)
            if self._db.execute("SELECT 1 FROM memory_parents WHERE parent=? LIMIT 1",
                                (reference,)).fetchone() is not None:
                raise ValueError("memory record is a parent of a retained record")
            charge = len(row[0]) + len(reference.encode())
            self._db.execute("DELETE FROM memory_records WHERE ref=?", (reference,))
            self._db.execute("DELETE FROM memory_parents WHERE child=?", (reference,))
            self._db.execute("UPDATE memory_meta SET used=used-?, records=records-1 WHERE id=1",
                             (charge,))
        return charge
