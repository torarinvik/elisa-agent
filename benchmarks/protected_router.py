"""Measure protected lookup and normal upgrade/rollback against catalog size.

The synthetic expert copies opaque payloads through a polymorphic interface.
Each root has a distinct supplied type identifier and a retained record. This
measures routing control, not new learned capability or end-to-end inference.
"""

from __future__ import annotations

import argparse
import cProfile
import json
import random
import statistics
import tempfile
from collections.abc import Sequence
from dataclasses import dataclass
from pathlib import Path
from time import perf_counter
from typing import Any

from nca.abi import Contract, Manifest, Message
from nca.effects import effect_scope, expert_scope
from nca.evidence import benchmark, evaluation
from nca.retention.routes import ProtectedRoute, ReplayContext, RouteCatalog
from nca.memory import MemoryRecord, MemoryStore
from nca.planner import Apply, Given
from nca.router import ReplayRejected, Router
from nca.runtime import execute
from nca.workspace import Workspace


@dataclass
class Reader:
    version: str
    faulty: bool = False
    calls: int = 0

    @property
    def manifest(self) -> Manifest:
        return Manifest("reader", self.version, Contract(("?a",), "?a"), effects=frozenset())

    def invoke(self, value: bytes) -> bytes:
        self.calls += 1
        return b"fault" if self.faulty else value


def correct(output: Any, label: Any) -> bool:
    return output == label


def measure(size: int, seed: int, queries: int) -> dict[str, float | int]:
    if size <= 0 or queries <= 0:
        raise ValueError("size and queries must be positive")
    rng = random.Random(seed)
    old, good, bad = Reader("1"), Reader("2"), Reader("3", faulty=True)
    names = tuple(f"t{i}" for i in range(size))
    visited = []
    effects = frozenset({"benchmark.read", "benchmark.write"})
    with tempfile.TemporaryDirectory(prefix="nca-protected-router-") as directory:
        memory = MemoryStore(
            Path(directory) / "memory.sqlite",
            capacity_bytes=size * 2048,
            read_effect="benchmark.read",
            write_effect="benchmark.write",
        )
        try:
            with effect_scope(effects), expert_scope(effects):
                roots, assertions = [], []
                for i, name in enumerate(names):

                    def decode(
                        record: MemoryRecord, *, name: str = name, index: int = i
                    ) -> tuple[Sequence[Message], bytes]:
                        visited.append(index)
                        return (Message(name, record.payload, "input"),), record.payload

                    plan = Apply(old, (Given(name, 0),), binding=(("a", name),))
                    roots.append(ProtectedRoute(f"root/{i}", (name,), plan, decode, correct))
                    reference = memory.append(
                        MemoryRecord("case", rng.randbytes(32), "benchmark@1", float(i))
                    )
                    assertions.append(
                        evaluation(
                            f"root/{i}",
                            benchmark((reference,)),
                            (True,),
                            "benchmark",
                            records=(reference,),
                        )
                    )
                catalog = RouteCatalog(roots, assertions)
                start = perf_counter()
                router = Router(catalog)
                activation_seconds = perf_counter() - start
                requests = [rng.randrange(size) for _ in range(queries)]
                start = perf_counter()
                for i in requests:
                    assert router.route((), (names[i],), names[i]) is roots[i].plan
                lookup_seconds = perf_counter() - start
                assert old.calls == good.calls == bad.calls == 0
                name = names[0]
                failed = Apply(bad, (Given(name, 0),), binding=(("a", name),))
                candidate = Apply(good, (Given(name, 0),), binding=(("a", name),))
                replay = ReplayContext(memory, {"benchmark"}, max_cases=1, budget=1)
                start = perf_counter()
                try:
                    router.upgrade((old, bad), (name,), name, failed, replay=replay)
                except ReplayRejected:
                    pass
                else:
                    raise AssertionError("protected upgrade admitted a faulty reader")
                refusal_seconds = perf_counter() - start
                assert router.catalog is catalog
                start = perf_counter()
                previous = router.upgrade((old, good), (name,), name, candidate, replay=replay)
                publish_seconds = perf_counter() - start
                assert previous is roots[0].plan
                assert router.route((), (name,), name) is candidate
                start = perf_counter()
                router.rollback(name, previous, available=(name,), replay=replay)
                rollback_seconds = perf_counter() - start
                assert router.route((), (name,), name) is previous
                assert len(visited) == 6 and set(visited) == {0}
                assert old.calls + good.calls + bad.calls == 6
                assert router.route((), ("unknown",), "unknown") is None
                # The legacy research path demonstrates the bypass being closed.
                unprotected = Router()
                unprotected.upgrade((old, bad), (name,), name, failed)
                answer = execute(
                    unprotected.route((), (name,), name),
                    (Message(name, b"payload", "input"),),
                    Workspace(),
                    1,
                )
                assert answer.payload == b"fault"
                return {
                    "activation_seconds": activation_seconds,
                    "lookup_seconds": lookup_seconds,
                    "refusal_seconds": refusal_seconds,
                    "publish_seconds": publish_seconds,
                    "rollback_seconds": rollback_seconds,
                    "queries": queries,
                    "protected_invocations": 6,
                    "replayed_roots": len(set(visited)),
                }
        finally:
            memory.close()


def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--sizes", type=int, nargs="+", default=[100, 1000, 10000])
    parser.add_argument("--seeds", type=int, nargs="+", default=[3677, 3678, 3679])
    parser.add_argument("--queries", type=int, default=1000)
    parser.add_argument("--profile", action="store_true")
    args = parser.parse_args()
    if any(size <= 0 for size in args.sizes) or args.queries <= 0:
        parser.error("sizes and queries must be positive")
    keys = (
        "activation_seconds",
        "lookup_seconds",
        "refusal_seconds",
        "publish_seconds",
        "rollback_seconds",
    )
    for size in args.sizes:
        samples = [measure(size, seed, args.queries) for seed in args.seeds]
        print(
            json.dumps(
                {
                    "size": size,
                    "seeds": args.seeds,
                    "samples": samples,
                    "timing": {
                        key: {
                            "mean_seconds": statistics.mean(float(s[key]) for s in samples),
                            "stdev_seconds": statistics.stdev(float(s[key]) for s in samples)
                            if len(samples) > 1
                            else 0.0,
                        }
                        for key in keys
                    },
                }
            )
        )
    if args.profile:
        cProfile.runctx(
            "measure(max(args.sizes), args.seeds[0], args.queries)",
            globals(),
            locals(),
            sort="cumtime",
        )


if __name__ == "__main__":
    main()
