"""Supervised oblique intermediate interfaces from vector observations (§36.20)."""

import math
from collections.abc import Callable, Hashable, Sequence
from dataclasses import replace
from itertools import combinations
from typing import Any

from nca.abi import Module
from nca.discovery import Proposal
from nca.numeric_learning import propose_partition
from nca.objects import Constructor, canonical
from nca.vector_learning import _vector


class ProjectionEncoder:
    """A supplied measurement followed by a learned finite linear projection."""

    def __init__(self, measurement: Module, direction: tuple[float, ...], cost: float) -> None:
        self.measurement, self.direction = measurement, _vector(direction)
        if not math.isfinite(cost) or cost < 0:
            raise ValueError("projection cost must be finite and nonnegative")
        self.constructor = Constructor("learned-vector-projection", "1", 0,
            canonical({"source": measurement.manifest.contract.output,
                       "direction": direction, "meaning": "dot product with direction"}).decode())
        self.manifest = replace(measurement.manifest,
            module_id=f"{measurement.manifest.module_id}/projection/{self.constructor.ref}",
            contract=replace(measurement.manifest.contract, output=self.constructor.type()),
            cost=measurement.manifest.cost + cost)

    def invoke(self, *inputs: Any) -> float:
        value = _vector(self.measurement.invoke(*inputs))
        if len(value) != len(self.direction):
            raise ValueError("projection input dimension differs from training")
        result = math.fsum(a * b for a, b in zip(value, self.direction, strict=True))
        if not math.isfinite(result):
            raise ValueError("projection exceeds finite range")
        return result


def propose_projections(incumbent: Module, measurement: Module,
                        rows: Sequence[tuple[Any, ...]], labels: Sequence[Hashable], *,
                        limit: int, projection_cost: float, encoding_cost: float,
                        decoder_cost: float,
                        place_boundary: Callable[[float, float], float] | None = None) -> list[Proposal]:
    """Fit centroid-difference projections and threshold heads on training rows only.

    Target order determines budgeted pair order. No direction is proposed for
    equal centroids. Stable observations/models and independent selection are
    required. This family can miss nonlinear distinctions entirely.
    """
    if type(limit) is not int or limit < 1:
        raise ValueError("projection limit must be a positive integer")
    if len(rows) < 2 or len(rows) != len(labels):
        raise ValueError("projection fitting needs aligned observations")
    contract = incumbent.manifest.contract
    if replace(measurement.manifest.contract, output=contract.output) != contract:
        raise ValueError("measurement must preserve inputs, slots and relevance")
    if any(len(row) != len(contract.inputs) + len(contract.slots) for row in rows):
        raise ValueError("training row arity differs from contract")
    if any(not math.isfinite(c) or c < 0
           for c in (projection_cost, encoding_cost, decoder_cost)):
        raise ValueError("costs must be finite and nonnegative")
    groups: dict[Hashable, list[tuple[float, ...]]] = {}
    dimension = None
    for row, label in zip(rows, labels, strict=True):
        value = _vector(measurement.invoke(*row))
        if dimension is not None and len(value) != dimension:
            raise ValueError("inconsistent vector dimensions")
        dimension = len(value)
        groups.setdefault(label, []).append(value)
    centroids = [tuple(math.fsum(x[i] / len(group) for x in group)
                       for i in range(dimension or 0)) for group in groups.values()]
    proposals = []
    for index, (a, b) in enumerate(combinations(centroids, 2)):
        if index >= limit:
            break
        direction = _vector(tuple(y - x for x, y in zip(a, b, strict=True)))
        if not any(direction):
            continue
        projection = ProjectionEncoder(measurement, direction, projection_cost)
        for proposal in propose_partition(incumbent, projection, rows, labels,
                                         encoding_cost=encoding_cost, decoder_cost=decoder_cost,
                                         place_boundary=place_boundary):
            proposals.append(replace(proposal,
                                    constructors=(projection.constructor,) + proposal.constructors))
    return proposals


class PolynomialEncoder:
    """Resource-bounded nonconstant monomials, with an explicit generated interface."""

    def __init__(self, measurement: Module, dimension: int, degree: int, *,
                 max_terms: int, cost: float) -> None:
        from itertools import combinations_with_replacement

        if (type(dimension) is not int or dimension < 0 or type(degree) is not int
                or degree < 1 or type(max_terms) is not int or max_terms < 1):
            raise ValueError("invalid polynomial dimensions, degree or term budget")
        if not math.isfinite(cost) or cost < 0:
            raise ValueError("polynomial cost must be finite and nonnegative")
        if math.comb(dimension + degree, degree) - 1 > max_terms:
            raise ValueError("polynomial term budget exceeded")
        self.measurement, self.dimension, self.degree = measurement, dimension, degree
        self.terms = tuple(term for power in (range(1, degree + 1) if dimension else ())
                           for term in combinations_with_replacement(range(dimension), power))
        self.constructor = Constructor("polynomial-lift", "1", 0,
            canonical({"source": measurement.manifest.contract.output,
                       "dimension": dimension, "degree": degree,
                       "meaning": "nonconstant monomials by degree then coordinate index"}).decode())
        self.manifest = replace(measurement.manifest,
            module_id=f"{measurement.manifest.module_id}/polynomial/{self.constructor.ref}",
            contract=replace(measurement.manifest.contract, output=self.constructor.type()),
            cost=measurement.manifest.cost + cost)

    def invoke(self, *inputs: Any) -> tuple[float, ...]:
        value = _vector(self.measurement.invoke(*inputs))
        if len(value) != self.dimension:
            raise ValueError("polynomial input dimension differs from training")
        return _vector(tuple(math.prod(value[i] for i in term) for term in self.terms))


def propose_polynomial_partitions(incumbent: Module, measurement: Module,
                                  rows: Sequence[tuple[Any, ...]], labels: Sequence[Hashable], *,
                                  degrees: Sequence[int], max_terms: int, limit: int,
                                  lifting_cost: float, projection_cost: float,
                                  encoding_cost: float, decoder_cost: float,
                                  place_boundary: Callable[[float, float], float] | None = None
                                  ) -> list[Proposal]:
    """Propose polynomial decompositions using training observations only (§36.21).

    Caller-selected degrees define the search family; each degree gets at most
    limit centroid pairs. Over-budget lifts fail explicitly, without truncating
    their basis. Invoke inside independent discovery's training callback.
    """
    contract = incumbent.manifest.contract
    if replace(measurement.manifest.contract, output=contract.output) != contract:
        raise ValueError("measurement must preserve inputs, slots and relevance")
    if len(rows) < 2 or len(rows) != len(labels):
        raise ValueError("polynomial fitting needs aligned observations")
    if any(len(row) != len(contract.inputs) + len(contract.slots) for row in rows):
        raise ValueError("training row arity differs from contract")
    dimension = len(_vector(measurement.invoke(*rows[0])))
    proposals = []
    for degree in degrees:
        lift = PolynomialEncoder(measurement, dimension, degree,
                                 max_terms=max_terms, cost=lifting_cost)
        for proposal in propose_projections(incumbent, lift, rows, labels, limit=limit,
                projection_cost=projection_cost, encoding_cost=encoding_cost,
                decoder_cost=decoder_cost, place_boundary=place_boundary):
            proposals.append(replace(proposal,
                                    constructors=(lift.constructor,) + proposal.constructors))
    return proposals
