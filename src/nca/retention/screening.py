"""Optional impossibility screen for deterministic acquisition (§20.16).

Equal keys must mean equal predictor inputs. ``separates(a, b)`` must imply
that no prediction agrees with both labels under the acquirer's agreement
rule. These are caller-supplied semantic assumptions, not inferred from Python
inequality. Hidden state and randomness must be represented in the inputs.
Fresh IID cases from the distribution of use are required, conditional on
past requests. This screen cannot establish learnability when it passes.
"""

from __future__ import annotations

import math
from collections.abc import Callable, Hashable, Sequence
from dataclasses import dataclass
from fractions import Fraction
from typing import Any


@dataclass(frozen=True)
class ScreenResult:
    cases: int
    pairs: tuple[tuple[int, int], ...]
    threshold: int | None
    level: Fraction

    @property
    def rejected(self) -> bool:
        return self.threshold is not None and len(self.pairs) >= self.threshold


def _disjoint_pairs(cases: Sequence[tuple[Any, Any]], keys: Sequence[Hashable],
                    separates: Callable[[Any, Any], bool]) -> list[tuple[int, int]]:
    """Greedy maximal matching, retaining every unmatched observation.

    For pure callbacks, no incompatible pair remains among final unmatched
    observations. This is not maximum matching. A bucket may require quadratic
    callback work; arbitrary semantic separation cannot be replaced by label
    equality or interpreted inside a numerical kernel.
    """
    pending: dict[Hashable, list[int]] = {}
    pairs: list[tuple[int, int]] = []
    for i, (_, label) in enumerate(cases):
        bucket = pending.setdefault(keys[i], [])
        position = next((p for p, j in enumerate(bucket)
                         if separates(cases[j][1], label)), None)
        if position is None:
            bucket.append(i)
        else:
            j = bucket.pop(position)
            pairs.append((j, i))
            if not bucket:
                del pending[keys[i]]
    return pairs


class FeasibilityScreen:
    """Spend a separate false-discard budget over this object's lifetime.

    A good fixed deterministic predictor is discarded with probability at
    most ``confidence`` over any finite number of calls, under the module's
    assumptions. The default counter is in memory; resetting it starts a new
    budget. ``CertifiedAcquirer`` with history supplies durable indices instead.
    Calls must be serialized, as with CertifiedAcquirer.
    Prefixes that pass are reusable as training data, but never as the fresh
    final certification cases. The key and separation callbacks must be pure.
    """

    def __init__(self, *, cases: int, confidence: float,
                 key: Callable[[Any], Hashable],
                 separates: Callable[[Any, Any], bool]) -> None:
        if isinstance(cases, bool) or not isinstance(cases, int) or cases < 2:
            raise ValueError("screening needs at least two cases")
        if not 0 < confidence < 1:
            raise ValueError("screen confidence must be between zero and one")
        self.cases, self.confidence = cases, Fraction(confidence)
        self.key, self.separates = key, separates
        self.decisions = self.rejections = 0
        self.last: ScreenResult | None = None

    def reject(self, cases: Sequence[tuple[Any, Any]], tolerance: float, *,
               index: int | None = None) -> bool:
        """Check a fixed-size fresh prefix; incomplete draws must not be tested.

        The caller chooses its size before observing it, at most ``cases``.
        Pair selection may depend on labels: disjointness gives a pathwise
        lower bound on *any* compatible predictor's errors, so no independence
        assumption about the selected pairs is made.

        An external ``index`` must come from a durable, non-reused reservation
        committed before drawing these cases; it can skip unused levels.
        """
        n = len(cases)
        if not 2 <= n <= self.cases or not 0 < tolerance < 1:
            raise ValueError("invalid screen size or tolerance")
        index = self.decisions if index is None else index
        if isinstance(index, bool) or not isinstance(index, int) or index < self.decisions:
            raise ValueError("screen decision indices must increase without reuse")
        level = self.confidence / ((index + 1) * (index + 2))
        self.decisions = index + 1
        epsilon = Fraction(tolerance)
        threshold = next((r for r in range(1, n // 2 + 1)
                          if math.comb(n, r) * epsilon ** r <= level), None)
        keys = [self.key(value) for value, _ in cases]
        pairs = _disjoint_pairs(cases, keys, self.separates)
        # Runtime certificate check: endpoints are distinct and each pair
        # really witnesses an incompatible target for an identical input.
        used: set[int] = set()
        for a, b in pairs:
            if a in used or b in used or a == b or keys[a] != keys[b] \
                    or not self.separates(cases[a][1], cases[b][1]):
                raise ValueError("invalid contradiction certificate")
            used.update((a, b))
        self.last = ScreenResult(n, tuple(pairs), threshold, level)
        self.rejections += self.last.rejected
        return self.last.rejected
