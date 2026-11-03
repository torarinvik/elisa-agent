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
import json
import math
from collections.abc import Callable, Mapping, Sequence
from dataclasses import dataclass, field
from pathlib import Path
from typing import Any, Union

from nca.abi import App, Calls, Contract, Manifest, Module, Slot, Term, Var, format_type, parse_type
from nca.objects import loaders

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

    ``entry`` names a callable: a loader identifier registered under
    ``nca.loaders`` (``loaders``), which survives code moves, or else a
    ``"package.module:attribute"`` import path. Loading calls it with
    ``arguments`` and expects a module whose manifest equals this one.
    ``weights`` is the digest of the bytes the implementation loads, so
    implementations that differ only in their weights differ in reference.
    Nonempty ``dependencies`` resolve to ordered executable scopes passed as
    the factory's reserved ``dependencies`` keyword. Factories retain these
    lazy modules; they must not invoke them during loading.
    """

    manifest: Manifest
    entry: str
    arguments: Mapping[str, Json] = field(default_factory=dict)
    weights: Ref | None = None
    size: int = 0
    """Resident bytes once loaded, for the expert store's budget."""
    dependencies: tuple[Ref, ...] = ()
    """Executable scopes passed lazily to the factory, in order (§28.7)."""

    def data(self) -> dict[str, Json]:
        data: dict[str, Json] = {"kind": "primitive", "manifest": manifest_data(self.manifest),
                                "entry": self.entry, "arguments": dict(self.arguments),
                                "weights": self.weights, "size": self.size}
        if self.dependencies:
            data["dependencies"] = list(self.dependencies)
        return data

    @property
    def ref(self) -> Ref:
        return digest(self.data())

    def load(self, resolve: Callable[[Ref], Sequence[Module]] | None = None) -> Any:
        target = loaders.resolve(self.entry)
        arguments: dict[str, Any] = dict(self.arguments)
        if self.dependencies:
            if resolve is None:
                raise ValueError("loading dependencies needs a scope resolver")
            if "dependencies" in arguments:
                raise ValueError("dependencies is reserved for resolved expert scopes")
            arguments["dependencies"] = tuple(tuple(resolve(ref)) for ref in self.dependencies)
        implementation = target(**arguments)
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
                         data["weights"], data["size"], tuple(data.get("dependencies", ())))
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


def primitive(module: Any, entry: str, arguments: Mapping[str, Json] | None = None,
              weights: Ref | None = None, size: int = 0,
              dependencies: tuple[Ref, ...] = ()) -> Primitive:
    """Describe an existing module as a primitive with the given loader."""
    return Primitive(module.manifest, entry, dict(arguments or {}), weights, size, dependencies)

from nca.objects.store import (
    Store as Store,
    Names as Names,
    _ready as _ready,
    _contracts as _contracts,
    _requires as _requires,
    _effects_cover as _effects_cover,
)
