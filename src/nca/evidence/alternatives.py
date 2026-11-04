"""Answering over alternatives (THEORY §39).

A *fork* is an expert with ``candidates(*inputs) -> list[(output, q)]``:
candidate outputs, each with a lower bound ``q`` on the probability that it
is the correct output, given the observations. ``answer_over_alternatives``
evaluates the route once per candidate, as extra rows of a compiled batch
each with its own risk ledger, and answers the answer with the largest
support ``Σ q (1 − c)`` when its bound ``c₀ + 1 − support`` is at most the
target. ``Tabled`` gives an expert's ranked ``alternatives`` such bounds
from a table that ``fit_table`` estimates on labeled in-situ inputs.
"""

from __future__ import annotations

from collections.abc import Callable, Hashable, Iterator, Sequence
from dataclasses import dataclass, replace
from typing import Any

from nca.abi import Module, TypeId
from nca.effects import invoke_scoped
from nca.cache import ResultCache, value_digest
from nca.compile import compile_route
from nca.planner import Apply, Given, Map, Plan
from nca.runtime import RiskLedger
from nca.stats import clopper_pearson_upper


@dataclass(frozen=True)
class Choice:
    answer: Any
    """The answer, or ``None`` if its bound exceeds the target."""
    bound: float
    """``c₀ + 1 − support`` of the answer with the largest support."""
    candidates: int


def _forks(node: Plan) -> Iterator[Apply]:
    if isinstance(node, Map):
        yield from _forks(node.source)
    elif isinstance(node, Apply):
        if hasattr(node.module, "candidates"):
            yield node
        for arg in node.args:
            yield from _forks(arg)


def _substitute(node: Plan, fork: Apply, replacement: Plan) -> Plan:
    if node is fork:
        return replacement
    if isinstance(node, Map):
        return replace(node, source=_substitute(node.source, fork, replacement))
    if isinstance(node, Apply):
        return replace(node, args=tuple(_substitute(a, fork, replacement) for a in node.args))
    return node


def _charge(ledger: RiskLedger) -> float:
    return min(1.0, ledger.charge) if ledger.certified else 1.0


def answer_over_alternatives(plan: Plan, available: Sequence[TypeId],
                             rows: Sequence[tuple[Any, ...]], delta: float,
                             exact: Callable[[Module], bool] | None = None,
                             cache: ResultCache | None = None) -> list[Choice]:
    """Answer each row over the candidates of the route's one fork, outside
    any map body (Theorem 39.1)."""
    forks = list(_forks(plan))
    if len(forks) != 1:
        raise ValueError(f"the route needs exactly one fork outside map bodies, has {len(forks)}")
    (fork,) = forks

    def ledgers(n: int) -> list[RiskLedger]:
        return [RiskLedger() if exact is None else RiskLedger(exact) for _ in range(n)]

    before = ledgers(len(rows))
    inputs = [compile_route(arg, available)(rows, cache=cache, ledgers=before)
              for arg in fork.args]
    expanded: list[tuple[Any, ...]] = []
    weights: list[tuple[int, float]] = []
    for j, row in enumerate(rows):
        for output, q in fork.module.candidates(*(column[j] for column in inputs)):
            expanded.append((*row, output))
            weights.append((j, q))
    after = ledgers(len(expanded))
    rest = _substitute(plan, fork, Given(fork.contract.output, len(available)))
    answers = (compile_route(rest, (*available, fork.contract.output))(
        expanded, cache=cache, ledgers=after) if expanded else [])
    support: list[dict[Any, tuple[float, Any]]] = [{} for _ in rows]
    for (j, q), answer, ledger in zip(weights, answers, after, strict=True):
        key = value_digest(answer)
        total, _ = support[j].get(key, (0.0, answer))
        support[j][key] = (total + q * (1.0 - _charge(ledger)), answer)
    choices = []
    for j, ledger in enumerate(before):
        best, answer = max(support[j].values(), key=lambda entry: entry[0],
                           default=(0.0, None))
        bound = min(1.0, _charge(ledger) + 1.0 - best)
        count = sum(1 for k, _ in weights if k == j)
        choices.append(Choice(answer if bound <= delta else None, bound, count))
    return choices


class Tabled:
    """A fork from an expert's ranked ``alternatives``: candidate ``k`` of
    inputs in stratum ``s = stratum(*inputs)`` gets ``table[(s, k)]``;
    candidates without an entry are dropped. The expert's own ``invoke`` is
    unchanged."""

    def __init__(self, module: Module, table: dict[tuple[Hashable, int], float],
                 stratum: Callable[..., Hashable]) -> None:
        self.module = module
        self.manifest = module.manifest
        self.table = table
        self.stratum = stratum

    def invoke(self, *inputs: Any) -> Any:
        return invoke_scoped(self.module, *inputs)

    def candidates(self, *inputs: Any) -> list[tuple[Any, float]]:
        outputs = list(self.module.alternatives(*inputs))
        key = self.stratum(*inputs)
        return [(output, self.table[(key, k)]) for k, output in enumerate(outputs)
                if (key, k) in self.table]


def fit_table(module: Module, values: Sequence[Any], labels: Sequence[Any],
              correct: Callable[[Any, Any], bool], stratum: Callable[..., Hashable],
              beta: float, ranks: int) -> dict[tuple[Hashable, int], float]:
    """Clopper–Pearson lower bounds on the rate at which each of the first
    ``ranks`` candidates of ``module.alternatives`` is correct, per stratum,
    all holding together with probability at least ``1 − beta`` (§39.2).
    ``correct(candidate, label)`` scores a candidate, and ``stratum(value)``
    groups the inputs by an observable property."""
    counts: dict[tuple[Hashable, int], list[int]] = {}
    strata: dict[Hashable, int] = {}
    for value, label in zip(values, labels, strict=True):
        outputs = list(module.alternatives(value))
        key = stratum(value)
        strata[key] = strata.get(key, 0) + 1
        for k in range(ranks):
            cell = counts.setdefault((key, k), [0, 0])
            if k < len(outputs) and correct(outputs[k], label):
                cell[0] += 1
    for (key, _), cell in counts.items():
        cell[1] = strata[key]
    level = beta / max(len(counts), 1)
    return {cell: 1.0 - clopper_pearson_upper(n - s, n, level)
            for cell, (s, n) in counts.items()}
