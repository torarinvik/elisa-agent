"""Confidence-triggered refinement for recognizers.

``RequestingRecognizer`` wraps a recognizer: when its most probable class has
probability at least ``threshold`` it answers; otherwise it returns a
``Request`` delegating its output to the kernel, which routes the same glyph
to another recognizer with the same contract. ``lean/NCA/Cascade.lean`` gives
the composite's exact error and expected cost.

``ConsultingRecognizer`` continues instead of delegating: when unsure it asks
the kernel for a second opinion on the glyph and answers with the mixture
``(1 - w) · own + w · second`` (``lean/NCA/Continuation.lean``).
"""

from __future__ import annotations

from collections.abc import Generator
from dataclasses import replace

import torch

from nca.abi import Request
from nca.modules.digit_recognizer import GLYPH, DigitRecognizer


class RequestingRecognizer:
    def __init__(self, base: DigitRecognizer, threshold: float) -> None:
        self.base = base
        self.threshold = threshold
        self.manifest = replace(base.manifest,
                                module_id=f"{base.manifest.module_id}.requesting")

    def invoke(self, glyph: torch.Tensor) -> tuple[float, ...] | Request:
        distribution = self.base.invoke(glyph)
        if max(distribution) >= self.threshold:
            return distribution
        return Request(self.manifest.contract.output, {GLYPH: glyph}, provisional=distribution)


class ConsultingRecognizer:
    def __init__(self, base: DigitRecognizer, threshold: float, weight: float = 0.5) -> None:
        self.base = base
        self.threshold = threshold
        self.weight = weight
        self.manifest = replace(base.manifest,
                                module_id=f"{base.manifest.module_id}.consulting")

    def invoke(self, glyph: torch.Tensor) -> Generator[Request, tuple[float, ...],
                                                        tuple[float, ...]]:
        own = self.base.invoke(glyph)
        if max(own) >= self.threshold:
            return own
        second = yield Request(self.manifest.contract.output, {GLYPH: glyph})
        return tuple((1 - self.weight) * a + self.weight * b for a, b in zip(own, second))
