"""Migrating between hub versions: one bridge versus re-attaching (§29.6).

An old hub and a new hub each have N members with private permutation codes,
every member attached to its version's founder (``learning.hub.attach``).
``bridge`` attaches the new hub to the old one once, through the old founder;
``reattach`` attaches every old member to the new founder instead. Measures
paired observations spent on migration, cross-version accuracy, and whether
every within-version route is unchanged. Run: python benchmarks/hub_migration.py.
"""

from __future__ import annotations

import argparse
import json
import random
import statistics
from functools import partial

from nca.abi import Contract, Message, Module
from nca.learning.discovery import fit_decoder
from nca.learning.hub import attach
from nca.planner import plan
from nca.runtime import execute
from nca.workspace import Workspace

OLD, NEW, VALUES, PAIRS, SAMPLE = "hub.v1", "hub.v2", 64, 256, 32
fit = partial(fit_decoder, cost=1.0)


def run(members: int, mode: str, seed: int) -> dict[str, float]:
    rng = random.Random(seed)
    codes = []
    for _ in range(2 * members):
        permutation = list(range(VALUES))
        rng.shuffle(permutation)
        codes.append(permutation)

    def code(k: int, value: int) -> str:
        return f"{k}:{codes[k][value]}"

    def draws() -> list[int]:
        return [rng.randrange(VALUES) for _ in range(PAIRS)]

    def version(hub: str, first: int) -> tuple[list[Module], Module]:
        exact = [code(first, v) for v in range(VALUES)]
        founder = fit(Contract((f"type{first}",), hub), exact, exact)
        modules = [founder, fit(Contract((hub,), f"type{first}"), exact, exact)]
        for k in range(first + 1, first + members):
            modules += attach(f"type{k}", hub, founder,
                              [(code(k, v), code(first, v)) for v in draws()], fit)
        return modules, founder

    old, old_founder = version(OLD, 0)
    new, new_founder = version(NEW, members)
    if mode == "bridge":
        added = list(attach(NEW, OLD, old_founder,
                            [(code(members, v), code(0, v)) for v in draws()], fit))
        spent = PAIRS
    else:
        added = [m for k in range(members) for m in attach(
            f"type{k}", NEW, new_founder, [(code(k, v), code(members, v)) for v in draws()],
            fit)]
        spent = members * PAIRS
    modules = old + new + added
    within = [(i, j) for base in (0, members) for i in range(base, base + members)
              for j in range(base, base + members) if i != j]
    kept = sum(plan(modules, (f"type{i}",), f"type{j}")
               == plan(old if i < members else new, (f"type{i}",), f"type{j}")
               for i, j in rng.sample(within, SAMPLE))
    cross = [(i, j) for i in range(2 * members) for j in range(2 * members)
             if (i < members) != (j < members)]
    correct = total = 0
    for i, j in rng.sample(cross, SAMPLE):
        route = plan(modules, (f"type{i}",), f"type{j}")
        for v in range(VALUES):
            out = execute(route, (Message(f"type{i}", code(i, v), "input"),), Workspace(), 6)
            correct += out.payload == code(j, v)
            total += 1
    return {"migration_observations": spent, "connectors_added": len(added),
            "cross_accuracy": correct / total, "within_routes_kept": kept / SAMPLE}


def main() -> None:
    parser = argparse.ArgumentParser()
    parser.add_argument("--members", type=int, nargs="+", default=[8, 16, 32])
    parser.add_argument("--seeds", type=int, nargs="+", default=[3698, 3699, 3700])
    args = parser.parse_args()
    for mode in ("bridge", "reattach"):
        for members in args.members:
            runs = [run(members, mode, seed) for seed in args.seeds]
            print(json.dumps({"mode": mode, "members": members, **{
                key: (statistics.mean(r[key] for r in runs), statistics.stdev(r[key] for r in runs))
                for key in runs[0]}}))


if __name__ == "__main__":
    main()
