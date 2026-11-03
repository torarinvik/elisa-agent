"""Self-regulating plasticity over (piece, region) keys (§43.8).

The field records, for each caller-chosen key, a plasticity in ``[0, 1]``
updated from two observed signals in ``[0, 1]``: *surprise* (for example a
failure rate, refuted calibration or detected shift in that region) raises it,
*stability* (for example use-weighted dependents or attestation strength)
damps it. A pluggable regulator performs the update; the default smooths toward
``surprise · (1 - stability)``, staying in ``[0, 1]`` and moving at most its rate
per observation (``NCA.smooth_unit``, ``NCA.smooth_step``). Keys open at
``open_at`` and close at ``close_at`` (hysteresis), so a key cannot flip back
in fewer than ``(open_at - close_at) / rate`` observations
(``NCA.hysteresis_gap``). ``allocate`` divides an acquisition budget among open
keys in proportion to plasticity, and ``settle`` closes a key once the gate
admits a change for it.

The field only directs where proposals are made. Whether a change is admitted
is the gate's decision, and Theorem 43.1 holds for any proposal rule, so no
regulator, learned or contributed, can weaken non-regression. Pieces never
report their own plasticity; callers derive signals from ledgers and audits.
Arithmetic is generic, so exact rationals work as well as floats.
"""

from __future__ import annotations

from collections.abc import Hashable
from dataclasses import dataclass
from numbers import Real
from typing import Protocol


class Regulator(Protocol):
    def __call__(self, plasticity: Real, surprise: Real, stability: Real) -> Real:
        """The next plasticity, in ``[0, 1]``."""
        ...


@dataclass(frozen=True)
class Smoothing:
    """Exponential smoothing toward ``surprise · (1 - stability)``."""

    rate: Real = 0.2

    def __post_init__(self) -> None:
        if not 0 < self.rate <= 1:
            raise ValueError("smoothing rate must lie in (0, 1]")

    def __call__(self, plasticity: Real, surprise: Real, stability: Real) -> Real:
        return (1 - self.rate) * plasticity + self.rate * (surprise * (1 - stability))


def _unit(value: Real, name: str) -> Real:
    if not 0 <= value <= 1:
        raise ValueError(f"{name} must lie in [0, 1]")
    return value


class PlasticityField:
    """Per-key plasticity with hysteresis; unseen keys start closed at ``initial``."""

    def __init__(self, regulator: Regulator | None = None, *, open_at: Real = 0.6,
                 close_at: Real = 0.3, initial: Real = 0) -> None:
        if not 0 <= close_at < open_at <= 1:
            raise ValueError("thresholds need 0 <= close_at < open_at <= 1")
        self.regulator = regulator if regulator is not None else Smoothing()
        self.open_at, self.close_at = open_at, close_at
        self.initial = _unit(initial, "initial plasticity")
        if initial > close_at:
            raise ValueError("initial plasticity must not exceed close_at")
        self._values: dict[Hashable, Real] = {}
        self._open: dict[Hashable, bool] = {}

    def observe(self, key: Hashable, surprise: Real, stability: Real) -> Real:
        """Update ``key`` from one observation window; returns its plasticity."""
        previous = self._values.get(key, self.initial)
        value = _unit(self.regulator(previous, _unit(surprise, "surprise"),
                                     _unit(stability, "stability")), "regulated plasticity")
        opened = self._open.get(key, False)
        self._values[key] = value
        self._open[key] = self.close_at < value if opened else self.open_at <= value
        return value

    def settle(self, key: Hashable) -> None:
        """Close ``key`` and reset it to the initial plasticity after the gate
        admits a change for it; reopening needs ``(open_at - close_at) / rate``
        further observations (``NCA.reopen_after_settle``)."""
        self._values[key] = self.initial
        self._open[key] = False

    def plasticity(self, key: Hashable) -> Real:
        return self._values.get(key, self.initial)

    def is_open(self, key: Hashable) -> bool:
        return self._open.get(key, False)

    def allocate(self, budget: int) -> dict[Hashable, int]:
        """Split ``budget`` attempts over open keys in proportion to plasticity,
        by largest remainder with ties in first-observed order."""
        if isinstance(budget, bool) or not isinstance(budget, int) or budget < 0:
            raise ValueError("budget must be a nonnegative integer")
        weights = {key: self._values[key] for key, opened in self._open.items() if opened}
        total = sum(weights.values())
        if not weights or total <= 0:
            return {}
        shares = {key: budget * weight / total for key, weight in weights.items()}
        granted = {key: int(share) for key, share in shares.items()}
        order = sorted(weights, key=lambda key: -(shares[key] - granted[key]))
        for key in order[:budget - sum(granted.values())]:
            granted[key] += 1
        return granted
