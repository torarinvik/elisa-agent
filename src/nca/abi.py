"""Cognitive ABI: typed contracts, module manifests, and the message envelope."""

from __future__ import annotations

import functools
import itertools
import re
from collections.abc import Callable, Mapping
from dataclasses import dataclass, field
from typing import Any

TypeId = str
"""A semantic type in its canonical text form (THEORY §1.1): a constructor
name, optionally applied to argument types, as in ``"digit.distribution.v1"``
or ``"seq[digit.distribution.v1]"``. Names carry their namespace and version.
Variables (``"?a"``) stand for any type.

Two values are compatible only if their type ids are equal; byte shape alone
never implies compatibility. Conversions between types are modules.
"""


@dataclass(frozen=True)
class Var:
    """A type variable."""

    name: str


@dataclass(frozen=True)
class App:
    """A constructor applied to argument types; a constant has none."""

    name: str
    args: tuple[Term, ...] = ()


Term = Var | App
"""A type term (THEORY §1.1)."""

_TOKEN = re.compile(r"\s*(\??[A-Za-z0-9_][A-Za-z0-9_./-]*|[\[\],])")


@functools.lru_cache(maxsize=65536)
def parse_type(type_id: TypeId) -> Term:
    """The term ``type_id`` denotes; ``ValueError`` if it is not well formed."""
    tokens: list[str] = []
    position = 0
    text = type_id.rstrip()
    while position < len(text):
        match = _TOKEN.match(text, position)
        if match is None:
            raise ValueError(f"malformed type {type_id!r} at {position}")
        tokens.append(match.group(1))
        position = match.end()

    def term(i: int) -> tuple[Term, int]:
        if i >= len(tokens) or tokens[i] in "[],":
            raise ValueError(f"malformed type {type_id!r}: expected a name")
        name = tokens[i]
        if name.startswith("?"):
            return Var(name[1:]), i + 1
        if i + 1 >= len(tokens) or tokens[i + 1] != "[":
            return App(name), i + 1
        args = []
        i += 2
        while True:
            arg, i = term(i)
            args.append(arg)
            if i < len(tokens) and tokens[i] == ",":
                i += 1
            elif i < len(tokens) and tokens[i] == "]":
                return App(name, tuple(args)), i + 1
            else:
                raise ValueError(f"malformed type {type_id!r}: expected ',' or ']'")

    result, end = term(0)
    if end != len(tokens):
        raise ValueError(f"malformed type {type_id!r}: trailing input")
    return result


def format_type(term: Term) -> TypeId:
    """The canonical text form of ``term``."""
    if isinstance(term, Var):
        return f"?{term.name}"
    if not term.args:
        return term.name
    return f"{term.name}[{','.join(format_type(a) for a in term.args)}]"


def canonical_type(type_id: TypeId) -> TypeId:
    """``type_id`` in canonical form, without whitespace."""
    return format_type(parse_type(type_id))


def type_variables(term: Term) -> frozenset[str]:
    """The variables occurring in ``term``."""
    if isinstance(term, Var):
        return frozenset((term.name,))
    return frozenset().union(*(type_variables(a) for a in term.args))


def substitute(term: Term, binding: Mapping[str, Term]) -> Term:
    """``term`` with each bound variable replaced (THEORY §1.2)."""
    if isinstance(term, Var):
        return binding.get(term.name, term)
    return App(term.name, tuple(substitute(a, binding) for a in term.args))


def match_type(pattern: Term, ground: Term, binding: dict[str, Term]) -> bool:
    """Extend ``binding`` so that ``pattern`` instantiates to ``ground``; ``False``
    if no extension does. On success the bound variables are exactly those of
    ``pattern`` not bound before (THEORY §2.1)."""
    if isinstance(pattern, Var):
        bound = binding.setdefault(pattern.name, ground)
        return bound == ground
    return (isinstance(ground, App) and pattern.name == ground.name
            and len(pattern.args) == len(ground.args)
            and all(match_type(p, g, binding) for p, g in zip(pattern.args, ground.args)))


Binding = tuple[tuple[str, TypeId], ...]
"""A substitution, as its variables (sorted) and the types bound to them."""


@functools.lru_cache(maxsize=65536)
def seq_type(element: TypeId) -> TypeId:
    """The type of finite sequences of ``element``."""
    return format_type(App("seq", (parse_type(element),)))


@functools.lru_cache(maxsize=65536)
def elem_type(type_id: TypeId) -> TypeId | None:
    """The element type if ``type_id`` is a sequence type, else ``None``."""
    term = parse_type(type_id)
    if isinstance(term, App) and term.name == "seq" and len(term.args) == 1:
        return format_type(term.args[0])
    return None


Slot = tuple[tuple[TypeId, ...], TypeId]
"""A sub-goal ``inputs ⇒ output`` that the kernel fills with a plan."""


@dataclass(frozen=True)
class Contract:
    inputs: tuple[TypeId, ...]
    output: TypeId
    slots: tuple[Slot, ...] = ()
    """Sub-goals the module calls as functions (higher-order experts, ``NCA.HContract``)."""

    def __post_init__(self) -> None:
        for type_id in (*self.inputs, self.output,
                        *(t for inputs, output in self.slots for t in (*inputs, output))):
            if canonical_type(type_id) != type_id:
                raise ValueError(f"type {type_id!r} is not in canonical form "
                                 f"{canonical_type(type_id)!r}")
        unbound = frozenset().union(
            *(type_variables(parse_type(t)) for t in (*self.inputs, *(
                t for inputs, output in self.slots for t in (*inputs, output))))
        ) - type_variables(parse_type(self.output))
        if unbound:
            raise ValueError(f"contract is not range-restricted: variables {sorted(unbound)} "
                             "do not occur in its output")

    @functools.cached_property
    def polymorphic(self) -> bool:
        """Whether the contract has type variables (THEORY §1.2)."""
        return bool(type_variables(parse_type(self.output)))

    def instance(self, binding: Binding) -> Contract:
        """The contract with ``binding`` substituted."""
        if not binding:
            return self
        terms = {name: parse_type(t) for name, t in binding}

        def bind(type_id: TypeId) -> TypeId:
            return format_type(substitute(parse_type(type_id), terms))

        return Contract(tuple(bind(t) for t in self.inputs), bind(self.output),
                        tuple((tuple(bind(t) for t in inputs), bind(output))
                              for inputs, output in self.slots))

    def producing(self, goal: TypeId) -> Binding | None:
        """The binding of the unique instance whose output is the ground type
        ``goal`` (THEORY §2.1, Theorem 2.4), or ``None`` if there is none."""
        if not self.polymorphic:
            return () if self.output == goal else None
        binding: dict[str, Term] = {}
        if not match_type(parse_type(self.output), parse_type(goal), binding):
            return None
        return tuple(sorted((name, format_type(t)) for name, t in binding.items()))


@dataclass(frozen=True)
class Calls:
    """Calls per invocation to a slot on inputs of length ``L``:
    ``fixed + per_element · L``."""

    fixed: float = 0.0
    per_element: float = 0.0

    def at(self, length: int) -> float:
        return self.fixed + self.per_element * length


@dataclass(frozen=True)
class Manifest:
    module_id: str
    version: str
    contract: Contract
    cost: float = 1.0
    """Cost of one invocation (for example, floating-point operations)."""
    calls: tuple[Calls, ...] = ()
    """Worst-case calls per invocation to each slot (``ν``), for budgets and
    guarantees."""
    expected_calls: tuple[Calls, ...] | None = None
    """Expected calls per invocation to each slot (``ν̄``), the planner's cost
    objective; ``calls`` if not declared."""

    @property
    def ref(self) -> str:
        return f"{self.module_id}@{self.version}"


@dataclass(frozen=True)
class SequenceDemand:
    """Demand on a sequence: what is read of element ``i`` of a length-``n`` sequence."""

    element: Callable[[int, int], "Demand"]


Demand = frozenset[str] | SequenceDemand | None
"""What a consumer reads of a value: ``None`` everything, a set of named fields,
or a per-element demand for sequences. The empty set means nothing is read."""

NOTHING: frozenset[str] = frozenset()


@dataclass(frozen=True)
class Request:
    """Asks the kernel: "produce a value of ``type_id`` from these inputs, without
    me". Returned by a module to delegate its output, or yielded by a module's
    generator to obtain a sub-result and continue."""

    type_id: TypeId
    inputs: Mapping[TypeId, Any]
    provisional: Any = None
    """The requester's own best answer, used if the request turns out irrelevant."""


_message_ids = itertools.count()


@dataclass(frozen=True)
class Message:
    type_id: TypeId
    payload: Any
    producer: str
    """Manifest ref of the producing module, or ``"input"`` for task inputs."""
    parents: tuple[str, ...] = ()
    message_id: str = field(default_factory=lambda: f"msg:{next(_message_ids)}")
