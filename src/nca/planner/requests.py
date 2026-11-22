"""Discover concrete kernel requests from installed signatures and typed observations."""
from __future__ import annotations

from collections.abc import Iterable, Iterator, Sequence
from dataclasses import dataclass
from typing import overload

from nca.abi import (Contract, Message, Module, Request, Term, Var, VarName, format_type,
                     match_type, parse_type, substitute, type_variables)

from nca.index import ProducerIndex
from nca.planner import Apply, Given, plan_stable_indexed


class ProviderGroup(Sequence[Module]):
    """Read-only, installation-ordered view of providers for one request signature."""

    def __init__(self) -> None:
        self._items: list[Module] = []
        self._refs: dict[str, Module | None] = {}

    def _append(self, module: Module) -> None:
        ref = module.manifest.ref
        self._refs[ref] = None if ref in self._refs else module
        self._items.append(module)

    def __len__(self) -> int:
        return len(self._items)

    @overload
    def __getitem__(self, key: int) -> Module: ...

    @overload
    def __getitem__(self, key: slice) -> list[Module]: ...

    def __getitem__(self, key: int | slice) -> Module | list[Module]:
        return self._items[key]

    def by_ref(self, ref: str) -> Module | None:
        """Look up a unique installed provider without scanning its peers."""
        return self._refs.get(ref)


@dataclass(frozen=True)
class RequestCandidate:
    request: Request
    providers: ProviderGroup
    """Compatible declarations in installation order. Implementations remain unloaded."""


class RequestTemplates:
    """An append-only index of distinct request signatures, independent of expert weights."""

    def __init__(self, modules: Iterable[Module] = ()) -> None:
        self._empty: list[Contract] = []
        self._heads: dict[str | None, list[Contract]] = {}
        self._providers: dict[tuple[tuple[str, ...], str], ProviderGroup] = {}
        for module in modules:
            self.add(module)

    def add(self, module: Module) -> None:
        contract = module.manifest.contract
        signature = contract.inputs, contract.output
        if signature in self._providers:
            self._providers[signature]._append(module)
            return
        self._providers[signature] = ProviderGroup()
        self._providers[signature]._append(module)
        if not contract.inputs:
            self._empty.append(contract)
            return
        first = parse_type(contract.inputs[0])
        head = None if isinstance(first, Var) else first.name
        self._heads.setdefault(head, []).append(contract)

    def candidates(self, messages: Sequence[Message], *, work: int | None = None) -> Iterator[RequestCandidate]:
        """Yield bindings lazily, including distinct values of the same type.

        Only ground result types inferred from the supplied inputs are offered.
        A template is a proposal. The resolver checks reachability and slot fillings.
        A finite work allowance charges each signature visit and each attempted operand match.
        """
        if work is not None and (type(work) is not int or work < 0):
            raise ValueError("binding work must be a nonnegative integer")
        remaining = None if work is None else iter(range(work))
        terms = tuple(parse_type(message.type_id) for message in messages)
        if any(type_variables(term) for term in terms):
            raise ValueError("request evidence must have ground types")
        for contract in self._empty:
            if remaining is not None and next(remaining, None) is None:
                return
            if not type_variables(parse_type(contract.output)):
                yield RequestCandidate(Request(contract.output, ()), self._providers[((), contract.output)])
        heads = dict.fromkeys(term.name for term in terms)
        if heads:
            for head in (*heads, None):
                for contract in self._heads.get(head, ()):
                    if remaining is not None and next(remaining, None) is None:
                        return
                    providers = self._providers[(contract.inputs, contract.output)]
                    for request in _bindings(contract, messages, terms, remaining):
                        yield RequestCandidate(request, providers)

    def requests(self, messages: Sequence[Message]) -> Iterator[Request]:
        """Concrete type-based requests using the kernel's stable routing policy."""
        for candidate in self.candidates(messages):
            yield candidate.request


def _bindings(contract: Contract, messages: Sequence[Message], terms: Sequence[Term],
              remaining: Iterator[int] | None) -> Iterator[Request]:
    patterns = tuple(map(parse_type, contract.inputs))
    output = parse_type(contract.output)
    inputs: list[tuple[str, object]] = []

    def visit(position: int, binding: dict[VarName, Term]) -> Iterator[Request]:
        if position == len(patterns):
            result = substitute(output, binding)
            if not type_variables(result):
                yield Request(format_type(result), tuple(inputs))
            return
        for message, term in zip(messages, terms):
            if remaining is not None and next(remaining, None) is None:
                return
            extended = binding.copy()
            if match_type(patterns[position], term, extended):
                inputs.append((message.type_id, message.payload))
                yield from visit(position + 1, extended)
                inputs.pop()

    yield from visit(0, {})


def bound_route(module: Module, inputs: tuple[str, ...], output: str, index: ProducerIndex,
                fuel: int) -> Apply | None:
    """Type-check a provider call on its explicitly bound operands and plan its slots."""
    contract = module.manifest.contract
    if len(inputs) != len(contract.inputs) or fuel < 1:
        return None
    if inputs and fuel < 2:
        return None
    binding: dict[VarName, Term] = {}
    for pattern, actual in zip((*contract.inputs, contract.output), (*inputs, output)):
        term = parse_type(actual)
        if type_variables(term) or not match_type(parse_type(pattern), term, binding):
            return None
    if contract.variables != binding.keys():
        return None
    parameters = tuple(sorted((name, format_type(term)) for name, term in binding.items()))
    instance = contract.instance(parameters)
    slots = []
    for available, goal in instance.slots:
        route = plan_stable_indexed(index, available, goal, fuel - 1)
        if route is None:
            return None
        slots.append(route)
    return Apply(module, tuple(Given(t, i) for i, t in enumerate(inputs)), tuple(slots), parameters)
