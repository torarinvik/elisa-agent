"""Plan type checking, pinned routes, and evidence-based upgrades.

``infer`` mirrors ``NCA.infer`` (``lean/NCA/Types/Check.lean``), proved to accept
exactly the well-typed plans; slot fillings are checked against the slots'
inputs alone, as in ``NCA.HTyped``, and must use the inputs the slot declares
relevant. ``Router`` mirrors ``NCA.route`` and
``NCA.upgrade`` (``lean/NCA/Planning/Upgrade.lean``): pins override stable planning,
an upgrade pins a checked plan for one goal, and upgrades are proved local,
reversible, and stable under module installation.

``sign_test`` decides whether an upgrade is supported by evidence.
"""

from __future__ import annotations

import math
from collections.abc import Iterator, Mapping
from contextlib import contextmanager
from dataclasses import dataclass
from threading import Lock
from types import MappingProxyType
from fractions import Fraction
from typing import TYPE_CHECKING, Sequence

from nca.abi import Module, TypeId, canonical_type, parse_type, seq_type, type_variables
from nca.effects import effect_scope
from nca.planner import Apply, Given, Plan, output_type, plan_stable, slot_goals, uses

if TYPE_CHECKING:
    from nca.retention.routes import GuardedUpdate, ReplayContext, RouteCatalog

RouteKey = tuple[tuple[TypeId, ...], TypeId]


def infer(modules: Sequence[Module], available: Sequence[TypeId], node: Plan) -> TypeId | None:
    """The type ``node`` produces, or ``None`` if it is not well-typed."""
    if isinstance(node, Given):
        if node.position is None:
            return node.type_id if node.type_id in available else None
        in_range = 0 <= node.position < len(available)
        return node.type_id if in_range and available[node.position] == node.type_id else None
    if isinstance(node, Apply):
        if not any(m is node.module for m in modules) or not _instantiates(node):
            return None
        contract = node.contract
        arg_types = [infer(modules, available, arg) for arg in node.args]
        if len(node.slots) != len(contract.slots) or any(
            infer(modules, inputs, filling) != output or not required <= uses(filling, inputs)
            for filling, (inputs, output, required) in zip(node.slots, slot_goals(contract))
        ):
            return None
        return contract.output if tuple(arg_types) == contract.inputs else None
    body = infer(modules, (node.element,), node.body)
    source = infer(modules, available, node.source)
    if body is None or source != seq_type(node.element):
        return None
    return seq_type(body)


def _instantiates(node: Apply) -> bool:
    """Whether ``node.binding`` binds exactly the variables of the module's
    contract, free ones included, each to a ground type in canonical form."""
    names = [name for name, _ in node.binding]
    if frozenset(names) != node.module.manifest.contract.variables or len(names) != len(set(names)):
        return False
    try:
        return all(
            canonical_type(t) == t and not type_variables(parse_type(t)) for _, t in node.binding
        )
    except ValueError:
        return False


class ReplayRejected(RuntimeError):
    """A completed protected upgrade/rollback failed retained replay."""

    def __init__(self, update: GuardedUpdate) -> None:
        super().__init__("protected route change failed retained replay")
        self.update = update


@dataclass(frozen=True)
class _RouterState:
    pins: dict[TypeId, Plan]
    catalog: RouteCatalog | None
    bindings: Mapping[RouteKey, str]
    receipt: GuardedUpdate | None


class Router:
    """Stable planning, optionally backed by a protected route catalog.

    With a catalog, dispatch is exact in available inputs and goal, and unknown
    signatures fail closed. Legacy goal pins are empty/read-only. Unprotected
    construction retains the research API; it offers no replay guarantee.
    """

    def __init__(
        self, catalog: RouteCatalog | None = None, *, bindings: Mapping[RouteKey, str] | None = None
    ) -> None:
        self._state = _RouterState({}, None, MappingProxyType({}), None)
        self._update_lock = Lock()
        if catalog is not None:
            self.protect(catalog, bindings=bindings)
        elif bindings is not None:
            raise ValueError("protected bindings require a catalog")

    @property
    def pins(self) -> Mapping[TypeId, Plan]:
        """Legacy goal pins; empty/read-only after protection is activated."""
        state = self._state
        return state.pins if state.catalog is None else MappingProxyType(state.pins)

    @pins.setter
    def pins(self, pins: Mapping[TypeId, Plan]) -> None:
        with self._mutation():
            state = self._state
            if state.catalog is not None:
                raise PermissionError("protected pins are managed through the catalog")
            self._state = _RouterState(
                pins if isinstance(pins, dict) else dict(pins), None, state.bindings, None
            )

    @property
    def catalog(self) -> RouteCatalog | None:
        return self._state.catalog

    @property
    def last_update(self) -> GuardedUpdate | None:
        """Last completed protected check, including a refused check."""
        return self._state.receipt

    @contextmanager
    def _mutation(self) -> Iterator[None]:
        if not self._update_lock.acquire(blocking=False):
            raise RuntimeError("router mutation is already in progress")
        try:
            yield
        finally:
            self._update_lock.release()

    def protect(
        self, catalog: RouteCatalog, *, bindings: Mapping[RouteKey, str] | None = None
    ) -> None:
        """Activate protection; every existing legacy pin must remain represented.

        Ambiguous catalog signatures require explicit dispatch bindings. Unbound
        roots still participate in affected-root replay for expert replacement.
        There is no public operation to disable protection.
        """
        with self._mutation():
            state = self._state
            if state.catalog is not None:
                raise PermissionError("router protection is already active")
            catalog.validate_versions()
            selected = {}
            if bindings is None:
                for anchor, route in catalog.routes.items():
                    key = (route.available, output_type(route.plan))
                    if key in selected:
                        raise ValueError("ambiguous protected signature needs explicit bindings")
                    selected[key] = anchor
            else:
                for (available, goal), anchor in tuple(bindings.items()):
                    route = catalog.routes.get(anchor)
                    key = (tuple(available), goal)
                    if route is None or key != (route.available, output_type(route.plan)):
                        raise ValueError("protected binding does not match its route")
                    selected[key] = anchor
            for goal, pin in state.pins.items():
                if not any(
                    key[1] == goal and catalog.routes[anchor].plan is pin
                    for key, anchor in selected.items()
                ):
                    raise ValueError("protection would discard an existing pin")
            self._state = _RouterState({}, catalog, MappingProxyType(selected), None)

    def route(
        self, modules: Sequence[Module], available: Sequence[TypeId], goal: TypeId, fuel: int = 8
    ) -> Plan | None:
        state = self._state
        if state.catalog is not None:
            anchor = state.bindings.get((tuple(available), goal))
            return None if anchor is None else state.catalog.routes[anchor].plan
        return state.pins.get(goal) or plan_stable(modules, available, goal, fuel)

    def _finish(self, state: _RouterState, update: GuardedUpdate) -> None:
        if self._state is not state or update.previous is not state.catalog:
            raise RuntimeError("router snapshot changed during replay")
        self._state = _RouterState({}, update.catalog, state.bindings, update)

    def _replan(
        self,
        state: _RouterState,
        available: Sequence[TypeId],
        goal: TypeId,
        candidate: Plan,
        replay: ReplayContext | None,
    ) -> Plan:
        if replay is None:
            raise PermissionError("protected route changes require replay context")
        anchor = state.bindings.get((tuple(available), goal))
        if anchor is None or state.catalog is None:
            raise PermissionError("signature has no protected route")
        previous = state.catalog.routes[anchor].plan
        with effect_scope(replay.effects | frozenset({replay.memory.read_effect})):
            update = state.catalog.replan(
                {anchor: candidate},
                replay.memory,
                replay.issuers,
                max_cases=replay.max_cases,
                budget=replay.budget,
                cost_budget=replay.cost_budget,
                max_losses=replay.max_losses,
                sampler=replay.sampler,
            )
        self._finish(state, update)
        if not update.accepted:
            raise ReplayRejected(update)
        return previous

    def upgrade(
        self,
        modules: Sequence[Module],
        available: Sequence[TypeId],
        goal: TypeId,
        candidate: Plan,
        *,
        replay: ReplayContext | None = None,
    ) -> Plan | None:
        """Pin a typed candidate; protected mode additionally requires replay."""
        with self._mutation():
            state = self._state
            if state.catalog is None and replay is not None:
                raise PermissionError("replay context requires a protected router")
            if state.catalog is not None and replay is None:
                raise PermissionError("protected route changes require replay context")
            if infer(modules, available, candidate) != goal:
                raise ValueError(f"candidate route does not produce {goal}")
            if state.catalog is not None:
                return self._replan(state, available, goal, candidate, replay)
            previous = state.pins.get(goal)
            state.pins[goal] = candidate
            return previous

    def rollback(
        self,
        goal: TypeId,
        previous: Plan | None,
        *,
        available: Sequence[TypeId] | None = None,
        replay: ReplayContext | None = None,
    ) -> None:
        """Protected rollback is a fresh gated replan; route removal is refused."""
        with self._mutation():
            state = self._state
            if state.catalog is not None:
                if previous is None or available is None:
                    raise PermissionError("protected rollback needs a route and input signature")
                self._replan(state, available, goal, previous, replay)
            elif replay is not None or available is not None:
                raise PermissionError("replay context requires a protected router")
            elif previous is None:
                state.pins.pop(goal, None)
            else:
                state.pins[goal] = previous

    def replace_experts(
        self, changes: Sequence[tuple[Module, Module]], replay: ReplayContext
    ) -> GuardedUpdate:
        """Gate all registered dependents and atomically switch the dispatch snapshot."""
        with self._mutation():
            state = self._state
            if state.catalog is None:
                raise PermissionError("expert replacement requires a protected catalog")
            with effect_scope(replay.effects | frozenset({replay.memory.read_effect})):
                update = state.catalog.replace(
                    changes,
                    replay.memory,
                    replay.issuers,
                    max_cases=replay.max_cases,
                    budget=replay.budget,
                    cost_budget=replay.cost_budget,
                    max_losses=replay.max_losses,
                    sampler=replay.sampler,
                )
            self._finish(state, update)
            return update


def sign_test(
    current: Sequence[bool], candidate: Sequence[bool], alpha: float = 0.05
) -> tuple[bool, float]:
    """One-sided exact sign test on paired per-sample correctness.

    Among samples where the routes disagree in correctness, ``wins`` are those
    only the candidate gets right. Under the null hypothesis that neither route
    is better, ``wins ~ Binomial(discordant, 1/2)``. Returns whether to accept
    the candidate and the p-value ``P(X >= wins)``.
    """
    probability = sign_probability(current, candidate)
    return probability < alpha, float(probability)


def sign_probability(current: Sequence[bool], candidate: Sequence[bool]) -> Fraction:
    """Exact paired sign-test tail, retaining ordering below float range.

    Both sequences must be aligned. Integer arithmetic avoids underflow in
    decisions; converting the returned fraction to float may still yield zero.
    """
    if len(current) != len(candidate):
        raise ValueError("paired outcomes must have equal lengths")
    wins = sum(c and not o for o, c in zip(current, candidate, strict=True))
    losses = sum(o and not c for o, c in zip(current, candidate, strict=True))
    n = wins + losses
    return Fraction(sum(math.comb(n, k) for k in range(wins, n + 1)), 2**n)
