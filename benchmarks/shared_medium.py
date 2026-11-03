"""Connectors needed as contributor types grow: shared hub versus pairwise (§29.4).

Every contributor type encodes the same latent value with its own private code.
``hub``: each type learns an encoder to and a decoder from one shared type from
its own paired observations. ``pairwise``: each new type learns translators to
and from every existing type. Translators are fit by the core's
``fit_decoder`` from paired samples; routes come from the ordinary planner.
``root``, ``chain`` and ``random`` learn the hub without hub labels: the hub is
the first type's code, and each new type attaches by pairing with one member
(the first, the previous, or a random one) through ``learning.hub.attach``.
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
from functools import partial

from nca.learning.discovery import Decoder, fit_decoder
from nca.learning.hub import attach
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
    encoders: dict[int, Decoder] = {}
    depth = {0: 0}
    for k in range(types if mode in ("hub", "pairwise") else 0):
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
    if mode not in ("hub", "pairwise"):
        exact = [code(0, v) for v in range(VALUES)]
        encoders[0] = fit("type0", HUB, list(zip(exact, exact, strict=True)))
        modules += [encoders[0], fit(HUB, "type0", list(zip(exact, exact, strict=True)))]
        for k in range(1, types):
            partner = {"root": 0, "chain": k - 1}.get(mode, rng.randrange(k))
            depth[k] = depth[partner] + 1
            pairs = [(code(k, v), code(partner, v))
                     for v in (rng.randrange(VALUES) for _ in range(PAIRS))]
            encoders[k], decoder = attach(f"type{k}", HUB, encoders[partner], pairs,
                                          partial(fit_decoder, cost=1.0))
            modules += [encoders[k], decoder]
            observations += PAIRS
            last = PAIRS
    planned = correct = total = 0
    by_depth: dict[int, list[int]] = {}
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
            if mode not in ("hub", "pairwise"):
                tally = by_depth.setdefault(max(depth[i], depth[j]), [0, 0])
                tally[0] += out.payload == code(j, v)
                tally[1] += 1
    sampled = min(64, len(queries))
    return {"connectors": len(modules), "observations": observations,
            "last_type_observations": last, "planned_fraction": planned / sampled,
            "accuracy": correct / total if total else 0.0,
            "plan_ms": 1000 * seconds / sampled,
            "max_depth": max(depth.values()),
            "deep_accuracy": (lambda d: d[0] / d[1] if d[1] else 0.0)(
                [sum(t[0] for key, t in by_depth.items() if key >= 8),
                 sum(t[1] for key, t in by_depth.items() if key >= 8)])}


def main() -> None:
    parser = argparse.ArgumentParser()
    parser.add_argument("--types", type=int, nargs="+", default=[4, 8, 16, 32])
    parser.add_argument("--seeds", type=int, nargs="+", default=[3695, 3696, 3697])
    args = parser.parse_args()
    for mode in ("hub", "pairwise", "root", "chain", "random"):
        for types in args.types:
            runs = [run(types, mode, seed) for seed in args.seeds]
            print(json.dumps({"mode": mode, "types": types, **{
                key: (statistics.mean(r[key] for r in runs), statistics.stdev(r[key] for r in runs))
                for key in runs[0]}}))


if __name__ == "__main__":
    main()
