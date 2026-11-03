"""Artifact DAG admission, directory persistence and mutable reference names."""
from __future__ import annotations

import json
from collections.abc import Iterator
from pathlib import Path

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


class Store:
    """Objects by reference, and attestations by subject.

    ``put`` admits an object only once every reference it depends on is
    present: a primitive's dependencies or a composite's members (whose effects
    its declaration must cover), an attestation's subject, a constructor's refined constructors
    (of equal arity), and every constructor its contracts mention (applied
    to as many arguments as its arity), so every stored object is a
    well-formed DAG node. ``save`` and ``open`` keep one canonical JSON file per object,
    named by its digest.
    """

    def __init__(self) -> None:
        self._objects: dict[_api.Ref, _api.Object] = {}
        self._about: dict[_api.Ref, list[_api.Ref]] = {}

    def __contains__(self, ref: object) -> bool:
        return ref in self._objects

    def __len__(self) -> int:
        return len(self._objects)

    def put(self, obj: _api.Object) -> _api.Ref:
        ref = obj.ref
        if ref in self._objects:
            return ref
        for needed in _requires(obj):
            if needed not in self._objects:
                raise KeyError(f"{needed}, needed by {ref}, is not in the store")
        for constructor, arity in _api.constructors(_contracts(obj)).items():
            found = self._objects[constructor]
            if not isinstance(found, _api.Constructor) or found.arity != arity:
                raise ValueError(f"{constructor} is not a constructor of arity {arity}")
        if isinstance(obj, _api.Constructor):
            for refined in obj.refines:
                found = self._objects[refined]
                if not isinstance(found, _api.Constructor) or found.arity != obj.arity:
                    raise ValueError(f"{obj.name} refines {refined}, "
                                     f"which is not a constructor of arity {obj.arity}")
        if isinstance(obj, _api.Primitive) and obj.dependencies and "dependencies" in obj.arguments:
            raise ValueError("dependencies is reserved for resolved expert scopes")
        if isinstance(obj, (_api.Primitive, _api.Composite)):
            declared = obj.manifest.effects if isinstance(obj, _api.Primitive) else obj.effects
            members = obj.dependencies if isinstance(obj, _api.Primitive) else obj.members
            for member in members:
                if isinstance(self._objects[member], _api.Attestation):
                    raise ValueError("an attestation cannot be an executable dependency or member")
                if not _effects_cover(declared, self.effects(member)):
                    raise ValueError(f"{ref} does not declare the effects of {member}")
        if isinstance(obj, _api.Attestation):
            self._about.setdefault(obj.subject, []).append(ref)
        self._objects[ref] = obj
        return ref

    def get(self, ref: _api.Ref) -> _api.Object:
        return self._objects[ref]

    def effects(self, ref: _api.Ref) -> frozenset[str] | None:
        obj = self._objects[ref]
        if isinstance(obj, _api.Primitive):
            return obj.manifest.effects
        if isinstance(obj, _api.Composite):
            return obj.effects
        if isinstance(obj, _api.Constructor):
            return frozenset()  # Its upcasts return their input.
        raise ValueError("attestations have no effects")

    def attestations(self, subject: _api.Ref, kind: str | None = None) -> list[_api.Attestation]:
        """The attestations about ``subject``, in the order they were stored."""
        found = [self._objects[ref] for ref in self._about.get(subject, ())]
        return [a for a in found if isinstance(a, _api.Attestation) and (kind is None or a.kind == kind)]

    def flatten(self, ref: _api.Ref) -> list[_api.Ref]:
        """The primitives of ``ref`` in member order, each at its first
        occurrence (§28.2). Exported and transparent composites alike are
        expanded; this is the transparent view."""
        seen: set[_api.Ref] = set()
        order: list[_api.Ref] = []

        def visit(node: _api.Ref) -> None:
            obj = self._objects[node]
            if isinstance(obj, _api.Primitive):
                if node not in seen:
                    seen.add(node)
                    order.append(node)
            elif isinstance(obj, _api.Composite):
                for member in obj.members:
                    visit(member)

        visit(ref)
        return order

    def walk(self, ref: _api.Ref) -> Iterator[_api.Ref]:
        """Every object reachable from ``ref``, each once, dependencies first."""
        seen: set[_api.Ref] = set()

        def visit(node: _api.Ref) -> Iterator[_api.Ref]:
            if node in seen:
                return
            seen.add(node)
            obj = self._objects[node]
            for needed in _requires(obj):
                yield from visit(needed)
            yield node

        yield from visit(ref)

    def save(self, directory: Path) -> None:
        directory.mkdir(parents=True, exist_ok=True)
        for ref, obj in self._objects.items():
            path = directory / f"{ref.removeprefix('sha256:')}.json"
            if not path.exists():
                path.write_bytes(_api.canonical(obj.data()))

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
