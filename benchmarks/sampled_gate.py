"""Exact replay versus sampled admission over growing retained evidence (§43.7).

``cost``: routes gain retained cases every step in a durable store; each step
proposes an update affecting two routes and both gates score it, measuring
cases replayed per decision. ``validity``: many streams of proposals whose
true loss rate just exceeds the tolerance, over an in-memory record table,
measuring how often any is admitted. Losses are synthetic hash draws; this
measures admission, not learning. Run: python benchmarks/sampled_gate.py.
"""

from __future__ import annotations

import argparse
import hashlib
import json
import random
import statistics
import tempfile
from pathlib import Path
from time import perf_counter

from nca.effects import effect_scope, expert_scope
from nca.evidence import benchmark, evaluation
from nca.memory import MemoryRecord, MemoryStore
from nca.objects import Attestation
from nca.retention import replay_gate
from nca.retention.sampled import SampledGate

TOLERANCE, CONFIDENCE, SUCCESS = 0.05, 0.05, 0.8


def fails(proposal: int, reference: str, loss: float) -> bool:
    """Proposal ``proposal`` fails a baseline success with probability loss/SUCCESS."""
    draw = int(hashlib.sha256(f"{proposal}/{reference}".encode()).hexdigest()[:12], 16)
    return draw / 16 ** 12 < loss / SUCCESS


def cost(steps: int, seed: int, routes: int = 8, growth: int = 80) -> dict[str, float | int]:
    rng = random.Random(seed)
    effects = frozenset({"bench.read", "bench.write"})
    exact_cases = sampled_cases = exact_refused = sampled_refused = 0
    exact_seconds = sampled_seconds = 0.0
    last_exact = last_sampled = 0
    with tempfile.TemporaryDirectory(prefix="nca-sampled-") as directory:
        memory = MemoryStore(Path(directory) / "memory.sqlite",
                             capacity_bytes=steps * routes * growth * 512,
                             read_effect="bench.read", write_effect="bench.write")
        try:
            with effect_scope(effects), expert_scope(effects):
                pools: dict[str, list[tuple[str, bool]]] = {f"route-{r}": [] for r in range(routes)}
                gate = SampledGate(memory, (), {"lab"}, tolerance=TOLERANCE,
                                   confidence=CONFIDENCE, seed=seed, max_cases=10 ** 7)
                for step in range(steps):
                    batch: list[Attestation] = []
                    for name, pool in pools.items():
                        new = [(memory.append(MemoryRecord(
                                    "case", json.dumps([name, step, i, rng.random()]).encode(),
                                    "bench@1", float(step))), rng.random() < SUCCESS)
                               for i in range(growth)]
                        pool.extend(new)
                        refs, bits = zip(*new, strict=True)
                        batch.append(evaluation(name, benchmark(refs), bits, "lab", records=refs))
                    gate.add(batch)
                    affected = rng.sample(sorted(pools), 2)
                    loss = rng.choice((0.0, 2 * TOLERANCE))

                    def score(identity: str, record: MemoryRecord) -> bool:
                        nonlocal counted
                        counted += 1
                        return not fails(step, record.ref, loss)

                    counted = 0
                    start = perf_counter()
                    whole = [evaluation(name, benchmark([r for r, _ in pools[name]]),
                                        [b for _, b in pools[name]], "lab",
                                        records=[r for r, _ in pools[name]])
                             for name in affected]
                    exact = replay_gate(memory, whole, {"lab"}, score, max_cases=10 ** 7)
                    exact_seconds += perf_counter() - start
                    exact_cases += counted
                    last_exact = counted
                    exact_refused += not exact.accepted
                    counted = 0
                    start = perf_counter()
                    decision = gate.decide(affected, score)
                    sampled_seconds += perf_counter() - start
                    sampled_cases += counted
                    last_sampled = counted
                    sampled_refused += not decision.accepted
        finally:
            memory.close()
    return {"steps": steps, "exact_cases": exact_cases, "sampled_cases": sampled_cases,
            "last_exact": last_exact, "last_sampled": last_sampled,
            "exact_seconds": exact_seconds, "sampled_seconds": sampled_seconds,
            "exact_refused": exact_refused, "sampled_refused": sampled_refused}


class Table:
    """In-memory records for the validity simulation; the gate only reads."""

    read_effect, write_effect = "bench.read", "bench.write"

    def get(self, reference: str) -> MemoryRecord:
        return MemoryRecord("case", reference.encode(), "bench@1", 0.0)


def validity(streams: int, decisions: int, loss: float, seed: int) -> dict[str, float | int]:
    admitted_streams = admitted = 0
    for stream in range(streams):
        rng = random.Random(seed * 100003 + stream)
        claims = []
        for name in ("a", "b"):
            refs = [f"{stream}/{name}/{i}" for i in range(4000)]
            bits = [rng.random() < SUCCESS for _ in refs]
            claims.append(evaluation(name, benchmark(refs), bits, "lab", records=refs))
        gate = SampledGate(Table(), claims, {"lab"}, tolerance=TOLERANCE,  # type: ignore[arg-type]
                           confidence=CONFIDENCE, seed=stream, max_cases=10 ** 6)
        any_admitted = False
        for k in range(decisions):
            proposal = stream * 1000 + k
            decision = gate.decide(["a", "b"], lambda identity, record:
                                   identity == "b" or not fails(proposal, record.ref, loss))
            assert not decision.insufficient
            admitted += decision.accepted
            any_admitted |= decision.accepted
        admitted_streams += any_admitted
    return {"streams": streams, "decisions": decisions, "loss": loss,
            "admitted": admitted, "streams_with_admission": admitted_streams}


def main() -> None:
    parser = argparse.ArgumentParser()
    parser.add_argument("--steps", type=int, nargs="+", default=[25, 50, 100])
    parser.add_argument("--seeds", type=int, nargs="+", default=[3680, 3681, 3682])
    parser.add_argument("--streams", type=int, default=1000)
    args = parser.parse_args()
    for steps in args.steps:
        runs = [cost(steps, seed) for seed in args.seeds]
        summary = {key: (statistics.mean(float(run[key]) for run in runs),
                         statistics.stdev(float(run[key]) for run in runs))
                   for key in runs[0] if key != "steps"}
        print(json.dumps({"steps": steps, **summary}))
    for loss in (1.05 * TOLERANCE, 2 * TOLERANCE):
        print(json.dumps(validity(args.streams, 20, loss, args.seeds[0])))


if __name__ == "__main__":
    main()
