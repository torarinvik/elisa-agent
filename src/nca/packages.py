"""Composites installed as experts, each planned in its own scope (THEORY §28).

``install(store, ref)`` returns the experts a scope sees for an object:

* a primitive is one lazy expert, loaded on first use;
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
"""

from __future__ import annotations

from collections.abc import Callable, Sequence
from typing import Any

from nca.abi import Calls, Contract, Manifest, Message, Module, Slot
from nca.kernel import Kernel
from nca.loader import ExpertStore, LazyExpert
from nca.objects import Composite, Primitive, Ref, Store
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

    def invoke(self, *values: Any) -> Any:
        if not self._fillings:
            raise RuntimeError(f"{self.manifest.module_id} invoked outside its composite")
        return self._fillings[-1](*values)


def _profile(node: Plan, length: int, unit: Callable[[Module], float]) -> float:
    """Sum of ``unit`` over the invocations of ``node`` at sequence length ``length``."""
    if isinstance(node, Given):
        return 0.0
    if isinstance(node, Map):
        return _profile(node.source, length, unit) + length * _profile(node.body, length, unit)
    calls = slot_calls(node.module.manifest, length) or [1.0] * len(node.slots)
    return (unit(node.module) + sum(_profile(arg, length, unit) for arg in node.args)
            + sum(n * _profile(sub, length, unit) for n, sub in zip(calls, node.slots)))


def _affine(count: Callable[[int], float]) -> Calls | None:
    fixed, one, two = count(0), count(1), count(2)
    return Calls(fixed, one - fixed) if two - one == one - fixed else None


class Export:
    """One exported contract of a composite, as an expert of the outer scope."""

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
        index = ProducerIndex(self.library)
        route = plan_stable_indexed(index, exported.inputs, exported.output)
        if route is None:
            raise ValueError(f"{composite.name} cannot implement its export "
                             f"{exported.inputs} ⇒ {exported.output}")
        self.route = route
        self.kernel = Kernel(self.library, index=index)
        self.identity = f"{composite.ref}#{index}"

        def cost(at: int) -> float:
            return _profile(route, at, lambda m: m.manifest.cost)

        counts = [_affine(lambda at, r=r: _profile(route, at, lambda m: float(m is r)))
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


def install(store: Store, ref: Ref, experts: ExpertStore | None = None, *,
            budget: int = 10_000, length: int = 1) -> list[Module]:
    """The experts a scope sees for the object ``ref``, in order.

    Primitives become lazy experts in ``experts`` (a fresh unbounded store by
    default), each with its reference as identity, so a primitive shared by
    several composites is one expert. ``budget`` bounds the invocations of
    one call of an export, and ``length`` is the sequence length at which
    exports declare their cost.
    """
    experts = experts if experts is not None else ExpertStore()
    made: dict[Ref, Module] = {}

    def module(node: Ref) -> Module:
        if node not in made:
            obj = store.get(node)
            assert isinstance(obj, Primitive)
            made[node] = LazyExpert(obj.manifest, obj.load, obj.size, experts, identity=node)
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
        if not isinstance(obj, Composite):
            raise ValueError("only experts and composites can be installed")
        if obj.exports is None:
            return members(obj)
        inner = members(obj)
        return [Export(obj, i, inner, budget=budget, length=length)
                for i in range(len(obj.exports))]

    return scope(ref)
