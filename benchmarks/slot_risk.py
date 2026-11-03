"""Risk of a general consumer fed refined values through an upcast (§29.7).

A consumer of a general constructor is fit by ``fit_decoder`` from draws over
all of its values, and its rate is measured exactly on that distribution. A
producer of a refining constructor emits a uniform subset of those values,
either at random (``random``) or half from the consumer's failures
(``shadow``). ``in_situ`` charges the consumer its measured rate as if it held
on the refined values; ``certified`` passes the density-ratio certificate
``c = |values| / |subset|`` to ``route_risk``. Measures the actual failure rate
on refined values and how often each charge falls below it (beyond rounding).
Run: python benchmarks/slot_risk.py.
"""

from __future__ import annotations

import argparse
import json
import random
import statistics

from nca.abi import Contract, Manifest, Module, TypeId
from nca.evidence import route_risk
from nca.learning.discovery import fit_decoder
from nca.objects import Constructor
from nca.packages import Upcast
from nca.planner import Apply, Given

GENERAL = Constructor("record", "1.0.0", 0, "A hypothetical general value.")
REFINED = Constructor("narrow-record", "1.0.0", 0, "A hypothetical narrower value.",
                      (GENERAL.ref,))
VALUES, DRAWS, SUBSET, TRIALS = 200, 600, 20, 200


class Source:
    manifest = Manifest("produce", "1", Contract(("source",), REFINED.type()),
                        effects=frozenset())

    def invoke(self, value: int) -> int:
        return value


def run(kind: str, seed: int) -> dict[str, float]:
    rng = random.Random(seed)
    truth = [rng.randrange(7) for _ in range(VALUES)]
    keys = [rng.randrange(VALUES) for _ in range(DRAWS)]
    consumer = fit_decoder(Contract((GENERAL.type(),), "answer"), keys,
                           [truth[k] for k in keys], cost=1.0)
    wrong = {v for v in range(VALUES) if consumer.invoke(v) != truth[v]}
    measured = len(wrong) / VALUES
    route = Apply(consumer, (Apply(Upcast(REFINED, 0), (Apply(Source(), (Given("source"),)),)),))

    def rate(module: Module) -> float | None:
        return measured if module is consumer else 0.0

    def shift(module: Module, types: tuple[TypeId, ...]) -> float | None:
        return VALUES / SUBSET

    in_situ = route_risk(route, rate)
    certified = route_risk(route, rate, shift=shift)
    actual, under_situ, under_cert = [], 0, 0
    for _ in range(TRIALS):
        if kind == "random" or not wrong:
            subset = rng.sample(range(VALUES), SUBSET)
        else:
            bad = rng.sample(sorted(wrong), min(len(wrong), SUBSET // 2))
            rest = [v for v in range(VALUES) if v not in bad]
            subset = bad + rng.sample(rest, SUBSET - len(bad))
        fails = sum(v in wrong for v in subset) / SUBSET
        actual.append(fails)
        under_situ += in_situ < fails - 1e-12
        under_cert += certified < fails - 1e-12
    return {"measured_rate": measured, "actual_mean": statistics.mean(actual),
            "actual_max": max(actual), "in_situ_charge": in_situ,
            "certified_charge": certified, "in_situ_violations": under_situ / TRIALS,
            "certified_violations": under_cert / TRIALS}


def main() -> None:
    parser = argparse.ArgumentParser()
    parser.add_argument("--seeds", type=int, nargs="+", default=[3701, 3702, 3703])
    args = parser.parse_args()
    for kind in ("random", "shadow"):
        runs = [run(kind, seed) for seed in args.seeds]
        print(json.dumps({"kind": kind, **{
            key: (statistics.mean(r[key] for r in runs), statistics.stdev(r[key] for r in runs))
            for key in runs[0]}}))


if __name__ == "__main__":
    main()
