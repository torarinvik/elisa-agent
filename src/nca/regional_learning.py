"""Acquire arbitrary local experts where incumbent training failures concentrate."""

import math
from collections.abc import Callable, Hashable, Sequence
from dataclasses import replace
from typing import Any

from nca.abi import Module
from nca.discovery import Proposal, _total_calls
from nca.numeric_learning import fit_partition_encoder


class RegionalExpert:
    """A learned expert in one feature region, with the incumbent elsewhere."""

    def __init__(self, incumbent: Module, feature: Module, key: Hashable,
                 specialist: Module, cost: float) -> None:
        contract = incumbent.manifest.contract
        if specialist.manifest.contract != contract:
            raise ValueError("regional expert must preserve the external contract")
        if replace(feature.manifest.contract, output=contract.output) != contract:
            raise ValueError("routing feature must preserve inputs, slots and relevance")
        manifests = (incumbent.manifest, feature.manifest, specialist.manifest)
        if any(not math.isfinite(m.cost) or m.cost < 0 for m in manifests) or (
                not math.isfinite(cost) or cost < 0):
            raise ValueError("regional costs must be finite and nonnegative")
        effects = (None if any(m.effects is None for m in manifests)
                   else frozenset().union(*(m.effects for m in manifests)))
        self.incumbent, self.feature, self.key, self.specialist = incumbent, feature, key, specialist
        self.manifest = replace(incumbent.manifest,
            module_id=f"{incumbent.manifest.module_id}/regional/{specialist.manifest.module_id}",
            cost=cost + sum(m.cost for m in manifests), calls=_total_calls(manifests),
            expected_calls=None, effects=effects)

    def invoke(self, *inputs: Any) -> Any:
        if self.feature.invoke(*inputs) == self.key:
            return self.specialist.invoke(*inputs)
        return self.incumbent.invoke(*inputs)


def propose_regional_experts(incumbent: Module, feature: Module,
        propose: Callable[[Sequence[tuple[Any, ...]], Sequence[Any]], Sequence[Proposal]],
        rows: Sequence[tuple[Any, ...]], labels: Sequence[Any],
        correct: Callable[[Any, Any], bool], *, max_regions: int,
        overhead_cost: float) -> list[Proposal]:
    """Train replacements in error-bearing regions using training rows only (§36.26).

    Rank by error count, ties by first occurrence; this is not optimal allocation.
    Pass the whole region, including successful controls, to the proposer. Its
    targets may be arbitrary objects, not just categories. Each returned expert
    becomes a separate whole-task candidate for discover's independent selection.
    Models, row payloads and feature keys must remain stable. No active library,
    saved package or risk certificate is changed by this in-memory proposal step.
    """
    if type(max_regions) is not int or max_regions < 1:
        raise ValueError("region budget must be a positive integer")
    if not rows or len(rows) != len(labels):
        raise ValueError("regional training needs nonempty aligned rows and labels")
    if not math.isfinite(overhead_cost) or overhead_cost < 0:
        raise ValueError("regional overhead must be finite and nonnegative")
    contract = incumbent.manifest.contract
    if replace(feature.manifest.contract, output=contract.output) != contract:
        raise ValueError("routing feature must preserve inputs, slots and relevance")
    if any(len(row) != len(contract.inputs) + len(contract.slots) for row in rows):
        raise ValueError("rows must supply slot fillings followed by inputs")
    groups: dict[Hashable, list[int]] = {}
    errors: dict[Hashable, int] = {}
    for index, (row, target) in enumerate(zip(rows, labels, strict=True)):
        key = feature.invoke(*row)
        groups.setdefault(key, []).append(index)
        errors[key] = errors.get(key, 0) + int(not correct(incumbent.invoke(*row), target))
    selected = sorted((key for key in groups if errors[key]), key=lambda key: -errors[key])
    proposals = []
    for key in selected[:max_regions]:
        indices = groups[key]
        local = tuple(propose(tuple(rows[i] for i in indices), tuple(labels[i] for i in indices)))
        for candidate in local:
            expert = RegionalExpert(incumbent, feature, key, candidate.expert, overhead_cost)
            proposals.append(Proposal(expert, candidate.constructors))
    return proposals


def propose_failure_partitions(incumbent: Module, measurements: Sequence[Module],
        propose: Callable[[Sequence[tuple[Any, ...]], Sequence[Any]], Sequence[Proposal]],
        rows: Sequence[tuple[Any, ...]], labels: Sequence[Any],
        correct: Callable[[Any, Any], bool], *, max_measurements: int, max_regions: int,
        encoding_cost: float, overhead_cost: float,
        place_boundary: Callable[[float, float], float] | None = None) -> list[Proposal]:
    """Learn routing cuts from training failures, then acquire task specialists (§36.27).

    Measurements are finite-float experts with the original external inputs.
    Auxiliary failure labels train only the router; specialists receive original
    task targets in their assigned regions. Constant failure indicators yield no
    proposals. Use inside discover's training callback. Inputs/models/scoring
    must remain stable; training may invoke the incumbent/measurements repeatedly.
    This family learns scalar cuts, not measurement implementations.
    """
    if any(type(n) is not int or n < 1 for n in (max_measurements, max_regions)):
        raise ValueError("measurement and region budgets must be positive integers")
    if len(rows) < 2 or len(rows) != len(labels):
        raise ValueError("failure partition training needs at least two aligned rows")
    if any(not math.isfinite(c) or c < 0 for c in (encoding_cost, overhead_cost)):
        raise ValueError("failure partition costs must be finite and nonnegative")
    contract = incumbent.manifest.contract
    if any(len(row) != len(contract.inputs) + len(contract.slots) for row in rows):
        raise ValueError("rows must supply slot fillings followed by inputs")
    measurements = tuple(measurements[:max_measurements])
    if any(replace(m.manifest.contract, output=contract.output) != contract for m in measurements):
        raise ValueError("measurements must preserve inputs, slots and relevance")
    failures = tuple(not correct(incumbent.invoke(*row), target)
                     for row, target in zip(rows, labels, strict=True))
    if len(set(failures)) < 2:
        return []
    proposals = []
    for measurement in measurements:
        encoder = fit_partition_encoder(measurement, rows, failures,
                                        encoding_cost=encoding_cost, place_boundary=place_boundary)
        if encoder is None:
            continue
        local = propose_regional_experts(incumbent, encoder, propose, rows, labels, correct,
                                         max_regions=max_regions, overhead_cost=overhead_cost)
        proposals.extend(Proposal(candidate.expert, (encoder.constructor,) + candidate.constructors)
                         for candidate in local)
    return proposals
