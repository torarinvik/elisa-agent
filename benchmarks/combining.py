"""Acquiring experts that combine inputs (§20.9).

A latent pair (u, v) of values below 16. Source types carry u or v alone under
private codes, each with a few derived types reached by exact connectors, and
goal types carry (u + v) mod 16 under private codes. A task gives one u-type
and one v-type and asks for a goal type. Connectors are acquired through
``planner.gaps.repair`` with ``retention.acquisition.CertifiedAcquirer`` over a
lookup table on input tuples: no expert reading one input can be certified.
``unary`` allows one-input gaps only; ``binary`` allows two inputs. Measures
served fraction, accuracy on all value pairs, requests and labels per task.
Run: python benchmarks/combining.py.
"""

from __future__ import annotations

import argparse
import json
import random
import statistics
from collections.abc import Hashable, Sequence
from typing import Any

from nca.abi import Contract, Manifest, Message, Module
from nca.planner import plan
from nca.planner.gaps import repair
from nca.retention.acquisition import CertifiedAcquirer
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


class Exact:
    def __init__(self, source: str, target: str, table: dict[Any, Any]) -> None:
        self.table = table
        self.manifest = Manifest(f"{source}->{target}", "1", Contract((source,), target),
                                 effects=frozenset())

    def invoke(self, value: Any) -> Any:
        return self.table[value]


def run(policy: str, seed: int) -> dict[str, float]:
    rng = random.Random(seed)
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
            u, v = rng.randrange(VALUES), rng.randrange(VALUES)
            key = tuple(value(t, u, v) for t in contract.inputs)
            rows.append((key if len(key) > 1 else key[0], value(contract.output, u, v)))
        return rows

    acquirer = CertifiedAcquirer(fit, sample, train=TRAIN, tolerance=0.05, confidence=0.05)
    served = correct = total = requests = 0
    for _ in range(TASKS):
        given = (f"u{rng.randrange(2)}", f"v{rng.randrange(2)}")
        goal = f"g{rng.randrange(GOALS)}"
        route = plan(library, given, goal)
        if route is None:
            result = repair(library, given, goal, acquirer, attempts=200,
                            arity=2 if policy == "binary" else 1)
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
            "requests": requests / TASKS, "labels": acquirer.labels / TASKS}


def main() -> None:
    parser = argparse.ArgumentParser()
    parser.add_argument("--seeds", type=int, nargs="+", default=[3726, 3727, 3728])
    args = parser.parse_args()
    for policy in ("unary", "binary"):
        runs = [run(policy, seed) for seed in args.seeds]
        print(json.dumps({"policy": policy, **{
            key: (statistics.mean(r[key] for r in runs), statistics.stdev(r[key] for r in runs))
            for key in runs[0]}}))


if __name__ == "__main__":
    main()
