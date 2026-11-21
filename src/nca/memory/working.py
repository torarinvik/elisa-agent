"""Working memory: channels that hold the recent past by step, read back by experts and kept from (§64).

A channel has a name the host gives it and a capacity in steps; the frame gives neither a meaning. An
entry is whatever the host writes, held as it is and never read here. What is held is exactly what §64.1
says: at step ``n`` the entry written at step ``i`` with ``i <= n < i + capacity``. An entry may be pinned,
which keeps it in the holding, or kept in a durable store by a record the caller makes of it (§64.4).

Beside the channels the memory has a scratchpad (§76.6): notes that whoever thinks leaves for the same step
and for later ones, each under a name and held until it is written again, dropped, or as old as the life it
was given.
"""
from __future__ import annotations

from collections import OrderedDict
from collections.abc import Callable, Mapping
from dataclasses import dataclass

from nca.memory.backend import MemoryBackend
from nca.memory.records import MemoryRecord
from nca.objects import Ref


@dataclass(frozen=True)
class Entry:
    """What was written to a channel, and the step it was written at."""

    step: int
    item: object


class Scratchpad:
    """Named notes over the working memory's count of steps, at most ``capacity`` of them at once (§76.6).

    A note is whatever its writer leaves, held as it is and never read here. Written under a name already
    there it takes the place of the note before it, so a thought may be refined within a step.
    """

    def __init__(self, capacity: int = 64) -> None:
        if type(capacity) is not int or capacity < 1:
            raise ValueError("a scratchpad's capacity must be a positive number of notes")
        self.capacity = capacity
        self.step = 0
        self._notes: dict[str, tuple[object, int, int | None]] = {}

    def note(self, name: str, item: object, life: int | None = None) -> None:
        """Leave a note at this step. With a ``life`` it is held at this step and the ``life - 1`` after it;
        with none, until it is written again or dropped. ``MemoryError`` where the pad is full."""
        if life is not None and (type(life) is not int or life < 1):
            raise ValueError("a note's life must be a positive number of steps")
        if name not in self._notes and len(self._notes) >= self.capacity:
            raise MemoryError(f"the scratchpad holds its {self.capacity} notes")
        self._notes[name] = (item, self.step, life)

    def __contains__(self, name: str) -> bool:
        return name in self._notes

    def read(self, name: str) -> object:
        """What is noted under a name; ``KeyError`` where nothing is."""
        return self._notes[name][0]

    def age(self, name: str) -> int:
        """How many steps ago the note under a name was written; ``KeyError`` where nothing is."""
        return self.step - self._notes[name][1]

    def drop(self, name: str) -> None:
        """Let go of the note under a name, if there is one."""
        self._notes.pop(name, None)

    def advance(self, step: int) -> None:
        """Go to a step, letting go of every note as old as its life."""
        self.step = step
        gone = [name for name, (_, written, life) in self._notes.items() if life is not None and written + life <= step]
        for name in gone:
            del self._notes[name]


class WorkingMemory:
    """Channels of fixed capacity over one count of steps, and a scratchpad of ``notes`` notes."""

    def __init__(self, capacities: Mapping[str, int], notes: int = 64) -> None:
        if any(type(capacity) is not int or capacity < 1 for capacity in capacities.values()):
            raise ValueError("a channel's capacity must be a positive number of steps")
        self.capacities = dict(capacities)
        self.step = 0
        self.scratch = Scratchpad(notes)
        self._held: dict[str, OrderedDict[int, Entry]] = {name: OrderedDict() for name in capacities}
        self._pinned: dict[str, dict[int, Entry]] = {name: {} for name in capacities}

    def open(self, channel: str, capacity: int) -> None:
        """Add a channel at this step, for whoever is to write it. It holds from now on what a channel of that
        capacity there from the first step would hold of what is written to it, and no other channel is
        touched (§64.1)."""
        if channel in self.capacities:
            raise ValueError(f"channel {channel!r} is already there")
        if type(capacity) is not int or capacity < 1:
            raise ValueError("a channel's capacity must be a positive number of steps")
        self.capacities[channel] = capacity
        self._held[channel], self._pinned[channel] = OrderedDict(), {}

    def advance(self) -> int:
        """Go to the next step, letting go of every entry no channel holds any longer (§64.1) and of every
        note as old as its life (§76.6)."""
        self.step += 1
        self.scratch.advance(self.step)
        for name, held in self._held.items():
            while held and next(iter(held)) + self.capacities[name] <= self.step:
                held.popitem(last=False)
        return self.step

    def write(self, channel: str, item: object) -> Entry:
        """Write the entry of this step to a channel; a channel has one entry a step."""
        held = self._held[channel]
        if self.step in held:
            raise ValueError("this channel already has an entry at this step")
        held[self.step] = Entry(self.step, item)
        return held[self.step]

    def serves(self, channel: str, age: int) -> bool:
        """Whether an entry of this age is held at every step, which is whether it is below the capacity (§64.1)."""
        return 0 <= age < self.capacities[channel]

    def together(self, channels: tuple[str, ...]) -> int:
        """How far back, in steps, these channels can be read at one step: the least of their capacities (§64.3)."""
        return min(self.capacities[channel] for channel in channels)

    def at(self, channel: str, step: int) -> object:
        """What a channel was written at a step, where that is held or pinned; ``KeyError`` where it is gone
        or was never written."""
        entry = self._held[channel].get(step) or self._pinned[channel].get(step)
        if entry is None:
            raise KeyError(f"channel {channel!r} has nothing available from step {step}")
        return entry.item

    def back(self, channel: str, age: int) -> object:
        """What a channel was written ``age`` steps ago; ``LookupError`` where the capacity does not serve that."""
        if not self.serves(channel, age):
            raise LookupError(f"channel {channel!r} does not serve an age of {age}")
        return self.at(channel, self.step - age)

    def recent(self, channel: str, steps: int) -> tuple[Entry, ...]:
        """The entries a channel was written in the last ``steps`` steps, oldest first."""
        if not self.serves(channel, steps - 1):
            raise LookupError(f"channel {channel!r} does not serve {steps} steps")
        held = self._held[channel]
        return tuple(held[step] for step in range(self.step - steps + 1, self.step + 1) if step in held)

    def pin(self, channel: str, step: int) -> None:
        """Keep a held entry in the holding until it is released (§64.4); ``KeyError`` where it is gone."""
        self._pinned[channel][step] = self._held[channel].get(step) or self._pinned[channel][step]

    def release(self, channel: str, step: int) -> None:
        """Stop keeping a pinned entry; it stays while its channel still holds it."""
        self._pinned[channel].pop(step, None)

    def keep(self, channel: str, step: int, backend: MemoryBackend, record: Callable[[Entry], MemoryRecord]) -> Ref:
        """Write an available entry to a durable store as the record the caller makes of it (§64.4, §43).

        The frame assigns the entry no type and no encoding: both are the caller's, in ``record``.
        """
        entry = self._held[channel].get(step) or self._pinned[channel].get(step)
        if entry is None:
            raise KeyError(f"channel {channel!r} has nothing available from step {step}")
        return backend.append(record(entry))
