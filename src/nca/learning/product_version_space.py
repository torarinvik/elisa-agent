"""Explicit Cartesian-product version spaces over independent predictors."""

from __future__ import annotations

from collections.abc import Callable, Iterator, Sequence
from math import prod
from operator import index as integer_index
from typing import Generic, TypeVar, overload

from nca.runtime import UnresolvedRequest

X = TypeVar("X")
Y = TypeVar("Y")


class _JointHypotheses(Sequence[Callable[[X], tuple[Y, ...]]], Generic[X, Y]):
    """A lazy compatibility view, including lazy slices."""

    def __init__(self, factors: tuple[tuple[Callable[[X], Y], ...], ...],
                 indices: range | None = None) -> None:
        self._factors = factors
        self._indices = range(prod(map(len, factors))) if indices is None else indices

    def __len__(self) -> int:
        return len(self._indices)

    @overload
    def __getitem__(self, index: int) -> Callable[[X], tuple[Y, ...]]: ...

    @overload
    def __getitem__(self, index: slice) -> _JointHypotheses[X, Y]: ...

    def __getitem__(self, index: int | slice) -> Callable[[X], tuple[Y, ...]] | _JointHypotheses[X, Y]:
        if isinstance(index, slice):
            return _JointHypotheses(self._factors, self._indices[index])
        return self._at(self._indices[integer_index(index)])

    def _at(self, position: int) -> Callable[[X], tuple[Y, ...]]:
        choices = []
        for factor in reversed(self._factors):
            position, offset = divmod(position, len(factor))
            choices.append(factor[offset])
        selected = tuple(reversed(choices))
        return lambda inputs: tuple(predict(inputs) for predict in selected)

    def __iter__(self) -> Iterator[Callable[[X], tuple[Y, ...]]]:
        for position in self._indices:
            yield self._at(position)


class ProductVersionSpace(Generic[X, Y]):
    """Factor a declared full product of pure, total component predictors.

    Outputs are host tuples, with no NCA value type implied. Equality must be
    faithful and component tuples must preserve distinctions. Predictors and
    their execution semantics must remain fixed. The logical joint-family cap
    is checked before fitting; counters count component predictor evaluations.
    This proposal mechanism does not certify its representation or predictions.
    """

    def __init__(self, factors: Sequence[Sequence[Callable[[X], Y]]],
                 observations: Sequence[tuple[X, tuple[Y, ...]]], *, max_candidates: int) -> None:
        if type(max_candidates) is not int or max_candidates < 1:
            raise ValueError("candidate limit must be positive")
        declared = tuple(tuple(factor) for factor in factors)
        if any(not factor for factor in declared) or prod(map(len, declared)) > max_candidates:
            raise ValueError("a complete bounded product family is required")
        if not observations or any(type(label) is not tuple or len(label) != len(declared)
                                   for _, label in observations):
            raise ValueError("nonempty observations must match the product output arity")
        retained = []
        self.fit_evaluations = 0
        for index, factor in enumerate(declared):
            choices = []
            for predict in factor:
                for inputs, expected in observations:
                    self.fit_evaluations += 1
                    try:
                        actual = predict(inputs)
                    except UnresolvedRequest:
                        break
                    if actual != expected[index]:
                        break
                else:
                    choices.append(predict)
            if not choices:
                raise ValueError("no hypothesis is consistent with the observations")
            retained.append(tuple(choices))
        self.factors = tuple(retained)
        self.hypotheses = _JointHypotheses(self.factors)
        self.prediction_evaluations = 0

    @property
    def hypothesis_count(self) -> int:
        """Exact retained joint count without materializing joint predictors."""
        return prod(map(len, self.factors))

    @property
    def component_count(self) -> int:
        """Number of physically retained component choices."""
        return sum(map(len, self.factors))

    def predict(self, inputs: X) -> tuple[Y, ...]:
        result = []
        for factor in self.factors:
            self.prediction_evaluations += 1
            answer = factor[0](inputs)
            for predict in factor[1:]:
                self.prediction_evaluations += 1
                if predict(inputs) != answer:
                    raise UnresolvedRequest("consistent hypotheses disagree")
            result.append(answer)
        return tuple(result)

    def refine(self, observations: Sequence[tuple[X, tuple[Y, ...]]]) -> "ProductVersionSpace[X, Y]":
        """Return a filtered product, leaving the existing model unchanged."""
        return ProductVersionSpace(self.factors, observations, max_candidates=self.hypothesis_count)

    def choose_disagreement(self, inputs: Sequence[X], *, max_inputs: int) -> int | None:
        """Rank supplied inputs by the exact largest joint outcome partition."""
        if type(max_inputs) is not int or max_inputs < 1 or len(inputs) > max_inputs:
            raise ValueError("input enumeration exceeds its positive bound")
        best = None
        best_largest = self.hypothesis_count
        for position, item in enumerate(inputs):
            maxima = []
            for factor in self.factors:
                groups: list[tuple[Y, int]] = []
                for predict in factor:
                    self.prediction_evaluations += 1
                    answer = predict(item)
                    for index, (value, count) in enumerate(groups):
                        if value == answer:
                            groups[index] = (value, count + 1)
                            break
                    else:
                        groups.append((answer, 1))
                maxima.append(max(count for _, count in groups))
            largest = prod(maxima)
            if largest < best_largest:
                best, best_largest = position, largest
        return best
