"""Acquire typed bridges from paired expert observations (§36.17)."""

import math
from collections import Counter, deque
from collections.abc import Callable, Hashable, Sequence
from dataclasses import replace
from itertools import chain, combinations, islice
from typing import Any, Protocol

from nca.abi import Contract, Module
from nca.learning.discovery import Decoded, Decoder, JointFeature, Proposal, fit_decoder
from nca.objects import Constructor, canonical, digest
from nca.value_codec import encode_value


class AdapterFitter(Protocol):
    def __call__(self, contract: Contract, keys: Sequence[Any], labels: Sequence[Any], *,
                 cost: float) -> Module: ...


def fit_interface_bridge(source: Module, teacher: Module, rows: Sequence[tuple[Any, ...]], *,
                         adapter_cost: float, fit: AdapterFitter = fit_decoder) -> Decoded:
    """Fit a reusable source-to-teacher representation without a consumer (§36.57).

    Source and teacher share external inputs, slots and relevance. The adapter
    connects their declared output types using training pairs only. The result
    retains source and fitted adapter, with no separate teacher dependency.
    Stable data/models and faithful fitters are assumptions. Agreement on these
    pairs does not establish extrapolation.
    Retain the bridge as its own graph root when it should be reusable later.
    """
    if not math.isfinite(adapter_cost) or adapter_cost < 0:
        raise ValueError("adapter cost must be finite and nonnegative")
    contract = teacher.manifest.contract
    if replace(source.manifest.contract, output=contract.output) != contract:
        raise ValueError("paired experts must preserve external inputs, slots and relevance")
    if not rows or any(len(row) != len(contract.slots) + len(contract.inputs) for row in rows):
        raise ValueError("training rows must supply slot fillings followed by inputs")
    pairs = [(source.invoke(*row), teacher.invoke(*row)) for row in rows]
    adapter_contract = Contract((source.manifest.contract.output,), contract.output)
    adapter = fit(adapter_contract, tuple(a for a, _ in pairs), tuple(b for _, b in pairs),
                  cost=adapter_cost)
    if adapter.manifest.contract != adapter_contract:
        raise ValueError("fitted adapter must preserve the requested interface contract")
    return Decoded(source, adapter, contract)


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
    bridge = fit_interface_bridge(source, teacher, rows, adapter_cost=decoder_cost, fit=fit)
    return Proposal(Decoded(bridge, consumer, contract))


def propose_adapters(incumbent: Module, sources: Sequence[Proposal], teachers: Sequence[Proposal],
        consumers: Sequence[Module], rows: Sequence[tuple[Any, ...]], *,
        max_candidates: int, decoder_cost: float,
        fit: AdapterFitter = fit_decoder, share_alignment: bool = False,
        fitters: Sequence[AdapterFitter] | None = None) -> list[Proposal]:
    """Acquire a bounded family of typed bridges into supplied consumers (§36.56).

    Use within independent discovery's training callback. Filter source/teacher
    external signatures and unary slot-free consumer contracts through metadata
    only. By default compatible triples spend one fit each, following supplied
    source, teacher and consumer order. Incompatible modules spend no fit budget.
    The bound covers completed candidates; library scanning and fitter computation
    remain caller-controlled. Input sequences are shallow snapshots.
    Propagate source/teacher constructor declarations, but retain no teacher code
    in proposed inference graphs. Stable models/pairs and independent end-to-end
    selection are required; teacher agreement does not certify task correctness.
    Opt-in share_alignment (§36.57) fits one reusable bridge per compatible
    source/teacher pair and shares that model across completed consumer routes.
    It changes the training family for stochastic fitters. Candidate limits still
    count complete routes, and inference values are never cached by this option.
    Explicit fitters (§36.58) override fit and define an ordered alignment family;
    an empty family emits nothing. Order is source/teacher/fitter/consumer, with
    sharing local to each fitter entry. Fitters must accept the paired value
    shapes; errors are not suppressed. Freeze all candidates before evaluation.
    """
    if type(max_candidates) is not int or max_candidates < 1:
        raise ValueError("adapter candidate budget must be a positive integer")
    if not math.isfinite(decoder_cost) or decoder_cost < 0:
        raise ValueError("decoder cost must be finite and nonnegative")
    contract = incumbent.manifest.contract
    if not rows or any(len(row) != len(contract.inputs) + len(contract.slots) for row in rows):
        raise ValueError("training rows must supply slot fillings followed by inputs")
    sources, teachers, consumers = tuple(sources), tuple(teachers), tuple(consumers)
    family = tuple(fitters) if fitters is not None else (fit,)
    proposals = []
    for source in sources:
        if replace(source.expert.manifest.contract, output=contract.output) != contract:
            continue
        for teacher in teachers:
            if replace(teacher.expert.manifest.contract, output=contract.output) != contract:
                continue
            expected = Contract((teacher.expert.manifest.contract.output,), contract.output)
            for fitter in family:
                bridge: Decoded | None = None
                for consumer in consumers:
                    if consumer.manifest.contract != expected:
                        continue
                    if share_alignment:
                        if bridge is None:
                            bridge = fit_interface_bridge(source.expert, teacher.expert, rows,
                                                           adapter_cost=decoder_cost, fit=fitter)
                        proposal = Proposal(Decoded(bridge, consumer, contract))
                    else:
                        proposal = propose_adapter(incumbent, source.expert, teacher.expert, consumer,
                                                    rows, decoder_cost=decoder_cost, fit=fitter)
                    proposals.append(replace(proposal,
                        constructors=source.constructors + teacher.constructors))
                    if len(proposals) == max_candidates:
                        return proposals
    return proposals


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
        max_candidates: int, limit: int, pair_cost: float,
        max_companions: int = 1, max_joint_candidates: int | None = None) -> list[Proposal]:
    """Resolve empirical category ambiguity by pairing representations (§36.45).

    Observe the seed once per training row and each bounded companion once.
    Rank joint features by modal training successes, retaining only strict gains
    over the seed and at most limit outputs. Ties retain companion order. Stable
    hashable keys/labels and observations are required. Use within a training-only
    FeatureRefiner; categorical modal gains need not help another head family or
    generalize. Returned features retain their original implementations, not data.
    Optional bounded lookahead (§36.47) scores companion subsets smallest first,
    index order within each size. max_joint_candidates bounds scored subsets
    (default max_candidates), including non-improving subsets. No intermediate
    gain is required. Snapshots trade temporary memory for one observation per
    supplied companion; the retained product is left-associated in subset order.
    """
    if max_joint_candidates is None:
        max_joint_candidates = max_candidates
    if any(type(n) is not int or n < 1
           for n in (max_candidates, limit, max_companions, max_joint_candidates)):
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
    observations = tuple(tuple(p.expert.invoke(*row) for row in rows) for p in companions)
    subsets = chain.from_iterable(combinations(range(len(companions)), size)
                                  for size in range(1, min(max_companions, len(companions)) + 1))
    ranked = []
    for subset in islice(subsets, max_joint_candidates):
        joint_keys = keys
        for index in subset:
            joint_keys = tuple(zip(joint_keys, observations[index], strict=True))
        successes = score(joint_keys)
        if successes > baseline:
            joined = feature.expert
            constructors = feature.constructors
            for index in subset:
                joined = JointFeature(joined, companions[index].expert, pair_cost)
                constructors += companions[index].constructors
            ranked.append((successes, Proposal(joined, constructors)))
    ranked.sort(key=lambda item: -item[0])
    return [proposal for _, proposal in ranked[:limit]]


def fit_categorical_partition(measurement: Module, rows: Sequence[tuple[Any, ...]],
                               labels: Sequence[Hashable], *, encoding_cost: float) -> Proposal:
    """Learn a typed quotient of observed keys by modal target category (§36.48).

    Keys must be stable hashable JSON scalars/tuples; category names need only
    stable hashing/equality. Codes follow canonical key order, making the learned
    partition invariant to a bijective category renaming with unchanged modal
    choices. Modal ties retain training occurrence order. Unseen keys use a code
    for the global modal category, possibly absent among observed key modes.
    Category labels and training rows are not retained, only key-to-code wiring.
    Training modal accuracy is preserved by a categorical head, not necessarily
    other head families or tasks. Select composed candidates independently.
    Store returned constructor declarations before retaining the composed graph.
    """
    if not math.isfinite(encoding_cost) or encoding_cost < 0:
        raise ValueError("encoding cost must be finite and nonnegative")
    if not rows or len(rows) != len(labels):
        raise ValueError("categorical partition needs nonempty aligned rows and labels")
    contract = measurement.manifest.contract
    if any(len(row) != len(contract.inputs) + len(contract.slots) for row in rows):
        raise ValueError("rows must supply slot fillings followed by inputs")
    counts: dict[Hashable, Counter[Hashable]] = {}
    for row, label in zip(rows, labels, strict=True):
        counts.setdefault(measurement.invoke(*row), Counter())[label] += 1
    ordered = sorted(counts, key=lambda key: canonical(encode_value(key)))
    codes: dict[Hashable, int] = {}

    def code(label: Hashable) -> int:
        if label not in codes:
            codes[label] = len(codes)
        return codes[label]

    table = {key: code(counts[key].most_common(1)[0][0]) for key in ordered}
    fallback = code(Counter(labels).most_common(1)[0][0])
    definition = {"table": [[encode_value(key), table[key]] for key in ordered],
                  "fallback": fallback}
    constructor = Constructor("learned-categorical-partition", "1", 0,
        canonical({"source": contract.output, "partition": digest(definition),
                   "meaning": "empirical key partition with an unseen-key fallback"}).decode())
    head = Decoder(Contract((contract.output,), constructor.type()), table, fallback, encoding_cost)
    return Proposal(Decoded(measurement, head, replace(contract, output=constructor.type())),
                    (constructor,))
