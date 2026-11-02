"""Content-addressed objects: experts, composites and attestations (THEORY §28).

Every object is immutable data identified by the SHA-256 digest of its
canonical encoding, its *reference*. There are three kinds:

* ``Primitive``: one expert, its manifest and how to load its implementation
  (an entry point, JSON arguments, and the digest of its weights);
* ``Composite``: an ordered list of member references, each a primitive or a
  composite, with the slots it requires from its surroundings and the
  contracts it exports (``None`` exports every member: a transparent
  composite);
* ``Attestation``: a claim about another object, such as calibration
  temperatures, an audit or a signature, kept beside its subject rather than
  inside it.

A composite names its members by reference, so composites form a DAG with
shared members, and since a reference is computed from contents that
include the references of the members, no object can contain itself.
Human-readable names are a separate, mutable layer (``Names``) pointing at
references, as branch names point at commits.
"""

from __future__ import annotations

import hashlib
import importlib
import json
import math
from collections.abc import Iterator, Mapping, Sequence
from dataclasses import dataclass, field
from pathlib import Path
from typing import Any, Union

from nca.abi import Calls, Contract, Manifest, Slot

Ref = str
"""``"sha256:"`` followed by 64 hexadecimal digits."""

Json = Union[None, bool, int, float, str, list["Json"], dict[str, "Json"]]


def canonical(value: Any) -> bytes:
    """The canonical encoding: JSON with sorted keys and no insignificant
    whitespace. Tuples encode as lists; non-finite floats are rejected."""
    def check(item: Any) -> None:
        if isinstance(item, float) and not math.isfinite(item):
            raise ValueError("canonical encoding needs finite numbers")
        if isinstance(item, Mapping):
            if any(not isinstance(key, str) for key in item):
                raise ValueError("canonical encoding needs string keys")
            for v in item.values():
                check(v)
        elif isinstance(item, (list, tuple)):
            for v in item:
                check(v)
        elif not isinstance(item, (str, int, float, bool)) and item is not None:
            raise TypeError(f"cannot encode {type(item).__name__}")

    check(value)
    return json.dumps(value, sort_keys=True, separators=(",", ":"),
                      ensure_ascii=False, allow_nan=False).encode()


def digest(value: Any) -> Ref:
    """The reference of ``value``'s canonical encoding."""
    return "sha256:" + hashlib.sha256(canonical(value)).hexdigest()


def file_digest(path: Path) -> Ref:
    """The reference of a file's bytes, for weights."""
    sha = hashlib.sha256()
    with open(path, "rb") as handle:
        for block in iter(lambda: handle.read(1 << 20), b""):
            sha.update(block)
    return "sha256:" + sha.hexdigest()


def _slots_data(slots: Sequence[Slot]) -> list[Json]:
    return [[list(inputs), output] for inputs, output in slots]


def _slots_from(data: Sequence[Any]) -> tuple[Slot, ...]:
    return tuple((tuple(inputs), output) for inputs, output in data)


def contract_data(contract: Contract) -> dict[str, Json]:
    return {"inputs": list(contract.inputs), "output": contract.output,
            "slots": _slots_data(contract.slots),
            "relevant": [list(r) for r in contract.relevant]}


def contract_from(data: Mapping[str, Any]) -> Contract:
    return Contract(tuple(data["inputs"]), data["output"], _slots_from(data["slots"]),
                    tuple(tuple(r) for r in data["relevant"]))


def _calls_data(calls: Sequence[Calls] | None) -> list[Json] | None:
    return None if calls is None else [[c.fixed, c.per_element] for c in calls]


def _calls_from(data: Sequence[Any] | None) -> tuple[Calls, ...] | None:
    return None if data is None else tuple(Calls(fixed, per) for fixed, per in data)


def manifest_data(manifest: Manifest) -> dict[str, Json]:
    return {"module_id": manifest.module_id, "version": manifest.version,
            "contract": contract_data(manifest.contract), "cost": manifest.cost,
            "calls": _calls_data(manifest.calls),
            "expected_calls": _calls_data(manifest.expected_calls),
            "effects": None if manifest.effects is None else sorted(manifest.effects)}


def manifest_from(data: Mapping[str, Any]) -> Manifest:
    effects = data["effects"]
    return Manifest(data["module_id"], data["version"], contract_from(data["contract"]),
                    data["cost"], _calls_from(data["calls"]) or (),
                    _calls_from(data["expected_calls"]),
                    None if effects is None else frozenset(effects))


@dataclass(frozen=True)
class Primitive:
    """One expert: its manifest and how to load its implementation.

    ``entry`` names a callable as ``"package.module:attribute"``; loading calls
    it with ``arguments`` and expects a module whose manifest equals this one.
    ``weights`` is the digest of the bytes the implementation loads, so
    implementations that differ only in their weights differ in reference.
    """

    manifest: Manifest
    entry: str
    arguments: Mapping[str, Json] = field(default_factory=dict)
    weights: Ref | None = None
    size: int = 0
    """Resident bytes once loaded, for the expert store's budget."""

    def data(self) -> dict[str, Json]:
        return {"kind": "primitive", "manifest": manifest_data(self.manifest),
                "entry": self.entry, "arguments": dict(self.arguments),
                "weights": self.weights, "size": self.size}

    @property
    def ref(self) -> Ref:
        return digest(self.data())

    def load(self) -> Any:
        module_name, _, attribute = self.entry.partition(":")
        target: Any = importlib.import_module(module_name)
        for part in attribute.split("."):
            target = getattr(target, part)
        implementation = target(**self.arguments)
        if implementation.manifest != self.manifest:
            raise ValueError(f"{self.entry} produced {implementation.manifest.ref}, "
                             f"not the declared {self.manifest.ref}")
        return implementation


@dataclass(frozen=True)
class Composite:
    """An ordered list of experts, primitive or composite, used as one expert.

    ``requires`` are slots its surroundings must fill, as for any
    higher-order expert (§20); ``exports`` are the contracts it offers, each
    implemented by planning over the members and the required slots.
    ``exports=None`` makes it transparent: installing it installs its members
    in order.
    """

    name: str
    version: str
    members: tuple[Ref, ...]
    requires: tuple[Slot, ...] = ()
    exports: tuple[Contract, ...] | None = None
    effects: frozenset[str] | None = None
    """Effects it may have; must include every member's declared effects."""

    def data(self) -> dict[str, Json]:
        return {"kind": "composite", "name": self.name, "version": self.version,
                "members": list(self.members), "requires": _slots_data(self.requires),
                "exports": (None if self.exports is None
                            else [contract_data(c) for c in self.exports]),
                "effects": None if self.effects is None else sorted(self.effects)}

    @property
    def ref(self) -> Ref:
        return digest(self.data())


@dataclass(frozen=True)
class Attestation:
    """A claim of ``kind`` about the object ``subject`` (§28.4)."""

    subject: Ref
    kind: str
    claim: Mapping[str, Json]
    issuer: str = ""

    def data(self) -> dict[str, Json]:
        return {"kind": "attestation", "subject": self.subject, "claim_kind": self.kind,
                "claim": dict(self.claim), "issuer": self.issuer}

    @property
    def ref(self) -> Ref:
        return digest(self.data())


Object = Union[Primitive, Composite, Attestation]


def object_from(data: Mapping[str, Any]) -> Object:
    kind = data["kind"]
    if kind == "primitive":
        return Primitive(manifest_from(data["manifest"]), data["entry"], data["arguments"],
                         data["weights"], data["size"])
    if kind == "composite":
        exports = data["exports"]
        effects = data["effects"]
        return Composite(data["name"], data["version"], tuple(data["members"]),
                         _slots_from(data["requires"]),
                         None if exports is None else tuple(contract_from(c) for c in exports),
                         None if effects is None else frozenset(effects))
    if kind == "attestation":
        return Attestation(data["subject"], data["claim_kind"], data["claim"], data["issuer"])
    raise ValueError(f"unknown object kind {kind!r}")


def _effects_cover(declared: frozenset[str] | None, member: frozenset[str] | None) -> bool:
    return declared is None or (member is not None and member <= declared)


class Store:
    """Objects by reference, and attestations by subject.

    ``put`` admits a composite only once its members are present and its
    declared effects cover theirs, so every stored composite is a well-formed
    DAG node. ``save`` and ``open`` keep one canonical JSON file per object,
    named by its digest.
    """

    def __init__(self) -> None:
        self._objects: dict[Ref, Object] = {}
        self._about: dict[Ref, list[Ref]] = {}

    def __contains__(self, ref: object) -> bool:
        return ref in self._objects

    def __len__(self) -> int:
        return len(self._objects)

    def put(self, obj: Object) -> Ref:
        ref = obj.ref
        if ref in self._objects:
            return ref
        if isinstance(obj, Composite):
            for member in obj.members:
                if member not in self._objects:
                    raise KeyError(f"composite member {member} is not in the store")
                if not _effects_cover(obj.effects, self.effects(member)):
                    raise ValueError(f"{obj.name} does not declare the effects of {member}")
                if isinstance(self._objects[member], Attestation):
                    raise ValueError("an attestation cannot be a composite member")
        if isinstance(obj, Attestation):
            if obj.subject not in self._objects:
                raise KeyError(f"attestation subject {obj.subject} is not in the store")
            self._about.setdefault(obj.subject, []).append(ref)
        self._objects[ref] = obj
        return ref

    def get(self, ref: Ref) -> Object:
        return self._objects[ref]

    def effects(self, ref: Ref) -> frozenset[str] | None:
        obj = self._objects[ref]
        if isinstance(obj, Primitive):
            return obj.manifest.effects
        if isinstance(obj, Composite):
            return obj.effects
        raise ValueError("attestations have no effects")

    def attestations(self, subject: Ref, kind: str | None = None) -> list[Attestation]:
        """The attestations about ``subject``, in the order they were stored."""
        found = [self._objects[ref] for ref in self._about.get(subject, ())]
        return [a for a in found if isinstance(a, Attestation) and (kind is None or a.kind == kind)]

    def flatten(self, ref: Ref) -> list[Ref]:
        """The primitives of ``ref`` in member order, each at its first
        occurrence (§28.2). Exported and transparent composites alike are
        expanded; this is the transparent view."""
        seen: set[Ref] = set()
        order: list[Ref] = []

        def visit(node: Ref) -> None:
            obj = self._objects[node]
            if isinstance(obj, Primitive):
                if node not in seen:
                    seen.add(node)
                    order.append(node)
            elif isinstance(obj, Composite):
                for member in obj.members:
                    visit(member)

        visit(ref)
        return order

    def walk(self, ref: Ref) -> Iterator[Ref]:
        """Every object reachable from ``ref``, each once, members first."""
        seen: set[Ref] = set()

        def visit(node: Ref) -> Iterator[Ref]:
            if node in seen:
                return
            seen.add(node)
            obj = self._objects[node]
            if isinstance(obj, Composite):
                for member in obj.members:
                    yield from visit(member)
            yield node

        yield from visit(ref)

    def save(self, directory: Path) -> None:
        directory.mkdir(parents=True, exist_ok=True)
        for ref, obj in self._objects.items():
            path = directory / f"{ref.removeprefix('sha256:')}.json"
            if not path.exists():
                path.write_bytes(canonical(obj.data()))

    @classmethod
    def open(cls, directory: Path) -> Store:
        """Read every object in ``directory``, checking each file's digest."""
        store = cls()
        pending: dict[Ref, Object] = {}
        for path in sorted(directory.glob("*.json")):
            data = json.loads(path.read_bytes())
            ref = digest(data)
            if ref != f"sha256:{path.stem}":
                raise ValueError(f"{path.name} does not match its digest")
            pending[ref] = object_from(data)
        while pending:
            ready = [ref for ref, obj in pending.items() if _ready(store, obj)]
            if not ready:
                raise ValueError("objects refer to references missing from the store")
            for ref in ready:
                store.put(pending.pop(ref))
        return store


def _ready(store: Store, obj: Object) -> bool:
    if isinstance(obj, Composite):
        return all(member in store for member in obj.members)
    if isinstance(obj, Attestation):
        return obj.subject in store
    return True


class Names:
    """Mutable names for immutable references (§28.3)."""

    def __init__(self) -> None:
        self._names: dict[str, Ref] = {}

    def bind(self, name: str, ref: Ref) -> Ref | None:
        """Point ``name`` at ``ref`` and return what it pointed at before."""
        previous = self._names.get(name)
        self._names[name] = ref
        return previous

    def resolve(self, name: str) -> Ref:
        return self._names[name]

    def items(self) -> list[tuple[str, Ref]]:
        return sorted(self._names.items())


def primitive(module: Any, entry: str, arguments: Mapping[str, Json] | None = None,
              weights: Ref | None = None, size: int = 0) -> Primitive:
    """Describe an existing module as a primitive with the given loader."""
    return Primitive(module.manifest, entry, dict(arguments or {}), weights, size)
