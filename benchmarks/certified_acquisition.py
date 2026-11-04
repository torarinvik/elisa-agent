"""Generalizing versus memorizing acquisition, with and without certificates
(§20.9).

Types encode one latent integer in [0, 10^6): most by a private affine code,
a quarter by a private scrambled code no affine map recovers. A sequence of
tasks asks for translations between random types; the library persists, and
connectors are acquired by ``planner.gaps.repair`` (at most three missing).
``table`` fits lookup tables and admits them unchecked; ``table_cert`` and
``affine_cert`` admit through ``retention.acquisition.CertifiedAcquirer``
(zero errors on fresh cases). Every served task is evaluated on fresh latent
values. Measures served fraction, accuracy, labels, and how often the
certified route risk falls below the measured error.
Run: python benchmarks/certified_acquisition.py.
"""

from __future__ import annotations

import argparse
import json
import math
import random
import statistics
from functools import partial
from collections.abc import Hashable, Sequence
from time import process_time
from fractions import Fraction
from typing import Any

from nca.abi import Contract, Manifest, Message, Module
from nca.evidence import route_risk
from nca.learning.affine import fit_affine
from nca.learning.discovery import fit_decoder
from nca.planner import plan
from nca.planner.gaps import repair
from nca.retention.acquisition import CertifiedAcquirer
from nca.retention.certification import zero_loss_test
from nca.retention import acquisition, sampled
from nca.native import load
from nca.stats import family_audit_alpha
from nca.runtime import execute
from nca.workspace import Workspace

TYPES, SCRAMBLED, SPAN, TRAIN, TASKS, EVAL = 12, 3, 10 ** 6, 256, 40, 200
TOLERANCE = CONFIDENCE = 0.05


def run(policy: str, seed: int) -> dict[str, float]:
    rng = random.Random(seed)
    names = [f"t{k}" for k in range(TYPES)]
    index = {name: k for k, name in enumerate(names)}
    slopes = [rng.choice((-3, -2, 2, 3, 5)) for _ in range(TYPES)]
    offsets = [rng.randrange(-1000, 1000) for _ in range(TYPES)]
    keys = [rng.randrange(1, 2 ** 31) for _ in range(TYPES)]

    def encode(k: int, v: int) -> float:
        if k < SCRAMBLED:
            return float((v * keys[k] + 12345) % 2 ** 31)
        return float(slopes[k] * v + offsets[k])

    def sample(contract: Contract, count: int) -> list[tuple[Any, Any]]:
        i, j = index[contract.inputs[0]], index[contract.output]
        return [(encode(i, v), encode(j, v)) for v in (rng.randrange(SPAN) for _ in range(count))]

    def close(output: Any, label: Any) -> bool:
        return isinstance(output, float) and abs(output - label) < 0.5

    labels = 0

    def table(contract: Contract) -> Module | None:
        nonlocal labels
        rows = sample(contract, TRAIN)
        labels += TRAIN
        return fit_decoder(contract, [k for k, _ in rows], [v for _, v in rows], cost=1.0)

    def affine(contract: Contract, xs: Any, ys: Any) -> Module | None:
        try:
            return fit_affine(contract, xs, ys, cost=1.0)
        except ValueError:
            return None

    fitter = {"table_cert": partial(fit_decoder, cost=1.0), "affine_cert": affine}.get(policy)
    acquirer = None if fitter is None else CertifiedAcquirer(
        fitter, sample, train=TRAIN if policy == "table_cert" else 8, tolerance=TOLERANCE,
        confidence=CONFIDENCE, agree=close)
    library: list[Module] = []
    served = correct = total = violations = certified_routes = 0
    for _ in range(TASKS):
        i, j = rng.sample(range(TYPES), 2)
        route = plan(library, (names[i],), names[j])
        if route is None:
            result = repair(library, (names[i],), names[j], acquirer or table, attempts=60,
                            missing=3)
            if result is None:
                continue
            library += result.acquired
            route = result.route
        served += 1
        right = 0
        for v in (rng.randrange(SPAN) for _ in range(EVAL)):
            out = execute(route, (Message(names[i], encode(i, v), "input"),), Workspace(), 16)
            right += close(out.payload, encode(j, v))
        correct, total = correct + right, total + EVAL
        if acquirer is not None:
            bound = route_risk(route, acquirer.rate)
            if bound is not None:
                certified_routes += 1
                violations += bound < 1 - right / EVAL
    return {"served": served / TASKS, "accuracy": correct / total if total else 0.0,
            "labels": labels + (acquirer.labels if acquirer else 0),
            "certified_routes": certified_routes / TASKS,
            "bound_violations": violations / certified_routes if certified_routes else 0.0}


def legacy_required_cases(tolerance: float, level: float) -> int:
    """Pre-43.13 reciprocal and floating-quotient reference."""
    if not 0 < tolerance < 1 or not 0 < level < 1:
        raise ValueError("invalid parameters")
    need = math.log(1 / level)
    cases = max(1, math.ceil(need / tolerance))
    while need > tolerance * cases:
        cases += 1
    return cases


def sizing_trial(policy: str, repeats: int = 1000) -> dict[str, float | int]:
    pairs = ((0.05, 0.025), (0.05, 1e-320), (0.05, math.ulp(0.0)),
             (1e-320, 0.025), (math.ulp(0.0), 0.025), (0.05, math.nextafter(1.0, 0.0)))
    old = sampled._LOG_UPPER
    sampled._LOG_UPPER = getattr(load("stats"), "negative_log_upper", None) if policy == "elisa" else None
    count = legacy_required_cases if policy == "legacy" else sampled.required_cases
    started = process_time()
    completed = errors = max_bits = 0
    try:
        for _ in range(repeats):
            for tolerance, level in pairs:
                try:
                    result = count(tolerance, level)
                except OverflowError:
                    errors += 1
                else:
                    completed += 1
                    max_bits = max(max_bits, result.bit_length())
    finally:
        sampled._LOG_UPPER = old
    return {"sizing_attempts": repeats * len(pairs), "completed": completed,
            "overflow_errors": errors, "largest_count_bits": max_bits,
            "labels": 0, "expert_requests": 0, "cpu_seconds": process_time() - started}


def extreme_acquisition_trial(policy: str) -> dict[str, float | int]:
    old_log, old_size = sampled._LOG_UPPER, acquisition.required_cases
    sampled._LOG_UPPER = getattr(load("stats"), "negative_log_upper", None) if policy == "elisa" else None
    acquisition.required_cases = legacy_required_cases if policy == "legacy" else sampled.required_cases
    fits = 0

    def fitting(contract: Contract, keys: Sequence[Hashable], labels: Sequence[Hashable]) -> Module:
        nonlocal fits
        fits += 1
        return fit_decoder(contract, keys, labels, cost=1.0)

    def sampling(contract: Contract, count: int) -> list[tuple[Any, Any]]:
        return [(0, 0)] * count  # Fresh IID draws from a constant operating distribution.

    acquire = None
    started = process_time()
    accepted = errors = 0
    try:
        try:
            acquire = CertifiedAcquirer(fitting, sampling, train=1, tolerance=0.5, confidence=1e-320)
            accepted = int(acquire(Contract(("source",), "target")) is not None)
        except OverflowError:
            errors = 1
    finally:
        sampled._LOG_UPPER, acquisition.required_cases = old_log, old_size
    return {"acquisition_attempts": 1, "accepted": accepted, "overflow_errors": errors,
            "labels": 0 if acquire is None else acquire.labels, "fits": fits,
            "decisions": 0 if acquire is None else acquire.decisions,
            "cpu_seconds": process_time() - started}


def legacy_decision_share(total: float, index: int) -> float:
    return total / ((index + 1) * (index + 2))


def legacy_family_share(total: float, count: int) -> float:
    level = total / count
    if count > 1:
        level = math.nextafter(level, 0.0)
    if level <= 0:
        raise ValueError("audit confidence allocation underflow")
    return level


def allocation_trial(legacy: bool, count: int = 10000) -> dict[str, float | int]:
    decision = legacy_decision_share if legacy else sampled.decision_level
    family = legacy_family_share if legacy else family_audit_alpha
    upward = route_upward = avoidable = unrepresentable = 0
    for index in range(count):
        parent = decision(0.05, index)
        target = Fraction(0.05) / ((index + 1) * (index + 2))
        upward += Fraction(parent) > target
        share = parent / 3 if legacy else family(parent, 3)
        route_upward += 3 * Fraction(share) > Fraction(parent)
    tiny = math.ulp(0.0)
    for units in range(1, 21):
        for size in range(1, 21):
            target = Fraction(units * tiny) / size
            try:
                family(units * tiny, size)
            except ValueError:
                if target >= Fraction(tiny):
                    avoidable += 1
                else:
                    unrepresentable += 1
    # Time only the allocation path, excluding the exact-rational audit above.
    started = process_time()
    for index in range(count):
        parent = decision(0.05, index)
        if legacy:
            _ = parent / 3
        else:
            family(parent, 3)
    return {"decisions": count, "route_splits": count, "upward_decision_shares": upward,
            "upward_route_families": route_upward, "avoidable_subnormal_refusals": avoidable,
            "unrepresentable_subnormal_refusals": unrepresentable,
            "labels": 0, "expert_requests": 0, "allocation_cpu_seconds": process_time() - started}


def staged_allocation_trial(legacy: bool) -> dict[str, float | int]:
    saved = acquisition.decision_level, acquisition.family_audit_alpha
    if legacy:
        acquisition.decision_level, acquisition.family_audit_alpha = legacy_decision_share, legacy_family_share
    fits = 0

    def fitting(contract: Contract, keys: Sequence[Hashable], labels: Sequence[Hashable]) -> Module:
        nonlocal fits
        fits += 1
        return fit_decoder(contract, keys, labels, cost=1.0)

    def sampling(contract: Contract, count: int) -> list[tuple[Any, Any]]:
        return [(0, 0)] * count

    started = process_time()
    acquire = CertifiedAcquirer(fitting, sampling, train=2, stages=(1, 2), tolerance=0.5,
                                 confidence=4 * math.ulp(0.0))
    accepted = refused = 0
    try:
        try:
            accepted = int(acquire(Contract(("source",), "target")) is not None)
        except ValueError:
            refused = 1
    finally:
        acquisition.decision_level, acquisition.family_audit_alpha = saved
    return {"requests": 1, "accepted": accepted, "allocation_refusals": refused,
            "fits": fits, "labels": acquire.labels, "decisions": acquire.decisions,
            "cpu_seconds": process_time() - started}


def batching_trial(limit: int | None, loss: float, seed: int) -> dict[str, float]:
    """Isolate label overshoot versus sampler calls on fixed IID outcome streams.

    No fitting or domain implementation is involved; each request tests a frozen
    candidate's pre-generated 512 outcomes. Randomness is independent of batching.
    CPU includes outcome generation identically in every policy.
    """
    rng = random.Random(seed)
    labels = evaluations = calls = accepted = overshoot = 0
    started = process_time()
    requests, size = 1000, 512
    for _ in range(requests):
        outcomes = tuple(rng.random() >= loss for _ in range(size))
        cursor = scored = 0

        def draw(count: int) -> tuple[bool, ...]:
            nonlocal cursor, calls
            calls += 1
            held = outcomes[cursor:cursor + count]
            cursor += len(held)
            return held

        def agree(outcome: bool) -> bool:
            nonlocal scored
            scored += 1
            return outcome

        result = zero_loss_test(draw, agree, cases=size, batch_limit=limit)
        assert result.passed == all(outcomes)
        assert result.drawn == cursor
        if limit is not None:
            assert cursor - scored < limit
        accepted += bool(result.passed)
        labels += cursor
        evaluations += scored
        overshoot += cursor - scored
    return {"requests": requests, "fits": 0, "accepted": accepted,
            "labels": labels, "evaluations": evaluations, "sampler_calls": calls,
            "unscored_labels": overshoot, "cpu_seconds": process_time() - started}


def noisy_trial(fixed: bool, loss: float, seed: int) -> dict[str, float]:
    """Known constant predictor under IID observation noise; no learner claim.

    Each request receives the same random prefix across policies, but shares
    the acquirer's non-reset confidence budget with all preceding requests.
    More successful admissions can require many more validation labels.
    """
    contract = Contract(("observation",), "label")
    fits = evaluated = cursor = 0
    rng = random.Random(seed)

    class Candidate:
        manifest = Manifest("constant-candidate", "1", contract, effects=frozenset())

        def invoke(self, value: Any) -> int:
            nonlocal evaluated
            evaluated += 1
            return 0

    def fit(*args: Any) -> Module:
        nonlocal fits
        fits += 1
        return Candidate()

    def sample(request: Contract, count: int) -> list[tuple[Any, Any]]:
        nonlocal cursor
        rows = [((attempt, i), int(rng.random() < loss)) for i in range(cursor, cursor+count)]
        cursor += count
        return rows

    started = process_time()
    acquire = CertifiedAcquirer(fit, sample, train=1, tolerance=0.2, confidence=0.1,
                                validation_cases=256 if fixed else None)
    accepted = 0
    for attempt in range(20):
        rng = random.Random(seed + attempt * 1000)
        cursor = 0
        accepted += acquire(contract) is not None
    return {"requests": 20, "decisions": acquire.decisions, "fits": fits, "accepted": accepted,
            "labels": acquire.labels, "evaluations": evaluated,
            "cpu_seconds": process_time() - started}


def main() -> None:
    parser = argparse.ArgumentParser()
    parser.add_argument("--seeds", type=int, nargs="+", default=[3713, 3714, 3715])
    parser.add_argument("--numerics", action="store_true")
    parser.add_argument("--budget-allocation", action="store_true")
    parser.add_argument("--batching", action="store_true")
    parser.add_argument("--noisy", action="store_true")
    args = parser.parse_args()
    if args.noisy:
        for loss in (0.0, 0.05, 0.4):
            for fixed in (False, True):
                runs = [noisy_trial(fixed, loss, seed) for seed in args.seeds]
                print(json.dumps({"loss": loss, "fixed_cases": fixed, **{
                    key: statistics.mean(run[key] for run in runs) for key in runs[0]}}), flush=True)
        return
    if args.batching:
        for loss in (0.0, 0.01, 0.1):
            for limit in (None, 32, 8, 1):
                runs = [batching_trial(limit, loss, seed) for seed in args.seeds]
                print(json.dumps({"loss": loss, "batch_limit": limit, **{
                    key: statistics.mean(run[key] for run in runs) for key in runs[0]}}), flush=True)
        return
    if args.budget_allocation:
        for legacy in (True, False):
            for name, trial in (("allocation", allocation_trial), ("staged", staged_allocation_trial)):
                runs = [trial(legacy) for _ in range(3)]
                print(json.dumps({"trial": name, "legacy": legacy, **{
                    key: statistics.mean(run[key] for run in runs) for key in runs[0]}}), flush=True)
        return
    if args.numerics:
        policies = ["legacy", "python"]
        if getattr(load("stats"), "negative_log_upper", None) is not None:
            policies.append("elisa")
        for policy in policies:
            runs = [sizing_trial(policy) for _ in range(3)]
            print(json.dumps({"trial": "sizing", "policy": policy, **{
                key: statistics.mean(run[key] for run in runs) for key in runs[0]}}), flush=True)
            runs = [extreme_acquisition_trial(policy) for _ in range(3)]
            print(json.dumps({"trial": "acquisition", "policy": policy, **{
                key: statistics.mean(run[key] for run in runs) for key in runs[0]}}), flush=True)
        return
    for policy in ("table", "table_cert", "affine_cert"):
        runs = [run(policy, seed) for seed in args.seeds]
        print(json.dumps({"policy": policy, **{
            key: (statistics.mean(r[key] for r in runs), statistics.stdev(r[key] for r in runs))
            for key in runs[0]}}))


if __name__ == "__main__":
    main()
