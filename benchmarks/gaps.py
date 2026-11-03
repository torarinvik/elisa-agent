"""Repairing unreachable goals by acquiring missing connectors (§20.9).

Types share one latent value under private permutation codes. The library is
a sparse set of exact connectors; a task asks for a goal type the planner
cannot reach from its input. Paired data exists for a random fraction of type
pairs, and the acquirer fits a connector by ``fit_decoder`` from 256 pairs
when data exists. ``gaps`` requests connectors in ``planner.gaps.fill`` order;
``random`` requests untried pairs at random until a route exists. Measures
requests and acquisitions per task, acquisitions the final route does not use,
repair rate and accuracy of the repaired route.
Run: python benchmarks/gaps.py.
"""

from __future__ import annotations

import argparse
import json
import random
import statistics
from typing import Any

from nca.abi import Contract, Manifest, Message, Module
from nca.learning.discovery import fit_decoder
from nca.planner import Apply, Map, Plan, plan
from nca.planner.gaps import fill, gaps
from nca.runtime import execute
from nca.workspace import Workspace

TYPES, EDGES, VALUES, PAIRS, DATA, TASKS = 40, 48, 64, 256, 0.1, 40


class Exact:
    def __init__(self, source: str, target: str, table: dict[str, str]) -> None:
        self.table = table
        self.manifest = Manifest(f"{source}->{target}", "1", Contract((source,), target),
                                 effects=frozenset())

    def invoke(self, value: Any) -> Any:
        return self.table[value]


def modules_of(node: Plan) -> set[int]:
    if isinstance(node, Apply):
        return {id(node.module)}.union(*(modules_of(a) for a in node.args))
    return modules_of(node.body) | modules_of(node.source) if isinstance(node, Map) else set()


def run(policy: str, seed: int) -> dict[str, float]:
    rng = random.Random(seed)
    codes = []
    for _ in range(TYPES):
        permutation = list(range(VALUES))
        rng.shuffle(permutation)
        codes.append(permutation)

    def code(k: int, v: int) -> str:
        return f"{k}:{codes[k][v]}"

    names = [f"t{k}" for k in range(TYPES)]
    library: list[Module] = []
    for _ in range(EDGES):
        i, j = rng.sample(range(TYPES), 2)
        library.append(Exact(names[i], names[j], {code(i, v): code(j, v) for v in range(VALUES)}))
    data = {(i, j) for i in range(TYPES) for j in range(TYPES) if i != j and rng.random() < DATA}
    requests = acquisitions = unused = repaired = correct = total = tried = 0
    while tried < TASKS:
        s, g = rng.sample(range(TYPES), 2)
        if plan(library, (names[s],), names[g]) is not None or not any(
                (int(gap.contract.inputs[0][1:]), int(gap.contract.output[1:])) in data
                for gap in gaps(library, (names[s],), names[g])):
            continue
        tried += 1
        acquired: list[Module] = []

        def acquire(contract: Contract) -> Module | None:
            nonlocal requests
            requests += 1
            i, j = int(contract.inputs[0][1:]), int(contract.output[1:])
            if (i, j) not in data:
                return None
            values = [rng.randrange(VALUES) for _ in range(PAIRS)]
            module = fit_decoder(contract, [code(i, v) for v in values],
                                 [code(j, v) for v in values], cost=1.0)
            acquired.append(module)
            return module

        route = None
        if policy == "gaps":
            filled = fill(library, (names[s],), names[g], acquire, attempts=10 ** 6)
            route = None if filled is None else filled.route
        else:
            pairs = [(i, j) for i in range(TYPES) for j in range(TYPES) if i != j]
            rng.shuffle(pairs)
            for i, j in pairs:
                module = acquire(Contract((names[i],), names[j]))
                if module is not None:
                    route = plan([*library, *acquired], (names[s],), names[g])
                    if route is not None:
                        break
        acquisitions += len(acquired)
        if route is None:
            continue
        repaired += 1
        used = modules_of(route)
        unused += sum(id(m) not in used for m in acquired)
        for v in range(VALUES):
            out = execute(route, (Message(names[s], code(s, v), "input"),), Workspace(), 64)
            correct += out.payload == code(g, v)
            total += 1
    return {"requests": requests / TASKS, "acquisitions": acquisitions / TASKS,
            "unused_acquisitions": unused / TASKS, "repaired": repaired / TASKS,
            "accuracy": correct / total if total else 0.0}


def main() -> None:
    parser = argparse.ArgumentParser()
    parser.add_argument("--seeds", type=int, nargs="+", default=[3704, 3705, 3706])
    args = parser.parse_args()
    for policy in ("gaps", "random"):
        runs = [run(policy, seed) for seed in args.seeds]
        print(json.dumps({"policy": policy, **{
            key: (statistics.mean(r[key] for r in runs), statistics.stdev(r[key] for r in runs))
            for key in runs[0]}}))


if __name__ == "__main__":
    main()
