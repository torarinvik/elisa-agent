"""Training-only proposals of interfaces and experts, selected by evidence (§36.3)."""

from __future__ import annotations

import json
import math
from collections import Counter, deque
from collections.abc import Callable, Hashable, Mapping, Sequence
from dataclasses import dataclass, field, replace
from itertools import combinations
from typing import Any

from nca.abi import Calls, Contract, Manifest, Module
from nca.effects import invoke_scoped
from nca.learning.evaluation import invoke_unary
from nca.objects import (Constructor, Json, Primitive, Ref, Store, canonical,
                         contract_data, contract_from, digest)
from nca.packages import install
from nca.router import sign_probability
from nca.value_codec import decode_value, encode_value


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


def fit_decoder(contract: Contract, keys: Sequence[Hashable], labels: Sequence[Hashable], *,
                cost: float) -> Decoder:
    """Fit a modal categorical head with a global training-mode fallback."""
    if not keys or len(keys) != len(labels) or len(contract.inputs) != 1 or contract.slots:
        raise ValueError("decoder fitting needs aligned nonempty data and a unary slot-free contract")
    if not math.isfinite(cost) or cost < 0:
        raise ValueError("decoder cost must be finite and nonnegative")
    counts: dict[Hashable, Counter[Hashable]] = {}
    for key, label in zip(keys, labels, strict=True):
        counts.setdefault(key, Counter())[label] += 1
    table = {key: count.most_common(1)[0][0] for key, count in counts.items()}
    return Decoder(contract, table, Counter(labels).most_common(1)[0][0], cost)


def _load_decoder(contract: Mapping[str, Any], table: list[list[Json]],
                  fallback: Json, cost: float, module_id: str = "learned-decoder") -> Decoder:
    """Interpret a stored finite head, preserving scalar values and equality."""
    parsed = contract_from(contract)
    if len(parsed.inputs) != 1 or parsed.slots:
        raise ValueError("a stored decoder needs one input and no slots")
    result = Decoder(parsed, {decode_value(key): decode_value(value) for key, value in table},
                     decode_value(fallback), cost)
    result.manifest = replace(result.manifest, module_id=module_id)
    return result


def decoder_object(decoder: Decoder, *, size: int) -> Primitive:
    """Snapshot a learned structural head as data for the generic decoder runtime.

    Its constructors must be stored before admission. Size is declared resident
    bytes, excluding dependencies. This does not install or calibrate the head.
    """
    table = [[encode_value(key), encode_value(value)] for key, value in decoder._table.items()]
    _load_decoder(contract_data(decoder.manifest.contract), table,
                  encode_value(decoder.fallback), decoder.manifest.cost)
    table.sort(key=lambda pair: canonical(pair[0]))
    arguments = {"contract": contract_data(decoder.manifest.contract), "table": table,
                 "fallback": encode_value(decoder.fallback), "cost": decoder.manifest.cost}
    manifest = replace(decoder.manifest, module_id=f"learned-decoder/{digest(arguments)}")
    arguments["module_id"] = manifest.module_id
    return Primitive(manifest, "nca/decoder@1", arguments, size=size)


class Decoded:
    """A feature expert followed by a unary head, with its original slots."""

    def __init__(self, feature: Module, decoder: Module, contract: Contract) -> None:
        if (replace(feature.manifest.contract, output=contract.output) != contract
                or decoder.manifest.contract != Contract((feature.manifest.contract.output,),
                                                          contract.output)):
            raise ValueError("composition needs matching source inputs and a unary slot-free head")
        self.feature, self.decoder = feature, decoder
        a, b = feature.manifest.effects, decoder.manifest.effects
        effects = None if a is None or b is None else a | b
        self.manifest = replace(feature.manifest,
                                module_id=f"{feature.manifest.module_id}/decoded",
                                contract=contract,
                                cost=feature.manifest.cost + decoder.manifest.cost, effects=effects)

    def invoke(self, *inputs: Any) -> Any:
        return invoke_unary(self, inputs, lambda m: (m.feature, m.decoder)
                            if m is self or type(m) is Decoded and "invoke" not in m.__dict__ else None)


def _total_calls(manifests: Sequence[Manifest], expected: bool = False) -> tuple[Calls, ...]:
    if not manifests:
        return ()
    counts = [(m.expected_calls if expected and m.expected_calls is not None else m.calls)
              for m in manifests]
    if any(len(count) != len(manifests[0].contract.slots) for count in counts):
        return ()  # Never invent counts for undeclared slot usage.
    return tuple(Calls(sum(c.fixed for c in group), sum(c.per_element for c in group))
                 for group in zip(*counts, strict=True))


class JointFeature:
    """An ordered structural product of two features over the same inputs."""

    def __init__(self, left: Module, right: Module, pair_cost: float) -> None:
        if not math.isfinite(pair_cost) or pair_cost < 0:
            raise ValueError("pair cost must be finite and nonnegative")
        a, b = left.manifest, right.manifest
        if replace(a.contract, output=b.contract.output) != b.contract:
            raise ValueError("joint features must share inputs, slots and relevance")
        self.left, self.right, self.pair_cost = left, right, pair_cost

        effects = None if a.effects is None or b.effects is None else a.effects | b.effects
        self.manifest = Manifest(
            f"joint({a.ref},{b.ref})", "1",
            replace(a.contract, output=f"pair[{a.contract.output},{b.contract.output}]"),
            cost=a.cost + b.cost + pair_cost, calls=_total_calls((a, b)),
            expected_calls=_total_calls((a, b), True) or None, effects=effects)

    def invoke(self, *inputs: Any) -> tuple[Any, Any]:
        return invoke_scoped(self.left, *inputs), invoke_scoped(self.right, *inputs)


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
    proposals = []
    for feature in features:
        decoder = fit_decoder(Contract((feature.manifest.contract.output,), contract.output),
                              tuple(invoke_scoped(feature, *row) for row in rows), labels,
                              cost=decoder_cost)
        proposals.append(Proposal(Decoded(feature, decoder, contract)))
    return proposals


@dataclass(eq=False)
class _Decision:
    fallback: Hashable
    counts: tuple[tuple[Hashable, int], ...]
    feature: int | None = None
    children: dict[Hashable, _Decision] = field(default_factory=dict)


class FeatureTree:
    """A learned conditional decomposition with modal fallback on unseen keys."""

    def __init__(self, features: Sequence[Module], root: _Decision, manifest: Manifest, *,
                 projection_states: int = 0, projection_exhausted: bool = False) -> None:
        self.features, self.root, self.manifest = tuple(features), root, manifest
        self.projection_states = projection_states
        self.projection_exhausted = projection_exhausted

    def invoke(self, *inputs: Any) -> Hashable:
        return self._state(*inputs).fallback

    def _state(self, *inputs: Any) -> _Decision:
        node = self.root
        while node.feature is not None:
            key = invoke_scoped(self.features[node.feature], *inputs)
            child = node.children.get(key)
            if child is None:
                return node
            node = child
        return node


class TreeStateEncoder:
    """A trained tree exposing its learned empirical-state code (§36.8)."""

    def __init__(self, tree: FeatureTree, constructor: Constructor,
                 codes: Mapping[_Decision, int], cost: float) -> None:
        self.tree, self.constructor, self._codes = tree, constructor, dict(codes)
        self.manifest = replace(tree.manifest, module_id=f"{tree.manifest.module_id}/state",
                                contract=replace(tree.manifest.contract, output=constructor.type()),
                                cost=tree.manifest.cost + cost)

    def invoke(self, *inputs: Any) -> int:
        return self._codes[self.tree._state(*inputs)]


def factor_tree(tree: FeatureTree, *, encoding_cost: float, decoder_cost: float) -> Proposal:
    """Derive a learned type and prediction-preserving encoder/head proposal.

    The codebook records each node's counts and tie choice, not calibrated
    probabilities. Codes follow canonical record order; identical records share
    a code. Labels must be JSON scalars, faithfully encoded without repr or
    coercion. Every possible stopping node is covered, including unseen-key
    fallbacks. The tree and features must remain fixed after factoring.
    Only the type object is persistable here; the executable proposal remains
    in memory and is neither installed nor calibrated.
    """
    if any(not math.isfinite(cost) or cost < 0 for cost in (encoding_cost, decoder_cost)):
        raise ValueError("factorization costs must be finite and nonnegative")
    records: dict[_Decision, bytes] = {}
    pending = [tree.root]
    while pending:
        node = pending.pop()
        if any(type(label) not in (str, int, float, bool, type(None)) for label, _ in node.counts):
            raise TypeError("tree state factoring requires JSON scalar labels")
        counts = sorted(node.counts, key=lambda item: canonical(item[0]))
        records[node] = canonical({"counts": counts, "chosen": node.fallback})
        pending.extend(node.children.values())
    unique = sorted(set(records.values()))
    positions = {record: index for index, record in enumerate(unique)}
    meaning = canonical({"format": "empirical-node-counts-v1",
                         "target": tree.manifest.contract.output,
                         "states": [json.loads(record) for record in unique]}).decode()
    constructor = Constructor("learned-tree-states", "1", 0, meaning)
    encoder = TreeStateEncoder(tree, constructor,
                               {node: positions[record] for node, record in records.items()},
                               encoding_cost)
    table = {positions[record]: node.fallback for node, record in records.items()}
    decoder = Decoder(Contract((constructor.type(),), tree.manifest.contract.output),
                      table, tree.root.fallback, decoder_cost)
    return Proposal(Decoded(encoder, decoder, tree.manifest.contract), (constructor,))


def train_tree(incumbent: Module, features: Sequence[Module],
               rows: Sequence[tuple[Any, ...]], labels: Sequence[Hashable], *,
               max_nodes: int, overhead_cost: float, lookahead: int = 1,
               lookahead_budget: int | None = None,
               refine: Callable[[Sequence[tuple[Any, ...]], Sequence[Hashable]],
                                Sequence[Module]] | None = None) -> FeatureTree:
    """Fit a breadth-first categorical feature tree on training data only (§36.6).

    Splits maximize projected modal successes, then minimize projected declared
    feature cost, then use feature order. No gain is required, allowing
    interactions. Each feature is used at most once per path.
    The node budget includes leaves; a split is admitted only if all its children
    fit. No global optimality, generalization, persistence or calibration is
    claimed. Fixed features and stable, hashable keys/labels are assumptions.
    Declared cost and slot calls conservatively sum all features used anywhere
    in the tree, plus the caller's whole-tree overhead bound. Horizons above one
    require an explicit projection-state budget (§36.7). Exhaustion falls back
    to modal leaves during projection and is reported on the returned tree.
    Projection does not optimize allocation of the global final-node budget.
    An optional trainer can propose new features on each unresolved training
    subset (§36.15). They are scoped to that subtree. Projection uses only
    already fitted features; samples and fitted experts must remain stable.
    """
    if max_nodes < 1 or not rows or len(rows) != len(labels):
        raise ValueError("tree training needs a positive node budget and aligned nonempty data")
    if not math.isfinite(overhead_cost) or overhead_cost < 0:
        raise ValueError("tree overhead must be finite and nonnegative")
    if lookahead < 1 or (lookahead_budget is not None and lookahead_budget < 1):
        raise ValueError("lookahead and its work budget must be positive")
    if lookahead > 1 and lookahead_budget is None:
        raise ValueError("lookahead above one needs an explicit work budget")
    contract = incumbent.manifest.contract
    features, rows, labels = list(features), tuple(rows), tuple(labels)
    if any(len(row) != len(contract.slots) + len(contract.inputs) for row in rows):
        raise ValueError("rows must supply slot fillings followed by inputs")
    def validate(feature: Module) -> None:
        manifest = feature.manifest
        if replace(manifest.contract, output=contract.output) != contract:
            raise ValueError("features must preserve inputs, slots and relevance")
        if not math.isfinite(manifest.cost) or manifest.cost < 0 or any(
                not math.isfinite(c.fixed) or not math.isfinite(c.per_element)
                or c.fixed < 0 or c.per_element < 0 for c in manifest.calls):
            raise ValueError("feature costs and slot counts must be finite and nonnegative")
    for feature in features:
        validate(feature)
    values: list[Sequence[Any] | Mapping[int, Any]] = [
        tuple(invoke_scoped(feature, *row) for row in rows) for feature in features]

    def groups_for(indices: tuple[int, ...], feature: int) -> dict[Hashable, list[int]]:
        groups: dict[Hashable, list[int]] = {}
        for i in indices:
            groups.setdefault(values[feature][i], []).append(i)
        return groups

    expanded, exhausted = 0, False
    projections: dict[tuple[tuple[int, ...], tuple[int, ...], int], tuple[int, float]] = {}

    def project(indices: tuple[int, ...], available: tuple[int, ...],
                depth: int) -> tuple[int, float]:
        nonlocal expanded, exhausted
        key = indices, available, depth
        if key in projections:
            return projections[key]
        modal = Counter(labels[i] for i in indices).most_common(1)[0][1]
        best = modal, 0.0
        if depth == 0 or modal == len(indices) or not available:
            return best
        if expanded >= (lookahead_budget or 0):
            exhausted = True
            return best
        expanded += 1
        for feature in available:
            groups = groups_for(indices, feature)
            if len(groups) < 2:
                continue
            others = tuple(f for f in available if f != feature)
            children = [project(tuple(group), others, depth - 1) for group in groups.values()]
            score = sum(child[0] for child in children)
            effort = features[feature].manifest.cost * len(indices) + sum(c[1] for c in children)
            if (score, -effort) > (best[0], -best[1]):
                best = score, effort
        projections[key] = best
        return best

    root_counts = Counter(labels)
    root = _Decision(root_counts.most_common(1)[0][0], tuple(root_counts.items()))
    pending = deque([(root, tuple(range(len(rows))), tuple(range(len(features))))])
    remaining, used = max_nodes - 1, set()
    while pending:
        node, indices, available = pending.popleft()
        if len({labels[i] for i in indices}) == 1 or remaining < 2:
            continue
        if refine is not None:
            acquired = tuple(refine(tuple(rows[i] for i in indices),
                                    tuple(labels[i] for i in indices)))
            for feature in acquired:
                validate(feature)
            new_indices = tuple(range(len(features), len(features) + len(acquired)))
            for feature in acquired:
                values.append({i: invoke_scoped(feature, *rows[i]) for i in indices})
            features.extend(acquired)
            available += new_indices
        best: tuple[int, dict[Hashable, list[int]]] | None = None
        best_rank: tuple[int, float] = (-1, 0)
        for feature in available:
            groups = groups_for(indices, feature)
            if not 1 < len(groups) <= remaining:
                continue
            others = tuple(f for f in available if f != feature)
            children = [project(tuple(group), others, lookahead - 1) for group in groups.values()]
            score = sum(child[0] for child in children)
            effort = features[feature].manifest.cost * len(indices) + sum(c[1] for c in children)
            rank = score, -effort
            if rank > best_rank:
                best, best_rank = (feature, groups), rank
        if best is None:
            continue
        feature, groups = best
        node.feature = feature
        used.add(feature)
        remaining -= len(groups)
        for key, group in groups.items():
            counts = Counter(labels[i] for i in group)
            child = _Decision(counts.most_common(1)[0][0], tuple(counts.items()))
            node.children[key] = child
            pending.append((child, tuple(group), tuple(f for f in available if f != feature)))
    manifests = [features[i].manifest for i in sorted(used)]
    effects = (None if any(m.effects is None for m in manifests)
               else frozenset().union(*(m.effects for m in manifests)))
    manifest = Manifest("learned-feature-tree", "1", contract,
                        cost=overhead_cost + sum(m.cost for m in manifests),
                        calls=(_total_calls(manifests) if manifests else
                               tuple(Calls() for _ in contract.slots)), effects=effects)
    return FeatureTree(features, root, manifest, projection_states=expanded,
                       projection_exhausted=exhausted)


class Corrected:
    """A learned local correction, otherwise delegating to the incumbent."""

    def __init__(self, incumbent: Module, feature: Module,
                 corrections: Mapping[Hashable, Hashable], cost: float) -> None:
        if not math.isfinite(cost) or cost < 0:
            raise ValueError("correction cost must be finite and nonnegative")
        if (replace(feature.manifest.contract, output=incumbent.manifest.contract.output)
                != incumbent.manifest.contract):
            raise ValueError("correction feature must preserve inputs, slots and relevance")
        self.incumbent, self.feature = incumbent, feature
        self.overhead_cost = cost
        self.corrections = dict(corrections)
        a, b = incumbent.manifest, feature.manifest
        effects = None if a.effects is None or b.effects is None else a.effects | b.effects
        self.manifest = replace(a, module_id=f"{a.module_id}/corrected/{b.module_id}",
                                cost=a.cost + b.cost + cost, calls=_total_calls((a, b)),
                                expected_calls=None, effects=effects)

    def invoke(self, *inputs: Any) -> Any:
        key = invoke_scoped(self.feature, *inputs)
        if key in self.corrections:
            return self.corrections[key]
        return invoke_scoped(self.incumbent, *inputs)


def propose_corrections(incumbent: Module, features: Sequence[Module],
                        rows: Sequence[tuple[Any, ...]], labels: Sequence[Hashable], *,
                        correction_cost: float, preserve_successes: bool = False) -> list[Proposal]:
    """Fit only feature regions improving on incumbent training accuracy (§36.12).

    Use inside discover's training callback. Equality defines correctness here;
    keys/labels must be stable and hashable. Unseen keys retain the incumbent.
    Empty corrections yield no proposal. Cost and slot declarations include
    both experts conservatively; no persistence or risk certificate is claimed.
    With preserve_successes, reject a key's constant correction if it would
    break any incumbent-successful training example in that key. This is a
    finite retained-control guarantee, not a claim about unseen inputs.
    """
    if not rows or len(rows) != len(labels):
        raise ValueError("correction training needs aligned nonempty rows and labels")
    if not math.isfinite(correction_cost) or correction_cost < 0:
        raise ValueError("correction cost must be finite and nonnegative")
    contract = incumbent.manifest.contract
    features = tuple(features)
    if any(len(row) != len(contract.slots) + len(contract.inputs) for row in rows):
        raise ValueError("rows must supply slot fillings followed by inputs")
    if any(replace(f.manifest.contract, output=contract.output) != contract for f in features):
        raise ValueError("features must preserve inputs, slots and relevance")
    baseline = [invoke_scoped(incumbent, *row) == label for row, label in zip(rows, labels, strict=True)]
    proposals = []
    for feature in features:
        counts: dict[Hashable, Counter[Hashable]] = {}
        successes: Counter[Hashable] = Counter()
        protected: dict[Hashable, set[Hashable]] = {}
        for row, label, correct in zip(rows, labels, baseline, strict=True):
            key = invoke_scoped(feature, *row)
            counts.setdefault(key, Counter())[label] += 1
            successes[key] += int(correct)
            if correct:
                protected.setdefault(key, set()).add(label)
        corrections = {}
        for key, count in counts.items():
            label, mass = count.most_common(1)[0]
            if mass > successes[key] and (not preserve_successes or
                                         protected.get(key, set()) <= {label}):
                corrections[key] = label
        if corrections:
            proposals.append(Proposal(Corrected(incumbent, feature, corrections, correction_cost)))
    return proposals


def discover(incumbent: Module,
             propose: Callable[[Sequence[tuple[Any, ...]], Sequence[Any]], Sequence[Proposal]],
             rows: Sequence[tuple[Any, ...]], labels: Sequence[Any],
             correct: Callable[[Any, Any], bool], alpha: float = 0.05) -> Discovery:
    """Propose on the first half, test the frozen family on the second.

    Rows supply slot fillings before ordinary inputs, as in Module.invoke.
    Candidates preserve the external contract but may introduce new types and
    decompositions. Tests use alpha/count. Lowest accepted p-value wins, with
    ties in proposal order. Acceptance/ranking use exact rational tails; reported
    float p-values can underflow. Requires independent splits, honest scoring, and
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
    baseline = tuple(bool(correct(invoke_scoped(incumbent, *row), label)) for row, label in held)
    trials = []
    probabilities = []
    for proposal in proposals:
        outcomes = tuple(bool(correct(invoke_scoped(proposal.expert, *row), label)) for row, label in held)
        probability = sign_probability(baseline, outcomes)
        probabilities.append(probability)
        trials.append(Trial(proposal, outcomes, float(probability),
                            probability * len(proposals) < alpha))
    accepted_indices = [i for i, trial in enumerate(trials) if trial.accepted]
    chosen = (trials[min(accepted_indices, key=lambda i: probabilities[i])].proposal
              if accepted_indices else None)
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
