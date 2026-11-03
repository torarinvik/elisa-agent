"""Replay scaling over task streams with deliberately forgetting proposals.

Each synthetic task has one opaque key/value fact. A supplied dictionary update
is the learner fixture; this measures the retained gate, not learned abstraction
or generalization. Run: python benchmarks/retained_replay.py.
"""

from __future__ import annotations

import argparse
import cProfile
import json
import random
import statistics
import tempfile
from pathlib import Path
from time import perf_counter

from nca.effects import effect_scope, expert_scope
from nca.evidence import benchmark, evaluation
from nca.memory import MemoryRecord, MemoryStore
from nca.objects import Attestation, digest
from nca.retention import replay_gate


def measure(tasks: int, seed: int) -> dict[str, float | int]:
    if tasks <= 0:
        raise ValueError("tasks must be positive")
    rng = random.Random(seed)
    facts = [(f"{i}:{rng.getrandbits(64)}", str(rng.getrandbits(64))) for i in range(tasks)]
    model: dict[str, str] = {}
    retained: list[Attestation] = []
    rejected = 0
    scored = 0
    gate_seconds = 0.0
    last_update_seconds = 0.0
    capacity = tasks * 2048
    effects = frozenset({"benchmark.read", "benchmark.write"})
    with tempfile.TemporaryDirectory(prefix="nca-replay-") as directory:
        path = Path(directory) / "memory.sqlite"
        memory = MemoryStore(
            path,
            capacity_bytes=capacity,
            read_effect="benchmark.read",
            write_effect="benchmark.write",
        )
        try:
            with effect_scope(effects), expert_scope(effects):
                for index, (key, label) in enumerate(facts):
                    forgetting = {key: label}
                    preserving = {**model, key: label}

                    def score(identity: str, record: MemoryRecord) -> bool:
                        nonlocal scored
                        scored += 1
                        old_key, old_label = json.loads(record.payload)
                        assert identity == digest({"reader": old_key})
                        return candidate.get(old_key) == old_label

                    start = perf_counter()
                    candidate = forgetting
                    bad = replay_gate(memory, retained, {"benchmark"}, score, max_cases=tasks)
                    assert bad.accepted == (index == 0)
                    rejected += not bad.accepted
                    candidate = preserving
                    good_start = perf_counter()
                    good = replay_gate(memory, retained, {"benchmark"}, score, max_cases=tasks)
                    last_update_seconds = perf_counter() - good_start
                    gate_seconds += perf_counter() - start
                    assert good.accepted
                    model = preserving
                    assert model[key] == label
                    record = MemoryRecord(
                        "case",
                        json.dumps([key, label]).encode(),
                        "benchmark-source@1",
                        float(index),
                    )
                    reference = memory.append(record)
                    retained.append(
                        evaluation(
                            digest({"reader": key}),
                            benchmark((reference,)),
                            (True,),
                            "benchmark",
                            records=(reference,),
                        )
                    )
                used, count = memory.usage()
                assert count == tasks
        finally:
            memory.close()
        memory = MemoryStore(
            path,
            capacity_bytes=capacity,
            read_effect="benchmark.read",
            write_effect="benchmark.write",
        )
        try:
            with effect_scope(effects), expert_scope(effects):
                candidate = model
                assert replay_gate(memory, retained, {"benchmark"}, score, max_cases=tasks).accepted
        finally:
            memory.close()
    assert rejected == tasks - 1
    assert scored == tasks * tasks
    assert all(model[key] == label for key, label in facts)
    ungated = {facts[-1][0]: facts[-1][1]}
    return {
        "gate_seconds": gate_seconds,
        "last_update_seconds": last_update_seconds,
        "cases_evaluated": scored,
        "logical_bytes": used,
        "labels": tasks,
        "bad_rejected": rejected,
        "retained_accuracy": 1.0,
        "ungated_accuracy": sum(ungated.get(key) == label for key, label in facts) / tasks,
    }


def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--tasks", type=int, nargs="+", default=[8, 32, 128])
    parser.add_argument("--seeds", type=int, nargs="+", default=[3671, 3672, 3673])
    parser.add_argument("--profile", action="store_true")
    args = parser.parse_args()
    if any(tasks <= 0 for tasks in args.tasks):
        parser.error("task counts must be positive")
    for tasks in args.tasks:
        samples = [measure(tasks, seed) for seed in args.seeds]
        print(
            json.dumps(
                {
                    "tasks": tasks,
                    "seeds": args.seeds,
                    "samples": samples,
                    "timing": {
                        key: {
                            "mean_seconds": statistics.mean(
                                float(sample[key]) for sample in samples
                            ),
                            "stdev_seconds": statistics.stdev(
                                float(sample[key]) for sample in samples
                            )
                            if len(samples) > 1
                            else 0.0,
                        }
                        for key in ("gate_seconds", "last_update_seconds")
                    },
                }
            )
        )
    if args.profile:
        cProfile.runctx(
            "measure(max(args.tasks), args.seeds[0])", globals(), locals(), sort="cumtime"
        )


if __name__ == "__main__":
    main()
