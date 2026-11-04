"""Measure durable exact recall against memory size with fixed-size payloads.

Run with an environment containing nca: python benchmarks/episodic_memory.py.
Queries use known record references; this is not semantic retrieval. Timings
include hash verification and decoding, with OS/database caches uncontrolled.
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
from time import process_time

from nca.effects import EffectDenied, effect_scope, expert_scope
from nca.memory import MemoryFull, MemoryRecord, MemoryStore

READ = "benchmark.read"
WRITE = "benchmark.append"


def churn(cycles: int) -> dict[str, float | int]:
    """Append, scan from a saved cursor, evict everything and reopen.

    No labels or expert requests are used. The legacy comparator is the
    former max(live positions)+1 rule on the same empty-store workload.
    """
    if cycles < 1:
        raise ValueError("cycles must be positive")
    visible = cursor = legacy_visible = legacy_cursor = 0
    with tempfile.TemporaryDirectory(prefix="nca-memory-churn-") as directory:
        path = Path(directory) / "episodes.sqlite"
        started, cpu = perf_counter(), process_time()
        for i in range(cycles):
            store = MemoryStore(path, capacity_bytes=10000, read_effect=READ, write_effect=WRITE)
            try:
                with effect_scope(frozenset({READ, WRITE})), expert_scope(frozenset({READ, WRITE})):
                    ref = store.append(MemoryRecord("observation", str(i).encode(), "source", 0.0))
                    rows = store.scan(after=cursor, limit=1)
                    visible += bool(rows)
                    if rows:
                        cursor = rows[-1][0]
                    store.remove(ref)
                # Every previous live record was deleted: the old algorithm
                # allocates position 1 again, so only its first scan sees it.
                legacy_visible += 1 > legacy_cursor
                legacy_cursor = max(legacy_cursor, 1)
            finally:
                store.close()
        return {"cycles": cycles, "visible": visible, "legacy_model_visible": legacy_visible,
                "last_cursor": cursor, "seconds": perf_counter() - started,
                "cpu_seconds": process_time() - cpu, "labels": 0, "requests": 0}


def measure(size: int, seed: int, queries: int) -> dict[str, float | int]:
    if size <= 0 or queries <= 0:
        raise ValueError("size and queries must be positive")
    rng = random.Random(seed)
    records = [MemoryRecord("observation", rng.randbytes(64), "benchmark-producer@1", float(i))
               for i in range(size)]
    refs = [record.ref for record in records]
    capacity = sum(len(record.encode()) + len(ref) for record, ref in zip(records, refs))
    with tempfile.TemporaryDirectory(prefix="nca-memory-") as directory:
        path = Path(directory) / "episodes.sqlite"
        store = MemoryStore(path, capacity_bytes=capacity, read_effect=READ, write_effect=WRITE)
        try:
            try:
                store.append(records[0])
            except EffectDenied:
                pass
            else:
                raise AssertionError("append without declared/granted authority succeeded")
            with effect_scope(frozenset({READ, WRITE})), expert_scope(frozenset({READ, WRITE})):
                start = perf_counter()
                for record, ref in zip(records, refs, strict=True):
                    assert store.append(record) == ref
                append_seconds = perf_counter() - start
                assert store.usage() == (capacity, size)
                assert store.append(records[0]) == refs[0]
                try:
                    store.append(MemoryRecord("observation", b"overflow", "producer", 0.0))
                except MemoryFull:
                    pass
                else:
                    raise AssertionError("full store accepted a fresh record")
        finally:
            store.close()
        store = MemoryStore(path, capacity_bytes=capacity, read_effect=READ, write_effect=WRITE)
        indices = [rng.randrange(size) for _ in range(queries)]
        try:
            with effect_scope(frozenset({READ})), expert_scope(frozenset({READ})):
                start = perf_counter()
                for index in indices:
                    assert store.get(refs[index]) == records[index]
                recall_seconds = perf_counter() - start
                assert store.usage() == (capacity, size)
        finally:
            store.close()
        return {"append_seconds": append_seconds, "recall_seconds": recall_seconds,
                "logical_bytes": capacity, "database_bytes": path.stat().st_size,
                "queries": queries}


def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--sizes", type=int, nargs="+", default=[100, 1000, 10000])
    parser.add_argument("--seeds", type=int, nargs="+", default=[3668, 3669, 3670])
    parser.add_argument("--queries", type=int, default=1000)
    parser.add_argument("--profile", action="store_true")
    parser.add_argument("--churn-cycles", type=int, nargs="+")
    args = parser.parse_args()
    if args.churn_cycles is not None:
        for cycles in args.churn_cycles:
            print(json.dumps(churn(cycles)))
        return
    if any(size <= 0 for size in args.sizes) or args.queries <= 0:
        parser.error("sizes and queries must be positive")
    for size in args.sizes:
        samples = [measure(size, seed, args.queries) for seed in args.seeds]
        print(json.dumps({"size": size, "seeds": args.seeds, "queries": args.queries,
                          "samples": samples,
                          "timing": {key: {"mean_seconds": statistics.mean(
                              float(sample[key]) for sample in samples),
                              "stdev_seconds": statistics.stdev(
                                  float(sample[key]) for sample in samples
                              ) if len(samples) > 1 else 0.0}
                              for key in ("append_seconds", "recall_seconds")}}))
    if args.profile:
        cProfile.runctx("measure(max(args.sizes), args.seeds[0], args.queries)",
                        globals(), locals(), sort="cumtime")


if __name__ == "__main__":
    main()
