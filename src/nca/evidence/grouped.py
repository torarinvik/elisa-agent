"""Experts calibrated by groups of their inputs (THEORY §37).

``Grouped`` reads each input through the rung fitted on labeled inputs of
that input's group, as computed by a grouping function of the input. An
input whose group has no rung is read uncalibrated and reports no risk,
which leaves a risk ledger uncertified (§33.2).
"""

from __future__ import annotations

from collections.abc import Callable, Hashable, Mapping, Sequence
from typing import Any

import torch

from nca.abi import Module
from nca.ladder import Calibrated, Rung


class Grouped:
    def __init__(self, module: Module, group: Callable[[Any], Hashable],
                 rungs: Mapping[Hashable, Rung]) -> None:
        self.module = module
        self.manifest = module.manifest
        self.group = group
        self.readers = {key: Calibrated(rung) for key, rung in rungs.items()}

    def invoke(self, value: Any) -> tuple[float, ...]:
        reader = self.readers.get(self.group(value))
        return tuple(self.module.invoke(value)) if reader is None else reader.invoke(value)

    def risk(self, output: Sequence[float], *inputs: Any) -> float | None:
        reader = self.readers.get(self.group(inputs[0]))
        return None if reader is None else reader.risk(output)


def fit_groups(module: Module, group: Callable[[Any], Hashable], values: Sequence[Any],
               labels: Sequence[int]) -> dict[Hashable, Rung]:
    """One rung per group present among the labeled ``values``, each fitted on
    that group's values (§37.2)."""
    if len(values) != len(labels):
        raise ValueError("fitting needs one label per value")
    members: dict[Hashable, tuple[list[Any], list[int]]] = {}
    for value, label in zip(values, labels):
        chosen, targets = members.setdefault(group(value), ([], []))
        chosen.append(value)
        targets.append(label)
    rungs = {}
    for key, (chosen, targets) in members.items():
        rung = Rung(module)
        rung.calibrate(chosen, torch.tensor(targets))
        rungs[key] = rung
    return rungs
