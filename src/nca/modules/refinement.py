"""Confidence-triggered refinement for any expert whose output is a
probability distribution.

``RequestingExpert`` wraps such an expert: when its most probable class has
probability at least ``threshold`` it answers; otherwise it returns a
``Request`` delegating its output to the kernel, which routes the same inputs
to another expert with the same contract. ``lean/NCA/Cascade.lean`` gives the
composite's exact error and expected cost.

``ConsultingExpert`` continues instead of delegating: when unsure it asks the
kernel for a second opinion on the same inputs and answers with the mixture
``(1 - w) · own + w · second`` (``lean/NCA/Continuation.lean``).
"""

from __future__ import annotations

from collections.abc import Generator, Sequence
from dataclasses import replace
from typing import Any

from nca.abi import Module, Request


class RequestingExpert:
    def __init__(self, base: Module, threshold: float) -> None:
        self.base = base
        self.threshold = threshold
        self.manifest = replace(base.manifest,
                                module_id=f"{base.manifest.module_id}.requesting")

    def invoke(self, *inputs: Any) -> Sequence[float] | Request:
        distribution = self.base.invoke(*inputs)
        if max(distribution) >= self.threshold:
            return distribution
        contract = self.manifest.contract
        return Request(contract.output, tuple(zip(contract.inputs, inputs, strict=True)),
                       provisional=distribution)


class ConsultingExpert:
    def __init__(self, base: Module, threshold: float, weight: float = 0.5) -> None:
        self.base = base
        self.threshold = threshold
        self.weight = weight
        self.manifest = replace(base.manifest,
                                module_id=f"{base.manifest.module_id}.consulting")

    def invoke(self, *inputs: Any) -> Generator[Request, Sequence[float], tuple[float, ...]]:
        own = self.base.invoke(*inputs)
        if max(own) >= self.threshold:
            return tuple(own)
        contract = self.manifest.contract
        second = yield Request(contract.output, tuple(zip(contract.inputs, inputs, strict=True)))
        return tuple((1 - self.weight) * a + self.weight * b for a, b in zip(own, second))
