"""Per-execution risk charges and the shared nested-execution ledger context."""
from __future__ import annotations

from collections.abc import Callable, Sequence
from contextvars import ContextVar
from dataclasses import dataclass, field
import math
from numbers import Real
from typing import Any

from nca.abi import NOTHING, Demand, Module
from nca.effects import effect_call
from nca.native import load

_ADD_UPPER = getattr(load("stats"), "nonnegative_add_upper", None)


def _report_upper(value: Any, *, allow_infinite: bool = False) -> float:
    """Normalize supported real scalars without rounding a report downward."""
    if isinstance(value, bool) or not isinstance(value, Real) or value < 0:
        raise ValueError("risk reports must be finite nonnegative real scalars")
    try:
        result = float(value)
    except (OverflowError, ValueError) as error:
        raise ValueError("risk report exceeds finite binary64 range") from error
    if value > result:
        result = math.nextafter(result, math.inf)
    if not math.isfinite(result) and not (allow_infinite and result == math.inf):
        raise ValueError("risk reports must be finite nonnegative real scalars")
    return result


def _add_upper(a: float, b: float) -> float:
    """Upper binary64 sum using FastTwoSum's residual under strict IEEE FP."""
    if a < 0 or b < 0 or math.isnan(a) or math.isnan(b):
        raise ValueError("risk ledger operands must be nonnegative")
    if a == 0:
        return b
    if b == 0 or math.isinf(a):
        return a
    if _ADD_UPPER is not None:
        return _ADD_UPPER(a, b)
    larger, smaller = (a, b) if a >= b else (b, a)
    total = larger + smaller
    if math.isinf(total):
        return total
    residual = smaller - (total - larger)
    return math.nextafter(total, math.inf) if residual > 0 else total


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

    def __post_init__(self) -> None:
        self.charge = _report_upper(self.charge, allow_infinite=True)

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
        reported = _report_upper(reported)
        ledger.charge = _add_upper(ledger.charge, reported)
        ledger.entries.append((module, tuple(values), reported))
        answering = getattr(module, "answering", None)
        expert = (module if answering is None else
                  effect_call(module.manifest.effects, answering, *values))
        ledger.invocations.append(Invocation(expert, tuple(values), payload, reported))
    elif not ledger.exact(module):
        ledger.uncertified.append(module.manifest.module_id)
