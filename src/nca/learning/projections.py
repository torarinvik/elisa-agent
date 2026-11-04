"""Supervised oblique intermediate interfaces from vector observations (§36.20)."""

import math
from array import array
from collections import Counter
from collections.abc import Callable, Hashable, Mapping, Sequence
from dataclasses import replace
from heapq import heappop, heappush
from itertools import combinations
from typing import Any

import numpy as np

from nca.abi import Module
from nca.effects import invoke_scoped
from nca.learning.discovery import Proposal
from nca.native import load
from nca.learning.numeric import _observation, _partition_from_ordered, propose_partition
from nca.objects import Constructor, canonical
from nca.learning.vector import _vector


_NATIVE = load("polynomial")
_PROTOTYPE_NATIVE = load("prototypes")


def _polynomial_reference(value: tuple[float, ...],
                          terms: tuple[tuple[int, ...], ...]) -> tuple[float, ...]:
    return tuple(math.prod(value[i] for i in term) for term in terms)


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
        value = _vector(invoke_scoped(self.measurement, *inputs))
        if len(value) != len(self.direction):
            raise ValueError("projection input dimension differs from training")
        return self.project(value)

    def project(self, value: tuple[float, ...]) -> float:
        """Project an already validated immutable training observation."""
        result = math.fsum(a * b for a, b in zip(value, self.direction, strict=True))
        if not math.isfinite(result):
            raise ValueError("projection exceeds finite range")
        return result


def _fit_projections(measurement: Module, rows: Sequence[tuple[Any, ...]],
                     labels: Sequence[Hashable], limit: int, cost: float,
                     reuse_observations: bool
                     ) -> tuple[list[ProjectionEncoder], list[tuple[tuple[float, ...], Hashable]]]:
    if type(limit) is not int or limit < 1:
        raise ValueError("projection limit must be a positive integer")
    if len(rows) < 2 or len(rows) != len(labels):
        raise ValueError("projection fitting needs aligned observations")
    contract = measurement.manifest.contract
    if any(len(row) != len(contract.inputs) + len(contract.slots) for row in rows):
        raise ValueError("training row arity differs from contract")
    if not math.isfinite(cost) or cost < 0:
        raise ValueError("costs must be finite and nonnegative")
    if reuse_observations and (measurement.manifest.effects != frozenset() or contract.slots):
        raise ValueError("observation reuse requires known empty effects and no slots")
    centroids, observations = _centroid_training(measurement, rows, labels, reuse_observations)
    projections = []
    for index, (a, b) in enumerate(combinations(centroids, 2)):
        if index >= limit:
            break
        direction = _vector(tuple(y - x for x, y in zip(a, b, strict=True)))
        if any(direction):
            projections.append(ProjectionEncoder(measurement, direction, cost))
    return projections, observations


def _centroid_training(measurement: Module, rows: Sequence[tuple[Any, ...]],
                       labels: Sequence[Hashable], reuse_observations: bool,
                       max_groups: int | None = None,
                       centers_per_group: int | Mapping[Hashable, int] = 1,
                       refinement_steps: int = 0
                       ) -> tuple[tuple[tuple[float, ...], ...], list[tuple[tuple[float, ...], Hashable]]]:
    if len(rows) < 2 or len(rows) != len(labels):
        raise ValueError("centroid fitting needs aligned observations")
    contract = measurement.manifest.contract
    if any(len(row) != len(contract.inputs) + len(contract.slots) for row in rows):
        raise ValueError("training row arity differs from contract")
    observations = []
    groups: dict[Hashable, list[tuple[float, ...]]] = {}
    dimension = None
    for row, label in zip(rows, labels, strict=True):
        value = _vector(invoke_scoped(measurement, *row))
        if dimension is not None and len(value) != dimension:
            raise ValueError("inconsistent vector dimensions")
        dimension = len(value)
        if reuse_observations:
            observations.append((value, label))
        if label not in groups and max_groups is not None and len(groups) >= max_groups:
            raise ValueError("centroid group budget exceeded")
        groups.setdefault(label, []).append(value)
    centroids = []
    for label, group in groups.items():
        limit = (centers_per_group if isinstance(centers_per_group, int)
                 else centers_per_group[label])
        fitted = _group_centers(group, limit, refinement_steps)
        if max_groups is not None and len(centroids) + len(fitted) > max_groups:
            raise ValueError("total centroid budget exceeded")
        centroids.extend(fitted)
    return tuple(centroids), observations


def _prototype_distances(value: tuple[float, ...],
                         centers: Sequence[tuple[float, ...]]) -> tuple[float, ...]:
    distances = tuple(math.dist(value, center) for center in centers)
    if any(not math.isfinite(distance) for distance in distances):
        raise ValueError("prototype distances exceed finite range")
    return distances


def _group_centers(group: Sequence[tuple[float, ...]], limit: int,
                   steps: int) -> tuple[tuple[float, ...], ...]:
    def mean(points: Sequence[tuple[float, ...]]) -> tuple[float, ...]:
        return _vector(tuple(math.fsum(x[i] / len(points) for x in points)
                             for i in range(len(points[0]))))

    if limit == 1:
        return (mean(group),)
    centers = [group[0]]
    while len(centers) < limit:
        distances = [min(_prototype_distances(value, centers)) for value in group]
        index = max(range(len(group)), key=lambda i: distances[i])
        if distances[index] == 0:
            break
        centers.append(group[index])
    for _ in range(steps):
        assigned: list[list[tuple[float, ...]]] = [[] for _ in centers]
        for value in group:
            distances = _prototype_distances(value, centers)
            assigned[min(range(len(centers)), key=lambda i: distances[i])].append(value)
        updated = [mean(points) if points else center
                   for points, center in zip(assigned, centers, strict=True)]
        if updated == centers:
            break
        centers = updated
    return tuple(centers)


class PrototypeEncoder:
    """A typed nearest-prototype interface fitted from vector observations."""

    def __init__(self, measurement: Module, centers: tuple[tuple[float, ...], ...],
                 cost: float) -> None:
        centers = tuple(_vector(center) for center in centers)
        if not centers or any(len(c) != len(centers[0]) for c in centers):
            raise ValueError("prototype centers must be nonempty with consistent dimensions")
        if not math.isfinite(cost) or cost < 0:
            raise ValueError("prototype cost must be finite and nonnegative")
        self.measurement, self.centers = measurement, centers
        self._packed_centers = array("d", (x for center in centers for x in center))
        self.constructor = Constructor("learned-prototype-partition", "1", 0,
            canonical({"source": measurement.manifest.contract.output, "centers": centers,
                       "meaning": "nearest Euclidean center; first center breaks ties"}).decode())
        self.manifest = replace(measurement.manifest,
            module_id=f"{measurement.manifest.module_id}/prototypes/{self.constructor.ref}",
            contract=replace(measurement.manifest.contract, output=self.constructor.type()),
            cost=measurement.manifest.cost + cost)

    def invoke(self, *inputs: Any) -> int:
        value = _vector(invoke_scoped(self.measurement, *inputs))
        if len(value) != len(self.centers[0]):
            raise ValueError("prototype input dimension differs from training")
        if _PROTOTYPE_NATIVE is not None:
            selected = _PROTOTYPE_NATIVE.nearest(array("d", value), self._packed_centers)
            if selected >= 0:
                if selected >= len(self.centers):
                    raise RuntimeError("native prototype evaluator returned an invalid center")
                return selected
        distances = _prototype_distances(value, self.centers)
        return min(range(len(distances)), key=lambda i: distances[i])


def fit_prototype_encoder(measurement: Module, rows: Sequence[tuple[Any, ...]],
                          labels: Sequence[Hashable], *, max_centroids: int,
                          encoding_cost: float, centers_per_category: int = 1,
                          refinement_steps: int = 3) -> PrototypeEncoder:
    """Learn a reusable vector partition from opaque categories (§36.49).

    Group order follows category occurrence; labels are not retained. Equal
    centroids share a code. A group budget fails explicitly instead of dropping
    categories. Stable observations and independent whole-task selection are
    required; centroid geometry need not separate arbitrary categories.
    Opt-in multiple centers (§36.50) use first-observation/farthest-first seeds
    and bounded within-category Lloyd steps, keeping empty-cluster centers.
    The total budget rejects overflow rather than dropping fitted modes.
    Initialization and ties follow observation order; no global optimum is claimed.
    """
    if any(type(n) is not int or n < 1 for n in (max_centroids, centers_per_category)):
        raise ValueError("centroid budgets must be positive integers")
    if type(refinement_steps) is not int or refinement_steps < 0:
        raise ValueError("refinement steps must be a nonnegative integer")
    if centers_per_category > max_centroids:
        raise ValueError("per-category budget exceeds total centroid budget")
    if not math.isfinite(encoding_cost) or encoding_cost < 0:
        raise ValueError("prototype cost must be finite and nonnegative")
    centers, _ = _centroid_training(measurement, rows, labels, False, max_centroids,
                                     centers_per_category, refinement_steps)
    return PrototypeEncoder(measurement, tuple(dict.fromkeys(centers)), encoding_cost)


def fit_projection_encoders(measurement: Module, rows: Sequence[tuple[Any, ...]],
                            labels: Sequence[Hashable], *, limit: int,
                            projection_cost: float) -> list[ProjectionEncoder]:
    """Learn scalar measurements from opaque auxiliary categories (§36.38).

    Labels need not be the task's output type. Fit on training rows only, then
    use the projections in routing or another independent acquisition step.
    Pair order follows first label occurrence; limit bounds considered pairs,
    including equal-centroid pairs which emit no direction. Stable observations
    are assumed. Each encoder exposes its generated constructor; callers must
    propagate it when retaining a decomposition. No labels or samples are kept
    in the inference object, and nonlinear distinctions may be missed entirely.
    """
    projections, _ = _fit_projections(measurement, rows, labels, limit, projection_cost, False)
    return projections


def fit_regression_projection(measurement: Module, rows: Sequence[tuple[Any, ...]],
                              feedback: Sequence[float], *,
                              projection_cost: float) -> ProjectionEncoder | None:
    """Fit a scalar measurement from continuous training feedback (§36.41).

    Center observations/feedback and solve least squares with minimum-norm
    handling of rank deficiency. Only the direction is retained; a subsequent
    head can fit an offset. Return no measurement for an exactly zero direction.
    Stable finite observations are required; floating-point conditioning and
    generalization are not proved. No task output type is assigned to feedback.
    """
    if len(rows) < 2 or len(rows) != len(feedback):
        raise ValueError("regression projection needs aligned observations")
    contract = measurement.manifest.contract
    if any(len(row) != len(contract.inputs) + len(contract.slots) for row in rows):
        raise ValueError("training row arity differs from contract")
    if not math.isfinite(projection_cost) or projection_cost < 0:
        raise ValueError("projection cost must be finite and nonnegative")
    targets = tuple(map(_observation, feedback))
    values = tuple(_vector(invoke_scoped(measurement, *row)) for row in rows)
    direction = _regression_direction(values, targets)
    return ProjectionEncoder(measurement, direction, projection_cost) if any(direction) else None


def _regression_direction(values: Sequence[tuple[float, ...]],
                          targets: Sequence[float]) -> tuple[float, ...]:
    """Fit already validated, aligned finite training snapshots."""
    if any(len(value) != len(values[0]) for value in values):
        raise ValueError("inconsistent vector dimensions")
    n = len(values)
    means = tuple(math.fsum(value[i] / n for value in values) for i in range(len(values[0])))
    mean_target = math.fsum(target / n for target in targets)
    design = np.asarray([_vector(tuple(x - m for x, m in zip(value, means, strict=True)))
                         for value in values])
    response = np.asarray([_observation(target - mean_target) for target in targets])
    try:
        return _vector(tuple(np.linalg.lstsq(design, response, rcond=None)[0].tolist()))
    except np.linalg.LinAlgError as error:
        raise ValueError("projection least-squares solver failed") from error


def propose_projections(incumbent: Module, measurement: Module,
                        rows: Sequence[tuple[Any, ...]], labels: Sequence[Hashable], *,
                        limit: int, projection_cost: float, encoding_cost: float,
                        decoder_cost: float,
                        place_boundary: Callable[[float, float], float] | None = None,
                        reuse_observations: bool = False) -> list[Proposal]:
    """Fit centroid-difference projections and threshold heads on training rows only.

    Target order determines budgeted pair order. No direction is proposed for
    equal centroids. Stable observations/models and independent selection are
    required. This family can miss nonlinear distinctions entirely. Opt-in reuse
    additionally asserts determinism, requires known empty effects and no slots,
    and never retains training snapshots in the proposed inference route.
    """
    contract = incumbent.manifest.contract
    if replace(measurement.manifest.contract, output=contract.output) != contract:
        raise ValueError("measurement must preserve inputs, slots and relevance")
    if any(not math.isfinite(c) or c < 0 for c in (encoding_cost, decoder_cost)):
        raise ValueError("costs must be finite and nonnegative")
    projections, observations = _fit_projections(measurement, rows, labels, limit,
                                                 projection_cost, reuse_observations)
    proposals = []
    for projection in projections:
        if reuse_observations:
            ordered = sorted(((projection.project(value), label) for value, label in observations),
                             key=lambda item: item[0])
            fitted = _partition_from_ordered(incumbent, projection, ordered, encoding_cost,
                                             decoder_cost, place_boundary)
        else:
            fitted = propose_partition(incumbent, projection, rows, labels,
                                       encoding_cost=encoding_cost, decoder_cost=decoder_cost,
                                       place_boundary=place_boundary)
        for proposal in fitted:
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
        self._offsets, self._indices = array("q", [0]), array("q")
        for term in self.terms:
            self._indices.extend(term)
            self._offsets.append(len(self._indices))
        self.constructor = Constructor("polynomial-lift", "1", 0,
            canonical({"source": measurement.manifest.contract.output,
                       "dimension": dimension, "degree": degree,
                       "meaning": "nonconstant monomials by degree then coordinate index"}).decode())
        self.manifest = replace(measurement.manifest,
            module_id=f"{measurement.manifest.module_id}/polynomial/{self.constructor.ref}",
            contract=replace(measurement.manifest.contract, output=self.constructor.type()),
            cost=measurement.manifest.cost + cost)

    def invoke(self, *inputs: Any) -> tuple[float, ...]:
        return self.encode(invoke_scoped(self.measurement, *inputs))

    def encode(self, value: tuple[float, ...]) -> tuple[float, ...]:
        """Evaluate a training snapshot using the same validated polynomial path."""
        value = _vector(value)
        if len(value) != self.dimension:
            raise ValueError("polynomial input dimension differs from training")
        if _NATIVE is None:
            result = _polynomial_reference(value, self.terms)
        else:
            result = tuple(_NATIVE.monomials(array("d", value), self._offsets, self._indices))
            if len(result) != len(self.terms):
                raise RuntimeError("native polynomial evaluator returned an invalid term count")
        return _vector(result)


def propose_polynomial_partitions(incumbent: Module, measurement: Module,
                                  rows: Sequence[tuple[Any, ...]], labels: Sequence[Hashable], *,
                                  degrees: Sequence[int], max_terms: int, limit: int,
                                  lifting_cost: float, projection_cost: float,
                                  encoding_cost: float, decoder_cost: float,
                                  place_boundary: Callable[[float, float], float] | None = None,
                                  reuse_observations: bool = False) -> list[Proposal]:
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
    if reuse_observations and (measurement.manifest.effects != frozenset()
                               or measurement.manifest.contract.slots):
        raise ValueError("observation reuse requires known empty effects and no slots")
    dimension = len(_vector(invoke_scoped(measurement, *rows[0])))
    proposals = []
    for degree in degrees:
        lift = PolynomialEncoder(measurement, dimension, degree,
                                 max_terms=max_terms, cost=lifting_cost)
        for proposal in propose_projections(incumbent, lift, rows, labels, limit=limit,
                projection_cost=projection_cost, encoding_cost=encoding_cost,
                decoder_cost=decoder_cost, place_boundary=place_boundary,
                reuse_observations=reuse_observations):
            proposals.append(replace(proposal,
                                    constructors=(lift.constructor,) + proposal.constructors))
    return proposals


def fit_polynomial_regression_features(measurement: Module,
        rows: Sequence[tuple[Any, ...]], feedback: Sequence[float], *, max_degree: int,
        max_terms: int, max_error: float, lifting_cost: float,
        projection_cost: float, reuse_observations: bool = False) -> list[Proposal]:
    """Grow polynomial representations while training residuals remain (§36.42).

    Fit a centered regression projection at each complete degree, retaining its
    generated lift/projection declarations. Stop after the first fitted projection
    whose affine-offset residual meets max_error, or before a degree/term limit.
    The offset is used only for training stopping; fit an actual head separately.
    No basis is partially truncated. Limits bound represented families, not all
    runtime/memory use. Constant/zero directions emit no feature and search may
    continue. Use independent whole-task selection after head acquisition; this
    training stop can miss features that generalize better at higher degrees.
    Stable measurements and finite floating-point arithmetic remain assumptions.
    Opt-in reuse asserts determinism and requires known empty effects and no
    slots (§36.43). It observes each row once and retains snapshots only for this
    training call, trading temporary memory for fewer repeated evaluations.
    """
    if any(type(n) is not int or n < 1 for n in (max_degree, max_terms)):
        raise ValueError("degree and term budgets must be positive integers")
    if any(not math.isfinite(c) or c < 0 for c in (max_error, lifting_cost, projection_cost)):
        raise ValueError("error tolerance and costs must be finite and nonnegative")
    if len(rows) < 2 or len(rows) != len(feedback):
        raise ValueError("polynomial regression needs aligned observations")
    contract = measurement.manifest.contract
    if any(len(row) != len(contract.inputs) + len(contract.slots) for row in rows):
        raise ValueError("training row arity differs from contract")
    if reuse_observations and (measurement.manifest.effects != frozenset() or contract.slots):
        raise ValueError("observation reuse requires known empty effects and no slots")
    targets = tuple(map(_observation, feedback))
    observations = (tuple(_vector(invoke_scoped(measurement, *row)) for row in rows)
                    if reuse_observations else ())
    dimension = len(observations[0] if reuse_observations
                    else _vector(invoke_scoped(measurement, *rows[0])))
    proposals = []
    for degree in range(1, max_degree + 1):
        if math.comb(dimension + degree, degree) - 1 > max_terms:
            break
        lift = PolynomialEncoder(measurement, dimension, degree,
                                 max_terms=max_terms, cost=lifting_cost)
        if reuse_observations:
            lifted = tuple(lift.encode(value) for value in observations)
            direction = _regression_direction(lifted, targets)
            projection = (ProjectionEncoder(lift, direction, projection_cost)
                          if any(direction) else None)
        else:
            projection = fit_regression_projection(lift, rows, targets,
                                                   projection_cost=projection_cost)
        if projection is None:
            continue
        proposals.append(Proposal(projection, (lift.constructor, projection.constructor)))
        predictions = (map(projection.project, lifted) if reuse_observations
                       else (invoke_scoped(projection, *row) for row in rows))
        residuals = tuple(_observation(target - prediction)
                          for target, prediction in zip(targets, predictions, strict=True))
        offset = math.fsum(residual / len(rows) for residual in residuals)
        if max(abs(_observation(residual - offset)) for residual in residuals) <= max_error:
            break
    return proposals


def fit_prototype_features(measurement: Module, rows: Sequence[tuple[Any, ...]],
        labels: Sequence[Hashable], *, max_per_category: int, max_centroids: int,
        max_errors: int, encoding_cost: float, refinement_steps: int = 3,
        allocate_by_errors: bool = False,
        max_allocation_trials: int | None = None) -> list[Proposal]:
    """Grow prototype interfaces until empirical categorical ambiguity is small (§36.52).

    By default fit allowances 1..max_per_category, scoring modal labels per code.
    Stop at the first candidate with at most max_errors training mistakes, or
    before the conservative complete allocation (categories * allowance) exceeds
    max_centroids. No category is omitted to fit a budget. Duplicate centers can
    make actual models smaller than this allocation bound. Every fitted candidate
    remains available to downstream head fitting and independent selection.
    Stable observations and hashable labels are assumed; neither monotonic score
    improvement nor useful generalization is guaranteed. Budgets limit represented
    families, not total runtime/memory. No training samples or labels are retained.
    Optional allocate_by_errors (§36.53) increments just the eligible category
    with the most remaining modal training errors, ties by first occurrence.
    It reserves the sum of per-category allowances and stops if no error-bearing
    category can grow. This local heuristic can miss indirect improvements from
    growing a category with no current errors; all candidates still need selection.
    Optional max_allocation_trials (§36.54) enables bounded alternative allocation
    search with allocate_by_errors. Children may grow currently correct categories;
    frontier order uses parent error count, then grown-category errors and stable
    insertion order. Each allocation is fitted once. The bound counts all fits,
    including identical resulting models; it does not guarantee optimal allocation.
    """
    if any(type(n) is not int or n < 1 for n in (max_per_category, max_centroids)):
        raise ValueError("prototype growth budgets must be positive integers")
    if any(type(n) is not int or n < 0 for n in (max_errors, refinement_steps)):
        raise ValueError("error and refinement budgets must be nonnegative integers")
    if max_allocation_trials is not None and (
            type(max_allocation_trials) is not int or max_allocation_trials < 1
            or not allocate_by_errors):
        raise ValueError("allocation trial budget must be positive and requires error allocation")
    if not math.isfinite(encoding_cost) or encoding_cost < 0:
        raise ValueError("prototype cost must be finite and nonnegative")
    if len(rows) < 2 or len(rows) != len(labels):
        raise ValueError("prototype growth needs aligned observations")
    contract = measurement.manifest.contract
    if any(len(row) != len(contract.inputs) + len(contract.slots) for row in rows):
        raise ValueError("training row arity differs from contract")
    allowances = dict.fromkeys(labels, 1)
    order = tuple(allowances)
    seen = {tuple(allowances.values())}
    frontier: list[tuple[int, int, int, tuple[int, ...]]] = []
    serial = 0
    proposals = []
    while max(allowances.values()) <= max_per_category and sum(allowances.values()) <= max_centroids:
        centers, _ = _centroid_training(measurement, rows, labels, False, max_centroids,
                                         allowances, refinement_steps)
        encoder = PrototypeEncoder(measurement, tuple(dict.fromkeys(centers)), encoding_cost)
        proposals.append(Proposal(encoder, (encoder.constructor,)))
        counts: dict[int, Counter[Hashable]] = {}
        codes = tuple(invoke_scoped(encoder, *row) for row in rows)
        for code, label in zip(codes, labels, strict=True):
            counts.setdefault(code, Counter())[label] += 1
        modes = {code: histogram.most_common(1)[0][0] for code, histogram in counts.items()}
        errors = Counter(label for code, label in zip(codes, labels, strict=True)
                         if modes[code] != label)
        if sum(errors.values()) <= max_errors or (max_allocation_trials is not None
                                                  and len(proposals) >= max_allocation_trials):
            break
        if max_allocation_trials is not None:
            if sum(allowances.values()) < max_centroids:
                for label in order:
                    if allowances[label] >= max_per_category:
                        continue
                    child = dict(allowances)
                    child[label] += 1
                    state = tuple(child.values())
                    if state not in seen:
                        seen.add(state)
                        serial += 1
                        heappush(frontier, (sum(errors.values()), -errors[label], serial, state))
            if not frontier:
                break
            allowances = dict(zip(order, heappop(frontier)[-1], strict=True))
        elif allocate_by_errors:
            eligible = [label for label in allowances
                        if errors[label] and allowances[label] < max_per_category]
            if not eligible:
                break
            selected = max(eligible, key=lambda label: errors[label])
            allowances[selected] += 1
        else:
            allowances = {label: count + 1 for label, count in allowances.items()}
    return proposals
