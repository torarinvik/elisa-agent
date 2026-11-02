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

``Escalating`` holds a ladder of substitutes that report their risk and
answers each distinct input at that input's level; ``refine`` raises the
level of one input, which ``evidence.refine_within`` does for the riskiest
charged invocation of any route (THEORY §33.3).
"""

from __future__ import annotations

from collections.abc import Generator, Sequence
from dataclasses import replace
from typing import Any

from nca.abi import Module, Request
from nca.cache import value_digest


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


class Escalating:
    """A ladder of reporting substitutes, cheapest first, used as one expert.

    Each distinct input (by content digest) is answered at its own level,
    starting at the bottom; its report is that of the rung that answered.
    Inputs without a canonical encoding stay at the bottom. Its declared
    cost is the bottom rung's.
    """

    def __init__(self, rungs: Sequence[Module], module_id: str) -> None:
        contracts = {r.manifest.contract for r in rungs}
        if not rungs or len(contracts) != 1:
            raise ValueError("an escalating expert needs rungs with one shared contract")
        self.rungs = list(rungs)
        self.manifest = replace(rungs[0].manifest, module_id=module_id)
        self.levels: dict[str, int] = {}
        self._answered_by = 0

    def _level(self, values: tuple[Any, ...]) -> tuple[str | None, int]:
        key = value_digest(list(values))
        return key, 0 if key is None else self.levels.get(key, 0)

    def invoke(self, *values: Any) -> Any:
        _, self._answered_by = self._level(values)
        return self.rungs[self._answered_by].invoke(*values)

    def risk(self, output: Any) -> float | None:
        report = getattr(self.rungs[self._answered_by], "risk", None)
        return None if report is None else report(output)

    def refine(self, *values: Any) -> bool:
        """Answer ``values`` one rung higher from now on; ``False`` at the top."""
        key, level = self._level(values)
        if key is None or level + 1 >= len(self.rungs):
            return False
        self.levels[key] = level + 1
        return True
