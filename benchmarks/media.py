"""Inventing intermediate types: repair with and without media (§20.9).

Types share one latent value under private permutation codes, and paired data
links each type to a few random partners. A sequence of tasks asks for
translations between random types; the library persists, so connectors
acquired for one task serve later ones. The acquirer fits a connector between
two types from their paired data by ``fit_decoder``, and connects a type to a
medium by ``learning.hub.attach`` through any member it has data with, supplying the
encoder and decoder together.
``plain1`` and ``plain3`` repair with at most one or three missing
connectors; ``media1`` may also found a medium on a goal and grow it over all
types (``planner.gaps.repair``). Measures the repair rate in
each half of the sequence, acquisitions per task, media founded and accuracy.
Run: python benchmarks/media.py.
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
from nca.planner.gaps import Founder, medium, repair
from nca.runtime import execute
from nca.workspace import Workspace

TYPES, PARTNERS, VALUES, PAIRS, TASKS = 24, 1, 64, 256, 120
fit = partial(fit_decoder, cost=1.0)


def run(policy: str, seed: int) -> dict[str, float]:
    rng = random.Random(seed)
    codes = []
    for _ in range(TYPES):
        permutation = list(range(VALUES))
        rng.shuffle(permutation)
        codes.append(permutation)
    names = [f"t{k}" for k in range(TYPES)]
    index = {name: k for k, name in enumerate(names)}
    data: dict[int, set[int]] = {k: set() for k in range(TYPES)}
    for k in range(TYPES):
        for j in rng.sample([j for j in range(TYPES) if j != k], PARTNERS):
            data[k].add(j)
            data[j].add(k)

    def code(k: int, v: int) -> str:
        return f"{k}:{codes[k][v]}"

    def pairs(i: int, j: int) -> list[tuple[str, str]]:
        return [(code(i, v), code(j, v)) for v in (rng.randrange(VALUES) for _ in range(PAIRS))]

    library: list[Module] = []
    founders = {medium(name)[0].type(): k for k, name in enumerate(names)}
    members: dict[str, dict[int, Module]] = {}

    def acquire(contract: Contract) -> Module | tuple[Module, ...] | None:
        source, target = contract.inputs[0], contract.output
        if source in index and target in index:
            i, j = index[source], index[target]
            if j not in data[i]:
                return None
            keys, labels = zip(*pairs(i, j), strict=True)
            return fit(contract, list(keys), list(labels))
        hub, member = (target, source) if target in founders else (source, target)
        if hub not in founders or member not in index:
            return None
        k = index[member]
        known = members.setdefault(hub, {founders[hub]: medium(names[founders[hub]])[1]})
        partners = [z for z in known if z in data[k]]
        if not partners:
            return None
        encoder, decoder = attach(member, hub, known[partners[0]], pairs(k, partners[0]), fit)
        known[k] = encoder
        return (decoder, encoder) if source == hub else (encoder, decoder)

    repaired = [0, 0]
    acquisitions = founded = correct = total = 0
    for t in range(TASKS):
        i, j = rng.sample(range(TYPES), 2)
        route = plan(library, (names[i],), names[j])
        if route is None:
            result = repair(library, (names[i],), names[j], acquire, attempts=200, missing=int(policy[-1]),
                            media=names if policy.startswith("media") else None)
            if result is None:
                continue
            library += result.acquired
            founded += sum(isinstance(m, Founder) for m in result.acquired) // 2
            acquisitions += sum(not isinstance(m, Founder) for m in result.acquired)
            route = result.route
        repaired[2 * t // TASKS] += 1
        for v in range(VALUES):
            out = execute(route, (Message(names[i], code(i, v), "input"),), Workspace(), 64)
            correct += out.payload == code(j, v)
            total += 1
    half = TASKS // 2
    return {"served_first_half": repaired[0] / half, "served_second_half": repaired[1] / half,
            "acquisitions": acquisitions, "media": founded,
            "accuracy": correct / total if total else 0.0}


def main() -> None:
    parser = argparse.ArgumentParser()
    parser.add_argument("--seeds", type=int, nargs="+", default=[3710, 3711, 3712])
    args = parser.parse_args()
    for policy in ("plain1", "plain3", "media1"):
        runs = [run(policy, seed) for seed in args.seeds]
        print(json.dumps({"policy": policy, **{
            key: (statistics.mean(r[key] for r in runs), statistics.stdev(r[key] for r in runs))
            for key in runs[0]}}))


if __name__ == "__main__":
    main()
