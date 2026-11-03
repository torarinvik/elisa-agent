"""Bounded episodic memory with evidence-preserving eviction (§43.11).

Four routes gain retained cases every step in a store of fixed capacity, and
each step a sampled-gate decision checks a proposal on one route (half lossless,
half with loss rate 2ε). ``evict`` reclaims space by evicting drawn and
unprotected records when an append would not fit; ``none`` stops retaining once
the store is full. Measures memory use, protected removals and decisions.
Run: python benchmarks/eviction.py.
"""

from __future__ import annotations

import argparse
import hashlib
import json
import random
import statistics
import tempfile
from pathlib import Path

from nca.effects import effect_scope, expert_scope
from nca.evidence import benchmark, evaluation
from nca.memory import MemoryFull, MemoryRecord, MemoryStore
from nca.retention.eviction import candidates, evict, protected
from nca.retention.sampled import SampledGate

TOLERANCE = CONFIDENCE = 0.05


def lost(proposal: int, reference: str, loss: float) -> bool:
    draw = int(hashlib.sha256(f"{proposal}/{reference}".encode()).hexdigest()[:12], 16)
    return draw / 16 ** 12 < loss


def run(policy: str, seed: int, steps: int = 300, growth: int = 50,
        capacity_records: int = 2400) -> dict[str, float]:
    rng = random.Random(seed)
    names = [f"route-{r}" for r in range(4)]
    effects = frozenset({"bench.read", "bench.write"})
    peak = protected_removed = evicted = dropped = 0
    admitted_bad = admitted_good = refused_short = decided = 0
    with tempfile.TemporaryDirectory(prefix="nca-eviction-") as directory:
        sample = MemoryRecord("case", b"x" * 24, "bench@1", 0.0)
        charge = len(sample.encode()) + 71
        memory = MemoryStore(Path(directory) / "memory.sqlite",
                             capacity_bytes=charge * capacity_records,
                             read_effect="bench.read", write_effect="bench.write")
        try:
            with effect_scope(effects), expert_scope(effects):
                gate = SampledGate(memory, (), {"lab"}, tolerance=TOLERANCE,
                                   confidence=CONFIDENCE, seed=seed, max_cases=10 ** 7)
                for step in range(steps):
                    batch, pending = [], []
                    for name in names:
                        refs = []
                        for _ in range(growth):
                            record = MemoryRecord("case", rng.randbytes(12).hex().encode(),
                                                  "bench@1", float(step))
                            try:
                                refs.append(memory.append(record))
                                pending.append(refs[-1])
                            except MemoryFull:
                                if policy == "none":
                                    dropped += 1
                                    continue
                                guard = protected(sampler=gate, pending=pending)
                                order = candidates(memory, guard, gate)
                                result = evict(memory, order, sampler=gate, needed=charge,
                                               pending=pending)
                                evicted += len(result.removed)
                                protected_removed += len(guard.intersection(result.removed))
                                try:
                                    refs.append(memory.append(record))
                                    pending.append(refs[-1])
                                except MemoryFull:
                                    dropped += 1
                        if refs:
                            batch.append(evaluation(name, benchmark(refs), [True] * len(refs),
                                                    "lab", records=refs))
                    gate.add(batch)
                    peak = max(peak, memory.usage()[1])
                    loss = rng.choice((0.0, 2 * TOLERANCE))
                    decision = gate.decide([rng.choice(names)], lambda identity, record, base:
                                           base and lost(step, record.ref, loss))
                    if decision.insufficient:
                        refused_short += 1
                        continue
                    decided += 1
                    if decision.accepted:
                        admitted_bad += loss > 0
                        admitted_good += loss == 0
        finally:
            memory.close()
    return {"peak_records": peak, "evicted": evicted, "protected_removed": protected_removed,
            "dropped": dropped, "decided": decided, "refused_short": refused_short,
            "admitted_good": admitted_good, "admitted_bad": admitted_bad}


def main() -> None:
    parser = argparse.ArgumentParser()
    parser.add_argument("--seeds", type=int, nargs="+", default=[3692, 3693, 3694])
    args = parser.parse_args()
    for policy in ("none", "evict"):
        runs = [run(policy, seed) for seed in args.seeds]
        print(json.dumps({"policy": policy, **{
            key: (statistics.mean(r[key] for r in runs), statistics.stdev(r[key] for r in runs))
            for key in runs[0]}}))


if __name__ == "__main__":
    main()
