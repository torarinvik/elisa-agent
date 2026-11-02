"""Training-only proposals of interfaces and experts, selected by evidence (§36.3)."""

from __future__ import annotations

import math
from collections import Counter
from collections.abc import Callable, Hashable, Mapping, Sequence
from dataclasses import dataclass, replace
from itertools import combinations
from typing import Any

from nca.abi import Calls, Contract, Manifest, Module
from nca.objects import Constructor, Ref, Store
from nca.packages import install
from nca.router import sign_test


@dataclass(frozen=True)
class Proposal:
    """An expert and optional new intermediate types; no active library changes.

    Internal composition is unrestricted. Constructor declarations assert no
    semantic equivalence to existing types and must describe the actual expert.
    """

    expert: Module
    constructors: tuple[Constructor, ...] = ()
    package: Ref | None = None
    """Source object when evaluated through discover_packages; not a certificate."""


@dataclass(frozen=True)
class Trial:
    proposal: Proposal
    outcomes: tuple[bool, ...]
    p_value: float
    accepted: bool


@dataclass(frozen=True)
class Discovery:
    baseline: tuple[bool, ...]
    trials: tuple[Trial, ...]
    chosen: Proposal | None


class Decoder:
    """An empirical decoder; unseen keys use the training set's modal label.

    Keys and labels must be hashable with stable equality. Counts tied for the
    mode are resolved by first occurrence in training order. No risk is claimed.
    """

    def __init__(self, contract: Contract, table: Mapping[Hashable, Hashable],
                 fallback: Hashable, cost: float) -> None:
        self.manifest = Manifest("learned-decoder", "1", contract, cost=cost,
                                 effects=frozenset())
        self._table = dict(table)
        self.fallback = fallback

    def invoke(self, key: Hashable) -> Hashable:
        return self._table.get(key, self.fallback)


class Decoded:
    """A feature expert followed by a learned decoder, with its original slots."""

    def __init__(self, feature: Module, decoder: Decoder, contract: Contract) -> None:
        self.feature, self.decoder = feature, decoder
        self.manifest = replace(feature.manifest,
                                module_id=f"{feature.manifest.module_id}/decoded",
                                contract=contract,
                                cost=feature.manifest.cost + decoder.manifest.cost)

    def invoke(self, *inputs: Any) -> Hashable:
        return self.decoder.invoke(self.feature.invoke(*inputs))


class JointFeature:
    """An ordered structural product of two features over the same inputs."""

    def __init__(self, left: Module, right: Module, pair_cost: float) -> None:
        a, b = left.manifest, right.manifest
        if replace(a.contract, output=b.contract.output) != b.contract:
            raise ValueError("joint features must share inputs, slots and relevance")
        self.left, self.right = left, right

        def calls(expected: bool) -> tuple[Calls, ...]:
            counts = [(m.expected_calls if expected and m.expected_calls is not None else m.calls)
                      for m in (a, b)]
            if any(len(count) != len(a.contract.slots) for count in counts):
                return ()  # Never invent counts for undeclared slot usage.
            return tuple(Calls(x.fixed + y.fixed, x.per_element + y.per_element)
                         for x, y in zip(*counts, strict=True))

        effects = None if a.effects is None or b.effects is None else a.effects | b.effects
        self.manifest = Manifest(
            f"joint({a.ref},{b.ref})", "1",
            replace(a.contract, output=f"pair[{a.contract.output},{b.contract.output}]"),
            cost=a.cost + b.cost + pair_cost, calls=calls(False),
            expected_calls=calls(True) or None, effects=effects)

    def invoke(self, *inputs: Any) -> tuple[Any, Any]:
        return self.left.invoke(*inputs), self.right.invoke(*inputs)


def joint_features(features: Sequence[Module], *, max_size: int, limit: int,
                   pair_cost: float) -> list[Module]:
    """Enumerate nonempty feature subsets, smallest first, up to explicit bounds.

    Singletons preserve the supplied order. Larger subsets use index order and
    left-associated pairs, deriving structural interfaces automatically (§36.5).
    Feed the result to propose_decoders within the training callback. A limit
    truncates search deterministically; it does not establish exhaustiveness.
    All supplied features must share inputs, slots and relevance. Repeated
    evaluation is intentional; no purity or cacheability is inferred.
    """
    if max_size < 1 or limit < 1:
        raise ValueError("joint search bounds must be positive")
    if not math.isfinite(pair_cost) or pair_cost < 0:
        raise ValueError("pair cost must be finite and nonnegative")
    features = tuple(features)
    if features and any(replace(f.manifest.contract, output=features[0].manifest.contract.output)
                        != features[0].manifest.contract for f in features):
        raise ValueError("joint features must share inputs, slots and relevance")
    candidates = []
    for size in range(1, min(max_size, len(features)) + 1):
        for subset in combinations(features, size):
            feature = subset[0]
            for other in subset[1:]:
                feature = JointFeature(feature, other, pair_cost)
            candidates.append(feature)
            if len(candidates) == limit:
                return candidates
    return candidates


def propose_decoders(incumbent: Module, features: Sequence[Module],
                     rows: Sequence[tuple[Any, ...]], labels: Sequence[Hashable], *,
                     decoder_cost: float) -> list[Proposal]:
    """Learn decompositions through supplied features from training data alone.

    Derive each decoder's contract from its feature's output and the incumbent's
    output. For every observed feature key, learn the modal target. This minimizes
    empirical classification errors among tables on that representation (§36.4).
    Feature inputs, slots and relevance must match the incumbent; their outputs
    may differ. No feature or value type is predefined here. Use this as discover's
    training callback: it performs no independent split or evidence selection.
    Features must remain fixed after training; nothing is saved or calibrated.
    """
    if not math.isfinite(decoder_cost) or decoder_cost < 0:
        raise ValueError("decoder cost must be finite and nonnegative")
    if not rows or len(rows) != len(labels):
        raise ValueError("decoder training needs nonempty aligned rows and labels")
    contract = incumbent.manifest.contract
    if any(len(row) != len(contract.slots) + len(contract.inputs) for row in rows):
        raise ValueError("rows must supply slot fillings followed by inputs")
    features = tuple(features)
    if any(replace(feature.manifest.contract, output=contract.output) != contract
           for feature in features):
        raise ValueError("features must preserve inputs, slots and relevance")
    fallback = Counter(labels).most_common(1)[0][0]
    proposals = []
    for feature in features:
        counts: dict[Hashable, Counter[Hashable]] = {}
        for row, label in zip(rows, labels, strict=True):
            counts.setdefault(feature.invoke(*row), Counter())[label] += 1
        table = {key: counter.most_common(1)[0][0] for key, counter in counts.items()}
        decoder = Decoder(Contract((feature.manifest.contract.output,), contract.output),
                          table, fallback, decoder_cost)
        proposals.append(Proposal(Decoded(feature, decoder, contract)))
    return proposals


def discover(incumbent: Module,
             propose: Callable[[Sequence[tuple[Any, ...]], Sequence[Any]], Sequence[Proposal]],
             rows: Sequence[tuple[Any, ...]], labels: Sequence[Any],
             correct: Callable[[Any, Any], bool], alpha: float = 0.05) -> Discovery:
    """Propose on the first half, test the frozen family on the second.

    Rows supply slot fillings before ordinary inputs, as in Module.invoke.
    Candidates preserve the external contract but may introduce new types and
    decompositions. Tests use alpha/count. Lowest accepted p-value wins, with
    ties in proposal order. Requires independent splits, honest scoring, and
    proposals that cannot inspect or mutate held-out samples. Snapshots are
    shallow; installation and calibration are separate decisions.
    """
    if not math.isfinite(alpha) or not 0 < alpha < 1:
        raise ValueError("alpha must be between zero and one")
    half = len(rows) // 2
    if not half or len(rows) != len(labels):
        raise ValueError("discovery needs at least two labeled rows")
    samples, targets = tuple(rows), tuple(labels)
    contract = incumbent.manifest.contract
    arity = len(contract.slots) + len(contract.inputs)
    if any(len(row) != arity for row in samples):
        raise ValueError("rows must supply slot fillings followed by the incumbent's inputs")
    proposals = tuple(propose(samples[:half], targets[:half]))
    for proposal in proposals:
        if proposal.expert.manifest.contract != incumbent.manifest.contract:
            raise ValueError("proposals must preserve the external contract")
    held = tuple(zip(samples[half:], targets[half:], strict=True))
    baseline = tuple(bool(correct(incumbent.invoke(*row), label)) for row, label in held)
    trials = []
    for proposal in proposals:
        outcomes = tuple(bool(correct(proposal.expert.invoke(*row), label)) for row, label in held)
        accepted, p_value = sign_test(baseline, outcomes, alpha / len(proposals))
        trials.append(Trial(proposal, outcomes, p_value, accepted))
    accepted_trials = [trial for trial in trials if trial.accepted]
    chosen = min(accepted_trials, key=lambda trial: trial.p_value).proposal if accepted_trials else None
    return Discovery(baseline, tuple(trials), chosen)


def discover_packages(
    incumbent: Module, store: Store,
    propose: Callable[[Sequence[tuple[Any, ...]], Sequence[Any]], Sequence[Ref]],
    rows: Sequence[tuple[Any, ...]], labels: Sequence[Any],
    correct: Callable[[Any, Any], bool], alpha: float = 0.05,
) -> Discovery:
    """Select reusable package exports trained only on the training split.

    The proposer stores its artifacts (including constructor declarations) and
    returns their references. All matching exports are frozen before evaluation;
    each spends one share of the family budget. A package with no matching
    export is an error. The chosen proposal retains its package reference and
    its expert's identity, so a saved store can reinstall it. Rejected artifacts
    remain in this candidate store; no active library or name is changed.

    As with discover, isolation, faithful entry points, and immutable artifacts
    are caller assumptions. This neither saves external weights nor calibrates
    experts or persists selection evidence.
    """
    def proposals(train: Sequence[tuple[Any, ...]], targets: Sequence[Any]) -> list[Proposal]:
        references = tuple(propose(train, targets))
        candidates = []
        for reference in references:
            matching = [expert for expert in install(store, reference)
                        if expert.manifest.contract == incumbent.manifest.contract]
            if not matching:
                raise ValueError("proposed package has no export with the external contract")
            candidates.extend(Proposal(expert, package=reference) for expert in matching)
        return candidates

    return discover(incumbent, proposals, rows, labels, correct, alpha)
