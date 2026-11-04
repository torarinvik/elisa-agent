"""Artifact DAG admission, directory persistence and mutable reference names."""
from __future__ import annotations

import hashlib
import json
import os
import tempfile
from collections.abc import Callable, Iterator, Sequence
from pathlib import Path
from threading import RLock

from nca import objects as _api
from nca.abi import Contract


def _contracts(obj: _api.Object) -> list[Contract]:
    if isinstance(obj, _api.Primitive):
        return [obj.manifest.contract]
    if isinstance(obj, _api.Composite):
        return [*(obj.exports or ()), *(Contract(inputs, output) for inputs, output in obj.requires)]
    return []


def _requires(obj: _api.Object) -> list[_api.Ref]:
    """The references ``obj`` cannot be admitted without."""
    if isinstance(obj, _api.Primitive):
        own = list(obj.dependencies)
    elif isinstance(obj, _api.Composite):
        own = list(obj.members)
    elif isinstance(obj, _api.Attestation):
        own = [obj.subject]
    elif isinstance(obj, _api.Constructor):
        own = list(obj.refines)
    else:
        own = []
    return [*own, *_api.constructors(_contracts(obj))]


def _effects_cover(declared: frozenset[str] | None, member: frozenset[str] | None) -> bool:
    return declared is None or (member is not None and member <= declared)


def _decode(reference: _api.Ref, encoded: bytes) -> _api.Object:
    """Decode an independent canonical view, checking its stored identity."""
    if "sha256:" + hashlib.sha256(encoded).hexdigest() != reference:
        raise ValueError("artifact digest mismatch")
    obj = _api.object_from(json.loads(encoded))
    if _api.canonical(obj.data()) != encoded:
        raise ValueError("artifact encoding does not round-trip canonically")
    return obj


def _publish(path: Path, encoded: bytes) -> None:
    """Prepare privately, then atomically create a complete, immutable name.

    Hard-link publication refuses replacement, including concurrent writers.
    This is per-file atomicity, not a directory transaction or power-loss
    durability guarantee. Filesystems must support same-directory hard links.
    """
    try:
        existing = path.read_bytes()
    except FileNotFoundError:
        pass
    else:
        if existing != encoded:
            raise ValueError(f"{path.name} conflicts with the stored artifact")
        return
    descriptor, temporary = tempfile.mkstemp(prefix=".nca-", suffix=".tmp", dir=path.parent)
    try:
        with os.fdopen(descriptor, "wb") as stream:
            if stream.write(encoded) != len(encoded):
                raise OSError("incomplete artifact preparation")
            stream.flush()
            os.fsync(stream.fileno())
        try:
            os.link(temporary, path)
        except FileExistsError:
            if path.read_bytes() != encoded:
                raise ValueError(f"{path.name} conflicts with the stored artifact") from None
    finally:
        os.unlink(temporary)


class Store:
    """Objects by reference, and attestations by subject.

    ``put`` admits an object only once every reference it depends on is
    present: a primitive's dependencies or a composite's members (whose effects
    its declaration must cover), an attestation's subject, a constructor's refined constructors
    (of equal arity), and every constructor its contracts mention (applied
    to as many arguments as its arity), so every stored object is a
    well-formed DAG node. ``save`` and ``open`` keep one canonical JSON file per object,
    named by its digest. Stored contents are canonical immutable bytes; decoded
    objects are independent views. Admission and index publication are serialized.
    """

    def __init__(self) -> None:
        self._objects: dict[_api.Ref, bytes] = {}
        self._lock = RLock()
        self._about: dict[_api.Ref, list[_api.Ref]] = {}

    def __contains__(self, ref: object) -> bool:
        with self._lock:
            return ref in self._objects

    def __len__(self) -> int:
        with self._lock:
            return len(self._objects)

    def put(self, obj: _api.Object) -> _api.Ref:
        encoded = _api.canonical(obj.data())
        ref = "sha256:" + hashlib.sha256(encoded).hexdigest()
        snapshot = _decode(ref, encoded)
        with self._lock:
            return self._put(ref, encoded, snapshot)

    def _put(self, ref: _api.Ref, encoded: bytes, obj: _api.Object) -> _api.Ref:
        if ref in self._objects:
            if self._objects[ref] != encoded:
                raise ValueError("artifact identity collision")
            return ref
        for needed in _requires(obj):
            if needed not in self._objects:
                raise KeyError(f"{needed}, needed by {ref}, is not in the store")
        for constructor, arity in _api.constructors(_contracts(obj)).items():
            found = self.get(constructor)
            if not isinstance(found, _api.Constructor) or found.arity != arity:
                raise ValueError(f"{constructor} is not a constructor of arity {arity}")
        if isinstance(obj, _api.Constructor):
            for refined in obj.refines:
                found = self.get(refined)
                if not isinstance(found, _api.Constructor) or found.arity != obj.arity:
                    raise ValueError(f"{obj.name} refines {refined}, "
                                     f"which is not a constructor of arity {obj.arity}")
        if isinstance(obj, _api.Primitive) and obj.dependencies and "dependencies" in obj.arguments:
            raise ValueError("dependencies is reserved for resolved expert scopes")
        if isinstance(obj, (_api.Primitive, _api.Composite)):
            declared = obj.manifest.effects if isinstance(obj, _api.Primitive) else obj.effects
            members = obj.dependencies if isinstance(obj, _api.Primitive) else obj.members
            for member in members:
                if isinstance(self.get(member), _api.Attestation):
                    raise ValueError("an attestation cannot be an executable dependency or member")
                if not _effects_cover(declared, self.effects(member)):
                    raise ValueError(f"{ref} does not declare the effects of {member}")
        if isinstance(obj, _api.Attestation):
            self._about.setdefault(obj.subject, []).append(ref)
        self._objects[ref] = encoded
        return ref

    def __getstate__(self) -> dict[str, object]:
        with self._lock:
            return {"_objects": dict(self._objects)}

    def __setstate__(self, state: dict[str, object]) -> None:
        if hasattr(self, "_objects"):
            raise ValueError("artifact restore requires a fresh instance")
        self.__init__()
        records = state["_objects"]
        if not isinstance(records, dict):
            raise ValueError("invalid artifact store state")
        pending = {
            ref: _decode(ref, value if isinstance(value, bytes) else _api.canonical(value.data()))
            for ref, value in records.items()
        }
        while pending:
            ready = [ref for ref, obj in pending.items() if _ready(self, obj)]
            if not ready:
                raise ValueError("objects refer to references missing from the store")
            for ref in ready:
                self.put(pending.pop(ref))

    def get(self, ref: _api.Ref) -> _api.Object:
        """Return a freshly decoded view; its mutations cannot change the store."""
        with self._lock:
            encoded = self._objects[ref]
        return _decode(ref, encoded)

    def effects(self, ref: _api.Ref) -> frozenset[str] | None:
        obj = self.get(ref)
        if isinstance(obj, _api.Primitive):
            return obj.manifest.effects
        if isinstance(obj, _api.Composite):
            return obj.effects
        if isinstance(obj, _api.Constructor):
            return frozenset()  # Its upcasts return their input.
        raise ValueError("attestations have no effects")

    def attestations(self, subject: _api.Ref, kind: str | None = None) -> list[_api.Attestation]:
        """The attestations about ``subject``, in the order they were stored."""
        with self._lock:
            references = tuple(self._about.get(subject, ()))
        found = [self.get(ref) for ref in references]
        return [a for a in found if isinstance(a, _api.Attestation) and (kind is None or a.kind == kind)]

    def _walk(self, ref: _api.Ref,
              children: Callable[[_api.Object], Sequence[_api.Ref]]
              ) -> Iterator[tuple[_api.Ref, _api.Object]]:
        """Postorder over an admitted DAG, decoding each reachable node once."""
        seen: set[_api.Ref] = set()
        pending: list[tuple[_api.Ref, _api.Object | None]] = [(ref, None)]
        while pending:
            node, completed = pending.pop()
            if completed is not None:
                yield node, completed
                continue
            if node in seen:
                continue
            seen.add(node)
            obj = self.get(node)
            pending.append((node, obj))
            pending.extend((needed, None) for needed in reversed(children(obj)))

    def flatten(self, ref: _api.Ref) -> list[_api.Ref]:
        """Primitives in first member occurrence order (§28.2).

        Expand exported and transparent composites, but never a primitive's
        executable dependencies. Shared composites are visited only once.
        """
        return [node for node, obj in self._walk(
            ref, lambda obj: obj.members if isinstance(obj, _api.Composite) else ())
                if isinstance(obj, _api.Primitive)]

    def walk(self, ref: _api.Ref) -> Iterator[_api.Ref]:
        """Every reachable object once, dependencies first, without recursion."""
        for node, _ in self._walk(ref, _requires):
            yield node

    def save(self, directory: Path) -> None:
        """Publish complete files without overwriting existing artifact names.

        An interrupted save can leave a dependency-first completed prefix;
        it is not a transaction over the whole directory. Private preparation
        files are ignored by open and removed on ordinary exception unwinding.
        """
        directory.mkdir(parents=True, exist_ok=True)
        with self._lock:
            records = tuple(self._objects.items())
        for ref, encoded in records:
            path = directory / f"{ref.removeprefix('sha256:')}.json"
            _publish(path, encoded)

    @classmethod
    def open(cls, directory: Path) -> Store:
        """Read every object in ``directory``, checking each file's digest."""
        store = cls()
        pending: dict[_api.Ref, _api.Object] = {}
        for path in sorted(directory.glob("*.json")):
            data = json.loads(path.read_bytes())
            ref = _api.digest(data)
            if ref != f"sha256:{path.stem}":
                raise ValueError(f"{path.name} does not match its digest")
            obj = _api.object_from(data)
            if obj.ref != ref:
                raise ValueError(f"{path.name} does not match its decoded object's digest")
            pending[ref] = obj
        while pending:
            ready = [ref for ref, obj in pending.items() if _ready(store, obj)]
            if not ready:
                raise ValueError("objects refer to references missing from the store")
            for ref in ready:
                store.put(pending.pop(ref))
        return store


def _ready(store: Store, obj: _api.Object) -> bool:
    return all(needed in store for needed in _requires(obj))


class Names:
    """Mutable names for immutable references (§28.6)."""

    def __init__(self) -> None:
        self._names: dict[str, _api.Ref] = {}

    def bind(self, name: str, ref: _api.Ref) -> _api.Ref | None:
        """Point ``name`` at ``ref`` and return what it pointed at before."""
        previous = self._names.get(name)
        self._names[name] = ref
        return previous

    def resolve(self, name: str) -> _api.Ref:
        return self._names[name]

    def items(self) -> list[tuple[str, _api.Ref]]:
        return sorted(self._names.items())
