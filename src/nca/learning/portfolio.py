"""Choose among supplied learners on training examples alone.

Each learner fits a training part and is scored on a separate selection part of
the same examples; the best is refitted on all of them. The result is one
frozen candidate for a caller's fresh-case gate. Selection reads no fresh case,
so it spends no gate confidence, and its score is not evidence of correctness.
"""

from collections.abc import Callable, Hashable, Sequence
from dataclasses import dataclass, field
from typing import Any

from nca.abi import Contract, Module
from nca.effects import invoke_scoped
from nca.runtime import UnresolvedRequest

Learner = Callable[[Contract, Sequence[Hashable], Sequence[Hashable]], Module | None]
FAILURES = (UnresolvedRequest, ValueError, TypeError, ArithmeticError, IndexError, KeyError,
            AttributeError, RecursionError)


def _scored(module: Module, contract: Contract, keys: Sequence[Any], labels: Sequence[Any],
            agree: Callable[[Any, Any], bool]) -> int:
    correct = 0
    for key, label in zip(keys, labels, strict=True):
        try:
            value = invoke_scoped(module, key) if len(contract.inputs) == 1 else invoke_scoped(module, *key)
            correct += bool(agree(value, label))
        except FAILURES:
            continue
    return correct


@dataclass
class Portfolio:
    """A fitter over named learners; every fifth example forms the selection part.

    A learner that refuses or raises a declared failure is skipped; a refusal
    on a selection case scores zero for that case. Resource exhaustion
    propagates. Earlier learners win ties. ``last`` records selection scores.
    """

    learners: Sequence[tuple[str, Learner]]
    agree: Callable[[Any, Any], bool] = lambda left, right: bool(left == right)
    last: dict[str, int] = field(default_factory=dict)
    chosen: str | None = None

    def __post_init__(self) -> None:
        if not self.learners or len({name for name, _ in self.learners}) != len(self.learners):
            raise ValueError("learners need distinct names")

    def __call__(self, contract: Contract, keys: Sequence[Hashable], labels: Sequence[Hashable]) -> Module | None:
        if len(keys) != len(labels):
            raise ValueError("keys and labels must correspond")
        self.last, self.chosen = {}, None
        fit_keys = [key for index, key in enumerate(keys) if index % 5]
        fit_labels = [label for index, label in enumerate(labels) if index % 5]
        for name, learner in self.learners:
            try:
                module = learner(contract, fit_keys, fit_labels)
            except FAILURES:
                continue
            if module is not None:
                self.last[name] = _scored(module, contract, keys[::5], labels[::5], self.agree)
        ranked = [name for name, _ in self.learners if self.last.get(name, 0) > 0]
        if not ranked:
            return None
        best = max(ranked, key=lambda name: self.last[name])
        self.chosen = best
        try:
            return dict(self.learners)[best](contract, keys, labels)
        except FAILURES:
            return None
