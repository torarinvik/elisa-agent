"""Plasticity signals from risk ledgers, audits and route dependents (§43.9).

``surprise`` reads a window of execution ledgers: for each key, chosen from each
charged invocation by a caller's function (an expert identity, optionally with
an input region), it is the larger of the mean reported risk of that key's
invocations and an audit refutation flag. Reports need no labels; an audit
that refutes calibration for a key (labeled, in situ or by agreement) raises
its surprise to one, catching experts that fail while reporting low risk.
Invocations charged without a report are not observations. ``stability`` damps
plasticity by the number ``d`` of protected routes depending on an expert, as
``d / (d + half)``. Both lie in ``[0, 1]`` (``NCA.meanSignal_unit``,
``NCA.dependentStability_unit``), the input range of Theorem 43.2.
"""

from __future__ import annotations

from collections.abc import Callable, Hashable, Mapping, Sequence

from nca.abi import Module
from nca.evidence import Audit
from nca.retention.plasticity import PlasticityField
from nca.retention.routes import RouteCatalog
from nca.runtime import Invocation, RiskLedger


def identity(invocation: Invocation) -> Hashable:
    """The default key: the answering expert's content identity or manifest."""
    expert = invocation.expert
    return getattr(expert, "identity", None) or expert.manifest.ref


def surprise(ledgers: Sequence[RiskLedger],
             key: Callable[[Invocation], Hashable | None] = identity, *,
             audits: Mapping[Hashable, Audit] | None = None,
             alpha: float = 0.05) -> dict[Hashable, float]:
    """Each observed key's surprise over one window; ``key`` returning ``None``
    skips an invocation. Audited keys count even without invocations."""
    if not 0 < alpha < 1:
        raise ValueError("alpha must lie in (0, 1)")
    totals: dict[Hashable, list[float]] = {}
    for ledger in ledgers:
        for invocation in ledger.invocations:
            name = key(invocation)
            if name is None:
                continue
            if not 0 <= invocation.report <= 1:
                raise ValueError("reported risks must be probabilities")
            entry = totals.setdefault(name, [0.0, 0])
            entry[0] += invocation.report
            entry[1] += 1
    signals = {name: total / count for name, (total, count) in totals.items()}
    for name, result in (audits or {}).items():
        if result.refutes(alpha):
            signals[name] = 1.0
        else:
            signals.setdefault(name, 0.0)
    return signals


def stability(catalog: RouteCatalog, module: Module, half: float = 1.0) -> float:
    """``d / (d + half)`` for the ``d`` protected routes using ``module``."""
    if not half > 0:
        raise ValueError("half-saturation must be positive")
    count = len(catalog.dependents(module))
    return count / (count + half)


def observe(field: PlasticityField, signals: Mapping[Hashable, float],
            stable: Callable[[Hashable], float]) -> dict[Hashable, float]:
    """Feed one window's signals to ``field``; returns each key's plasticity."""
    return {name: field.observe(name, value, stable(name)) for name, value in signals.items()}
