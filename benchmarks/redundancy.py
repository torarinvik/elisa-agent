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
Use --target 0.02 --maximum 9 --depths 8 to compare fixed and growing
end-to-end certification; only requested lanes are fit in that experiment.
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
from nca.planner import Plan, plan
from nca.retention.ensembles import EnsembleSearch, VoteCase
from nca.runtime import execute
from nca.workspace import Workspace

VALUES, PAIRS, LANES = 64, 256, 7


class LaneFactory:
    """Fit one additional lane per request; test draws use a separate RNG."""

    def __init__(self, depth: int, seed: int, correlated: bool) -> None:
        self.depth = depth
        self.rng = random.Random(seed)
        self.shared = ([[self.rng.randrange(VALUES) for _ in range(PAIRS)]
                        for _ in range(depth)] if correlated else [])
        self.codes: dict[str, list[int]] = {}
        self.modules: list[Module] = []
        self.lanes = self.labels = self.fit_requests = 0

    def code(self, name: str, v: int) -> str:
        if name not in self.codes:
            self.codes[name] = self.rng.sample(range(VALUES), VALUES)
        return f"{name}:{self.codes[name][v]}"

    def acquire(self, existing: tuple[Plan, ...]) -> Plan:
        lane, depth = self.lanes, self.depth
        chain = ["s", *(f"l{lane}h{h}" for h in range(1, depth)), "g"]
        modules: list[Module] = []
        for h, (a, b) in enumerate(zip(chain, chain[1:], strict=False)):
            values = self.shared[h] if self.shared else [self.rng.randrange(VALUES) for _ in range(PAIRS)]
            modules.append(fit_decoder(Contract((a,), b), [self.code(a, v) for v in values],
                                       [self.code(b, v) for v in values], cost=1.0))
            self.labels += len(values)
            self.fit_requests += 1
        self.modules.extend(modules)
        self.lanes += 1
        route = plan(modules, ("s",), "g", fuel=depth + 1)
        assert route is not None
        return route

    def case(self, value: int) -> VoteCase:
        return (Message("s", self.code("s", value), "input"),), self.code("g", value)


def run(depth: int, routes: int, seed: int, correlated: bool = False) -> dict[str, float]:
    started = process_time()
    factory = LaneFactory(depth, seed, correlated)
    built: list[Plan] = []
    for _ in range(LANES):
        built.append(factory.acquire(tuple(built)))
    planned = disjoint_routes(factory.modules, ("s",), "g", routes, fuel=depth + 1)
    risks = []
    for route in planned:
        wrong = sum(execute(route, factory.case(v)[0], Workspace(),
                            depth + 1).payload != factory.case(v)[1] for v in range(VALUES))
        risks.append(wrong / VALUES)
    correct = abstained = 0
    for v in range(VALUES):
        result = vote(planned, factory.case(v)[0], depth + 1)
        correct += result.answer == factory.case(v)[1]
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


def certify(depth: int, seed: int, correlated: bool, target: float,
            counts: tuple[int, ...]) -> dict[str, float | None]:
    started = process_time()
    factory = LaneFactory(depth, seed, correlated)
    cases = random.Random(seed + 20000)

    def sample(count: int) -> list[VoteCase]:
        return [factory.case(cases.randrange(VALUES)) for _ in range(count)]

    search = EnsembleSearch(counts=counts, tolerance=target, confidence=0.05, budget=depth + 1)
    result = search(Contract(("s",), "g"), factory.acquire, sample)
    error = None
    if result is not None:
        wrong = 0
        for value in range(VALUES):
            inputs, label = factory.case(value)
            answer = vote(result.routes, inputs, depth + 1)
            wrong += answer.agreeing == 0 or answer.answer != label
        error = wrong / VALUES
    return {"certified": float(result is not None), "admitted_error": error,
            "bad_certificates": float(error is not None and error > target),
            "route_requests": float(search.requests), "fit_requests": float(factory.fit_requests),
            "training_labels": float(factory.labels), "certification_labels": float(search.labels),
            "total_labels": float(factory.labels + search.labels), "tests": float(search.tests),
            "cpu_seconds": process_time() - started}


def main() -> None:
    parser = argparse.ArgumentParser()
    parser.add_argument("--seeds", type=int, nargs="+", default=list(range(3716, 3726)))
    parser.add_argument("--correlated", action="store_true",
                        help="reuse latent training cases across all lanes")
    parser.add_argument("--depths", type=int, nargs="+", default=[2, 4, 8, 16])
    parser.add_argument("--routes", type=int, nargs="+", default=[1, 3, 5, 7])
    parser.add_argument("--target", type=float)
    parser.add_argument("--maximum", type=int, default=9)
    args = parser.parse_args()
    if any(d < 1 for d in args.depths) or any(k < 1 or k > LANES for k in args.routes):
        parser.error("depths must be positive and route counts between one and available lanes")
    if args.target is not None:
        if args.maximum < 1 or not 0 < args.target < 1:
            parser.error("maximum must be positive and target between zero and one")
        staged = tuple(range(1, args.maximum + 1, 2))
        if staged[-1] != args.maximum:
            staged += (args.maximum,)
        for depth in args.depths:
            for policy, counts in (("fixed", (args.maximum,)), ("staged", staged)):
                runs = [certify(depth, seed, args.correlated, args.target, counts) for seed in args.seeds]
                means = {}
                for key in runs[0]:
                    values = [r[key] for r in runs if r[key] is not None]
                    means[key] = statistics.mean(values) if values else None
                print(json.dumps({"depth": depth, "correlated": args.correlated,
                                  "policy": policy, "target": args.target, **means}))
        return
    for depth in args.depths:
        for routes in args.routes:
            runs = [run(depth, routes, seed, args.correlated) for seed in args.seeds]
            print(json.dumps({"depth": depth, "k": routes, "correlated": args.correlated, **{
                key: round(statistics.mean(r[key] for r in runs), 6) for key in runs[0]}}))


if __name__ == "__main__":
    main()
