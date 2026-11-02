"""Acquire typed bridges from paired expert observations (§36.17)."""

import math
from collections.abc import Sequence
from dataclasses import replace
from typing import Any, Protocol

from nca.abi import Contract, Module
from nca.discovery import Decoded, Proposal, fit_decoder


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


def propose_heads(incumbent: Module, features: Sequence[Proposal], fit: HeadProposer,
                  rows: Sequence[tuple[Any, ...]], labels: Sequence[Any], *,
                  max_features: int, max_heads: int) -> list[Proposal]:
    """Acquire arbitrary unary heads on candidate representations (§36.40).

    Call within independent discovery's training callback. Each selected feature
    is observed once per training row; the fitter receives those observations,
    original targets, the required unary contract and a per-feature head budget.
    Retain only a bounded prefix of fitted heads and compose each with its feature.
    Feature/head constructors propagate in dependency order. Their package refs
    do not identify the resulting composite and are not copied to it.

    Observations/models must remain stable, and callbacks must not mutate shared
    training payloads. Fitting computation is caller-controlled. This does not
    learn the feature bodies, guarantee representation sufficiency, retain samples
    at inference or provide generalization evidence without whole-task selection.
    """
    if any(type(n) is not int or n < 1 for n in (max_features, max_heads)):
        raise ValueError("feature and head budgets must be positive integers")
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
    for feature in features:
        observations = tuple(feature.expert.invoke(*row) for row in rows)
        head_contract = Contract((feature.expert.manifest.contract.output,), contract.output)
        heads = tuple(fit(head_contract, observations, targets, max_heads)[:max_heads])
        for head in heads:
            if head.expert.manifest.contract != head_contract:
                raise ValueError("fitted heads must preserve the requested unary contract")
            proposals.append(Proposal(Decoded(feature.expert, head.expert, contract),
                                      feature.constructors + head.constructors))
    return proposals
