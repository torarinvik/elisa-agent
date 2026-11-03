"""Connectors needed as contributor types grow: shared hub versus pairwise (§29.4).

Every contributor type encodes the same latent value with its own private code.
``hub``: each type learns an encoder to and a decoder from one shared type from
its own paired observations. ``pairwise``: each new type learns translators to
and from every existing type. Translators are fit by the core's
``fit_decoder`` from paired samples; routes come from the ordinary planner.
Measures connectors, paired observations, planning success, held-out accuracy
and planning time. Run: python benchmarks/shared_medium.py.
"""

from __future__ import annotations

import argparse
import json
import random
import statistics
from time import perf_counter

from nca.abi import Contract
from nca.learning.discovery import Decoder, fit_decoder
from nca.planner import plan
from nca.runtime import execute
from nca.abi import Message
from nca.workspace import Workspace

HUB, VALUES, PAIRS = "hub.latent", 64, 256


def run(types: int, mode: str, seed: int) -> dict[str, float]:
    rng = random.Random(seed)
    codes = []
    for _ in range(types):
        permutation = list(range(VALUES))
        rng.shuffle(permutation)
        codes.append(permutation)

    def code(k: int, value: int) -> str:
        return f"{k}:{codes[k][value]}"

    def fit(source: str, target: str, pairs: list[tuple[str | int, str | int]]) -> Decoder:
        keys, labels = zip(*pairs, strict=True)
        return fit_decoder(Contract((source,), target), list(keys), list(labels), cost=1.0)

    modules: list[Decoder] = []
    observations = last = 0
    for k in range(types):
        added = 0
        partners = [None] if mode == "hub" else list(range(k))
        for j in partners:
            values = [rng.randrange(VALUES) for _ in range(PAIRS)]
            added += PAIRS
            if j is None:
                pairs = [(code(k, v), v) for v in values]
                modules.append(fit(f"type{k}", HUB, pairs))
                modules.append(fit(HUB, f"type{k}", [(v, c) for c, v in pairs]))
            else:
                pairs = [(code(k, v), code(j, v)) for v in values]
                modules.append(fit(f"type{k}", f"type{j}", pairs))
                modules.append(fit(f"type{j}", f"type{k}", [(b, a) for a, b in pairs]))
        observations += added
        last = added
    planned = correct = total = 0
    seconds = 0.0
    queries = [(i, j) for i in range(types) for j in range(types) if i != j]
    for i, j in rng.sample(queries, min(64, len(queries))):
        start = perf_counter()
        route = plan(modules, (f"type{i}",), f"type{j}")
        seconds += perf_counter() - start
        if route is None:
            continue
        planned += 1
        for v in range(VALUES):
            out = execute(route, (Message(f"type{i}", code(i, v), "input"),), Workspace(), 4)
            correct += out.payload == code(j, v)
            total += 1
    sampled = min(64, len(queries))
    return {"connectors": len(modules), "observations": observations,
            "last_type_observations": last, "planned_fraction": planned / sampled,
            "accuracy": correct / total if total else 0.0,
            "plan_ms": 1000 * seconds / sampled}


def main() -> None:
    parser = argparse.ArgumentParser()
    parser.add_argument("--types", type=int, nargs="+", default=[4, 8, 16, 32])
    parser.add_argument("--seeds", type=int, nargs="+", default=[3695, 3696, 3697])
    args = parser.parse_args()
    for mode in ("hub", "pairwise"):
        for types in args.types:
            runs = [run(types, mode, seed) for seed in args.seeds]
            print(json.dumps({"mode": mode, "types": types, **{
                key: (statistics.mean(r[key] for r in runs), statistics.stdev(r[key] for r in runs))
                for key in runs[0]}}))


if __name__ == "__main__":
    main()
