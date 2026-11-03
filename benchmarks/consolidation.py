"""Consolidating an accumulated chain of local corrections (§43.10).

An incumbent is right on even keys; one local patch per odd key accumulates
into a chain whose query time grows with its length. Consolidation distills a
lookup table from the chain's own outputs (no labels) and publishes it through
the gate. ``exact`` trains on every retained record and gates by exact replay;
``sampled`` may train only on cases the sampled gate has already drawn.
Run: python benchmarks/consolidation.py.
"""

from __future__ import annotations

import argparse
import json
import statistics
import sys
import tempfile
from pathlib import Path
from time import perf_counter
from typing import Any

from nca.effects import effect_scope, expert_scope
from nca.evidence import benchmark, evaluation
from nca.memory import MemoryRecord, MemoryStore
from nca.planner import Apply, Given
from nca.retention.consolidation import consolidate
from nca.retention.routes import ProtectedRoute, RouteCatalog
from nca.retention.sampled import SampledGate

sys.path.insert(0, str(Path(__file__).resolve().parents[1] / "tests"))
from test_consolidation import Incumbent, Patched, correct, decode, distill  # noqa: E402


def query_seconds(piece: Any, keys: int) -> float:
    start = perf_counter()
    for key in range(keys):
        piece.invoke(key)
    return perf_counter() - start


def measure(keys: int, mode: str) -> dict[str, float | int]:
    sys.setrecursionlimit(max(10000, 4 * keys))
    effects = frozenset({"bench.read", "bench.write"})
    with tempfile.TemporaryDirectory(prefix="nca-consolidation-") as directory:
        memory = MemoryStore(Path(directory) / "memory.sqlite", capacity_bytes=keys * 512,
                             read_effect="bench.read", write_effect="bench.write")
        try:
            with effect_scope(effects), expert_scope(effects):
                refs = [memory.append(MemoryRecord("case", str(k).encode(), "bench@1", k))
                        for k in range(keys)]
                piece: Any = Incumbent()
                for key in range(1, keys, 2):
                    piece = Patched(piece, key)
                route = ProtectedRoute("root", ("key",), Apply(piece, (Given("key", 0),)),
                                       decode, correct)
                claims = (evaluation("root", benchmark(refs), [True] * keys, "lab",
                                     records=refs),)
                catalog = RouteCatalog((route,), claims)
                before = query_seconds(piece, keys)
                gate, training = None, [("root", ref) for ref in refs]
                if mode == "sampled":
                    gate = SampledGate(memory, claims, {"lab"}, tolerance=0.05,
                                       confidence=0.05, seed=keys, max_cases=keys)
                    probe = catalog.replace(((piece, Patched(piece, 0, "probe")),), memory,
                                            {"lab"}, max_cases=keys, budget=1, sampler=gate)
                    training = [("root", ref) for ref in probe.sampled.routes[0].records]
                start = perf_counter()
                result = consolidate(catalog, piece, distill, training, memory, {"lab"},
                                     budget=1, max_cases=keys, sampler=gate)
                seconds = perf_counter() - start
                active = result.update.catalog.routes["root"].plan.module
                after = query_seconds(active, keys)
        finally:
            memory.close()
    return {"keys": keys, "patches": keys // 2, "examples": result.examples,
            "accepted": int(result.accepted), "retired": len(result.retired),
            "query_before": before, "query_after": after, "consolidation_seconds": seconds}


def main() -> None:
    parser = argparse.ArgumentParser()
    parser.add_argument("--keys", type=int, nargs="+", default=[500, 1000, 2000])
    parser.add_argument("--repeats", type=int, default=3)
    args = parser.parse_args()
    for mode in ("exact", "sampled"):
        for keys in args.keys:
            runs = [measure(keys, mode) for _ in range(args.repeats)]
            print(json.dumps({"mode": mode, **{
                name: (statistics.mean(float(r[name]) for r in runs),
                       statistics.stdev(float(r[name]) for r in runs))
                for name in runs[0]}}))


if __name__ == "__main__":
    main()
