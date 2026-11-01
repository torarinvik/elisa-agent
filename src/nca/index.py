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
from collections.abc import Iterator, Sequence
from typing import TYPE_CHECKING

from nca.abi import (Binding, Contract, Module, Term, TypeId, Var, elem_type, format_type,
                     parse_type, type_variables, unify)

if TYPE_CHECKING:
    from nca.planner import Memo, Plan


class ProducerIndex:
    """Installed modules indexed by output type, preserving installation order.

    Mirrors the index of ``NCA.planIdx`` (``lean/NCA/Loading.lean``), proved to
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
        self.routes: dict[tuple[tuple[TypeId, ...], TypeId, int], tuple[int, Plan | None]] = {}
        """Stable routes found so far, each with the library size it was planned at."""
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
        merged = heapq.merge(((p, m, ()) for p, m in exact if p < limit),
                             ((p, m, None) for p, m in self.generic if p < limit),
                             key=lambda item: item[0])
        for position, module, binding in merged:
            if binding is None:
                binding = module.manifest.contract.producing(goal)
                if binding is None:
                    continue
            yield position, module, binding

    def covered(self, type_id: TypeId, limit: int) -> bool:
        """Whether a polymorphic producer among the first ``limit`` modules has
        an instance producing ``type_id``."""
        key = (type_id, limit)
        if key not in self._cover_cache:
            self._cover_cache[key] = any(m.manifest.contract.producing(type_id) is not None
                                         for p, m in self.generic if p < limit)
        return self._cover_cache[key]

    def satisfiable(self, needs: frozenset[TypeId], reach: frozenset[TypeId], limit: int) -> bool:
        """Whether every need may be derivable: reachable, or produced by an
        instance of a polymorphic producer."""
        return all(t in reach or self.covered(t, limit) for t in needs)

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
        polymorphic producer may produce it. Backward search over producers
        gives a superset, since a closure derivation that uses ``a`` reaches
        ``goal`` from it through producers' inputs. Sequence goals are in every
        closure."""
        key = (goal, limit)
        if key not in self._source_cache:
            if (elem_type(goal) is not None or goal in self.reachable((), limit)
                    or self.covered(goal, limit)):
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
        derivable from ``available`` (THEORY §12, Theorem 12.17): the closure of
        the elements of available sequence types and of the sequence types that
        contracts firing in the closure produce. ``None`` when a polymorphic
        producer may produce any sequence type."""
        key = (tuple(available), limit)
        if key not in self._seq_cache:
            if any(self.head_of[p] in (None, ("seq", 1)) for p in self.polymorphic if p < limit):
                self._seq_cache[key] = None
            else:
                self.reachable(available, limit)
                outputs = (self.outputs[p] for p in self._fired_cache[key])
                seeds = {e for t in (*available, *outputs) if (e := elem_type(t)) is not None}
                self._seq_cache[key] = self.reachable(tuple(sorted(seeds)), limit)
        return self._seq_cache[key]

    def may_derive(self, available: Sequence[TypeId], goal: Term, limit: int) -> bool:
        """The closure oracle (``NCA.SoundOracle``): ``False`` only if no
        instance of ``goal`` is derivable from ``available``. Sequence types and
        variables are always accepted, as is any type a polymorphic producer can
        produce."""
        if isinstance(goal, Var) or goal.name == "seq":
            return True
        if not type_variables(goal):
            type_id = format_type(goal)
            return type_id in self.reachable(available, limit) or self.covered(type_id, limit)
        return (any(unify(goal, parse_type(t), {}) for t in self.reachable(available, limit))
                or any(unify(goal, renamed_output(m), {}) for p, m in self.generic if p < limit))

    def reachable(self, available: Sequence[TypeId], limit: int) -> frozenset[TypeId]:
        """Forward closure of ``available`` under the first ``limit`` contracts.

        Mirrors ``NCA.Closure``: sequence types count as always reachable, so a
        contract fires once all its non-sequence inputs are reachable. Horn-clause
        propagation touches only contracts consuming reachable types, so dormant
        modules elsewhere in the library cost nothing. Types that a polymorphic
        producer has an instance for count as reachable too, which keeps the
        closure an over-approximation of the derivable types.
        """
        key = (tuple(available), limit)
        if key in self._reach_cache:
            return self._reach_cache[key]
        reach = set(available)
        queue = list(available)
        remaining: dict[int, int] = {}
        if any(p < limit for p, _ in self.generic):
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

        for position in self.unconditional:
            if position < limit:
                fire(position)
        while queue:
            for position in self.consumers.get(queue.pop(), ()):
                if position >= limit:
                    continue
                remaining[position] = remaining.get(position, len(self.needs[position])) - 1
                if remaining[position] == 0:
                    fire(position)
        result = frozenset(reach)
        self._reach_cache[key] = result
        self._fired_cache[key] = frozenset(fired)
        return result

    def pattern_candidates(self, available: Sequence[TypeId], goal: Term,
                           limit: int) -> list[int]:
        """Positions, in installation order, of the modules among the first
        ``limit`` that can produce an instance of the pattern ``goal``
        (THEORY §2.2): an output whose root matches the goal's (Theorem 2.6)
        or is a variable, and, for a monomorphic contract, all ground inputs
        in the forward closure of ``available``."""
        self.reachable(available, limit)
        fired = self._fired_cache[(tuple(available), limit)]
        if isinstance(goal, Var):
            return [p for p in range(limit) if p in fired or p in self.polymorphic]
        key = (goal.name, len(goal.args))
        heads = self.heads.get(key, ())
        if len(fired) < len(heads):
            matching = [p for p in fired if self.head_of[p] == key]
            matching += [p for p in heads if p in self.polymorphic and p < limit]
        else:
            matching = [p for p in heads if p < limit and (p in fired or p in self.polymorphic)]
        return sorted({*matching, *(p for p in self.open_outputs if p < limit)})


_fresh = itertools.count()


def renamed_output(module: Module) -> Term:
    """The module's output pattern with its variables renamed apart from any
    variable of a search."""
    return parse_type(rename_apart(module.manifest.contract, ())[1].output)


def rename_apart(contract: Contract, binding: Binding) -> tuple[dict[str, str], Contract]:
    """Fresh names for the variables of ``contract.instance(binding)``, and
    the instance with them."""
    instance = contract.instance(binding)
    tag = next(_fresh)
    renaming = {v: f"{v}_{tag}" for v in sorted(instance.variables)}
    return renaming, instance.instance(tuple((v, f"?{r}") for v, r in renaming.items()))
