"""Acquire typed bridges from paired expert observations (§36.17)."""

import math
from collections import Counter, deque
from collections.abc import Callable, Hashable, Sequence
from dataclasses import replace
from typing import Any, Protocol

from nca.abi import Contract, Module
from nca.discovery import Decoded, JointFeature, Proposal, fit_decoder


class AdapterFitter(Protocol):
    def __call__(self, contract: Contract, keys: Sequence[Any], labels: Sequence[Any], *,
                 cost: float) -> Module: ...


def propose_adapter(incumbent: Module, source: Module, teacher: Module, consumer: Module,
                    rows: Sequence[tuple[Any, ...]], *, decoder_cost: float,
                    fit: AdapterFitter = fit_decoder) -> Proposal:
    """Fit a supplied bridge family and propose the completed external route.

    Call only with training rows, e.g. within discover's proposer. Source and
    teacher see the same external inputs/fillings. Their output types need not
    agree. The teacher must output the consumer's input type. The consumer is
    unary and slot-free. The default fitter needs stable, hashable categories;
    alternative fitters receive only the paired training values.
    Teacher agreement is training evidence, not a semantic-equivalence proof;
    select on independent end-to-end outcomes. No risk certificate is implied.
    """
    if not math.isfinite(decoder_cost) or decoder_cost < 0:
        raise ValueError("decoder cost must be finite and nonnegative")
    contract = incumbent.manifest.contract
    for module in (source, teacher):
        if replace(module.manifest.contract, output=contract.output) != contract:
            raise ValueError("paired experts must preserve external inputs, slots and relevance")
    head = consumer.manifest.contract
    if (head.inputs != (teacher.manifest.contract.output,) or head.slots
            or head.output != contract.output):
        raise ValueError("consumer must accept the teacher interface and produce the task output")
    if not rows or any(len(row) != len(contract.slots) + len(contract.inputs) for row in rows):
        raise ValueError("training rows must supply slot fillings followed by inputs")
    pairs = [(source.invoke(*row), teacher.invoke(*row)) for row in rows]
    adapter_contract = Contract((source.manifest.contract.output,), head.inputs[0])
    adapter = fit(adapter_contract, tuple(a for a, _ in pairs), tuple(b for _, b in pairs),
                  cost=decoder_cost)
    if adapter.manifest.contract != adapter_contract:
        raise ValueError("fitted adapter must preserve the requested interface contract")
    bridge = Decoded(source, adapter, teacher.manifest.contract)
    return Proposal(Decoded(bridge, consumer, contract))


class HeadProposer(Protocol):
    def __call__(self, contract: Contract, observations: Sequence[Any], targets: Sequence[Any],
                 budget: int) -> Sequence[Proposal]: ...


class FeatureRefiner(Protocol):
    def __call__(self, feature: Proposal, head: Module | None,
                 rows: Sequence[tuple[Any, ...]], targets: Sequence[Any],
                 budget: int) -> Sequence[Proposal]: ...


def propose_heads(incumbent: Module, features: Sequence[Proposal], fit: HeadProposer,
                  rows: Sequence[tuple[Any, ...]], labels: Sequence[Any], *,
                  max_features: int, max_heads: int,
                  refine: FeatureRefiner | None = None, max_refinements: int = 0,
                  correct: Callable[[Any, Any], bool] | None = None) -> list[Proposal]:
    """Acquire arbitrary unary heads on candidate representations (§36.40).

    Call within independent discovery's training callback. Each selected feature
    is observed once per training row; the fitter receives those observations,
    original targets, the required unary contract and a per-feature head budget.
    Retain only a bounded prefix of fitted heads and compose each with its feature.
    Feature/head constructors propagate in dependency order. Their package refs
    do not identify the resulting composite and are not copied to it.
    Optional refinement (§36.44) receives the feature, best training head (or
    None), original training rows/targets and remaining total feature slots.
    It runs only for unresolved training errors, subject to a call budget.
    Replacement proposals own their full constructor declarations, including any
    seed dependencies they actually use. All admitted features, including initial
    and repeated proposals, consume the same max_features budget. Fitting and
    refinement callbacks own their internal computation limits.

    Observations/models must remain stable, and callbacks must not mutate shared
    training payloads. Fitting computation is caller-controlled. This does not
    learn the feature bodies, guarantee representation sufficiency, retain samples
    at inference or provide generalization evidence without whole-task selection.
    """
    if any(type(n) is not int or n < 1 for n in (max_features, max_heads)):
        raise ValueError("feature and head budgets must be positive integers")
    if type(max_refinements) is not int or max_refinements < 0:
        raise ValueError("refinement budget must be a nonnegative integer")
    if max_refinements and (refine is None or correct is None):
        raise ValueError("feature refinement requires a refiner and correctness predicate")
    if not rows or len(rows) != len(labels):
        raise ValueError("head training needs nonempty aligned rows and labels")
    contract = incumbent.manifest.contract
    if any(len(row) != len(contract.slots) + len(contract.inputs) for row in rows):
        raise ValueError("rows must supply slot fillings followed by inputs")
    features = tuple(features[:max_features])
    if any(replace(p.expert.manifest.contract, output=contract.output) != contract for p in features):
        raise ValueError("features must preserve inputs, slots and relevance")
    targets = tuple(labels)
    proposals = []
    pending = deque(features)
    admitted, refinement_calls = len(features), 0
    while pending:
        feature = pending.popleft()
        observations = tuple(feature.expert.invoke(*row) for row in rows)
        head_contract = Contract((feature.expert.manifest.contract.output,), contract.output)
        heads = tuple(fit(head_contract, observations, targets, max_heads)[:max_heads])
        for head in heads:
            if head.expert.manifest.contract != head_contract:
                raise ValueError("fitted heads must preserve the requested unary contract")
            proposals.append(Proposal(Decoded(feature.expert, head.expert, contract),
                                      feature.constructors + head.constructors))
        remaining = max_features - admitted
        if refine is not None and correct is not None and remaining and (
                refinement_calls < max_refinements):
            scores = [(sum(bool(correct(head.expert.invoke(value), target))
                           for value, target in zip(observations, targets, strict=True)), head)
                      for head in heads]
            successes, seed = (min(scores, key=lambda item: (-item[0], item[1].expert.manifest.cost))
                               if scores else (0, None))
            if successes < len(rows):
                refinement_calls += 1
                extra = tuple(refine(feature, None if seed is None else seed.expert,
                                     tuple(rows), targets, remaining)[:remaining])
                if any(replace(p.expert.manifest.contract, output=contract.output) != contract
                       for p in extra):
                    raise ValueError("refined features must preserve inputs, slots and relevance")
                pending.extend(extra)
                admitted += len(extra)
    return proposals


def propose_joint_refinements(feature: Proposal, companions: Sequence[Proposal],
        rows: Sequence[tuple[Any, ...]], labels: Sequence[Hashable], *,
        max_candidates: int, limit: int, pair_cost: float) -> list[Proposal]:
    """Resolve empirical category ambiguity by pairing representations (§36.45).

    Observe the seed once per training row and each bounded companion once.
    Rank joint features by modal training successes, retaining only strict gains
    over the seed and at most limit outputs. Ties retain companion order. Stable
    hashable keys/labels and observations are required. Use within a training-only
    FeatureRefiner; categorical modal gains need not help another head family or
    generalize. Returned features retain their original implementations, not data.
    """
    if any(type(n) is not int or n < 1 for n in (max_candidates, limit)):
        raise ValueError("companion and output budgets must be positive integers")
    if not math.isfinite(pair_cost) or pair_cost < 0:
        raise ValueError("pair cost must be finite and nonnegative")
    if not rows or len(rows) != len(labels):
        raise ValueError("joint refinement needs nonempty aligned rows and labels")
    contract = feature.expert.manifest.contract
    if any(len(row) != len(contract.inputs) + len(contract.slots) for row in rows):
        raise ValueError("rows must supply slot fillings followed by inputs")
    companions = tuple(companions[:max_candidates])
    if any(replace(p.expert.manifest.contract, output=contract.output) != contract
           for p in companions):
        raise ValueError("companion features must preserve inputs, slots and relevance")

    def score(keys: Sequence[Hashable]) -> int:
        counts: dict[Hashable, Counter[Hashable]] = {}
        for key, label in zip(keys, labels, strict=True):
            counts.setdefault(key, Counter())[label] += 1
        return sum(max(histogram.values()) for histogram in counts.values())

    keys = tuple(feature.expert.invoke(*row) for row in rows)
    baseline = score(keys)
    ranked = []
    for companion in companions:
        joint_keys = tuple((key, companion.expert.invoke(*row))
                           for row, key in zip(rows, keys, strict=True))
        successes = score(joint_keys)
        if successes > baseline:
            joined = JointFeature(feature.expert, companion.expert, pair_cost)
            ranked.append((successes, Proposal(joined, feature.constructors + companion.constructors)))
    ranked.sort(key=lambda item: -item[0])
    return [proposal for _, proposal in ranked[:limit]]
