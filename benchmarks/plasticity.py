"""Directing a repair budget by plasticity versus uniformly, under shifts (§43.8).

Regions break at random times; each step observes a window of cases per region
and spends a fixed budget of repair attempts. A repair fixes a broken region
with probability one half and is wasted on a healthy one (the gate would
refuse it). Policies: ``uniform`` cycles the budget over all regions,
``field`` allocates it over open keys of a PlasticityField, ``settled`` also
settles a key after each successful repair, and ``oracle``
spends it only on truly broken regions. This measures allocation, not
learning or the gate. Run: python benchmarks/plasticity.py.
"""

from __future__ import annotations

import argparse
import json
import random
import statistics

from nca.retention.plasticity import PlasticityField, Smoothing

HEALTHY, BROKEN, WINDOW = 0.02, 0.4, 20


def run(policy: str, seed: int, regions: int = 64, steps: int = 400, budget: int = 4,
        breaking: float = 0.005) -> dict[str, float]:
    rng = random.Random(seed)
    stability = [rng.uniform(0.0, 0.4) for _ in range(regions)]
    broken = [False] * regions
    field = PlasticityField(Smoothing(0.3), open_at=0.4, close_at=0.15)
    cursor = spent = wasted = broken_steps = 0
    started: dict[int, int] = {}
    recoveries: list[int] = []
    for step in range(steps):
        for region in range(regions):
            if not broken[region] and rng.random() < breaking:
                broken[region], started[region] = True, step
        for region in range(regions):
            rate = BROKEN if broken[region] else HEALTHY
            failures = sum(rng.random() < rate for _ in range(WINDOW))
            surprise = min(1.0, max(0.0, (failures / WINDOW - HEALTHY) / (BROKEN - HEALTHY)))
            field.observe(region, surprise, stability[region])
        if policy == "uniform":
            targets = [(cursor + i) % regions for i in range(budget)]
            cursor = (cursor + budget) % regions
        elif policy in ("field", "settled"):
            targets = [key for key, count in field.allocate(budget).items() for _ in range(count)]
        else:
            targets = [region for region in range(regions) if broken[region]][:budget]
        for region in targets:
            spent += 1
            if not broken[region]:
                wasted += 1
            elif rng.random() < 0.5:
                broken[region] = False
                recoveries.append(step - started.pop(region))
                if policy == "settled":
                    field.settle(region)
        broken_steps += sum(broken)
    return {"spent": spent, "wasted": wasted, "broken_region_steps": broken_steps,
            "mean_recovery": statistics.mean(recoveries) if recoveries else float("nan"),
            "unrecovered": len(started)}


def main() -> None:
    parser = argparse.ArgumentParser()
    parser.add_argument("--seeds", type=int, nargs="+", default=[3686, 3687, 3688])
    args = parser.parse_args()
    for policy in ("uniform", "field", "settled", "oracle"):
        runs = [run(policy, seed) for seed in args.seeds]
        print(json.dumps({"policy": policy, **{
            key: (statistics.mean(r[key] for r in runs), statistics.stdev(r[key] for r in runs))
            for key in runs[0]}}))


if __name__ == "__main__":
    main()
