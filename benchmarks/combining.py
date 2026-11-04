"""Acquiring experts that combine inputs (§20.9).

A latent pair (u, v) of values below 16. Source types carry u or v alone under
private codes, each with a few derived types reached by exact connectors, and
goal types carry (u + v) mod 16 under private codes. A task gives one u-type
and one v-type and asks for a goal type. Connectors are acquired through
``planner.gaps.repair`` with ``retention.acquisition.CertifiedAcquirer`` over a
lookup table on input tuples: no expert reading one input can be certified.
``unary`` allows one-input gaps only; ``binary`` allows two inputs. Their
``_screen`` variants check a 64-case prefix before fitting. Measures served
fraction, accuracy on all value pairs, requests, labels, fits and CPU time.
The ``_memory`` policies add durable scoped refusal history; ``requests``
counts new acquisition attempts and ``cached_requests`` the avoided attempts.
``binary_staged_memory`` tries increasing training sizes, certifying each
candidate on fresh cases with a separate share of the request's confidence.
``fitted_cases`` counts all examples processed across fits, including reuse.
The ``isolated`` policies start each task with a fresh base library; ``ranked``
transfers only learned acquisition priorities between those deployments. They
are compared against each other, separately from expert-retaining policies.
Run: python benchmarks/combining.py.
"""

from __future__ import annotations

import argparse
import json
import random
import statistics
import time
import tempfile
from pathlib import Path
from collections.abc import Callable, Hashable, Sequence
from typing import Any

from nca.abi import Contract, Manifest, Message, Module
from nca.effects import effect_scope, expert_scope
from nca.memory import MemoryStore
from nca.planner import plan
from nca.planner.gaps import repair
from nca.retention.acquisition import CertifiedAcquirer
from nca.retention.screening import FeasibilityScreen
from nca.retention import screening
from nca.retention.history import AcquisitionHistory
from nca.runtime import execute
from nca.workspace import Workspace

VALUES, DERIVED, GOALS, TASKS, TRAIN = 16, 2, 3, 20, 4096


class Table:
    """A lookup table on input tuples, answering ``None`` off the table."""

    def __init__(self, contract: Contract, table: dict[Any, Any]) -> None:
        self.table = table
        self.manifest = Manifest("table", "1", contract, cost=1.0, effects=frozenset())

    def invoke(self, *values: Any) -> Any:
        return self.table.get(values if len(values) > 1 else values[0])


def fit(contract: Contract, keys: Sequence[Hashable], labels: Sequence[Hashable]) -> Module:
    return Table(contract, dict(zip(keys, labels, strict=True)))


def input_key(value: Any) -> Hashable:
    return value


def separates(a: Any, b: Any) -> bool:
    return bool(a != b)


class Exact:
    def __init__(self, source: str, target: str, table: dict[Any, Any]) -> None:
        self.table = table
        self.manifest = Manifest(f"{source}->{target}", "1", Contract((source,), target),
                                 effects=frozenset())

    def invoke(self, value: Any) -> Any:
        return self.table[value]


class LearnedPriority:
    """Benchmark policy: learn success frequencies by input count.

    This feature choice is an experimental model, not a core rule about which
    arities are useful. Unit attempt costs make the exchange score simply q.
    """

    def __init__(self) -> None:
        self.counts: dict[int, tuple[int, int]] = {}

    def score(self, contract: Contract) -> float:
        successes, attempts = self.counts.get(len(contract.inputs), (0, 0))
        return (successes + 1) / (attempts + 2)

    def observe(self, contract: Contract, success: bool) -> None:
        size = len(contract.inputs)
        successes, attempts = self.counts.get(size, (0, 0))
        self.counts[size] = (successes + success, attempts + 1)


def run(policy: str, seed: int) -> dict[str, float]:
    if not policy.endswith("_memory"):
        return _run(policy, seed, None)
    effects = frozenset({"benchmark.read", "benchmark.write"})
    with tempfile.TemporaryDirectory(prefix="nca-combining-history-") as directory:
        memory = MemoryStore(Path(directory) / "history.sqlite", capacity_bytes=10 ** 7,
                             read_effect="benchmark.read", write_effect="benchmark.write")
        history = AcquisitionHistory(memory, context=f"combining-v1/{seed}", type_id="record",
                                     producer="benchmark", entries=10000)
        try:
            with effect_scope(effects), expert_scope(effects):
                return _run(policy, seed, history)
        finally:
            memory.close()


def _run(policy: str, seed: int, history: AcquisitionHistory | None) -> dict[str, float]:
    rng = random.Random(seed)
    draws = random.Random(seed + 100000)
    tasks = random.Random(seed + 200000)
    started = time.process_time()
    fits = 0
    fitted_cases = 0
    meaning: dict[str, str] = {}
    codes: dict[str, list[int]] = {}
    library: list[Module] = []
    for part in ("u", "v"):
        for root in range(2):
            base = f"{part}{root}"
            meaning[base] = part
            codes[base] = rng.sample(range(VALUES), VALUES)
            for d in range(DERIVED):
                name = f"{base}d{d}"
                meaning[name], codes[name] = part, rng.sample(range(VALUES), VALUES)
                library.append(Exact(base, name, {f"{base}:{codes[base][x]}": f"{name}:{codes[name][x]}"
                                                  for x in range(VALUES)}))
    for g in range(GOALS):
        meaning[f"g{g}"], codes[f"g{g}"] = "sum", rng.sample(range(VALUES), VALUES)

    def value(name: str, u: int, v: int) -> str:
        latent = {"u": u, "v": v, "sum": (u + v) % VALUES}[meaning[name]]
        return f"{name}:{codes[name][latent]}"

    def sample(contract: Contract, count: int) -> list[tuple[Any, Any]]:
        rows = []
        for _ in range(count):
            u, v = draws.randrange(VALUES), draws.randrange(VALUES)
            key = tuple(value(t, u, v) for t in contract.inputs)
            rows.append((key if len(key) > 1 else key[0], value(contract.output, u, v)))
        return rows

    def counted_fit(contract: Contract, keys: Sequence[Hashable], labels: Sequence[Hashable]
                    ) -> Module:
        nonlocal fits, fitted_cases
        fits += 1
        fitted_cases += len(keys)
        return fit(contract, keys, labels)

    screen = (FeasibilityScreen(cases=64, confidence=0.05, key=input_key, separates=separates)
              if policy.endswith(("_screen", "_memory", "_ranked")) else None)
    acquirer = CertifiedAcquirer(counted_fit, sample, train=TRAIN, tolerance=0.05,
                                 confidence=0.05, screen=screen, history=history,
                                 stages=(64, 128, 256, 512, 1024, 2048, TRAIN)
                                 if "staged" in policy else None)
    served = correct = total = requests = 0
    priority = LearnedPriority() if policy.endswith("_ranked") else None
    base_library = tuple(library)

    def acquire(contract: Contract) -> Module | None:
        module = acquirer(contract)
        if priority is not None:
            priority.observe(contract, module is not None)
        return module

    for _ in range(TASKS):
        if "isolated" in policy:
            library = list(base_library)
        given = (f"u{tasks.randrange(2)}", f"v{tasks.randrange(2)}")
        goal = f"g{tasks.randrange(GOALS)}"
        route = plan(library, given, goal)
        if route is None:
            result = repair(library, given, goal, acquire, attempts=200,
                            arity=2 if policy.startswith("binary") else 1,
                            priority=priority.score if priority is not None else None)
            if result is None:
                continue
            requests += result.requests
            library += result.acquired
            route = result.route
        served += 1
        for u in range(VALUES):
            for v in range(VALUES):
                inputs = (Message(given[0], value(given[0], u, v), "input"),
                          Message(given[1], value(given[1], u, v), "input"))
                correct += execute(route, inputs, Workspace(), 16).payload == value(goal, u, v)
                total += 1
    return {"served": served / TASKS, "accuracy": correct / total if total else 0.0,
            "served_requests": requests / TASKS, "requests": acquirer.decisions / TASKS,
            "labels": acquirer.labels / TASKS, "fits": fits / TASKS,
            "fitted_cases": fitted_cases / TASKS,
            "cached_requests": acquirer.cache_hits / TASKS,
            "screen_rejections": (screen.rejections / TASKS if screen else 0.0),
            "cpu_seconds": time.process_time() - started}


def legacy_pairs(cases: Sequence[tuple[Any, Any]], keys: Sequence[Hashable],
                 separates: Callable[[Any, Any], bool]) -> list[tuple[int, int]]:
    """Pre-20.20 one-unmatched-observation reference, benchmark only."""
    pending: dict[Hashable, int] = {}
    pairs = []
    for i, (_, label) in enumerate(cases):
        j = pending.get(keys[i])
        if j is None:
            pending[keys[i]] = i
        elif separates(cases[j][1], label):
            pairs.append((j, i))
            del pending[keys[i]]
    return pairs


def matching_trial(policy: str, order: str, seed: int, requests: int = 30) -> dict[str, float]:
    """Fixed input, incompatible targets: IID, order stress, or compatible control.

    The blocked stream is not IID and supports only a pathwise witness claim.
    The constant control is learnable; its extra callback work is charged too.
    """
    started = time.process_time()
    fits = fitted_cases = comparisons = admitted = 0
    rng = random.Random(seed)

    def sample(contract: Contract, count: int) -> list[tuple[Any, Any]]:
        if order == "blocked":
            return [(0, 0)] * (count // 2) + [(0, 1)] * (count - count // 2)
        return [(0, int(rng.random() < 0.25) if order == "iid" else 0) for _ in range(count)]

    def separation(a: Any, b: Any) -> bool:
        nonlocal comparisons
        comparisons += 1
        return bool(a != b)

    def fitting(contract: Contract, keys: Sequence[Hashable], labels: Sequence[Hashable]) -> Module:
        nonlocal fits, fitted_cases
        fits += 1
        fitted_cases += len(keys)
        # Table expects tuple inputs only for contracts with multiple inputs.
        table = {key: label for key, label in zip(keys, labels, strict=True)}
        return Table(contract, table)

    screen = FeasibilityScreen(cases=64, confidence=0.05, key=input_key, separates=separation)
    acquirer = CertifiedAcquirer(fitting, sample, train=4096, tolerance=0.05,
                                 confidence=0.05, screen=screen)
    current = screening._disjoint_pairs
    if policy == "legacy":
        screening._disjoint_pairs = legacy_pairs
    try:
        for request in range(requests):
            # Common per-request prefixes despite policy-dependent later draws.
            rng = random.Random(seed + request * 10000)
            admitted += acquirer(Contract(("source",), "target")) is not None
    finally:
        screening._disjoint_pairs = current
    return {"requests": float(acquirer.decisions), "admitted": float(admitted),
            "screen_rejections": float(screen.rejections), "labels": float(acquirer.labels),
            "fits": float(fits), "fitted_cases": float(fitted_cases),
            "separation_calls": float(comparisons), "cpu_seconds": time.process_time() - started}


def main() -> None:
    parser = argparse.ArgumentParser()
    parser.add_argument("--seeds", type=int, nargs="+", default=[3726, 3727, 3728])
    parser.add_argument("--screen-matching", action="store_true")
    args = parser.parse_args()
    if args.screen_matching:
        for order in ("blocked", "iid", "compatible"):
            for policy in ("legacy", "retained"):
                runs = [matching_trial(policy, order, seed) for seed in args.seeds]
                print(json.dumps({"order": order, "policy": policy, **{
                    key: statistics.mean(r[key] for r in runs) for key in runs[0]}}), flush=True)
        return
    for policy in ("unary", "unary_screen", "unary_memory",
                   "binary", "binary_screen", "binary_memory", "binary_staged_memory",
                   "binary_staged_isolated_screen", "binary_staged_isolated_ranked"):
        runs = [run(policy, seed) for seed in args.seeds]
        print(json.dumps({"policy": policy, **{
            key: (statistics.mean(r[key] for r in runs), statistics.stdev(r[key] for r in runs))
            for key in runs[0]}}))


if __name__ == "__main__":
    main()
