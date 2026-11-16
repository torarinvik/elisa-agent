"""Working memory: what a channel holds by step, channels read together, and entries pinned and kept (§64)."""
from pathlib import Path

import pytest

from nca.effects import effect_scope, expert_scope
from nca.memory import Entry, MemoryRecord, MemoryStore, WorkingMemory

READ, WRITE = "test.recall", "test.append"
BOUND = 7


def filled(capacity: int, steps: int) -> WorkingMemory:
    """A channel written at every step from nought to ``steps``, now at step ``steps``."""
    memory = WorkingMemory({"seen": capacity})
    memory.write("seen", 0)
    for _ in range(steps):
        memory.advance()
        memory.write("seen", memory.step)
    return memory


def available(memory: WorkingMemory, channel: str, step: int) -> bool:
    try:
        memory.at(channel, step)
    except KeyError:
        return False
    return True


def test_an_entry_is_held_exactly_while_its_age_is_below_the_capacity() -> None:
    """held_iff_age (64.1) and kept_in_time (64.4), over every capacity, step and age up to a bound."""
    for capacity in range(1, BOUND):
        for steps in range(BOUND):
            memory = filled(capacity, steps)
            for age in range(steps + 1):
                assert available(memory, "seen", steps - age) == (age < capacity)
                assert memory.serves("seen", age) == (age < capacity)


def test_a_larger_holding_serves_all_a_smaller_one_does() -> None:
    """held_mono (64.2)."""
    for capacity in range(1, BOUND):
        small, large = filled(capacity, BOUND), filled(capacity + 2, BOUND)
        assert all(available(large, "seen", step) for step in range(BOUND + 1) if available(small, "seen", step))


def test_channels_read_together_are_served_as_far_back_as_the_smaller() -> None:
    """held_together (64.3)."""
    memory = WorkingMemory({"seen": 5, "done": 2})
    for _ in range(BOUND):
        memory.write("seen", ("s", memory.step))
        memory.write("done", ("d", memory.step))
        memory.advance()
    assert memory.together(("seen", "done")) == 2
    both = [step for step in range(memory.step + 1) if available(memory, "seen", step) and available(memory, "done", step)]
    alone = WorkingMemory({"least": 2})
    for _ in range(BOUND):
        alone.write("least", None)
        alone.advance()
    assert both == [step for step in range(alone.step + 1) if available(alone, "least", step)]


def test_what_is_read_back_is_what_was_written() -> None:
    memory = filled(4, 6)
    assert memory.back("seen", 0) == 6
    assert memory.back("seen", 3) == 3
    assert memory.recent("seen", 3) == (Entry(4, 4), Entry(5, 5), Entry(6, 6))
    with pytest.raises(LookupError):
        memory.back("seen", 4)
    with pytest.raises(LookupError):
        memory.recent("seen", 5)


def test_a_step_with_nothing_written_holds_nothing() -> None:
    memory = WorkingMemory({"seen": 3})
    memory.advance()
    assert not available(memory, "seen", 1)
    assert memory.recent("seen", 3) == ()


def test_a_second_entry_at_one_step_and_a_capacity_below_one_are_refused() -> None:
    memory = WorkingMemory({"seen": 2})
    memory.write("seen", "first")
    with pytest.raises(ValueError):
        memory.write("seen", "second")
    with pytest.raises(ValueError):
        WorkingMemory({"seen": 0})


def test_a_pinned_entry_outlives_the_holding_and_an_unkept_one_is_gone() -> None:
    """gone_when_unkept and kept_is_available (64.5)."""
    memory = WorkingMemory({"seen": 2})
    memory.write("seen", "kept")
    memory.pin("seen", 0)
    memory.advance()
    memory.write("seen", "unkept")
    for _ in range(BOUND):
        memory.advance()
    assert memory.at("seen", 0) == "kept"
    assert not available(memory, "seen", 1)
    memory.release("seen", 0)
    assert not available(memory, "seen", 0)
    with pytest.raises(KeyError):
        memory.pin("seen", 1)


def test_an_entry_kept_in_a_store_is_recalled_after_its_channel_let_it_go(tmp_path: Path) -> None:
    store = MemoryStore(tmp_path / "kept.sqlite", capacity_bytes=10000, read_effect=READ, write_effect=WRITE)
    memory = WorkingMemory({"seen": 2})
    memory.write("seen", b"\x01\x02")
    memory.advance()
    with effect_scope(frozenset({READ, WRITE})), expert_scope(frozenset({READ, WRITE})):
        kept = memory.keep("seen", 0, store, lambda entry: MemoryRecord("observation", entry.item, "host@1", float(entry.step)))
        for _ in range(BOUND):
            memory.advance()
        assert not available(memory, "seen", 0)
        assert store.get(kept).payload == b"\x01\x02"
        with pytest.raises(KeyError):
            memory.keep("seen", 0, store, lambda entry: MemoryRecord("observation", entry.item, "host@1", 0.0))
    store.close()
