"""Accuracy against route depth: one route versus a majority of disjoint ones
(§31.7).

Types share one latent value under private permutation codes. Seven lanes of
``depth`` learned connectors each lead from a source type to a goal type; every
connector is fit by ``fit_decoder`` from 256 random pairs of its own, so lanes
fail independently. ``evidence.redundancy`` plans ``k`` disjoint routes and
votes. Measures accuracy over all latent values, abstentions, and the
``vote_risk`` bound computed from each lane's measured risk.
Run: python benchmarks/redundancy.py.
"""

from __future__ import annotations

import argparse
import json
import random
import statistics

from nca.abi import Contract, Message, Module
from nca.evidence.redundancy import disjoint_routes, vote, vote_risk
from nca.learning.discovery import fit_decoder
from nca.runtime import execute
from nca.workspace import Workspace

VALUES, PAIRS, LANES = 64, 256, 7


def run(depth: int, routes: int, seed: int) -> dict[str, float]:
    rng = random.Random(seed)
    codes: dict[str, list[int]] = {}

    def code(name: str, v: int) -> str:
        if name not in codes:
            codes[name] = rng.sample(range(VALUES), VALUES)
        return f"{name}:{codes[name][v]}"

    modules: list[Module] = []
    for lane in range(LANES):
        chain = ["s", *(f"l{lane}h{h}" for h in range(1, depth)), "g"]
        for a, b in zip(chain, chain[1:], strict=False):
            values = [rng.randrange(VALUES) for _ in range(PAIRS)]
            modules.append(fit_decoder(Contract((a,), b), [code(a, v) for v in values],
                                       [code(b, v) for v in values], cost=1.0))
    planned = disjoint_routes(modules, ("s",), "g", routes, fuel=depth + 1)
    risks = []
    for route in planned:
        wrong = sum(execute(route, (Message("s", code("s", v), "input"),), Workspace(),
                            depth + 1).payload != code("g", v) for v in range(VALUES))
        risks.append(wrong / VALUES)
    correct = abstained = 0
    for v in range(VALUES):
        result = vote(planned, (Message("s", code("s", v), "input"),), depth + 1)
        correct += result.answer == code("g", v)
        abstained += result.answer is None
    return {"routes": len(planned), "accuracy": correct / VALUES,
            "abstained": abstained / VALUES, "route_risk": statistics.mean(risks),
            "bound": vote_risk(risks)}


def main() -> None:
    parser = argparse.ArgumentParser()
    parser.add_argument("--seeds", type=int, nargs="+", default=list(range(3716, 3726)))
    args = parser.parse_args()
    for depth in (2, 4, 8, 16):
        for routes in (1, 3, 5, 7):
            runs = [run(depth, routes, seed) for seed in args.seeds]
            print(json.dumps({"depth": depth, "k": routes, **{
                key: round(statistics.mean(r[key] for r in runs), 4) for key in runs[0]}}))


if __name__ == "__main__":
    main()
