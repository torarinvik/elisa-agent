"""Immutable route snapshots with complete explicit-dependency replay (§43.5).

Opaque experts and resolvers remain pinned objects. Only explicit plan wiring is
rewritten; changing a hidden implementation requires a new outer expert version.
Experts, codecs and resolvers must not mutate active implementations or perform
irreversible actions during replay. This is not a host-language sandbox.
"""

from __future__ import annotations

import json
import math
from collections.abc import Callable, Iterator, Mapping, Sequence
from dataclasses import dataclass, replace
from types import MappingProxyType
from typing import Any

from nca.abi import Contract, Manifest, Message, Module, TypeId
from nca.evidence import EVALUATION, Issuers
from nca.memory import MemoryBackend, MemoryRecord
from nca.objects import Attestation, canonical, object_from
from nca.planner import Apply, Given, Map, Plan, output_type
from nca.retention import ReplayGate, ReplayResult, replay_gate
from nca.retention.sampled import SampledDecision, SampledGate
from nca.router import infer
from nca.runtime import Resolver, RiskLedger, execute
from nca.workspace import Workspace


@dataclass(frozen=True)
class ReplayContext:
    """Memory, trust policy and per-execution resources for guarded publication.

    This carries no permission grant: the caller still needs memory read access.
    Router replay restricts effects to memory reads plus explicitly listed effects.
    """

    memory: MemoryBackend
    issuers: Issuers
    max_cases: int
    budget: int
    cost_budget: float | None = None
    max_losses: int = 0
    effects: frozenset[str] = frozenset()
    sampler: SampledGate | None = None
    """Admit on fresh sampled cases (§43.7) instead of exact replay."""

    def __post_init__(self) -> None:
        if isinstance(self.effects, (str, bytes)):
            raise TypeError("replay effects must be a collection of identifiers")
        object.__setattr__(self, "effects", frozenset(self.effects))


@dataclass(frozen=True)
class ProtectedRoute:
    """A current plan with a stable retained-evaluation anchor, not a new content ID.

    The anchor names the original attested baseline. Codecs interpret contributor
    record types; both current and candidate routes are executed by the runtime.
    """

    anchor: str
    available: tuple[TypeId, ...]
    plan: Plan
    decode: Callable[[MemoryRecord], tuple[Sequence[Message], Any]]
    correct: Callable[[Any, Any], bool]
    resolver: Resolver | None = None

    def __post_init__(self) -> None:
        object.__setattr__(self, "available", tuple(self.available))
        if not isinstance(self.anchor, str) or not self.anchor:
            raise ValueError("protected route requires an evidence anchor")


def _children(node: Plan) -> tuple[Plan, ...]:
    if isinstance(node, Given):
        return ()
    if isinstance(node, Map):
        return node.source, node.body
    return (*node.args, *node.slots)


def _postorder(plan: Plan) -> Iterator[Plan]:
    seen: set[int] = set()
    active: set[int] = set()
    stack = [(plan, False)]
    while stack:
        node, done = stack.pop()
        key = id(node)
        if key in seen:
            continue
        if done:
            active.remove(key)
            seen.add(key)
            yield node
        else:
            if key in active:
                raise ValueError("cyclic explicit route")
            active.add(key)
            stack.append((node, True))
            stack.extend((child, False) for child in reversed(_children(node)))


def _rewrite(plan: Plan, changes: Mapping[int, Module], memo: dict[int, Plan]) -> Plan:
    for node in _postorder(plan):
        if id(node) in memo:
            continue
        if isinstance(node, Given):
            result = node
        elif isinstance(node, Map):
            source, body = memo[id(node.source)], memo[id(node.body)]
            result = (
                node
                if source is node.source and body is node.body
                else replace(node, source=source, body=body)
            )
        else:
            module = changes.get(id(node.module), node.module)
            args = tuple(memo[id(child)] for child in node.args)
            slots = tuple(memo[id(child)] for child in node.slots)
            unchanged = module is node.module and all(
                a is b for a, b in zip((*args, *slots), (*node.args, *node.slots), strict=True)
            )
            result = node if unchanged else replace(node, module=module, args=args, slots=slots)
        memo[id(node)] = result
    return memo[id(plan)]


@dataclass(frozen=True)
class GuardedUpdate:
    previous: RouteCatalog
    catalog: RouteCatalog
    affected: tuple[str, ...]
    retained: ReplayGate
    current: ReplayGate
    sampled: SampledDecision | None = None
    """The sampled decision, when admission was sampled; exact gates are then empty."""

    @property
    def accepted(self) -> bool:
        if self.sampled is not None:
            return self.sampled.accepted
        return self.retained.accepted and self.current.accepted


class RouteCatalog:
    """Registered pinned routes, generalized to an immutable multi-root snapshot.

    The reverse index covers arguments, maps and slots, without opening expert
    implementations. Retained metadata is snapshotted as canonical bytes. Public
    route maps are read-only. Live expert objects must obey version immutability.
    """

    def __init__(
        self,
        routes: Sequence[ProtectedRoute],
        retained: Sequence[Attestation] | None,
        *,
        _previous: RouteCatalog | None = None,
    ) -> None:
        entries: dict[str, ProtectedRoute] = {}
        dependents: dict[int, set[str]] = {}
        dependencies: dict[str, frozenset[int]] = {}
        metadata: dict[int, tuple[Module, Manifest]] = {}

        def remember(module: Module) -> None:
            key = id(module)
            if key in metadata:
                return
            declared = module.manifest
            previous = None if _previous is None else _previous._metadata.get(key)
            if previous is not None and declared != previous[1]:
                raise ValueError("active expert manifest changed in place")
            metadata[key] = (module, declared)

        for route in tuple(routes):
            if route.anchor in entries:
                raise ValueError("duplicate protected route anchor")
            if _previous is not None and _previous.routes.get(route.anchor) is route:
                # Exact unchanged roots reuse their earlier type/dependency checks.
                keys = _previous._dependencies[route.anchor]
                for key in keys:
                    remember(_previous._metadata[key][0])
            else:
                nodes = tuple(_postorder(route.plan))
                modules = {
                    id(node.module): node.module for node in nodes if isinstance(node, Apply)
                }
                for module in modules.values():
                    remember(module)
                goal = output_type(route.plan)
                Contract(route.available, goal)
                if infer(tuple(modules.values()), route.available, route.plan) != goal:
                    raise ValueError("protected route is not well typed")
                keys = frozenset(modules)
            entries[route.anchor] = route
            dependencies[route.anchor] = keys
            for key in keys:
                dependents.setdefault(key, set()).add(route.anchor)
        if retained is None:
            if _previous is None or entries.keys() != _previous.routes.keys():
                raise ValueError("inherited evidence requires the same previous anchor set")
            encoded = _previous._retained
            by_anchor = _previous._by_anchor
        else:
            encoded = tuple(canonical(attestation.data()) for attestation in tuple(retained))
            positions: dict[str, list[int]] = {}
            for index, data in enumerate(encoded):
                attestation = object_from(json.loads(data))
                if (
                    not isinstance(attestation, Attestation)
                    or attestation.kind != EVALUATION
                    or attestation.claim.get("identity") not in entries
                ):
                    raise ValueError("retained evaluation does not name a registered anchor")
                positions.setdefault(attestation.claim["identity"], []).append(index)
            by_anchor = MappingProxyType(
                {anchor: tuple(indices) for anchor, indices in positions.items()}
            )
        self._routes = MappingProxyType(entries)
        self._dependents = {key: frozenset(anchors) for key, anchors in dependents.items()}
        self._retained = encoded
        self._by_anchor = by_anchor
        self._dependencies = MappingProxyType(dependencies)
        self._metadata = MappingProxyType(metadata)

    def dependents(self, module: Module) -> frozenset[str]:
        """The anchors of protected routes whose explicit plans use ``module``."""
        return self._dependents.get(id(module), frozenset())

    @property
    def routes(self) -> Mapping[str, ProtectedRoute]:
        return self._routes

    @property
    def retained(self) -> tuple[Attestation, ...]:
        return tuple(object_from(json.loads(data)) for data in self._retained)

    def replace(
        self,
        changes: Sequence[tuple[Module, Module]],
        memory: MemoryBackend,
        issuers: Issuers,
        *,
        max_cases: int,
        budget: int,
        cost_budget: float | None = None,
        max_losses: int = 0,
        sampler: SampledGate | None = None,
    ) -> GuardedUpdate:
        """Publish a replacement snapshot only after all affected routes replay.

        Each case executes current and proposed plans with separate per-run
        invocation/cost budgets and ledgers. Codecs, scoring and storage/index
        work are outside those invocation budgets. Correctness is checked against both
        original trusted outcomes and actual current outcomes, protecting newly
        acquired retained successes too. Case limits count distinct route/record
        pairs; this method performs two executions per pair. Exceptions publish
        nothing. Snapshot copying/index rebuilding can cost linear catalog work.
        """
        substitutions: dict[int, Module] = {}
        affected: set[str] = set()
        for old, new in tuple(changes):
            known = self._metadata.get(id(old))
            if known is not None and old.manifest != known[1]:
                raise ValueError("active expert manifest changed in place")
            old_version = getattr(old, "identity", None) or old.manifest.ref
            new_version = getattr(new, "identity", None) or new.manifest.ref
            if (
                id(old) in substitutions
                or old is new
                or old_version == new_version
                or old.manifest.contract != new.manifest.contract
            ):
                raise ValueError(
                    "replacement needs unique sources, matching contracts and new versions"
                )
            substitutions[id(old)] = new
            affected.update(self._dependents.get(id(old), ()))
        anchors = tuple(anchor for anchor in self.routes if anchor in affected)
        memo: dict[int, Plan] = {}
        proposed = {
            anchor: replace(
                self.routes[anchor], plan=_rewrite(self.routes[anchor].plan, substitutions, memo)
            )
            for anchor in anchors
        }
        return self._publish(
            proposed,
            memory,
            issuers,
            max_cases=max_cases,
            budget=budget,
            cost_budget=cost_budget,
            max_losses=max_losses,
            sampler=sampler,
        )

    def validate_versions(self) -> None:
        """Refuse metadata drift before activating or changing this snapshot."""
        for module, declared in self._metadata.values():
            if module.manifest != declared:
                raise ValueError("active expert manifest changed in place")

    def replan(
        self,
        plans: Mapping[str, Plan],
        memory: MemoryBackend,
        issuers: Issuers,
        *,
        max_cases: int,
        budget: int,
        cost_budget: float | None = None,
        max_losses: int = 0,
        sampler: SampledGate | None = None,
    ) -> GuardedUpdate:
        """Guard explicit root-plan changes without altering other expert versions.

        Available inputs, output type, codec and scorer stay attached to the root.
        Different internal wiring is allowed; opaque old objects are never edited.
        """
        proposed = {}
        for anchor, candidate in tuple(plans.items()):
            route = self.routes[anchor]
            if output_type(candidate) != output_type(route.plan):
                raise ValueError("candidate changes the protected route output type")
            if candidate is not route.plan:
                proposed[anchor] = replace(route, plan=candidate)
        return self._publish(
            proposed,
            memory,
            issuers,
            max_cases=max_cases,
            budget=budget,
            cost_budget=cost_budget,
            max_losses=max_losses,
            sampler=sampler,
        )

    def _publish(
        self,
        proposed: Mapping[str, ProtectedRoute],
        memory: MemoryBackend,
        issuers: Issuers,
        *,
        max_cases: int,
        budget: int,
        cost_budget: float | None,
        max_losses: int,
        sampler: SampledGate | None,
    ) -> GuardedUpdate:
        if isinstance(budget, bool) or not isinstance(budget, int) or budget < 0:
            raise ValueError("budget must be a nonnegative integer")
        if cost_budget is not None and (not math.isfinite(cost_budget) or cost_budget < 0):
            raise ValueError("cost_budget must be finite and nonnegative")
        self.validate_versions()
        anchors = tuple(anchor for anchor in self.routes if anchor in proposed)
        positions = sorted(index for anchor in anchors for index in self._by_anchor.get(anchor, ()))
        assertions = tuple(object_from(json.loads(self._retained[index])) for index in positions)
        covered = {attestation.claim["identity"] for attestation in assertions}
        if sampler is not None:
            covered = {anchor for anchor in anchors if sampler.knows(anchor)}
        if covered != set(proposed):
            raise ValueError("an affected route has no retained evaluation")
        candidate_catalog = (
            RouteCatalog(
                tuple(proposed.get(anchor, route) for anchor, route in self.routes.items()),
                None,
                _previous=self,
            )
            if anchors
            else self
        )
        baseline: dict[str, list[bool]] = {anchor: [] for anchor in anchors}

        def run(anchor: str, plan: Plan, record: MemoryRecord) -> bool:
            route = self.routes[anchor]
            messages, label = route.decode(record)
            messages = tuple(messages)
            if tuple(message.type_id for message in messages) != route.available:
                raise ValueError("decoded memory inputs do not match the protected route")
            output = execute(
                plan,
                messages,
                Workspace(),
                budget,
                route.resolver,
                cost_budget,
                ledger=RiskLedger(),
            ).payload
            correct = route.correct(output, label)
            if type(correct) is not bool:
                raise TypeError("route correctness must be boolean")
            return correct

        def score(anchor: str, record: MemoryRecord) -> bool:
            baseline[anchor].append(run(anchor, self.routes[anchor].plan, record))
            return run(anchor, candidate_catalog.routes[anchor].plan, record)

        if sampler is not None:
            if max_losses:
                raise ValueError("sampled admission requires zero losses")

            def loss(anchor: str, record: MemoryRecord, original: bool) -> bool:
                # Lost if the candidate fails where the original baseline or
                # the current route succeeds; the current route runs only when
                # the candidate fails and the original baseline did too.
                if run(anchor, candidate_catalog.routes[anchor].plan, record):
                    return False
                return original or run(anchor, self.routes[anchor].plan, record)

            decision = sampler.decide(anchors, loss)
            catalog = candidate_catalog if decision.accepted else self
            empty = ReplayGate(())
            return GuardedUpdate(self, catalog, anchors, empty, empty, decision)

        retained = replay_gate(
            memory, assertions, issuers, score, max_cases=max_cases, max_losses=max_losses
        )
        current_results = []
        for result in retained.routes:
            paired = tuple(zip(baseline[result.identity], result.outcomes, strict=True))
            losses = sum(old and not new for old, new in paired)
            wins = sum(not old and new for old, new in paired)
            current_results.append(
                ReplayResult(
                    result.identity,
                    result.records,
                    result.outcomes,
                    losses,
                    wins,
                    losses <= max_losses,
                )
            )
        current = ReplayGate(tuple(current_results))
        catalog = candidate_catalog if retained.accepted and current.accepted else self
        return GuardedUpdate(self, catalog, anchors, retained, current)
