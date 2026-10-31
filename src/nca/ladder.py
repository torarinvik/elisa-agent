"""Calibrated ladders of interchangeable experts and budgeted refinement.

Generic over experts: a *ladder* for a contract is every installed module with
that contract whose output is a probability distribution, ordered by declared
cost. Each rung carries temperatures fitted on held-out labeled inputs, one for its
full output and one per restricted decision it serves (fitted on the held-out
inputs whose label is among the decision's classes), so its risk estimates
the error probability of the decision actually made. ``SecondLook`` wraps any such
expert into a costlier one with the same contract that averages its readings
of several views of the input; it joins ladders like any other expert.

``refine`` reads every item at the bottom of its ladder and, while the sum of
risks (the union bound) exceeds the target ``δ``, moves the riskiest item one
rung up, using its latest reading. An item's risk is measured against the
classes its decision ranges over, ``1 - max_C p / Σ_C p``, which never exceeds
``1 - max p`` when the most probable class is in ``C``
(``NCA.restricted_risk_le``). It abstains when no rung remains. For
calibrated risks the error among answered inputs is at most ``δ``
(``NCA.selective_risk_le``), and refining where the bound falls most per unit
of compute is the ``NCA.threshold_optimal`` rule; with a floor ``ρ`` per item,
``n`` items need ``n · ρ ≤ δ`` (``NCA.length_limit``).
"""

from __future__ import annotations

from collections.abc import Callable, Sequence
from dataclasses import dataclass, field, replace
from typing import Any

import numpy as np
import torch
from torch import nn

from nca.abi import Contract
from nca.registry import Module


class SecondLook:
    """An expert reading its input and ``views`` of it, averaging the readings."""

    def __init__(self, module: Module, views: Callable[[Any], list[Any]], count: int) -> None:
        self.module = module
        self.views = views
        self.manifest = replace(module.manifest,
                                module_id=f"{module.manifest.module_id}.second-look",
                                cost=module.manifest.cost * (count + 1))

    def invoke(self, value: Any) -> tuple[float, ...]:
        readings = [self.module.invoke(v) for v in (value, *self.views(value))]
        return tuple(np.mean(readings, axis=0).tolist())


@dataclass
class Rung:
    """An expert read through temperatures fitted on held-out labeled inputs:
    one for its full output and one for each restricted decision it serves."""

    module: Module
    temperatures: dict[tuple[int, ...] | None, float] = field(default_factory=dict)
    held_out: tuple[torch.Tensor, torch.Tensor] | None = None

    @property
    def cost(self) -> float:
        return self.module.manifest.cost

    def observe(self, value: Any) -> torch.Tensor:
        """Log-probabilities of the expert's output."""
        return torch.tensor(self.module.invoke(value)).clamp_min(1e-12).log()

    def calibrate(self, values: Sequence[Any], labels: torch.Tensor) -> None:
        """Keep held-out observations and fit the full output's temperature."""
        self.held_out = (torch.stack([self.observe(v) for v in values]), labels)
        self.temperatures = {None: self._fit(*self.held_out)}

    def temperature(self, classes: Sequence[int] | None = None) -> float:
        """Temperature of the decision over ``classes``, fitted on first use on
        the held-out inputs whose label is among them."""
        key = None if classes is None else tuple(classes)
        if key not in self.temperatures:
            if self.held_out is None:
                return 1.0
            log, labels = self.held_out
            inside = torch.isin(labels, torch.tensor(key))
            remap = {c: k for k, c in enumerate(key)}
            restricted = torch.tensor([remap[int(y)] for y in labels[inside]])
            self.temperatures[key] = self._fit(log[inside][:, list(key)], restricted)
        return self.temperatures[key]

    def reading(self, log: torch.Tensor) -> torch.Tensor:
        return torch.softmax(log / self.temperature(), dim=-1)

    def risk(self, log: torch.Tensor, classes: Sequence[int] | None = None) -> float:
        """Calibrated error probability of the decision over ``classes``."""
        if classes is None:
            return risk(self.reading(log))
        return risk(torch.softmax(log[list(classes)] / self.temperature(classes), dim=-1))

    @staticmethod
    def _fit(log: torch.Tensor, labels: torch.Tensor) -> float:
        """The temperature minimizing negative log-likelihood."""
        def nll(t: float) -> float:
            return nn.functional.cross_entropy(log / t, labels).item()

        return float(min(np.geomspace(0.1, 8.0, 120), key=nll))


def ladder(modules: Sequence[Module], contract: Contract) -> list[Rung]:
    """Rungs for every module with ``contract``, cheapest first."""
    found = [m for m in modules if m.manifest.contract == contract]
    return [Rung(m) for m in sorted(found, key=lambda m: m.manifest.cost)]


@dataclass
class Refinement:
    readings: list[torch.Tensor]
    cost: float
    bound: float
    abstained: bool


def risk(reading: torch.Tensor, classes: Sequence[int] | None = None) -> float:
    """Error probability of the decision over ``classes`` (all if ``None``)."""
    mass = reading if classes is None else reading[list(classes)]
    return 1.0 - (mass.max() / mass.sum()).item()


def refine(values: Sequence[Any], ladders: Sequence[Sequence[Rung]], delta: float,
           start: int = 0, classes: Sequence[Sequence[int] | None] | None = None,
           ) -> Refinement:
    """Read ``values[i]`` with ``ladders[i]``, refining until the bound meets ``delta``.

    Every item starts at rung ``min(start, top)``, reading each rung below it.
    ``classes[i]`` restricts the decision item ``i`` serves.
    """
    decisions = classes if classes is not None else [None] * len(values)
    levels = [0] * len(values)
    readings: list[torch.Tensor] = [torch.empty(0)] * len(values)
    risks = [0.0] * len(values)
    cost = 0.0

    def climb(i: int) -> None:
        nonlocal cost
        rung = ladders[i][levels[i]]
        log = rung.observe(values[i])
        readings[i] = rung.reading(log)
        risks[i] = rung.risk(log, decisions[i])
        cost += rung.cost

    for i in range(len(values)):
        climb(i)
        while levels[i] < min(start, len(ladders[i]) - 1):
            levels[i] += 1
            climb(i)
    while sum(risks) > delta:
        open_ = [i for i in range(len(values)) if levels[i] + 1 < len(ladders[i])]
        if not open_:
            break
        i = max(open_, key=risks.__getitem__)
        levels[i] += 1
        climb(i)
    bound = sum(risks)
    return Refinement(readings, cost, bound, bound > delta)
