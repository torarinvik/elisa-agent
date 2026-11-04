"""Append-cursor state-machine links to NCA.Execution.Memory (§43.12)."""

import sqlite3
from itertools import product
from pathlib import Path

import pytest

from nca.memory import MemoryStore
from test_memory import authority, record, store


def test_cursor_survives_deleting_newest_and_reopening_empty_store(tmp_path: Path) -> None:
    path = tmp_path / "memory.sqlite"
    memory = store(path)
    with authority():
        first = memory.append(record(b"first"))
        cursor = memory.scan(limit=1)[0][0]
        memory.remove(first)
    memory.close()
    memory = store(path)
    with authority():
        second = memory.append(record(b"second"))
        assert memory.scan(after=cursor, limit=1) == ((cursor + 1, second),)
    memory.close()


def test_all_small_append_eviction_reopen_traces(tmp_path: Path) -> None:
    """Exhaust four-operation traces against cursorAppend/cursorErase.
    A duplicate is an identity transition; reopening preserves metadata."""
    for trial, actions in enumerate(product(range(4), repeat=4)):
        path = tmp_path / f"{trial}.sqlite"
        memory = store(path)
        high = 0
        live: dict[int, str] = {}
        with authority():
            for action in actions:
                if action == 0 or (action == 3 and not live):
                    high += 1
                    live[high] = memory.append(record(str(high).encode()))
                elif action == 1 and live:
                    position = max(live)
                    memory.remove(live.pop(position))
                elif action == 2:
                    memory.close()
                    memory = store(path)
                elif action == 3:
                    reference = live[max(live)]
                    assert memory.append(memory.get(reference)) == reference
                assert memory.scan(limit=10) == tuple(live.items())
        memory.close()


def legacy_database(path: Path) -> None:
    with sqlite3.connect(path) as db:
        db.execute("CREATE TABLE memory_meta (id INTEGER PRIMARY KEY, version INTEGER, "
                   "capacity INTEGER, used INTEGER, records INTEGER)")
        db.execute("INSERT INTO memory_meta VALUES (1, 1, 10000, 0, 0)")
        db.execute("CREATE TABLE memory_records (ref TEXT PRIMARY KEY, encoded BLOB NOT NULL, "
                   "position INTEGER UNIQUE NOT NULL) WITHOUT ROWID")


def test_legacy_deleted_positions_cannot_be_silently_reconstructed(tmp_path: Path) -> None:
    path = tmp_path / "old.sqlite"
    legacy_database(path)
    with pytest.raises(ValueError, match="legacy_cursor"):
        store(path)
    migrated = MemoryStore(path, capacity_bytes=10000, read_effect="test.recall",
                           write_effect="test.append", legacy_cursor=100)
    with authority():
        reference = migrated.append(record())
        assert migrated.scan(after=100, limit=1) == ((101, reference),)
    migrated.close()
    reopened = store(path)
    with authority():
        assert reopened.scan(after=100, limit=1) == ((101, reference),)
    reopened.close()


def test_record_and_cursor_counter_rollback_together(tmp_path: Path) -> None:
    path = tmp_path / "memory.sqlite"
    memory = store(path)
    with sqlite3.connect(path) as db:
        db.execute("CREATE TRIGGER deny_counter BEFORE UPDATE OF position ON memory_meta "
                   "BEGIN SELECT RAISE(ABORT, 'injected failure'); END")
    with authority():
        with pytest.raises(sqlite3.IntegrityError, match="injected failure"):
            memory.append(record())
        assert memory.usage() == (0, 0)
        assert memory.scan(limit=1) == ()
    with sqlite3.connect(path) as db:
        db.execute("DROP TRIGGER deny_counter")
    with authority():
        reference = memory.append(record())
        assert memory.scan(limit=1) == ((1, reference),)
    memory.close()
