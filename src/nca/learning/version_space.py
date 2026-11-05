"""Finite realizable learning with refusal on hypothesis disagreement."""

from collections.abc import Callable, Sequence
from typing import Generic, TypeVar

from nca.runtime import UnresolvedRequest

X = TypeVar("X")
Y = TypeVar("Y")


class VersionSpace(Generic[X, Y]):
    """Keep every supplied predictor consistent with observed final answers.

    Sound generalization requires correct observations and a true predictor in
    the complete supplied family. Predictors must remain unchanged and equality
    must faithfully compare outputs. This is not a statistical certificate.
    Callbacks own their execution bounds; a budget exception aborts fitting,
    rather than silently removing a possibly true hypothesis.
    """

    def __init__(self, hypotheses: Sequence[Callable[[X], Y]], observations: Sequence[tuple[X, Y]],
                 *, max_candidates: int) -> None:
        if type(max_candidates) is not int or max_candidates < 1:
            raise ValueError("candidate limit must be positive")
        if not hypotheses or len(hypotheses) > max_candidates or not observations:
            raise ValueError("a complete bounded family and nonempty observations are required")
        retained = []
        self.fit_evaluations = 0
        for predict in hypotheses:
            for inputs, expected in observations:
                self.fit_evaluations += 1
                try:
                    actual = predict(inputs)
                except UnresolvedRequest:
                    break
                if actual != expected:
                    break
            else:
                retained.append(predict)
        if not retained:
            raise ValueError("no hypothesis is consistent with the observations")
        self.hypotheses = tuple(retained)
        self.prediction_evaluations = 0

    def predict(self, inputs: X) -> Y:
        self.prediction_evaluations += 1
        answer = self.hypotheses[0](inputs)
        for predict in self.hypotheses[1:]:
            self.prediction_evaluations += 1
            if predict(inputs) != answer:
                raise UnresolvedRequest("consistent hypotheses disagree")
        return answer
