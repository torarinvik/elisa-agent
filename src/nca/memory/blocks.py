"""A library of blocks that are added and never changed, read a few at a time (§66).

A block is whatever the host makes of an input; the frame gives a block a name and no meaning, and never
looks inside one. Blocks live in a folder, written and read back by two functions the host supplies, and
at most a stated number are held in memory at once. An expert is registered by the names of the blocks
it reads, so that a block is taken away only when no expert reads it (§66.3). Since a block that has a
name keeps it, every expert's reading is what it was when the expert was made, whatever is added after
(§66.2).
"""
from __future__ import annotations

import hashlib
import json
import os
from collections import OrderedDict
from collections.abc import Callable, Mapping, Sequence
from pathlib import Path


class BlockLibrary:
    """Named blocks kept in a folder, loaded when read and let go when more than ``resident`` are held."""

    def __init__(self, folder: Path, save: Callable[[object, Path], None], load: Callable[[Path], object],
                 resident: int = 8) -> None:
        if resident < 1:
            raise ValueError("at least one block must be allowed in memory")
        self.folder, self.resident = Path(folder), resident
        self._save, self._load = save, load
        self.folder.mkdir(parents=True, exist_ok=True)
        self._index = self.folder / "index.json"
        kept = json.loads(self._index.read_text()) if self._index.exists() else {"blocks": [], "readers": {}}
        self._names: list[str] = kept["blocks"]
        self._readers: dict[str, list[str]] = kept["readers"]
        self._held: OrderedDict[str, object] = OrderedDict()
        self.loads = 0

    def _path(self, name: str) -> Path:
        return self.folder / (hashlib.sha256(name.encode()).hexdigest()[:32] + ".block")

    def _write(self) -> None:
        fresh = self._index.with_suffix(".new")
        fresh.write_text(json.dumps({"blocks": self._names, "readers": self._readers}))
        os.replace(fresh, self._index)

    def __contains__(self, name: str) -> bool:
        return name in self._names

    def names(self) -> tuple[str, ...]:
        """The names that have a block, in the order they were added."""
        return tuple(self._names)

    def add(self, name: str, block: object) -> None:
        """Add a block at a name that has none; a name that has a block keeps it (§66.1)."""
        if name in self:
            raise ValueError("this name already has a block, and a block is not changed once added")
        fresh = self._path(name).with_suffix(".new")
        self._save(block, fresh)
        os.replace(fresh, self._path(name))
        self._names.append(name)
        self._write()

    def get(self, name: str) -> object:
        """The block at a name, loaded if it is not held; the block least lately read is let go for it."""
        if name not in self:
            raise KeyError(name)
        if name in self._held:
            self._held.move_to_end(name)
            return self._held[name]
        while len(self._held) >= self.resident:
            self._held.popitem(last=False)
        self._held[name] = self._load(self._path(name))
        self.loads += 1
        return self._held[name]

    def held(self) -> tuple[str, ...]:
        """The names of the blocks now in memory."""
        return tuple(self._held)

    def read(self, reads: Sequence[str], given: object) -> list[object]:
        """What each block of a reading makes of an input, in the reading's order (§66.1)."""
        if len(reads) > self.resident:
            raise ValueError("a reading names more blocks than may be held at once")
        return [self.get(name)(given) for name in reads]  # type: ignore[operator]

    def register(self, expert: str, reads: Sequence[str]) -> None:
        """Record which blocks an expert reads; an expert's reading is set once."""
        if expert in self._readers:
            raise ValueError("this expert's reading is already recorded")
        missing = [name for name in reads if name not in self]
        if missing:
            raise KeyError(missing[0])
        self._readers[expert] = list(reads)
        self._write()

    def reading(self, expert: str) -> tuple[str, ...]:
        """The blocks an expert was registered as reading."""
        return tuple(self._readers[expert])

    def forget(self, expert: str) -> None:
        """Drop an expert's record, so that the blocks only it read may be taken away."""
        del self._readers[expert]
        self._write()

    def readers(self, name: str) -> tuple[str, ...]:
        """The experts registered as reading a block."""
        return tuple(expert for expert, reads in self._readers.items() if name in reads)

    def remove(self, name: str) -> None:
        """Take a block away, which is refused while any expert reads it (§66.3)."""
        if name not in self:
            raise KeyError(name)
        if self.readers(name):
            raise ValueError("an expert reads this block; taking it away would leave it without an output")
        self._names.remove(name)
        self._held.pop(name, None)
        self._write()
        self._path(name).unlink()


def choose(losses: Mapping[str, float], own: str) -> str:
    """The reading of least held-back loss, the expert's own kept where none is strictly better (§66.4)."""
    best = own
    for reading, loss in losses.items():
        if loss < losses[best]:
            best = reading
    return best
