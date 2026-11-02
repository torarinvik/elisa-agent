"""Content-addressed objects: experts, composites, attestations and type
constructors (THEORY §28, §29).

Every object is immutable data identified by the SHA-256 digest of its
canonical encoding, its *reference*. There are four kinds:

* ``Primitive``: one expert, its manifest and how to load its implementation
  (an entry point, JSON arguments, and the digest of its weights);
* ``Composite``: an ordered list of member references, each a primitive or a
  composite, with the slots it requires from its surroundings and the
  contracts it exports (``None`` exports every member: a transparent
  composite);
* ``Attestation``: a claim about another object, such as calibration
  temperatures, an audit or a signature, kept beside its subject rather than
  inside it;
* ``Constructor``: a type constructor, its arity, meaning and the
  constructors it refines. Its reference is its name in type terms, so a
  contract that mentions it names exactly this constructor.

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

from nca.abi import App, Calls, Contract, Manifest, Slot, Term, Var, format_type, parse_type

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
    """A claim of ``kind`` about the object ``subject`` (§28.4), made by
    ``issuer``. A signed attestation's issuer is a public key, written
    ``scheme:key``, and ``signature`` signs its unsigned data (§32)."""

    subject: Ref
    kind: str
    claim: Mapping[str, Json]
    issuer: str = ""
    signature: str | None = None

    def unsigned(self) -> dict[str, Json]:
        """What a signature signs."""
        return {"kind": "attestation", "subject": self.subject, "claim_kind": self.kind,
                "claim": dict(self.claim), "issuer": self.issuer}

    def data(self) -> dict[str, Json]:
        data = self.unsigned()
        if self.signature is not None:
            data["signature"] = self.signature
        return data

    @property
    def ref(self) -> Ref:
        return digest(self.data())


@dataclass(frozen=True)
class Constructor:
    """A type constructor (§29.1). ``meaning`` states what its values are and
    how they are represented; ``refines`` lists constructors of the same
    arity whose values include its own, with the same representation
    (§29.2)."""

    name: str
    version: str
    arity: int
    meaning: str
    refines: tuple[Ref, ...] = ()

    def data(self) -> dict[str, Json]:
        return {"kind": "constructor", "name": self.name, "version": self.version,
                "arity": self.arity, "meaning": self.meaning, "refines": list(self.refines)}

    @property
    def ref(self) -> Ref:
        return digest(self.data())

    def type(self, *arguments: str) -> str:
        """The type this constructor builds from ``arguments``."""
        if len(arguments) != self.arity:
            raise ValueError(f"{self.name} takes {self.arity} arguments, not {len(arguments)}")
        return format_type(App(self.ref, tuple(parse_type(a) for a in arguments)))


Object = Union[Primitive, Composite, Attestation, Constructor]


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
        return Attestation(data["subject"], data["claim_kind"], data["claim"], data["issuer"],
                           data.get("signature"))
    if kind == "constructor":
        return Constructor(data["name"], data["version"], data["arity"], data["meaning"],
                           tuple(data["refines"]))
    raise ValueError(f"unknown object kind {kind!r}")


def _constructors(term: Term, found: dict[Ref, int]) -> None:
    if isinstance(term, Var):
        return
    if term.name.startswith("sha256:"):
        if found.setdefault(term.name, len(term.args)) != len(term.args):
            raise ValueError(f"constructor {term.name} is applied to different numbers of arguments")
    for argument in term.args:
        _constructors(argument, found)


def constructors(contracts: Sequence[Contract]) -> dict[Ref, int]:
    """The constructor references ``contracts`` mention, with the number of
    arguments each is applied to."""
    found: dict[Ref, int] = {}
    for contract in contracts:
        for type_id in (*contract.inputs, contract.output,
                        *(t for inputs, output in contract.slots for t in (*inputs, output))):
            _constructors(parse_type(type_id), found)
    return found


def _contracts(obj: Object) -> list[Contract]:
    if isinstance(obj, Primitive):
        return [obj.manifest.contract]
    if isinstance(obj, Composite):
        return [*(obj.exports or ()), *(Contract(inputs, output) for inputs, output in obj.requires)]
    return []


def _requires(obj: Object) -> list[Ref]:
    """The references ``obj`` cannot be admitted without."""
    if isinstance(obj, Composite):
        own = list(obj.members)
    elif isinstance(obj, Attestation):
        own = [obj.subject]
    elif isinstance(obj, Constructor):
        own = list(obj.refines)
    else:
        own = []
    return [*own, *constructors(_contracts(obj))]


def _effects_cover(declared: frozenset[str] | None, member: frozenset[str] | None) -> bool:
    return declared is None or (member is not None and member <= declared)


class Store:
    """Objects by reference, and attestations by subject.

    ``put`` admits an object only once every reference it depends on is
    present: a composite's members (whose effects its declaration must
    cover), an attestation's subject, a constructor's refined constructors
    (of equal arity), and every constructor its contracts mention (applied
    to as many arguments as its arity), so every stored object is a
    well-formed DAG node. ``save`` and ``open`` keep one canonical JSON file per object,
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
        for needed in _requires(obj):
            if needed not in self._objects:
                raise KeyError(f"{needed}, needed by {ref}, is not in the store")
        for constructor, arity in constructors(_contracts(obj)).items():
            found = self._objects[constructor]
            if not isinstance(found, Constructor) or found.arity != arity:
                raise ValueError(f"{constructor} is not a constructor of arity {arity}")
        if isinstance(obj, Constructor):
            for refined in obj.refines:
                found = self._objects[refined]
                if not isinstance(found, Constructor) or found.arity != obj.arity:
                    raise ValueError(f"{obj.name} refines {refined}, "
                                     f"which is not a constructor of arity {obj.arity}")
        if isinstance(obj, Composite):
            for member in obj.members:
                if isinstance(self._objects[member], Attestation):
                    raise ValueError("an attestation cannot be a composite member")
                if not _effects_cover(obj.effects, self.effects(member)):
                    raise ValueError(f"{obj.name} does not declare the effects of {member}")
        if isinstance(obj, Attestation):
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
        if isinstance(obj, Constructor):
            return frozenset()  # Its upcasts return their input.
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
    return all(needed in store for needed in _requires(obj))


class Names:
    """Mutable names for immutable references (§28.6)."""

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
