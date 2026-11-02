"""Composites installed as experts, each planned in its own scope (THEORY §28).

``install(store, ref)`` returns the experts a scope sees for an object:

* a primitive is one lazy expert, loaded on first use;
* a constructor is one ``Upcast`` per constructor it refines (§29.3);
* a transparent composite (``exports=None``) is its members' experts in
  member order, each primitive once, at its first occurrence;
* an exporting composite is one ``Export`` per exported contract, and
  nothing else: its members and their types are private to it.

An ``Export`` is an ordinary higher-order expert. Its contract is the
exported contract with the composite's requirements as slots, so the outer
planner fills the requirements exactly as it fills any slot (§20). Inside,
the composite's members and one ``Requirement`` expert per slot form the
inner library; the route for the export is planned there once, by the stable
planner, and requests made inside are resolved by a kernel over that library.
Planning in the outer scope therefore reads only exports, however many
experts the composites hold.

The export declares what its route costs: each internal invocation's
declared cost, map bodies once per element and internal slot fillings by
their declared calls, all at sequence length ``length``; and how often each
requirement is called, as fixed and per-element counts when that count is
affine in the length (no requirement inside nested maps).

``discover(store)`` finds packages contributed by any installed distribution
under the ``nca.packages`` entry-point group, puts them into the store and
binds their names (§28.6). A distribution contributes a package by naming a
callable that takes the store and returns the reference of what it put
there, so domains need no registration in the core and can ship separately.
"""

from __future__ import annotations

from collections.abc import Callable, Sequence
from importlib import metadata
from typing import Any

from nca.abi import (App, Calls, Contract, Manifest, Message, Module, Slot, format_type,
                     parse_type)
from nca.kernel import Kernel
from nca.loader import ExpertStore, LazyExpert
from nca.objects import Composite, Constructor, Names, Primitive, Ref, Store
from nca.optimize import slot_calls
from nca.index import ProducerIndex
from nca.planner import Given, Map, Plan, plan_stable_indexed
from nca.runtime import execute
from nca.workspace import Workspace


class Requirement:
    """A required slot seen from inside a composite: an expert whose
    implementation is the filling supplied by the current invocation."""

    def __init__(self, name: str, version: str, index: int, slot: Slot) -> None:
        inputs, output = slot
        self.manifest = Manifest(f"{name}/requires/{index}", version, Contract(inputs, output),
                                 cost=0.0)
        self._fillings: list[Callable[..., Any]] = []

    def risk(self, output: Any, *inputs: Any) -> float:
        """Its filling's invocations are charged where they run (§33)."""
        return 0.0

    def invoke(self, *values: Any) -> Any:
        if not self._fillings:
            raise RuntimeError(f"{self.manifest.module_id} invoked outside its composite")
        return self._fillings[-1](*values)


class Upcast:
    """The adapter realizing a refinement: a value of ``S(α…)`` is returned
    unchanged as a value of ``T(α…)`` (§29.3). It has no identity for the
    result cache, since recomputing it is cheaper than looking it up."""

    def __init__(self, constructor: Constructor, index: int) -> None:
        arguments = tuple(f"?a{i}" for i in range(constructor.arity))
        refined = constructor.refines[index]
        self.constructor = constructor
        self.manifest = Manifest(
            f"{constructor.name}/refines/{index}", constructor.version,
            Contract((constructor.type(*arguments),),
                     format_type(App(refined, tuple(parse_type(a) for a in arguments)))),
            cost=0.0, effects=frozenset())

    def risk(self, output: Any, *inputs: Any) -> float:
        return 0.0

    def invoke(self, value: Any) -> Any:
        return value


def charge(node: Plan, length: int, unit: Callable[[Module], float], *,
           strict: bool = False) -> float:
    """Sum of ``unit`` over the invocations of ``node`` at sequence length
    ``length``: map bodies once per element, slot fillings by their declared
    calls (THEORY §28.3, §31.2). A slot of an expert that declares no calls
    is counted once, or, with ``strict``, is an error."""
    if isinstance(node, Given):
        return 0.0
    if isinstance(node, Map):
        return (charge(node.source, length, unit, strict=strict)
                + length * charge(node.body, length, unit, strict=strict))
    calls = slot_calls(node.module.manifest, length)
    if not calls and node.slots:
        if strict:
            raise ValueError(f"{node.module.manifest.module_id} declares no slot calls")
        calls = [1.0] * len(node.slots)
    return (unit(node.module) + sum(charge(arg, length, unit, strict=strict) for arg in node.args)
            + sum(n * charge(sub, length, unit, strict=strict)
                  for n, sub in zip(calls, node.slots)))


def _affine(count: Callable[[int], float]) -> Calls | None:
    fixed, one, two = count(0), count(1), count(2)
    return Calls(fixed, one - fixed) if two - one == one - fixed else None


class Export:
    """One exported contract of a composite, as an expert of the outer scope."""

    accounts_inside = True
    """Its route runs on the caller's risk ledger (§33)."""

    def __init__(self, composite: Composite, index: int, members: Sequence[Module], *,
                 budget: int = 10_000, length: int = 1) -> None:
        assert composite.exports is not None
        exported = composite.exports[index]
        if exported.slots:
            raise ValueError("exported contracts take inputs only; requirements are the slots")
        self.composite = composite
        self.budget = budget
        self.requirements = [Requirement(composite.name, composite.version, i, slot)
                             for i, slot in enumerate(composite.requires)]
        self.library: list[Module] = [*members, *self.requirements]
        producer_index = ProducerIndex(self.library)
        route = plan_stable_indexed(producer_index, exported.inputs, exported.output)
        if route is None:
            raise ValueError(f"{composite.name} cannot implement its export "
                             f"{exported.inputs} ⇒ {exported.output}")
        self.route = route
        self.kernel = Kernel(self.library, index=producer_index)
        self.identity = f"{composite.ref}#{index}"

        def cost(at: int) -> float:
            return charge(route, at, lambda m: m.manifest.cost)

        counts = [_affine(lambda at, r=r: charge(route, at, lambda m: float(m is r)))
                  for r in self.requirements]
        self.manifest = Manifest(
            f"{composite.name}#{index}", composite.version,
            Contract(exported.inputs, exported.output, composite.requires),
            cost=cost(length),
            calls=tuple(c for c in counts if c is not None) if all(counts) else (),
            effects=composite.effects)

    def invoke(self, *values: Any) -> Any:
        count = len(self.requirements)
        fillings, inputs = values[:count], values[count:]
        for requirement, filling in zip(self.requirements, fillings, strict=True):
            requirement._fillings.append(filling)
        try:
            messages = [Message(t, value, "input")
                        for t, value in zip(self.manifest.contract.inputs, inputs, strict=True)]
            return execute(self.route, messages, Workspace(), self.budget, self.kernel).payload
        finally:
            for requirement in self.requirements:
                requirement._fillings.pop()


def _forward(expert: LazyExpert, name: str, default: Any) -> Callable[..., Any]:
    """The implementation's optional rule ``name``, or what its absence means."""
    def rule(*arguments: Any) -> Any:
        own = getattr(expert.store.acquire(expert), name, None)
        return default if own is None else own(*arguments)

    return rule


def install(store: Store, ref: Ref, experts: ExpertStore | None = None, *,
            budget: int = 10_000, length: int = 1) -> list[Module]:
    """The experts a scope sees for the object ``ref``, in order.

    Primitives become lazy experts in ``experts`` (a fresh unbounded store by
    default), each with its reference as identity, so a primitive shared by
    several composites is one expert. Their demand and relevance rules and
    risk reports are the implementation's, read when first asked (loading
    it); without a rule, everything is demanded and relevant, and without a
    report the risk is unreported. ``budget`` bounds the
    invocations of one call of an export, and ``length`` is the sequence
    length at which exports declare their cost.
    """
    experts = experts if experts is not None else ExpertStore()
    made: dict[Ref, Module] = {}
    made_upcasts: dict[Ref, list[Module]] = {}

    def module(node: Ref) -> Module:
        if node not in made:
            obj = store.get(node)
            assert isinstance(obj, Primitive)
            resolved: dict[Ref, tuple[Module, ...]] = {}
            for dependency in obj.dependencies:
                if dependency not in resolved:
                    resolved[dependency] = tuple(scope(dependency))
            prerequisites = dict.fromkeys(
                ref for dependency in obj.dependencies for ref in store.walk(dependency)
                if isinstance(store.get(ref), Primitive))
            expert = LazyExpert(obj.manifest, lambda: obj.load(resolved.__getitem__),
                                obj.size, experts, identity=node,
                                dependencies=tuple(module(ref) for ref in prerequisites))
            expert.demand = _forward(expert, "demand", None)
            expert.relevant = _forward(expert, "relevant", True)
            expert.risk = _forward(expert, "risk", None)
            made[node] = expert
        return made[node]

    def members(obj: Composite) -> list[Module]:
        seen: set[int] = set()
        ordered = []
        for member in obj.members:
            for expert in scope(member):
                if id(expert) not in seen:
                    seen.add(id(expert))
                    ordered.append(expert)
        return ordered

    def scope(node: Ref) -> list[Module]:
        obj = store.get(node)
        if isinstance(obj, Primitive):
            return [module(node)]
        if isinstance(obj, Constructor):
            if node not in made_upcasts:
                made_upcasts[node] = [Upcast(obj, i) for i in range(len(obj.refines))]
            return made_upcasts[node]
        if not isinstance(obj, Composite):
            raise ValueError("only experts, composites and constructors can be installed")
        if obj.exports is None:
            return members(obj)
        inner = members(obj)
        return [Export(obj, i, inner, budget=budget, length=length)
                for i in range(len(obj.exports))]

    return scope(ref)


GROUP = "nca.packages"


def discover(store: Store, names: Names | None = None, group: str = GROUP) -> Names:
    """Put every package contributed under the entry-point ``group`` into
    ``store``, in name order, and bind each entry point's name to its
    reference in ``names`` (fresh by default).

    A name contributed twice, a name already bound to another reference, a
    contribution that fails and a reference missing from the store are
    errors naming the contribution; nothing is guessed.
    """
    names = names if names is not None else Names()
    found = sorted(metadata.entry_points(group=group), key=lambda entry: entry.name)
    for previous, entry in zip(found, found[1:]):
        if previous.name == entry.name:
            raise ValueError(f"package {entry.name} is contributed twice: "
                             f"{previous.value} and {entry.value}")
    for entry in found:
        try:
            ref = entry.load()(store)
        except Exception as error:
            raise RuntimeError(f"package {entry.name} ({entry.value}) failed") from error
        if ref not in store:
            raise ValueError(f"package {entry.name} returned {ref}, which is not in the store")
        previous = names.bind(entry.name, ref)
        if previous not in (None, ref):
            names.bind(entry.name, previous)
            raise ValueError(f"package {entry.name} is already bound to {previous}")
    return names
