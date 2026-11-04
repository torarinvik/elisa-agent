"""Cognitive ABI: typed contracts, module manifests, and the message envelope."""

from __future__ import annotations

import functools
import itertools
from collections.abc import Callable, Mapping
from dataclasses import dataclass, field
from typing import Any, Protocol

from nca.abi.types import (
    TypeId as TypeId,
    ScopedName as ScopedName,
    VarName as VarName,
    Var as Var,
    App as App,
    Term as Term,
    _TOKEN as _TOKEN,
    parse_type as parse_type,
    format_type as format_type,
    canonical_type as canonical_type,
    type_variables as type_variables,
    substitute as substitute,
    match_type as match_type,
    resolve as resolve,
    unify as unify,
    Binding as Binding,
    seq_type as seq_type,
    elem_type as elem_type,
)


@dataclass(frozen=True)
class Choice:
    """A value of type ``either[l,r]``: alternative ``index`` (0 for ``l``, 1 for
    ``r``) carrying ``value`` (THEORY §20.7). The other core constructors are
    represented by Python values: ``seq[a]`` by a sequence, ``pair[a,b]`` by a
    pair, and ``unit`` by ``()``."""

    index: int
    value: Any


Slot = tuple[tuple[TypeId, ...], TypeId]
"""A sub-goal ``inputs ⇒ output`` that the kernel fills with a plan."""


@dataclass(frozen=True)
class Contract:
    inputs: tuple[TypeId, ...]
    output: TypeId
    slots: tuple[Slot, ...] = ()
    """Sub-goals the module calls as functions (higher-order experts, ``NCA.HContract``)."""
    relevant: tuple[tuple[int, ...], ...] = ()
    """Legacy slot metadata retained for object identity; it imposes no constraint.

    Task-level input requirements are supplied to the planner separately.
    Slot functions may ignore any of their arguments.
    """

    def __post_init__(self) -> None:
        for type_id in (*self.inputs, self.output,
                        *(t for inputs, output in self.slots for t in (*inputs, output))):
            if canonical_type(type_id) != type_id:
                raise ValueError(f"type {type_id!r} is not in canonical form "
                                 f"{canonical_type(type_id)!r}")
        if len(self.relevant) > len(self.slots) or any(
                not 0 <= k < len(inputs)
                for positions, (inputs, _) in zip(self.relevant, self.slots) for k in positions):
            raise ValueError(f"relevant inputs {self.relevant!r} do not match the slots")

    @functools.cached_property
    def variables(self) -> frozenset[str]:
        """Every type variable of the contract."""
        return frozenset().union(*(type_variables(parse_type(t)) for t in (
            *self.inputs, self.output,
            *(t for inputs, output in self.slots for t in (*inputs, output)))))

    @functools.cached_property
    def free(self) -> frozenset[str]:
        """Variables that do not occur in the output (THEORY §2.2): the goal
        does not determine them, the plans for the inputs do."""
        return self.variables - type_variables(parse_type(self.output))

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
                              for inputs, output in self.slots), self.relevant)

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
    effects: frozenset[str] | None = None
    """What an invocation may do besides computing its output from its inputs
    (THEORY §28.5), for example ``{"random"}`` or ``{"io"}``. The empty set
    declares a pure expert, whose results may be cached and shared; ``None``
    declares nothing, so nothing may be assumed."""
    witness: str | None = None
    """Optional loader identifier for a proposal-only goal-decomposition witness."""

    def __post_init__(self) -> None:
        if self.witness is not None and (not isinstance(self.witness, str) or not self.witness):
            raise ValueError("witness identifier must be a nonempty string")

    @property
    def ref(self) -> str:
        return f"{self.module_id}@{self.version}"


class Module(Protocol):
    """An expert: known to the system by its manifest, run by ``invoke``."""

    manifest: Manifest

    def invoke(self, *inputs: Any) -> Any: ...


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
    inputs: tuple[tuple[TypeId, Any], ...] | Mapping[TypeId, Any]
    """The inputs as ``(type, value)`` pairs in order, so several may share a
    type (§20.8); a mapping is read in its order."""
    provisional: Any = None
    """The requester's own best answer, used if the request turns out irrelevant."""

    def __post_init__(self) -> None:
        pairs = tuple(self.inputs.items() if isinstance(self.inputs, Mapping) else self.inputs)
        if any(not isinstance(pair, tuple) or len(pair) != 2 for pair in pairs):
            raise ValueError("request inputs must be (type, value) pairs")
        object.__setattr__(self, "inputs", pairs)

    @property
    def types(self) -> tuple[TypeId, ...]:
        """The input types in order: the inputs available to the plan."""
        return tuple(type_id for type_id, _ in self.inputs)


_message_ids = itertools.count()


@dataclass(frozen=True)
class Message:
    type_id: TypeId
    payload: Any
    producer: str
    """Manifest ref of the producing module, or ``"input"`` for task inputs."""
    parents: tuple[str, ...] = ()
    message_id: str = field(default_factory=lambda: f"msg:{next(_message_ids)}")
