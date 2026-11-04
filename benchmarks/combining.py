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
from collections.abc import Hashable, Sequence
from typing import Any

from nca.abi import Contract, Manifest, Message, Module
from nca.effects import effect_scope, expert_scope
from nca.memory import MemoryStore
from nca.planner import plan
from nca.planner.gaps import repair
from nca.retention.acquisition import CertifiedAcquirer
from nca.retention.screening import FeasibilityScreen
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
        nonlocal fits
        fits += 1
        return fit(contract, keys, labels)

    screen = (FeasibilityScreen(cases=64, confidence=0.05, key=input_key, separates=separates)
              if policy.endswith(("_screen", "_memory")) else None)
    acquirer = CertifiedAcquirer(counted_fit, sample, train=TRAIN, tolerance=0.05,
                                 confidence=0.05, screen=screen, history=history)
    served = correct = total = requests = 0
    for _ in range(TASKS):
        given = (f"u{tasks.randrange(2)}", f"v{tasks.randrange(2)}")
        goal = f"g{tasks.randrange(GOALS)}"
        route = plan(library, given, goal)
        if route is None:
            result = repair(library, given, goal, acquirer, attempts=200,
                            arity=2 if policy.startswith("binary") else 1)
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
            "cached_requests": acquirer.cache_hits / TASKS,
            "screen_rejections": (screen.rejections / TASKS if screen else 0.0),
            "cpu_seconds": time.process_time() - started}


def main() -> None:
    parser = argparse.ArgumentParser()
    parser.add_argument("--seeds", type=int, nargs="+", default=[3726, 3727, 3728])
    args = parser.parse_args()
    for policy in ("unary", "unary_screen", "unary_memory",
                   "binary", "binary_screen", "binary_memory"):
        runs = [run(policy, seed) for seed in args.seeds]
        print(json.dumps({"policy": policy, **{
            key: (statistics.mean(r[key] for r in runs), statistics.stdev(r[key] for r in runs))
            for key in runs[0]}}))


if __name__ == "__main__":
    main()
