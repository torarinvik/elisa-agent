"""Typed working-state cursors over ordinary budgeted runtime execution."""
from __future__ import annotations

from collections.abc import Iterable, Iterator, Sequence

from nca import runtime as _api
from nca.abi import Contract, Message
from nca.cache import ResultCache
from nca.planner import Plan, output_type
from nca.runtime.ledger import RiskLedger
from nca.workspace import Workspace


class Process:
    """A well-typed route threaded through successive working-state messages.

    ``contract`` describes state at input position zero, followed by event inputs,
    and the same state type as output. The route and expert versions are retained
    as supplied; no replanning occurs. Payloads must be immutable or treated as
    immutable by experts. This is an in-process state cursor, not a sandbox or
    durable memory: workspace rollback cannot undo payload mutations or effects.
    """

    def __init__(self, plan: Plan, contract: Contract, initial: Message,
                 workspace: Workspace, *, resolver: _api.Resolver | None = None,
                 cache: ResultCache | None = None, ledger: RiskLedger | None = None) -> None:
        if (not contract.inputs or contract.slots
                or contract.inputs[0] != contract.output
                or initial.type_id != contract.output
                or output_type(plan) != contract.output):
            raise ValueError("process requires state-first inputs and the same state output")
        self.plan = plan
        self.contract = contract
        self.workspace = workspace
        self.resolver = resolver
        self.cache = cache
        self.ledger = ledger
        self._state = initial
        self._running = False

    @property
    def state(self) -> Message:
        """Last successfully completed transition, or the initial state."""
        return self._state

    def step(self, events: Sequence[Message], *, budget: int,
             cost_budget: float | None = None) -> Message:
        """Commit one transition, using ordinary runtime accounting and rollback.

        Budgets apply to this transition, including nested requests and slots.
        Earlier transitions stay committed if this one fails. Failed invocation
        costs and ledger charges retain the ordinary runtime semantics.
        """
        if self._running:
            raise RuntimeError("process transition is already running")
        events = tuple(events)
        if tuple(event.type_id for event in events) != self.contract.inputs[1:]:
            raise ValueError("event types do not match the process contract")
        self._running = True
        try:
            result = _api.execute(self.plan, (self._state, *events), self.workspace, budget,
                             self.resolver, cost_budget, self.cache, self.ledger)
            self._state = result
            return result
        finally:
            self._running = False

    def stream(self, events: Iterable[Sequence[Message]], *, max_steps: int,
               budget: int, cost_budget: float | None = None) -> Iterator[Message]:
        """Consume at most ``max_steps`` events lazily; stopping stops execution.

        Each event gets its own declared budgets. There is no background task or
        implicit retry. A failed event is consumed, and the exception propagates.
        """
        if isinstance(max_steps, bool) or not isinstance(max_steps, int) or max_steps < 0:
            raise ValueError("max_steps must be a nonnegative integer")
        source = iter(events)
        for _ in range(max_steps):
            try:
                event = next(source)
            except StopIteration:
                return
            yield self.step(event, budget=budget, cost_budget=cost_budget)
