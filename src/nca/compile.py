"""Compiled routes: columnar evaluation of a plan over a batch of inputs (THEORY §34).

A compiled route evaluates each node for every row of a batch together; a
``Map`` evaluates its body once on the elements of all rows' sequences. An
expert with ``invoke_batch(*columns) -> list`` is called once per column;
others are invoked per row. Demand is honored as by the runtime: a row whose
demand on an argument is empty passes ``None`` without evaluating it.

Compilation is an optimization for routes of functional experts. It spends no
budget, records no messages, keeps no risk ledger and resolves no requests:
slots are refused when compiling, and a request or continuation returned at
run time raises ``NotCompilable``, after which the caller can use
``runtime.execute``, the reference semantics.
"""

from __future__ import annotations

from collections.abc import Callable, Generator, Sequence
from typing import Any

from nca.abi import NOTHING, Demand, Request, SequenceDemand, TypeId
from nca.planner import Apply, Given, Map, Plan


class NotCompilable(ValueError):
    """The route, or one of its invocations, needs the runtime."""


Row = tuple[Any, ...]


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


def _invoke(module: Any, columns: list[list[Any]], rows: int) -> list[Any]:
    batch = getattr(module, "invoke_batch", None)
    if batch is not None and columns:
        outputs = list(batch(*columns))
    else:
        outputs = [module.invoke(*(column[j] for column in columns)) for j in range(rows)]
    if any(isinstance(out, (Generator, Request)) for out in outputs):
        raise NotCompilable(f"{module.manifest.ref} needs the kernel")
    return outputs


def _evaluate(node: Plan, envs: Sequence[tuple[Row, Sequence[TypeId]]],
              demands: Sequence[Demand]) -> list[Any]:
    if isinstance(node, Given):
        values = []
        for row, types in envs:
            if (node.position is not None and node.position < len(types)
                    and types[node.position] == node.type_id):
                values.append(row[node.position])
            else:
                values.append(row[types.index(node.type_id)])
        return values
    if isinstance(node, Map):
        sources = _evaluate(node.source, envs, [None] * len(envs))
        elements: list[tuple[Row, Sequence[TypeId]]] = []
        element_demands: list[Demand] = []
        where: list[list[int | None]] = []
        for sequence, demand in zip(sources, demands, strict=True):
            slots: list[int | None] = []
            for i, value in enumerate(sequence):
                element_demand = _element(demand, i, len(sequence))
                if element_demand == NOTHING:
                    slots.append(None)
                else:
                    slots.append(len(elements))
                    elements.append(((value,), (node.element,)))
                    element_demands.append(element_demand)
            where.append(slots)
        results = _evaluate(node.body, elements, element_demands) if elements else []
        return [[None if j is None else results[j] for j in slots] for slots in where]
    declare = getattr(node.module, "demand", None)
    columns: list[list[Any]] = []
    for i, arg in enumerate(node.args):
        arg_demands = [declare(i, d) if declare is not None else None for d in demands]
        read = [j for j, d in enumerate(arg_demands) if d != NOTHING]
        column: list[Any] = [None] * len(envs)
        if read:
            values = _evaluate(arg, [envs[j] for j in read], [arg_demands[j] for j in read])
            for j, value in zip(read, values, strict=True):
                column[j] = value
        columns.append(column)
    return _invoke(node.module, columns, len(envs))


def compile_route(plan: Plan, available: Sequence[TypeId],
                  demand: Demand = None) -> Callable[[Sequence[Row]], list[Any]]:
    """Compile ``plan`` over inputs of the ``available`` types, in order.

    The result maps a batch of rows, each one value per available type, to the
    answers ``execute`` gives for each row alone, when every expert is
    functional and its ``invoke_batch``, if any, agrees with ``invoke``.
    """
    _check(plan)
    types = tuple(available)

    def run(rows: Sequence[Row]) -> list[Any]:
        if not rows:
            return []
        for row in rows:
            if len(row) != len(types):
                raise ValueError(f"expected {len(types)} inputs per row, got {len(row)}")
        return _evaluate(plan, [(tuple(row), types) for row in rows], [demand] * len(rows))

    return run
