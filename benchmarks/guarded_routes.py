"""Measure managed route publication over catalog and affected-root counts.

The synthetic reader copies opaque bytes; a faulty version returns a different
value. Timings include full catalog preparation, evidence replay and publication.
Run: python benchmarks/guarded_routes.py.
"""

from __future__ import annotations

import argparse
import cProfile
import json
import random
import statistics
import tempfile
from dataclasses import dataclass
from pathlib import Path
from time import perf_counter
from typing import Any
from collections.abc import Sequence

from nca.abi import Contract, Manifest, Message
from nca.effects import effect_scope, expert_scope
from nca.evidence import benchmark, evaluation
from nca.guarded_routes import ProtectedRoute, RouteCatalog
from nca.memory import MemoryRecord, MemoryStore
from nca.planner import Apply, Given


@dataclass
class Reader:
    version: str
    faulty: bool = False
    name: str = "reader"
    calls: int = 0

    @property
    def manifest(self) -> Manifest:
        return Manifest(
            self.name, self.version, Contract(("input",), "output"), effects=frozenset()
        )

    def invoke(self, value: bytes) -> bytes:
        self.calls += 1
        return b"fault" if self.faulty else value


def decode(record: MemoryRecord) -> tuple[Sequence[Message], bytes]:
    return (Message("input", record.payload, "input"),), record.payload


def correct(output: Any, label: Any) -> bool:
    return output == label


def measure(size: int, affected: int, seed: int) -> dict[str, float | int]:
    if not 0 < affected <= size:
        raise ValueError("affected count must be positive and no greater than catalog size")
    rng = random.Random(seed)
    old, other = Reader("1"), Reader("1", name="unrelated")
    bad, good = Reader("2", faulty=True), Reader("3")
    shared = Apply(old, (Given("input", 0),))
    unrelated = Apply(other, (Given("input", 0),))
    roots = tuple(
        ProtectedRoute(
            f"root/{i}", ("input",), shared if i < affected else unrelated, decode, correct
        )
        for i in range(size)
    )
    effects = frozenset({"benchmark.read", "benchmark.write"})
    with tempfile.TemporaryDirectory(prefix="nca-route-update-") as directory:
        memory = MemoryStore(
            Path(directory) / "memory.sqlite",
            capacity_bytes=affected * 2048,
            read_effect="benchmark.read",
            write_effect="benchmark.write",
        )
        try:
            with effect_scope(effects), expert_scope(effects):
                assertions = []
                for i in range(affected):
                    reference = memory.append(
                        MemoryRecord("case", rng.randbytes(32), "benchmark-source@1", float(i))
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
                start = perf_counter()
                catalog = RouteCatalog(roots, assertions)
                build_seconds = perf_counter() - start
                start = perf_counter()
                refused = catalog.replace(
                    ((old, bad),), memory, {"benchmark"}, max_cases=affected, budget=1
                )
                refusal_seconds = perf_counter() - start
                assert not refused.accepted and refused.catalog is catalog
                start = perf_counter()
                accepted = catalog.replace(
                    ((old, good),), memory, {"benchmark"}, max_cases=affected, budget=1
                )
                publish_seconds = perf_counter() - start
                assert accepted.accepted and accepted.previous is catalog
                expected = tuple(f"root/{i}" for i in range(affected))
                assert refused.affected == accepted.affected == expected
                for i in range(size):
                    anchor = f"root/{i}"
                    before, after = catalog.routes[anchor], accepted.catalog.routes[anchor]
                    if i < affected:
                        assert before.plan.module is old and after.plan.module is good
                        assert after.plan is accepted.catalog.routes["root/0"].plan
                    else:
                        assert before is after
                assert old.calls == 2 * affected and good.calls == bad.calls == affected
                assert other.calls == 0
                return {
                    "build_seconds": build_seconds,
                    "refusal_seconds": refusal_seconds,
                    "publish_seconds": publish_seconds,
                    "affected": affected,
                    "invocations": old.calls + good.calls + bad.calls,
                    "unaffected_invocations": other.calls,
                }
        finally:
            memory.close()


def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--sizes", type=int, nargs="+", default=[100, 1000, 10000])
    parser.add_argument("--affected", type=int, nargs="+", default=[1, 8])
    parser.add_argument("--seeds", type=int, nargs="+", default=[3674, 3675, 3676])
    parser.add_argument("--profile", action="store_true")
    args = parser.parse_args()
    if any(not 0 < affected <= size for size in args.sizes for affected in args.affected):
        parser.error("affected counts must be positive and no greater than each size")
    for size in args.sizes:
        for affected in args.affected:
            samples = [measure(size, affected, seed) for seed in args.seeds]
            print(
                json.dumps(
                    {
                        "size": size,
                        "affected": affected,
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
                            for key in ("build_seconds", "refusal_seconds", "publish_seconds")
                        },
                    }
                )
            )
    if args.profile:
        cProfile.runctx(
            "measure(max(args.sizes), max(args.affected), args.seeds[0])",
            globals(),
            locals(),
            sort="cumtime",
        )


if __name__ == "__main__":
    main()
