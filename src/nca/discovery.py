"""Training-only proposals of interfaces and experts, selected by evidence (§36.3)."""

from __future__ import annotations

import math
from collections.abc import Callable, Sequence
from dataclasses import dataclass
from typing import Any

from nca.abi import Module
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
