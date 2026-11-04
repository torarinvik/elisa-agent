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
from typing import Any

from nca.abi import Contract, Message, Module
from nca.evidence import route_risk
from nca.learning.affine import fit_affine
from nca.learning.discovery import fit_decoder
from nca.planner import plan
from nca.planner.gaps import repair
from nca.retention.acquisition import CertifiedAcquirer
from nca.retention import acquisition, sampled
from nca.native import load
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


def main() -> None:
    parser = argparse.ArgumentParser()
    parser.add_argument("--seeds", type=int, nargs="+", default=[3713, 3714, 3715])
    parser.add_argument("--numerics", action="store_true")
    args = parser.parse_args()
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
