"""Compiled routes: columnar evaluation of a plan over a batch of inputs (THEORY §34).

A compiled route evaluates each node for every row of a batch together; a
``Map`` evaluates its body once on the elements of all rows' sequences. An
expert with ``invoke_batch(*columns) -> list`` is called once per column;
others are invoked per row. Demand is honored as by the runtime: a row whose
demand on an argument is empty passes ``None`` without evaluating it.

With a ``ResultCache``, each row's invocation is looked up and checked as by
the runtime, and the misses of a batch are evaluated once per distinct key.
With one ``RiskLedger`` per row, each row is charged as ``execute`` charges
it alone (§34.3): decision demand is propagated alongside read demand, and
an expert that accounts inside is invoked per row with that row's ledger
current.

Compilation spends no budget, records no messages and resolves no requests:
slots are refused when compiling, and a request or continuation returned at
run time raises ``NotCompilable``, after which the caller can use
``runtime.execute``, the reference semantics.
"""

from __future__ import annotations

from collections.abc import Callable, Generator, Hashable, Sequence
from typing import Any

from nca.abi import NOTHING, Demand, Module, Request, SequenceDemand, TypeId
from nca.cache import ResultCache
from nca.planner import Apply, Given, Map, Plan
from nca.runtime import _LEDGER, RiskLedger, charge, result_key


class NotCompilable(ValueError):
    """The route, or one of its invocations, needs the runtime."""


Row = tuple[Any, ...]
Env = tuple[Row, Sequence[TypeId], RiskLedger | None]


def _check(node: Plan) -> None:
    if isinstance(node, Map):
        _check(node.source)
        _check(node.body)
    elif isinstance(node, Apply):
        if node.slots:
            raise NotCompilable(f"{node.module.manifest.ref} has slots")
        for arg in node.args:
            _check(arg)


def _element(demand: Demand, i: int, length: int) -> Demand:
    return demand.element(i, length) if isinstance(demand, SequenceDemand) else demand


class _Batch:
    def __init__(self, cache: ResultCache | None) -> None:
        self.cache = cache

    def invoke(self, module: Module, columns: list[list[Any]],
               ledgers: list[RiskLedger | None]) -> list[Any]:
        rows = len(ledgers)
        batch = getattr(module, "invoke_batch", None)
        if getattr(module, "accounts_inside", False) and any(ledgers):
            outputs = []
            for j, ledger in enumerate(ledgers):
                token = _LEDGER.set(ledger)
                try:
                    outputs.append(module.invoke(*(column[j] for column in columns)))
                finally:
                    _LEDGER.reset(token)
        elif batch is not None and columns:
            outputs = list(batch(*columns))
        else:
            outputs = [module.invoke(*(column[j] for column in columns)) for j in range(rows)]
        if any(isinstance(out, (Generator, Request)) for out in outputs):
            raise NotCompilable(f"{module.manifest.ref} needs the kernel")
        return outputs

    def apply(self, module: Module, columns: list[list[Any]],
              envs: Sequence[Env]) -> list[Any]:
        """Each row's output, from the cache where it serves the row, the
        misses invoked once per distinct key."""
        outputs: list[Any] = [None] * len(envs)
        pending: dict[Hashable, list[int]] = {}
        checking: dict[Hashable, Any] = {}
        fresh: list[int] = []
        for j, (_, _, ledger) in enumerate(envs):
            key = result_key(self.cache, ledger, module, [column[j] for column in columns])
            if key is None:
                fresh.append(j)
                continue
            if key in pending:
                pending[key].append(j)
                continue
            hit, stored = self.cache.lookup(key)
            if hit and not self.cache.sample():
                outputs[j] = stored
                continue
            if hit:
                checking[key] = stored
            pending[key] = [j]
        invoked = fresh + [rows[0] for rows in pending.values()]
        if invoked:
            results = self.invoke(module, [[column[j] for j in invoked] for column in columns],
                                  [envs[j][2] for j in invoked])
            for j, result in zip(invoked, results, strict=True):
                outputs[j] = result
        for key, rows in pending.items():
            result = outputs[rows[0]]
            if key in checking:
                self.cache.check(key, checking[key], result)
            else:
                self.cache.store(key, result)
            for j in rows[1:]:
                outputs[j] = result
        return outputs

    def evaluate(self, node: Plan, envs: Sequence[Env], demands: Sequence[Demand],
                 decisions: Sequence[Demand]) -> list[Any]:
        if isinstance(node, Given):
            values = []
            for row, types, _ in envs:
                if (node.position is not None and node.position < len(types)
                        and types[node.position] == node.type_id):
                    values.append(row[node.position])
                else:
                    values.append(row[types.index(node.type_id)])
            return values
        if isinstance(node, Map):
            sources = self.evaluate(node.source, envs, [None] * len(envs), [None] * len(envs))
            elements: list[Env] = []
            element_demands: list[Demand] = []
            element_decisions: list[Demand] = []
            where: list[list[int | None]] = []
            for sequence, (_, _, ledger), demand, decision in zip(sources, envs, demands,
                                                                   decisions, strict=True):
                slots: list[int | None] = []
                for i, value in enumerate(sequence):
                    element_demand = _element(demand, i, len(sequence))
                    if element_demand == NOTHING:
                        slots.append(None)
                    else:
                        slots.append(len(elements))
                        elements.append(((value,), (node.element,), ledger))
                        element_demands.append(element_demand)
                        element_decisions.append(_element(decision, i, len(sequence)))
                where.append(slots)
            results = (self.evaluate(node.body, elements, element_demands, element_decisions)
                       if elements else [])
            return [[None if j is None else results[j] for j in slots] for slots in where]
        module = node.module
        declare = getattr(module, "demand", None)
        decides = getattr(module, "decides", None) or declare
        columns: list[list[Any]] = []
        for i, arg in enumerate(node.args):
            arg_demands = [declare(i, d) if declare is not None else None for d in demands]
            arg_decisions = [decides(i, d) if decides is not None else None for d in decisions]
            read = [j for j, d in enumerate(arg_demands) if d != NOTHING]
            column: list[Any] = [None] * len(envs)
            if read:
                values = self.evaluate(arg, [envs[j] for j in read],
                                       [arg_demands[j] for j in read],
                                       [arg_decisions[j] for j in read])
                for j, value in zip(read, values, strict=True):
                    column[j] = value
            columns.append(column)
        outputs = self.apply(module, columns, envs)
        for j, ((_, _, ledger), decision) in enumerate(zip(envs, decisions, strict=True)):
            charge(ledger, module, outputs[j], decision, [column[j] for column in columns])
        return outputs


def compile_route(plan: Plan, available: Sequence[TypeId], demand: Demand = None
                  ) -> Callable[..., list[Any]]:
    """Compile ``plan`` over inputs of the ``available`` types, in order.

    The result maps a batch of rows, each one value per available type, to the
    answers ``execute`` gives for each row alone, when every expert is
    functional and its ``invoke_batch``, if any, agrees with ``invoke``. It
    takes an optional ``cache`` and an optional list of ``ledgers``, one per
    row, used as ``execute`` uses them.
    """
    _check(plan)
    types = tuple(available)

    def run(rows: Sequence[Row], cache: ResultCache | None = None,
            ledgers: Sequence[RiskLedger] | None = None) -> list[Any]:
        if ledgers is not None and len(ledgers) != len(rows):
            raise ValueError(f"expected {len(rows)} ledgers, got {len(ledgers)}")
        for row in rows:
            if len(row) != len(types):
                raise ValueError(f"expected {len(types)} inputs per row, got {len(row)}")
        envs = [(tuple(row), types, None if ledgers is None else ledgers[j])
                for j, row in enumerate(rows)]
        return _Batch(cache).evaluate(plan, envs, [demand] * len(rows), [demand] * len(rows))

    return run
