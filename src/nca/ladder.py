"""Calibrated ladders of interchangeable experts and budgeted refinement.

Generic over experts: a *ladder* for a contract is every installed module with
that contract whose output is a probability distribution, ordered by declared
cost. Each rung carries a temperature fitted on held-out labeled inputs, so
``1 - max p`` estimates its error probability. ``SecondLook`` wraps any such
expert into a costlier one with the same contract that averages its readings
of several views of the input; it joins ladders like any other expert.

``refine`` reads every item at the bottom of its ladder and, while the sum of
risks (the union bound) exceeds the target ``δ``, moves the riskiest item one
rung up, using its latest reading. It abstains when no rung remains. For
calibrated risks the error among answered inputs is at most ``δ``
(``NCA.selective_risk_le``), and refining where the bound falls most per unit
of compute is the ``NCA.threshold_optimal`` rule; with a floor ``ρ`` per item,
``n`` items need ``n · ρ ≤ δ`` (``NCA.length_limit``).
"""

from __future__ import annotations

from collections.abc import Callable, Sequence
from dataclasses import dataclass, replace
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
    """An expert read through a fitted temperature."""

    module: Module
    temperature: float = 1.0

    @property
    def cost(self) -> float:
        return self.module.manifest.cost

    def read(self, value: Any) -> torch.Tensor:
        raw = torch.tensor(self.module.invoke(value)).clamp_min(1e-12)
        return torch.softmax(raw.log() / self.temperature, dim=-1)

    def calibrate(self, values: Sequence[Any], labels: torch.Tensor) -> None:
        """Fit the temperature minimizing negative log-likelihood on held-out inputs."""
        log = torch.stack([torch.tensor(self.module.invoke(v)) for v in values]) \
            .clamp_min(1e-12).log()

        def nll(t: float) -> float:
            return nn.functional.cross_entropy(log / t, labels).item()

        self.temperature = float(min(np.geomspace(0.1, 8.0, 120), key=nll))


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


def refine(values: Sequence[Any], ladders: Sequence[Sequence[Rung]], delta: float,
           start: int = 0) -> Refinement:
    """Read ``values[i]`` with ``ladders[i]``, refining until the bound meets ``delta``.

    Every item starts at rung ``min(start, top)``, reading each rung below it.
    """
    levels = [0] * len(values)
    readings: list[torch.Tensor] = [torch.empty(0)] * len(values)
    risks = [0.0] * len(values)
    cost = 0.0

    def climb(i: int) -> None:
        nonlocal cost
        rung = ladders[i][levels[i]]
        readings[i] = rung.read(values[i])
        risks[i] = 1.0 - readings[i].max().item()
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
