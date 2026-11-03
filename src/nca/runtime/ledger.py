"""Per-execution risk charges and the shared nested-execution ledger context."""
from __future__ import annotations

from collections.abc import Callable, Sequence
from contextvars import ContextVar
from dataclasses import dataclass, field
from typing import Any

from nca.abi import NOTHING, Demand, Module
from nca.effects import effect_call


def _never(module: Module) -> bool:
    return False


@dataclass(frozen=True)
class Invocation:
    """A charged invocation: the expert that answered it (an escalating
    expert's ``answering`` rung, else the expert itself), its inputs, its
    output and its report."""

    expert: Module
    values: tuple[Any, ...]
    output: Any
    report: float


@dataclass
class RiskLedger:
    """The per-input charge of one execution (§33.2)."""

    exact: Callable[[Module], bool] = _never
    """Experts charged nothing without reporting, such as attested exact ones."""
    charge: float = 0.0
    uncertified: list[str] = field(default_factory=list)
    """Experts invoked without a reported risk, by module id."""
    entries: list[tuple[Module, tuple[Any, ...], float]] = field(default_factory=list)
    """Each charged invocation: the expert, its input values and its report."""
    invocations: list[Invocation] = field(default_factory=list)
    """Each charged invocation as audits sample it (§38)."""

    @property
    def certified(self) -> bool:
        return not self.uncertified


_LEDGER: ContextVar[RiskLedger | None] = ContextVar("nca_risk_ledger", default=None)


def charge(ledger: RiskLedger | None, module: Module, payload: Any, decision: Demand,
           values: Sequence[Any]) -> None:
    """Charge ``module``'s invocation on ``values`` to ``ledger`` (§33.2)."""
    if ledger is None or decision == NOTHING or getattr(module, "accounts_inside", False):
        return
    report = getattr(module, "risk", None)
    reported = (None if report is None else
                effect_call(module.manifest.effects, report, payload, *values))
    if reported is not None:
        ledger.charge += reported
        ledger.entries.append((module, tuple(values), reported))
        answering = getattr(module, "answering", None)
        expert = (module if answering is None else
                  effect_call(module.manifest.effects, answering, *values))
        ledger.invocations.append(Invocation(expert, tuple(values), payload, reported))
    elif not ledger.exact(module):
        ledger.uncertified.append(module.manifest.module_id)
