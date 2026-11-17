"""A library of blocks that are added and never changed, read a few at a time, and found by key (§66).

A block is whatever the host makes of an input; the frame gives a block a name and no meaning, and never
looks inside one. Blocks live in a folder, written and read back by two functions the host supplies, and
at most a stated number are held in memory at once. An expert is registered by the names of the blocks
it reads, so that a block is taken away only when no expert reads it (§66.3). Since a block that has a
name keeps it, every expert's reading is what it was when the expert was made, whatever is added after
(§66.2). ``join`` makes a new expert from teaching the host supplies, trying a block of its own alone and
beside the best of the blocks offered. What the library records is appended to a log, so that adding to a large library costs what adding
to a small one does. ``KeyIndex`` holds a vector for each name in a file read in place and gives the names
nearest a query; ``PartStore`` holds parts that do change, such as an expert with the state of its teaching,
loaded when used and written back.
"""
from __future__ import annotations

import hashlib
import json
import os
from collections import OrderedDict
from collections.abc import Callable, Mapping, Sequence
from pathlib import Path

import numpy as np


class BlockLibrary:
    """Named blocks kept in a folder, loaded when read and let go when more than ``resident`` are held."""

    def __init__(self, folder: Path, save: Callable[[object, Path], None], load: Callable[[Path], object],
                 resident: int = 8) -> None:
        if resident < 1:
            raise ValueError("at least one block must be allowed in memory")
        self.folder, self.resident = Path(folder), resident
        self._save, self._load = save, load
        self.folder.mkdir(parents=True, exist_ok=True)
        self._log = self.folder / "index.log"
        self._names: dict[str, None] = {}
        self._readers: dict[str, list[str]] = {}
        self._read: dict[str, int] = {}
        if self._log.exists():
            for line in self._log.read_text().splitlines():
                self._apply(json.loads(line))
        self._held: OrderedDict[str, object] = OrderedDict()
        self.loads = 0

    def _apply(self, entry: list[object]) -> None:
        what, name = str(entry[0]), str(entry[1])
        if what == "add":
            self._names[name] = None
            self._read.setdefault(name, 0)
        elif what == "remove":
            del self._names[name]
            del self._read[name]
        elif what == "register":
            self._readers[name] = [str(read) for read in entry[2]]  # type: ignore[union-attr]
            for read in self._readers[name]:
                self._read[read] += 1
        else:
            for read in self._readers.pop(name):
                self._read[read] -= 1

    def _record(self, *entry: object) -> None:
        with self._log.open("a") as log:
            log.write(json.dumps(entry) + "\n")
        self._apply(list(entry))

    def _path(self, name: str) -> Path:
        return self.folder / (hashlib.sha256(name.encode()).hexdigest()[:32] + ".block")

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
        self._record("add", name)

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
        self._record("register", expert, list(reads))

    def reading(self, expert: str) -> tuple[str, ...]:
        """The blocks an expert was registered as reading."""
        return tuple(self._readers[expert])

    def forget(self, expert: str) -> None:
        """Drop an expert's record, so that the blocks only it read may be taken away."""
        if expert not in self._readers:
            raise KeyError(expert)
        self._record("forget", expert)

    def readers(self, name: str) -> tuple[str, ...]:
        """The experts registered as reading a block."""
        return tuple(expert for expert, reads in self._readers.items() if name in reads)

    def most_read(self, count: int) -> tuple[str, ...]:
        """The blocks read by the most experts, most read first: a block many read may help one unlike it."""
        ranked = sorted(self._read, key=lambda name: -self._read[name])
        return tuple(name for name in ranked[:count] if self._read[name])

    def remove(self, name: str) -> None:
        """Take a block away, which is refused while any expert reads it (§66.3)."""
        if name not in self:
            raise KeyError(name)
        if self._read[name]:
            raise ValueError("an expert reads this block; taking it away would leave it without an output")
        self._record("remove", name)
        self._held.pop(name, None)
        self._path(name).unlink()


def choose(losses: Mapping[str, float], own: str) -> str:
    """The reading of least held-back loss, the expert's own kept where none is strictly better (§66.4)."""
    best = own
    for reading, loss in losses.items():
        if loss < losses[best]:
            best = reading
    return best


def shortlist(library: BlockLibrary, index: KeyIndex, key: np.ndarray, near: int, read: int) -> tuple[str, ...]:
    """The blocks worth trying for a key: those nearest it, then those most experts read, each once.

    How many are tried is set by ``near`` and ``read`` and not by how many the library holds.
    """
    found = [name for name in index.nearest(key, near) if name in library]
    return tuple(dict.fromkeys([*found, *library.most_read(read)]))


def admit(library: BlockLibrary, expert: str, block: object, readings: Mapping[str, tuple[Sequence[str], float]],
          own: str) -> tuple[str, ...]:
    """Keep the reading of least held-back loss for a new expert, add its block and record what it reads (§66.4).

    ``readings`` gives, for each reading tried, the earlier blocks it reads and its loss; ``own`` names the
    reading of the new block alone. The block is added under the expert's name and read last.
    """
    kept = choose({name: loss for name, (_, loss) in readings.items()}, own)
    reads = (*readings[kept][0], expert)
    library.add(expert, block)
    library.register(expert, reads)
    return reads


def join(library: BlockLibrary, expert: str, teach: Callable[[Sequence[str], bool], tuple[object, float, object]],
         offered: Sequence[str] = (), read: int = 2) -> tuple[tuple[str, ...], object, dict[str, float]]:
    """Make a new expert from the host's teaching, with the reading of least held-back loss (§66.4).

    ``teach(reads, new)`` teaches whatever the host puts on top of the blocks named, beside a new block if
    ``new``, and returns that block (nothing if none), the loss on what it held back, and the rest of what it
    made. A block of the expert's own is taught first. Each block offered that the library holds is then
    tried alone, without a new block; the ``read`` of them with least loss are read beside a second new
    block, and of the two readings the one kept is admitted. What the expert reads, the rest of what the
    host made for that reading, and each reading's loss are returned. No block already held is changed.
    """
    own, loss, rest = teach((), True)
    tried: dict[str, tuple[tuple[str, ...], object, float, object]] = {"own": ((), own, loss, rest)}
    alone = {name: teach((name,), False)[1] for name in dict.fromkeys(offered) if name in library}
    if alone:
        reads = tuple(sorted(alone, key=alone.__getitem__)[:read])
        tried["beside"] = (reads, *teach(reads, True))
    losses = {name: loss for name, (_, _, loss, _) in tried.items()}
    _, block, _, rest = tried[choose(losses, "own")]
    return admit(library, expert, block, {name: (reads, loss) for name, (reads, _, loss, _) in tried.items()}, "own"), rest, losses


class KeyIndex:
    """A vector for each name, kept in a file that is read in place; the names nearest a query are given."""

    def __init__(self, folder: Path, width: int) -> None:
        self.folder, self.width = Path(folder), width
        self.folder.mkdir(parents=True, exist_ok=True)
        self._keys, self._list = self.folder / "keys.f32", self.folder / "keys.names"
        self._names = [json.loads(line) for line in self._list.read_text().splitlines()] if self._list.exists() else []

    def __len__(self) -> int:
        return len(self._names)

    def add(self, name: str, key: np.ndarray) -> None:
        """Give a name its key, which it keeps."""
        if key.shape != (self.width,):
            raise ValueError("a key must be a vector of the index's width")
        with self._keys.open("ab") as keys:
            keys.write(np.asarray(key, np.float32).tobytes())
        with self._list.open("a") as names:
            names.write(json.dumps(name) + "\n")
        self._names.append(name)

    def nearest(self, query: np.ndarray, count: int) -> tuple[str, ...]:
        """The names whose keys are nearest a query, nearest first."""
        if not self._names:
            return ()
        keys = np.memmap(self._keys, np.float32, "r", shape=(len(self._names), self.width))
        apart = ((keys - np.asarray(query, np.float32)) ** 2).sum(1)
        count = min(count, len(self._names))
        near = np.argpartition(apart, count - 1)[:count]
        return tuple(self._names[at] for at in near[np.argsort(apart[near], kind="stable")])


class PartStore:
    """Named parts that change, kept in a folder: loaded when used, written back, a stated number held."""

    def __init__(self, folder: Path, save: Callable[[object, Path], None], load: Callable[[Path], object],
                 resident: int = 8) -> None:
        if resident < 1:
            raise ValueError("at least one part must be allowed in memory")
        self.folder, self.resident = Path(folder), resident
        self._save, self._load = save, load
        self.folder.mkdir(parents=True, exist_ok=True)
        self._held: OrderedDict[str, object] = OrderedDict()

    def _path(self, name: str) -> Path:
        return self.folder / (hashlib.sha256(name.encode()).hexdigest()[:32] + ".part")

    def __contains__(self, name: str) -> bool:
        return name in self._held or self._path(name).exists()

    def put(self, name: str, part: object) -> None:
        """Write a part to its file, whole or not at all, and hold it."""
        fresh = self._path(name).with_suffix(".new")
        self._save(part, fresh)
        os.replace(fresh, self._path(name))
        self._held[name] = part
        self._held.move_to_end(name)
        while len(self._held) > self.resident:
            self._held.popitem(last=False)

    def get(self, name: str) -> object:
        """The part at a name, loaded if it is not held; the part least lately used is let go for it."""
        if name in self._held:
            self._held.move_to_end(name)
            return self._held[name]
        if not self._path(name).exists():
            raise KeyError(name)
        while len(self._held) >= self.resident:
            self._held.popitem(last=False)
        self._held[name] = self._load(self._path(name))
        return self._held[name]

    def held(self) -> tuple[str, ...]:
        """The names of the parts now in memory."""
        return tuple(self._held)
