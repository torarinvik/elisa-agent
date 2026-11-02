"""Acquire arbitrary local experts where incumbent training failures concentrate."""

import math
from collections import Counter
from collections.abc import Callable, Hashable, Iterator, Mapping, Sequence
from dataclasses import replace
from heapq import heappop, heappush
from typing import Any

from nca.abi import Module
from nca.discovery import Proposal, _total_calls
from nca.numeric_learning import SplitTieBreak, fit_partition_encoder, fit_regions_encoder


MeasurementProposer = Callable[
    [Sequence[tuple[Any, ...]], Sequence[Hashable], int], Sequence[Proposal]]
RegionalRefiner = Callable[[Module, Sequence[tuple[Any, ...]], Sequence[Any]], Sequence[Proposal]]


class RegionalPolicy:
    """One routing evaluation dispatches to a specialist or the incumbent."""

    def __init__(self, incumbent: Module, feature: Module,
                 specialists: Mapping[Hashable, Module], cost: float) -> None:
        contract = incumbent.manifest.contract
        specialists = dict(specialists)
        if any(module.manifest.contract != contract for module in specialists.values()):
            raise ValueError("regional expert must preserve the external contract")
        if replace(feature.manifest.contract, output=contract.output) != contract:
            raise ValueError("routing feature must preserve inputs, slots and relevance")
        manifests = (incumbent.manifest, feature.manifest,
                     *(module.manifest for module in specialists.values()))
        if any(not math.isfinite(m.cost) or m.cost < 0 for m in manifests) or (
                not math.isfinite(cost) or cost < 0):
            raise ValueError("regional costs must be finite and nonnegative")
        effects = (None if any(m.effects is None for m in manifests)
                   else frozenset().union(*(m.effects for m in manifests)))
        self.incumbent, self.feature, self.specialists = incumbent, feature, specialists
        self.overhead_cost = cost
        self.manifest = replace(incumbent.manifest, module_id="learned-regional-policy",
            cost=cost + sum(m.cost for m in manifests), calls=_total_calls(manifests),
            expected_calls=None, effects=effects)

    def invoke(self, *inputs: Any) -> Any:
        specialist = self.specialists.get(self.feature.invoke(*inputs))
        return (self.incumbent.invoke(*inputs) if specialist is None
                else specialist.invoke(*inputs))


class RegionalExpert(RegionalPolicy):
    """The single-region form, preserving its public fields and artifact factory."""

    def __init__(self, incumbent: Module, feature: Module, key: Hashable,
                 specialist: Module, cost: float) -> None:
        super().__init__(incumbent, feature, {key: specialist}, cost)
        self.key, self.specialist = key, specialist
        self.manifest = replace(self.manifest,
            module_id=f"{incumbent.manifest.module_id}/regional/{specialist.manifest.module_id}")


def _ranked_combinations(families: Sequence[Sequence[tuple[int, Proposal | None]]],
                         limit: int) -> Iterator[tuple[Proposal | None, ...]]:
    """Best-first product; None is fallback with zero incremental wiring cost."""
    if not families or any(not family for family in families):
        return

    def priority(indices: tuple[int, ...]) -> tuple[int, float, tuple[int, ...]]:
        chosen = [family[index] for family, index in zip(families, indices, strict=True)]
        return (-sum(score for score, _ in chosen),
                sum(0.0 if candidate is None else candidate.expert.manifest.cost
                    for _, candidate in chosen), indices)

    initial = (0,) * len(families)
    pending, seen = [priority(initial)], {initial}
    for step in range(limit):
        if not pending:
            break
        _, _, indices = heappop(pending)
        yield tuple(family[index][1] for family, index in zip(families, indices, strict=True))
        if step + 1 == limit:
            return
        for axis, family in enumerate(families):
            if indices[axis] + 1 >= len(family):
                continue
            neighbor = indices[:axis] + (indices[axis] + 1,) + indices[axis + 1:]
            if neighbor not in seen:
                seen.add(neighbor)
                heappush(pending, priority(neighbor))


def propose_regional_experts(incumbent: Module, feature: Module,
        propose: Callable[[Sequence[tuple[Any, ...]], Sequence[Any]], Sequence[Proposal]],
        rows: Sequence[tuple[Any, ...]], labels: Sequence[Any],
        correct: Callable[[Any, Any], bool], *, max_regions: int,
        overhead_cost: float, max_combinations: int = 0,
        refine: RegionalRefiner | None = None, max_refinements: int = 0) -> list[Proposal]:
    """Train replacements in error-bearing regions using training rows only (§36.26).

    Rank by error count, ties by first occurrence; this is not optimal allocation.
    Pass the whole region, including successful controls, to the proposer. Its
    targets may be arbitrary objects, not just categories. Each returned expert
    becomes a separate whole-task candidate for discover's independent selection.
    Models, row payloads and feature keys must remain stable. No active library,
    saved package or risk certificate is changed by this in-memory proposal step.
    max_combinations optionally adds a training-ranked Cartesian prefix over all
    trainable selected regions (§36.31), without an exhaustive-search guarantee.
    Scoring uses original regional training targets only; ties prefer lower
    incremental declared cost then stable family order. An explicit fallback
    choice leaves each region with the incumbent; omit baseline/single choices
    already offered separately (§36.32). An optional refiner receives the best
    local seed only when training errors remain, up to max_refinements calls
    (§36.33). Perfect training fit is not a generalization claim. Held-out
    selection remains separate; callbacks own their internal work budgets.
    """
    if type(max_combinations) is not int or max_combinations < 0:
        raise ValueError("combination budget must be a nonnegative integer")
    if type(max_refinements) is not int or max_refinements < 0:
        raise ValueError("refinement budget must be a nonnegative integer")
    if max_refinements and refine is None:
        raise ValueError("a positive refinement budget requires a refiner")
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
    alternatives = []
    refinement_calls = 0
    for key in selected[:max_regions]:
        indices = groups[key]
        subset, targets = tuple(rows[i] for i in indices), tuple(labels[i] for i in indices)
        local = tuple(propose(subset, targets))
        for candidate in local:
            expert = RegionalExpert(incumbent, feature, key, candidate.expert, overhead_cost)
            proposals.append(Proposal(expert, candidate.constructors))
        if refine is not None and refinement_calls < max_refinements:
            seeds = [(len(indices) - errors[key], Proposal(incumbent))]
            seeds.extend((sum(bool(correct(candidate.expert.invoke(*row), target))
                              for row, target in zip(subset, targets, strict=True)), candidate)
                         for candidate in local if candidate.expert is not incumbent)
            successes, seed = min(seeds, key=lambda item: (-item[0], item[1].expert.manifest.cost))
            if successes < len(indices):
                refinement_calls += 1
                extra = tuple(Proposal(p.expert, seed.constructors + p.constructors, p.package)
                              for p in refine(seed.expert, subset, targets))
                for candidate in extra:
                    expert = RegionalExpert(incumbent, feature, key, candidate.expert, overhead_cost)
                    proposals.append(Proposal(expert, candidate.constructors))
                local += extra
        if local:
            alternatives.append((key, local))
    if len(alternatives) > 1 and max_combinations:
        keys = tuple(key for key, _ in alternatives)
        ranked = []
        for key, family in alternatives:
            scores: list[tuple[int, Proposal | None]] = [
                (sum(bool(correct(candidate.expert.invoke(*rows[i]), labels[i]))
                     for i in groups[key]), candidate) for candidate in family
                if candidate.expert is not incumbent]
            scores.append((len(groups[key]) - errors[key], None))
            scores.sort(key=lambda item: (-item[0],
                0.0 if item[1] is None else item[1].expert.manifest.cost, item[1] is not None))
            ranked.append(scores)
        # Empty/single-specialist assignments are already offered separately.
        skipped_bound = 1 + sum(len(family) - 1 for family in ranked)
        emitted = 0
        for choice in _ranked_combinations(ranked, max_combinations + skipped_bound):
            active = [(key, candidate) for key, candidate in zip(keys, choice, strict=True)
                      if candidate is not None]
            if len(active) < 2:
                continue
            policy = RegionalPolicy(incumbent, feature,
                                     {key: candidate.expert for key, candidate in active},
                                     overhead_cost)
            constructors = tuple(constructor for _, candidate in active
                                 for constructor in candidate.constructors)
            proposals.append(Proposal(policy, constructors))
            emitted += 1
            if emitted == max_combinations:
                break
    return proposals


def propose_failure_partitions(incumbent: Module, measurements: Sequence[Module],
        propose: Callable[[Sequence[tuple[Any, ...]], Sequence[Any]], Sequence[Proposal]],
        rows: Sequence[tuple[Any, ...]], labels: Sequence[Any],
        correct: Callable[[Any, Any], bool], *, max_measurements: int, max_regions: int,
        encoding_cost: float, overhead_cost: float,
        place_boundary: Callable[[float, float], float] | None = None,
        routing_regions: int = 2, tie_break: SplitTieBreak | None = None,
        max_combinations: int = 0, refine: RegionalRefiner | None = None,
        max_refinements: int = 0,
        routing_signal: Callable[[tuple[Any, ...], Any, Any], Hashable] | None = None,
        max_measurement_candidates: int | None = None,
        propose_measurements: MeasurementProposer | None = None
        ) -> list[Proposal]:
    """Learn routing cuts from training failures, then acquire task specialists (§36.27).

    Measurements are finite-float experts with the original external inputs.
    Auxiliary failure labels train only the router; specialists receive original
    task targets in their assigned regions. By default constant failure indicators
    yield no proposals. Optional routing_signal(row, prediction, target) supplies
    stable hashable auxiliary labels, once per training row including successes;
    it can distinguish failures even when all predictions are wrong (§36.35).
    Constant auxiliary labels or no failures still yield no proposals. The callback
    is not retained for inference. Its meaning and usefulness are caller supplied.
    Use inside discover's training callback. Inputs/models/scoring
    must remain stable; training may invoke the incumbent/measurements repeatedly.
    Without a measurement proposer this family learns scalar cuts only. An explicit
    routing_regions budget permits interval refinement (§36.28); tie_break is a
    pure secondary score over read-only label histograms, with modal accuracy primary.
    Each measurement search has its own max_refinements call budget.
    Optional max_measurement_candidates bounds a larger screening prefix: rank
    fitted routers by training modal signal accuracy, ties in supplied order,
    then train specialists for at most max_measurements routers (§36.37).
    Without screening, the original prefix allocation is preserved. Screening
    may invoke measurements again and assumes stable observations; it does not
    claim that signal accuracy predicts task improvement.
    Optional propose_measurements(rows, signals, remaining_budget) learns scalar
    measurement proposals (§36.39). Fixed measurements consume the prefix first;
    only remaining candidate slots are requested and retained. The callback owns
    its computation budget, sees training data only, and supplies constructors
    that accompany selected routers. No-error or constant-signal samples skip it.
    """
    if type(max_combinations) is not int or max_combinations < 0:
        raise ValueError("combination budget must be a nonnegative integer")
    if type(max_refinements) is not int or max_refinements < 0:
        raise ValueError("refinement budget must be a nonnegative integer")
    if max_refinements and refine is None:
        raise ValueError("a positive refinement budget requires a refiner")
    if any(type(n) is not int or n < 1 for n in (max_measurements, max_regions, routing_regions)):
        raise ValueError("measurement and region budgets must be positive integers")
    if len(rows) < 2 or len(rows) != len(labels):
        raise ValueError("failure partition training needs at least two aligned rows")
    if any(not math.isfinite(c) or c < 0 for c in (encoding_cost, overhead_cost)):
        raise ValueError("failure partition costs must be finite and nonnegative")
    if max_measurement_candidates is not None and (
            type(max_measurement_candidates) is not int or max_measurement_candidates < 1):
        raise ValueError("measurement candidate budget must be a positive integer")
    contract = incumbent.manifest.contract
    if any(len(row) != len(contract.inputs) + len(contract.slots) for row in rows):
        raise ValueError("rows must supply slot fillings followed by inputs")
    measurement_budget = (max_measurements if max_measurement_candidates is None
                          else max_measurement_candidates)
    measurements = tuple(measurements[:measurement_budget])
    if any(replace(m.manifest.contract, output=contract.output) != contract for m in measurements):
        raise ValueError("measurements must preserve inputs, slots and relevance")
    failures = []
    signals = []
    for row, target in zip(rows, labels, strict=True):
        prediction = incumbent.invoke(*row)
        failure = not correct(prediction, target)
        failures.append(failure)
        signals.append(failure if routing_signal is None
                       else routing_signal(row, prediction, target))
    if not any(failures) or len(set(signals)) < 2:
        return []
    measurement_proposals = [Proposal(m) for m in measurements]
    remaining = measurement_budget - len(measurement_proposals)
    if propose_measurements is not None and remaining:
        learned = tuple(propose_measurements(tuple(rows), tuple(signals), remaining)[:remaining])
        if any(replace(p.expert.manifest.contract, output=contract.output) != contract
               for p in learned):
            raise ValueError("learned measurements must preserve inputs, slots and relevance")
        measurement_proposals.extend(learned)
    routers = []
    for measurement_proposal in measurement_proposals:
        measurement = measurement_proposal.expert
        if routing_regions == 2:
            encoder = fit_partition_encoder(measurement, rows, signals,
                        encoding_cost=encoding_cost, place_boundary=place_boundary,
                        tie_break=tie_break)
        else:
            encoder = fit_regions_encoder(measurement, rows, signals, max_regions=routing_regions,
                        encoding_cost=encoding_cost, place_boundary=place_boundary,
                        tie_break=tie_break)
        if encoder is not None:
            routers.append((encoder, measurement_proposal.constructors))
    if max_measurement_candidates is not None:
        def score(encoder: Module) -> int:
            counts: dict[Hashable, Counter[Hashable]] = {}
            for row, signal in zip(rows, signals, strict=True):
                counts.setdefault(encoder.invoke(*row), Counter())[signal] += 1
            return sum(max(histogram.values()) for histogram in counts.values())

        routers.sort(key=lambda item: score(item[0]), reverse=True)
    proposals = []
    for encoder, measurement_constructors in routers[:max_measurements]:
        local = propose_regional_experts(incumbent, encoder, propose, rows, labels, correct,
                                         max_regions=max_regions, overhead_cost=overhead_cost,
                                         max_combinations=max_combinations, refine=refine,
                                         max_refinements=max_refinements)
        proposals.extend(Proposal(candidate.expert, measurement_constructors +
                                 (encoder.constructor,) + candidate.constructors)
                         for candidate in local)
    return proposals
