"""Accuracy against route depth: one route versus a majority of disjoint ones
(§31.7).

Types share one latent value under private permutation codes. Seven lanes of
``depth`` learned connectors each lead from a source type to a goal type; every
connector is fit by ``fit_decoder`` from 256 random pairs of its own, so lanes
have separately sampled training data, which alone does not establish
independence of their errors after fitting. ``evidence.redundancy`` plans ``k`` disjoint routes and
votes. Measures accuracy over all latent values, abstentions, and the
``vote_risk`` bound computed from each lane's measured risk.
Run: python benchmarks/redundancy.py.
"""

from __future__ import annotations

import argparse
import json
import random
import statistics
from time import process_time

from nca.abi import Contract, Message, Module
from nca.evidence.redundancy import dependent_vote_risk, disjoint_routes, vote, vote_risk
from nca.learning.discovery import fit_decoder
from nca.runtime import execute
from nca.workspace import Workspace

VALUES, PAIRS, LANES = 64, 256, 7


def run(depth: int, routes: int, seed: int, correlated: bool = False) -> dict[str, float]:
    started = process_time()
    rng = random.Random(seed)
    shared = [[rng.randrange(VALUES) for _ in range(PAIRS)] for _ in range(depth)] if correlated else []
    codes: dict[str, list[int]] = {}

    def code(name: str, v: int) -> str:
        if name not in codes:
            codes[name] = rng.sample(range(VALUES), VALUES)
        return f"{name}:{codes[name][v]}"

    modules: list[Module] = []
    for lane in range(LANES):
        chain = ["s", *(f"l{lane}h{h}" for h in range(1, depth)), "g"]
        for h, (a, b) in enumerate(zip(chain, chain[1:], strict=False)):
            values = shared[h] if correlated else [rng.randrange(VALUES) for _ in range(PAIRS)]
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
    independent, dependent = vote_risk(risks), dependent_vote_risk(risks)
    failure = 1 - correct / VALUES
    return {"routes": len(planned), "accuracy": correct / VALUES,
            "abstained": abstained / VALUES, "route_risk": statistics.mean(risks),
            "bound": independent, "dependent_bound": dependent,
            "independent_violations": float(failure > independent),
            "dependent_violations": float(failure > dependent),
            "labels": float(PAIRS * LANES * depth), "fit_requests": float(LANES * depth),
            "cpu_seconds": process_time() - started}


def main() -> None:
    parser = argparse.ArgumentParser()
    parser.add_argument("--seeds", type=int, nargs="+", default=list(range(3716, 3726)))
    parser.add_argument("--correlated", action="store_true",
                        help="reuse latent training cases across all lanes")
    parser.add_argument("--depths", type=int, nargs="+", default=[2, 4, 8, 16])
    parser.add_argument("--routes", type=int, nargs="+", default=[1, 3, 5, 7])
    args = parser.parse_args()
    if any(d < 1 for d in args.depths) or any(k < 1 or k > LANES for k in args.routes):
        parser.error("depths must be positive and route counts between one and available lanes")
    for depth in args.depths:
        for routes in args.routes:
            runs = [run(depth, routes, seed, args.correlated) for seed in args.seeds]
            print(json.dumps({"depth": depth, "k": routes, "correlated": args.correlated, **{
                key: round(statistics.mean(r[key] for r in runs), 6) for key in runs[0]}}))


if __name__ == "__main__":
    main()
