"""Type terms, canonical syntax, substitution, matching and unification."""
from __future__ import annotations

import functools
import re
from collections.abc import Mapping
from dataclasses import dataclass
from typing import NamedTuple

TypeId = str
"""A semantic type in its canonical text form (THEORY §1.1): a constructor
name, optionally applied to argument types, as in ``"image.rgb.v1"``
or ``"seq[image.rgb.v1]"``. Names carry their namespace and version, or
are the ``sha256:`` reference of a constructor object (§29.1). Variables
(``"?a"``) stand for any type.

Two values are compatible only if their type ids are equal; byte shape alone
never implies compatibility. Conversions between types are modules.
"""


class ScopedName(NamedTuple):
    """Internal variable identity, disjoint from names parsed from contracts."""

    name: str
    scope: int

VarName = str | ScopedName


@dataclass(frozen=True)
class Var:
    """A type variable."""

    name: VarName


@dataclass(frozen=True)
class App:
    """A constructor applied to argument types; a constant has none."""

    name: str
    args: tuple[Term, ...] = ()


Term = Var | App
"""A type term (THEORY §1.1)."""

_TOKEN = re.compile(r"\s*(\??[A-Za-z0-9_][A-Za-z0-9_./:-]*|[\[\],])")


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
        if isinstance(term.name, ScopedName):
            raise ValueError("cannot serialize an unresolved scoped variable")
        return f"?{term.name}"
    if not term.args:
        return term.name
    return f"{term.name}[{','.join(format_type(a) for a in term.args)}]"


def canonical_type(type_id: TypeId) -> TypeId:
    """``type_id`` in canonical form, without whitespace."""
    return format_type(parse_type(type_id))


def type_variables(term: Term) -> frozenset[VarName]:
    """The variables occurring in ``term``."""
    if isinstance(term, Var):
        return frozenset((term.name,))
    if not term.args:
        return frozenset()
    return frozenset().union(*(type_variables(a) for a in term.args))


def substitute(term: Term, binding: Mapping[VarName, Term]) -> Term:
    """``term`` with each bound variable replaced (THEORY §1.2)."""
    if isinstance(term, Var):
        return binding.get(term.name, term)
    if not term.args:
        return term
    return App(term.name, tuple(substitute(a, binding) for a in term.args))


def match_type(pattern: Term, ground: Term, binding: dict[VarName, Term]) -> bool:
    """Extend ``binding`` so that ``pattern`` instantiates to ``ground``; ``False``
    if no extension does. On success the bound variables are exactly those of
    ``pattern`` not bound before (THEORY §2.1)."""
    if isinstance(pattern, Var):
        bound = binding.setdefault(pattern.name, ground)
        return bound == ground
    return (isinstance(ground, App) and pattern.name == ground.name
            and len(pattern.args) == len(ground.args)
            and all(match_type(p, g, binding) for p, g in zip(pattern.args, ground.args)))


def resolve(term: Term, binding: Mapping[VarName, Term]) -> Term:
    """``term`` under a binding whose bound terms may mention bound variables:
    substitute until no bound variable remains."""
    if isinstance(term, Var):
        bound = binding.get(term.name)
        return term if bound is None else resolve(bound, binding)
    if not term.args:
        return term
    args = tuple(resolve(a, binding) for a in term.args)
    return term if args == term.args else App(term.name, args)


def unify(left: Term, right: Term, binding: dict[VarName, Term]) -> bool:
    """Extend ``binding`` to a most general unifier of ``left`` and ``right``
    (THEORY §2.2); ``False`` if none exists. ``binding`` may be partly extended
    on failure, so callers pass a copy they can discard."""
    left, right = resolve(left, binding), resolve(right, binding)
    if isinstance(left, Var) or isinstance(right, Var):
        if left == right:
            return True
        var, term = (left, right) if isinstance(left, Var) else (right, left)
        assert isinstance(var, Var)
        if var.name in type_variables(term):
            return False
        binding[var.name] = term
        return True
    return (left.name == right.name and len(left.args) == len(right.args)
            and all(unify(a, b, binding) for a, b in zip(left.args, right.args)))


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
