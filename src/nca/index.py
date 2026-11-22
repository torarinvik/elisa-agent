"""The planner's index of installed modules and its closure oracles.

Modules are indexed by output type, by the root constructor of their output,
and by the types they consume, in installation order. Forward closures over
the first ``k`` modules (``NCA.Closure``) serve as sound reachability oracles
for pruning (THEORY §12), and every result is cached per library prefix, so
it survives installation (Theorem 12.18).
"""

from __future__ import annotations

import heapq
import itertools
from collections.abc import Collection, Iterator, Sequence
from typing import TYPE_CHECKING

from nca.abi import (Binding, Contract, Module, ScopedName, Term, TypeId, Var, elem_type, format_type,
                     match_type, parse_type, substitute, type_variables, unify)

if TYPE_CHECKING:
    from nca.planner import Memo, Plan

_MAX_BINDINGS = 1024
"""Beyond this many bindings of an eliminator's inputs, its contributions are
not enumerated and the closure is taken as total."""


class ProducerIndex:
    """Installed modules indexed by output type, preserving installation order.

    Mirrors the index of ``NCA.planIdx`` (``lean/NCA/Planning/Loading.lean``), proved to
    yield the same plans as scanning the library (``NCA.planIdx_eq``). A view
    limited to the first ``k`` modules serves layered planning.
    """

    def __init__(self, modules: Sequence[Module] = ()) -> None:
        self.size = 0
        self.outputs: list[TypeId] = []
        self.producers: dict[TypeId, list[tuple[int, Module]]] = {}
        self.modules: list[Module] = []
        self.generic: list[tuple[int, Module]] = []
        """Producers with polymorphic contracts, which may produce any instance."""
        self.sequence_outputs: list[tuple[int, TypeId]] = []
        self.needs: list[frozenset[TypeId]] = []
        self.consumers: dict[TypeId, list[int]] = {}
        self.unconditional: list[int] = []
        self.head_of: list[tuple[str, int] | None] = []
        """Root constructor and arity of each module's output; ``None`` for a variable."""
        self.heads: dict[tuple[str, int], list[int]] = {}
        self.open_outputs: list[int] = []
        self.polymorphic: set[int] = set()
        self._reach_cache: dict[tuple[tuple[TypeId, ...], int], frozenset[TypeId]] = {}
        self._cover_cache: dict[tuple[TypeId, int], bool] = {}
        self._candidate_cache: dict[tuple[tuple[TypeId, ...], int],
                                    tuple[list[TypeId], dict[TypeId, int]]] = {}
        self._source_cache: dict[tuple[TypeId, int], frozenset[TypeId] | None] = {}
        self._fired_cache: dict[tuple[tuple[TypeId, ...], int], frozenset[int]] = {}
        self._seq_cache: dict[tuple[tuple[TypeId, ...], int], frozenset[TypeId] | None] = {}
        self._memos: dict[int, Memo] = {}
        self._total_cache: dict[tuple[tuple[TypeId, ...], int], bool] = {}
        self._depth_cache: dict[tuple[tuple[TypeId, ...], int], dict[TypeId, int] | None] = {}
        self._in_progress: set[tuple[tuple[TypeId, ...], int]] = set()
        self.routes: dict[tuple[tuple[TypeId, ...], TypeId, int, frozenset[int]], tuple[int, Plan | None]] = {}
        """Stable routes found so far, each with the length of the shortest
        prefix it is planned with, or ``None`` with the library size at which
        there was none."""
        for module in modules:
            self.append(module)

    def append(self, module: Module) -> None:
        """Index a newly installed module after the others. Every cached result
        is keyed by a library prefix and stays valid (THEORY §12, Theorem 12.18)."""
        position = self.size
        self.size += 1
        contract = module.manifest.contract
        self.outputs.append(contract.output)
        output = parse_type(contract.output)
        head = None if isinstance(output, Var) else (output.name, len(output.args))
        self.head_of.append(head)
        if head is None:
            self.open_outputs.append(position)
        else:
            self.heads.setdefault(head, []).append(position)
        needs = frozenset(i for i in contract.inputs
                          if elem_type(i) is None and not type_variables(parse_type(i)))
        self.needs.append(needs)
        self.modules.append(module)
        if contract.polymorphic:
            self.polymorphic.add(position)
            self.generic.append((position, module))
            return
        self.producers.setdefault(contract.output, []).append((position, module))
        if elem_type(contract.output) is not None:
            self.sequence_outputs.append((position, contract.output))
        for input_type in needs:
            self.consumers.setdefault(input_type, []).append(position)
        if not needs:
            self.unconditional.append(position)

    def replace(self, position: int, module: Module) -> None:
        """Swap the module at ``position`` for one with the same contract. Results
        about types stay valid; cached plans, which name modules, are dropped."""
        old = self.modules[position]
        if old.manifest.contract != module.manifest.contract:
            raise ValueError(f"contract mismatch replacing {old.manifest.module_id}")
        self.modules[position] = module
        entries = (self.generic if position in self.polymorphic
                   else self.producers[old.manifest.contract.output])
        entries[:] = [(p, module if p == position else m) for p, m in entries]
        self._memos.clear()
        self.routes.clear()

    def without(self, positions: Collection[int]) -> ProducerIndex:
        """An index of the modules other than those at ``positions``. Every
        result cached for a library prefix before the first of them is kept,
        since that prefix is unchanged (Theorem 12.18); only the modules after
        it are indexed again. A stable route planned within that prefix stays
        the route, and a goal without one still has none, since removing
        modules never makes a goal derivable."""
        first = min(positions, default=self.size)
        index = ProducerIndex()
        index.size = first
        for name in ("outputs", "modules", "needs", "head_of"):
            setattr(index, name, getattr(self, name)[:first])
        for name in ("generic", "sequence_outputs"):
            setattr(index, name, [e for e in getattr(self, name) if e[0] < first])
        index.unconditional = [p for p in self.unconditional if p < first]
        index.open_outputs = [p for p in self.open_outputs if p < first]
        index.polymorphic = {p for p in self.polymorphic if p < first}
        index.producers = {t: kept for t, entries in self.producers.items()
                           if (kept := [e for e in entries if e[0] < first])}
        index.consumers = {t: kept for t, entries in self.consumers.items()
                           if (kept := [p for p in entries if p < first])}
        index.heads = {h: kept for h, entries in self.heads.items()
                       if (kept := [p for p in entries if p < first])}
        for cache, kept in ((self._reach_cache, index._reach_cache),
                            (self._cover_cache, index._cover_cache),
                            (self._candidate_cache, index._candidate_cache),
                            (self._source_cache, index._source_cache),
                            (self._fired_cache, index._fired_cache),
                            (self._seq_cache, index._seq_cache),
                            (self._total_cache, index._total_cache),
                            (self._depth_cache, index._depth_cache)):
            kept.update((key, value) for key, value in cache.items() if key[1] <= first)
        index._memos = {limit: dict(memo) for limit, memo in self._memos.items()
                        if limit <= first}
        index.routes = {key: (length, route) for key, (length, route) in self.routes.items()
                        if route is not None and length <= first}
        removed = set(positions)
        for position in range(first, self.size):
            if position not in removed:
                index.append(self.modules[position])
        index.routes.update((key, (index.size, None)) for key, (size, route) in self.routes.items()
                            if route is None and size == self.size)
        return index

    def memo(self, limit: int) -> Memo:
        """Plans found with the first ``limit`` modules, kept across planning calls."""
        return self._memos.setdefault(limit, {})

    def candidates(self, goal: TypeId, limit: int) -> Iterator[tuple[int, Module, Binding]]:
        """Producers of ``goal`` among the first ``limit`` modules, in installation
        order, each with the binding of its unique instance producing ``goal``
        (THEORY §2.1)."""
        exact = self.producers.get(goal, ())
        if not self.generic or self.generic[0][0] >= limit:
            for position, module in exact:
                if position >= limit:
                    return
                yield position, module, ()
            return
        term = parse_type(goal)
        head = None if isinstance(term, Var) else (term.name, len(term.args))
        heads = () if head is None else self.heads.get(head, ())
        generic_heads = (p for p in heads
                         if p < limit and p in self.polymorphic)
        generic_open = (p for p in self.open_outputs if p < limit)
        generic = heapq.merge(generic_heads, generic_open)
        merged = heapq.merge(((p, m, ()) for p, m in exact if p < limit),
                             ((p, self.modules[p], None) for p in generic),
                             key=lambda item: item[0])
        for position, module, binding in merged:
            if binding is None:
                binding = module.manifest.contract.producing(goal)
                if binding is None:
                    continue
            yield position, module, binding

    def covered(self, type_id: TypeId, limit: int) -> bool:
        """Whether a polymorphic producer among the first ``limit`` modules,
        other than one whose output is a bare variable, has an instance
        producing ``type_id``. Those are accounted for in the closure."""
        key = (type_id, limit)
        if key not in self._cover_cache:
            self._cover_cache[key] = any(m.manifest.contract.producing(type_id) is not None
                                         for p, m in self.generic
                                         if p < limit and self.head_of[p] is not None)
        return self._cover_cache[key]

    def satisfiable(self, available: Sequence[TypeId], needs: frozenset[TypeId],
                    limit: int) -> bool:
        """Whether every need may be derivable from ``available``: in the
        closure, or produced by an instance of a polymorphic producer."""
        reach = self.reachable(available, limit)
        return self.total(available, limit) or all(
            t in reach or self.covered(t, limit) for t in needs)

    def total(self, available: Sequence[TypeId], limit: int) -> bool:
        """Whether a polymorphic producer whose output is a bare variable may
        produce any type from ``available``, so the closure prunes nothing."""
        self.reachable(available, limit)
        return self._total_cache[(tuple(available), limit)]

    def may_produce(self, available: Sequence[TypeId], position: int, goal: TypeId,
                    limit: int) -> bool:
        """Whether the module at ``position`` may produce ``goal`` from
        ``available``. Only a module whose output is a bare variable is
        restricted here: by Theorem 12.19, ``goal`` must be a sequence type or in
        the closure, which includes the types polymorphic producers cover."""
        return (self.head_of[position] is not None or elem_type(goal) is not None
                or self.total(available, limit) or goal in self.reachable(available, limit)
                or self.covered(goal, limit))

    def element_candidates(self, available: Sequence[TypeId], limit: int,
                           ) -> tuple[list[TypeId], dict[TypeId, int]]:
        """``map`` candidate elements in planner order (THEORY §2): elements of
        the available sequence types, then of the ground sequence types the
        first ``limit`` modules produce, each with its first position."""
        key = (tuple(available), limit)
        if key not in self._candidate_cache:
            outputs = [t for position, t in self.sequence_outputs if position < limit]
            found = [e for t in (*available, *outputs) if (e := elem_type(t)) is not None]
            order: dict[TypeId, int] = {}
            for i, element in enumerate(found):
                order.setdefault(element, i)
            self._candidate_cache[key] = (found, order)
        return self._candidate_cache[key]

    def sources(self, goal: TypeId, limit: int) -> frozenset[TypeId] | None:
        """A superset of the types ``a`` with ``goal`` in the closure of ``[a]``,
        or ``None`` when that is every type: ``goal`` is in the closure of nothing, or a
        polymorphic producer may produce it, or one whose output is a bare
        variable is installed. Backward search over producers
        gives a superset, since a closure derivation that uses ``a`` reaches
        ``goal`` from it through producers' inputs. Sequence goals are in every
        closure."""
        key = (goal, limit)
        if key not in self._source_cache:
            if (elem_type(goal) is not None or goal in self.reachable((), limit)
                    or self.covered(goal, limit)
                    or any(p < limit for p in self.open_outputs)):
                self._source_cache[key] = None
            else:
                found = {goal}
                stack = [goal]
                while stack:
                    for position, module in self.producers.get(stack.pop(), ()):
                        if position >= limit:
                            break
                        for t in module.manifest.contract.inputs:
                            if t not in found:
                                found.add(t)
                                stack.append(t)
                self._source_cache[key] = frozenset(found)
        return self._source_cache[key]

    def seq_elements(self, available: Sequence[TypeId], limit: int) -> frozenset[TypeId] | None:
        """A superset of the non-sequence elements ``a`` for which ``seq a`` may be
        derivable from ``available`` (THEORY §12, Theorems 12.17 and 12.20,
        ``NCA.HTyped.seq_source``): the closure of the elements of the sequence types in the closure of
        ``available``. ``None`` when a polymorphic producer may produce any
        sequence type."""
        key = (tuple(available), limit)
        if key not in self._seq_cache:
            reach = self.reachable(available, limit)
            if (self.total(available, limit)
                    or any(self.head_of[p] == ("seq", 1) for p in self.polymorphic if p < limit)):
                self._seq_cache[key] = None
            else:
                seeds = {e for t in reach if (e := elem_type(t)) is not None}
                self._seq_cache[key] = self.reachable(tuple(sorted(seeds)), limit)
        return self._seq_cache[key]

    def polymorphic_sequences(self, limit: int) -> bool:
        """Whether a polymorphic producer among the first ``limit`` modules may
        output a sequence type: its output is a sequence or a bare variable."""
        return any(self.head_of[p] in (None, ("seq", 1)) for p in self.polymorphic if p < limit)

    def may_derive(self, available: Sequence[TypeId], goal: Term, limit: int) -> bool:
        """The closure oracle (``NCA.SoundOracle``): ``False`` only if no
        instance of ``goal`` is derivable from ``available``. Sequence types and
        variables are always accepted, as is any type a polymorphic producer can
        produce, and everything when the closure is total."""
        if isinstance(goal, Var) or goal.name == "seq" or self.total(available, limit):
            return True
        reach = self.reachable(available, limit)
        if not type_variables(goal):
            type_id = format_type(goal)
            return type_id in reach or self.covered(type_id, limit)
        return (any(unify(goal, parse_type(t), {}) for t in reach)
                or any(unify(goal, renamed_output(m), {}) for p, m in self.generic
                       if p < limit and self.head_of[p] is not None))

    def reachable(self, available: Sequence[TypeId], limit: int) -> frozenset[TypeId]:
        """Forward closure of ``available`` under the first ``limit`` contracts.

        Mirrors ``NCA.Closure``: sequence types count as always reachable, so a
        contract fires once all its non-sequence inputs are reachable. Horn-clause
        propagation touches only contracts consuming reachable types, so dormant
        modules elsewhere in the library cost nothing. Types that a polymorphic
        producer has an instance for count as reachable too, and contracts whose
        output is a bare variable contribute the types of Theorem 12.19, to a
        fixed point, as in ``NCA.ECl``. The closure stays an over-approximation
        of the derivable types (``NCA.HTyped.eclosure``); ``total`` reports
        when it is everything.
        """
        key = (tuple(available), limit)
        if key in self._reach_cache:
            return self._reach_cache[key]
        self._in_progress.add(key)
        reach = set(available)
        queue = list(available)
        remaining: dict[int, int] = {}
        if any(p < limit and self.head_of[p] is not None for p, _ in self.generic):
            for t in self.consumers:
                if t not in reach and self.covered(t, limit):
                    reach.add(t)
                    queue.append(t)

        fired: set[int] = set()

        def fire(position: int) -> None:
            fired.add(position)
            output = self.outputs[position]
            if output not in reach:
                reach.add(output)
                queue.append(output)

        def propagate() -> None:
            while queue:
                for position in self.consumers.get(queue.pop(), ()):
                    if position >= limit:
                        continue
                    remaining[position] = remaining.get(position, len(self.needs[position])) - 1
                    if remaining[position] == 0:
                        fire(position)

        for position in self.unconditional:
            if position < limit:
                fire(position)
        propagate()
        total = False
        while not total and any(p < limit for p in self.open_outputs):
            new, total = self._open_contributions(key, reach)
            new -= reach
            if not new:
                break
            reach |= new
            queue.extend(new)
            propagate()
        self._in_progress.discard(key)
        result = frozenset(reach)
        self._reach_cache[key] = result
        self._fired_cache[key] = frozenset(fired)
        self._total_cache[key] = total
        return result

    def depths(self, available: Sequence[TypeId], limit: int) -> dict[TypeId, int] | None:
        """For each type of the forward closure, the least ``d`` such that it
        is in the depth-bounded closure ``NCA.Within`` at depth ``d + 1``,
        under the first ``limit`` contracts; types absent are derivable at no
        depth. Mirrors ``NCA.Within`` by rounds of the propagation of
        ``reachable``: available types, outputs of contracts without
        non-sequence inputs, and types a polymorphic producer has an instance
        for, at 0. ``None`` when a contract's output is a bare
        variable, whose contributions it does not bound.
        """
        key = (tuple(available), limit)
        if key in self._depth_cache:
            return self._depth_cache[key]
        if any(p < limit for p in self.open_outputs):
            self._depth_cache[key] = None
            return None
        level: dict[TypeId, int] = {}
        current: list[TypeId] = []
        seeds = list(available) + [self.outputs[p] for p in self.unconditional if p < limit]
        if any(p < limit and self.head_of[p] is not None for p, _ in self.generic):
            seeds += [t for t in self.consumers if self.covered(t, limit)]
        for t in seeds:
            if t not in level:
                level[t] = 0
                current.append(t)
        produced: list[TypeId] = []
        remaining: dict[int, int] = {}
        depth = 0
        while current or produced:
            for t in current:
                for position in self.consumers.get(t, ()):
                    if position >= limit:
                        continue
                    remaining[position] = remaining.get(position, len(self.needs[position])) - 1
                    if remaining[position] == 0:
                        produced.append(self.outputs[position])
            depth += 1
            current = []
            for t in produced:
                if t not in level:
                    level[t] = depth
                    current.append(t)
            produced = []
        self._depth_cache[key] = level
        return level

    def _open_contributions(self, current: tuple[tuple[TypeId, ...], int], reach: set[TypeId],
                            ) -> tuple[set[TypeId], bool]:
        """The types contracts whose output is a bare variable may produce from
        ``reach``, the closure ``current`` computed so far (Theorem 12.19), and
        whether one of them may produce any type. The cases are the rules of
        ``NCA.ECl``. A slot whose inputs are all in ``reach`` contributes
        nothing new (``NCA.ECl.trans``); one whose closure is still being
        computed further out makes the result total."""
        limit = current[1]
        produced: set[TypeId] = set()
        for position in self.open_outputs:
            if position >= limit:
                break
            contract = self.modules[position].manifest.contract
            output = parse_type(contract.output)
            assert isinstance(output, Var)
            inputs = [parse_type(t) for t in contract.inputs]
            if output in inputs:
                continue
            bindings: list[dict[str, Term]] = [{}]
            for pattern in inputs:
                if isinstance(pattern, Var) or elem_type(format_type(pattern)) is not None:
                    continue
                if not type_variables(pattern):
                    type_id = format_type(pattern)
                    if type_id not in reach and not self.covered(type_id, limit):
                        bindings = []
                    continue
                if any(unify(pattern, renamed_output(m), {}) for p, m in self.generic
                       if p < limit and self.head_of[p] is not None):
                    return produced, True
                extended = []
                for binding in bindings:
                    for type_id in reach:
                        candidate = dict(binding)
                        if match_type(pattern, parse_type(type_id), candidate):
                            extended.append(candidate)
                bindings = extended
                if len(bindings) > _MAX_BINDINGS:
                    return produced, True
            slots = [inputs for inputs, out in contract.slots if parse_type(out) == output]
            for binding in bindings:
                if output.name in binding:
                    produced.add(format_type(binding[output.name]))
                    continue
                if not slots:
                    return produced, True
                for slot_inputs in slots:
                    ground = [substitute(parse_type(t), binding) for t in slot_inputs]
                    if any(type_variables(t) for t in ground):
                        return produced, True
                    key = (tuple(format_type(t) for t in ground), limit)
                    if all(t in reach for t in key[0]):
                        continue
                    if key in self._in_progress:
                        return produced, True
                    inner = self.reachable(key[0], limit)
                    if self._total_cache[key]:
                        return produced, True
                    produced |= inner
        return produced, False

    def pattern_candidates(self, available: Sequence[TypeId], goal: Term,
                           limit: int) -> list[int]:
        """Positions, in installation order, of the modules among the first
        ``limit`` that can produce an instance of the pattern ``goal``
        (THEORY §2.2): an output whose root matches the goal's (Theorem 2.6)
        or is a variable, and, for a monomorphic contract, all ground inputs
        in the forward closure of ``available``. By Theorem 12.19, a contract
        whose output is a bare variable qualifies only if ``goal`` is a
        sequence pattern or an instance of it is in the closure, unless the
        closure is total."""
        reach = self.reachable(available, limit)
        if isinstance(goal, Var) or self.total(available, limit):
            positions = range(limit) if isinstance(goal, Var) else (
                p for p in range(limit)
                if self.head_of[p] in (None, (goal.name, len(goal.args))))
            return list(positions)
        fired = self._fired_cache[(tuple(available), limit)]
        key = (goal.name, len(goal.args))
        heads = self.heads.get(key, ())
        if len(fired) < len(heads):
            matching = [p for p in fired if self.head_of[p] == key]
            matching += [p for p in heads if p in self.polymorphic and p < limit]
        else:
            matching = [p for p in heads if p < limit and (p in fired or p in self.polymorphic)]
        if (key == ("seq", 1) or any(unify(goal, parse_type(t), {}) for t in reach)
                or any(unify(goal, renamed_output(self.modules[p]), {}) for p in heads
                       if p in self.polymorphic and p < limit)):
            matching += [p for p in self.open_outputs if p < limit]
        return sorted(set(matching))


_fresh = itertools.count()


def renamed_output(module: Module) -> Term:
    """The module's output pattern with its variables renamed apart from any
    variable of a search."""
    return rename_apart(module.manifest.contract, ())[2]


def rename_apart(contract: Contract, binding: Binding) -> tuple[dict[str, ScopedName], tuple[Term, ...], Term]:
    """Fresh names and renamed input/output terms for a contract instance."""
    instance = contract.instance(binding)
    tag = next(_fresh)
    renaming = {v: ScopedName(v, tag) for v in sorted(instance.variables)}
    terms = {v: Var(r) for v, r in renaming.items()}
    def renamed(type_id: TypeId) -> Term:
        return substitute(parse_type(type_id), terms)
    return renaming, tuple(renamed(t) for t in instance.inputs), renamed(instance.output)
