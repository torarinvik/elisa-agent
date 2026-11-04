"""Typed, proposal-only witness specifications for composition search.

Witnesses are supplied by expert packages. Their suggestions are not
certificates: callers must validate candidate routes on independent cases.
"""

from collections.abc import Callable, Iterable, Iterator, Sequence
from dataclasses import dataclass
from itertools import chain, product
from math import isfinite
from typing import Any

from nca.abi import (Contract, Manifest, Message, Module, Term, TypeId, canonical_type,
                     format_type, match_type, parse_type, type_variables)
from nca.objects import loaders
from nca.planner import Apply, Plan
from nca.router import infer
from nca.runtime import BudgetExceeded, UnresolvedRequest, execute
from nca.workspace import Workspace


@dataclass(frozen=True)
class Example:
    """One desired output on an ordered tuple of inputs."""

    inputs: tuple[Any, ...]
    output: Any


@dataclass(frozen=True)
class Specification:
    """A ground route goal and the examples it should satisfy."""

    contract: Contract
    examples: tuple[Example, ...]

    def __post_init__(self) -> None:
        if self.contract.slots or self.contract.variables:
            raise ValueError("witness goals must be ground and slot-free")
        if any(len(example.inputs) != len(self.contract.inputs) for example in self.examples):
            raise ValueError("witness examples must match their input scope")


@dataclass(frozen=True)
class Request:
    """A target plus an instantiated expert contract and optional argument values.

    Each arguments row contains that expert's ordinary input values for the
    corresponding target example. The rows are proposals, not observations
    of hidden intermediate labels.
    """

    target: Specification
    expert: Contract
    arguments: tuple[tuple[Any, ...], ...] | None = None

    def __post_init__(self) -> None:
        if self.expert.variables or self.expert.output != self.target.contract.output:
            raise ValueError("expert must be ground and produce the target type")
        if self.arguments is not None and (len(self.arguments) != len(self.target.examples)
                or any(len(row) != len(self.expert.inputs) for row in self.arguments)):
            raise ValueError("argument proposals must match examples and expert inputs")


@dataclass(frozen=True)
class Decomposition:
    """Subgoals for ordinary inputs and higher-order slots, in contract order."""

    inputs: tuple[Specification, ...]
    slots: tuple[Specification, ...]


def decompositions(manifest: Manifest, request: Request) -> Iterator[Decomposition]:
    """Call a declared witness and reject suggestions with mismatched scopes.

    Missing witnesses yield no suggestions, allowing a search to fall back to
    enumeration. Semantic soundness of suggestions is a witness obligation;
    the function neither evaluates nor admits a resulting route.
    """
    if manifest.witness is None:
        return
    pattern = manifest.contract
    expert = request.expert
    if (len(pattern.inputs) != len(expert.inputs) or len(pattern.slots) != len(expert.slots)
            or any(len(a[0]) != len(b[0]) for a, b in zip(pattern.slots, expert.slots, strict=True))):
        raise ValueError("expert contract is not an instance of the manifest")
    patterns = (*pattern.inputs, pattern.output,
                *(typ for inputs, output in pattern.slots for typ in (*inputs, output)))
    ground = (*expert.inputs, expert.output,
              *(typ for inputs, output in expert.slots for typ in (*inputs, output)))
    binding: dict[str, Term] = {}
    if (not all(match_type(parse_type(left), parse_type(right), binding)
                for left, right in zip(patterns, ground, strict=True))
            or pattern.instance(tuple(sorted((name, format_type(value)) for name, value in binding.items()))) != expert):
        raise ValueError("expert contract is not an instance of the manifest")
    provider = loaders.resolve(manifest.witness)
    for candidate in provider(request):
        if not isinstance(candidate, Decomposition):
            raise TypeError("witness must return Decomposition values")
        expected_inputs = tuple(Contract(request.target.contract.inputs, typ)
                                for typ in request.expert.inputs)
        expected_slots = tuple(Contract(inputs, output) for inputs, output in request.expert.slots)
        if (tuple(goal.contract for goal in candidate.inputs) != expected_inputs
                or tuple(goal.contract for goal in candidate.slots) != expected_slots):
            raise ValueError("witness subgoals do not match the expert's contract")
        yield candidate


def _value_key(value: Any) -> tuple[Any, ...]:
    """Preserve scalar and container types; refuse values without a safe key."""
    if type(value) in (type(None), bool, int, str, bytes):
        return (type(value).__name__, value)
    if type(value) is float:
        if not isfinite(value):
            raise TypeError("nonfinite float is not safely memoizable")
        return ("float", value.hex())
    if type(value) in (tuple, list):
        return (type(value).__name__, tuple(_value_key(item) for item in value))
    if type(value) is dict and all(type(key) is str for key in value):
        return ("dict", tuple((key, _value_key(value[key])) for key in sorted(value)))
    raise TypeError("value is not safely memoizable")


def propose(modules: Sequence[Module], target: Specification, *, types: Sequence[TypeId],
            depth: int, expansions: int, execution_budget: int,
            fallback: Callable[[Specification, int], Plan | None],
            hints: Callable[[Module, Contract, Specification], Iterable[tuple[tuple[Any, ...], ...]]] | None = None,
            agree: Callable[[Any, Any], bool] = lambda left, right: bool(left == right)) -> Plan | None:
    """Search witness subgoals, then use a caller-supplied enumeration fallback.

    The bounds limit recursive goal visits, grounded expert instances, witness
    suggestions and per-example execution, not work inside a witness, hint
    provider, or fallback; those callbacks must enforce their own limits.
    Memoization assumes fixed, deterministic callbacks.
    Every returned route is type-checked and checked on the goal's examples;
    this is proposal search and never a fresh-case certificate.
    """
    if any(type(n) is not int or n < 1 for n in (depth, expansions, execution_budget)):
        raise ValueError("search budgets must be positive integers")
    universe = tuple(dict.fromkeys(types))
    if not universe or any(canonical_type(typ) != typ or type_variables(parse_type(typ)) for typ in universe):
        raise ValueError("type universe must contain canonical ground types")
    if any(module.manifest.effects != frozenset() for module in modules):
        raise ValueError("witness search requires experts declaring pure effects")
    memo: dict[tuple[Any, ...], Plan] = {}
    remaining = expansions

    def spend() -> bool:
        nonlocal remaining
        if remaining <= 0:
            return False
        remaining -= 1
        return True

    def valid(goal: Specification, route: Plan) -> bool:
        if infer(modules, goal.contract.inputs, route) != goal.contract.output:
            return False
        for index, example in enumerate(goal.examples):
            messages = tuple(Message(typ, value, "witness-input", message_id=f"{index}:{position}")
                             for position, (typ, value) in enumerate(zip(
                                 goal.contract.inputs, example.inputs, strict=True)))
            workspace = Workspace()
            for message in messages:
                workspace.post(message)
            try:
                result = execute(route, messages, workspace, execution_budget).payload
                if not agree(result, example.output):
                    return False
            except (BudgetExceeded, UnresolvedRequest, ValueError, TypeError, IndexError, KeyError):
                return False
        return True

    def solve(goal: Specification, fuel: int) -> Plan | None:
        if fuel <= 0 or not spend():
            return None
        try:
            key = (goal.contract, fuel, tuple((_value_key(example.inputs), _value_key(example.output))
                                             for example in goal.examples))
        except (TypeError, RecursionError):
            key = None
        if key is not None and key in memo:
            return memo[key]
        for module in modules:
            pattern = module.manifest.contract
            if module.manifest.witness is None:
                continue
            matched = pattern.producing(goal.contract.output)
            if matched is None or any(value not in universe for _, value in matched):
                continue
            free = tuple(sorted(pattern.variables - dict(matched).keys()))
            for values in product(universe, repeat=len(free)):
                if not spend():
                    return None
                binding = tuple(sorted((*matched, *zip(free, values, strict=True))))
                expert = pattern.instance(binding)
                options = (None,) if hints is None else chain((None,), hints(module, expert, goal))
                for arguments in options:
                    if not spend():
                        return None
                    for split in decompositions(module.manifest, Request(goal, expert, arguments)):
                        if not spend():
                            return None
                        children: list[Plan] = []
                        for child in (*split.inputs, *split.slots):
                            result = solve(child, fuel - 1)
                            if result is None:
                                break
                            children.append(result)
                        else:
                            count = len(split.inputs)
                            route = Apply(module, tuple(children[:count]), tuple(children[count:]), binding)
                            if valid(goal, route):
                                if key is not None:
                                    memo[key] = route
                                return route
        route = fallback(goal, fuel)
        if route is not None and valid(goal, route):
            if key is not None:
                memo[key] = route
            return route
        return None

    return solve(target, depth)
