"""Measure state-transition scaling against equivalent direct runtime execution.

Run with an environment containing nca: python benchmarks/state_stream.py.
The synthetic transition is a benchmark fixture, not an installed expert.
"""
from __future__ import annotations

import argparse
import cProfile
import json
import random
import statistics
from dataclasses import dataclass
from time import perf_counter

from nca.abi import Contract, Manifest, Message
from nca.planner import Apply, Given
from nca.runtime import Process, RiskLedger, execute
from nca.workspace import Workspace


@dataclass
class Transition:
    manifest: Manifest = Manifest(
        "benchmark-transition", "1", Contract(("state", "event"), "state"),
        effects=frozenset())

    def invoke(self, state: int, event: int) -> int:
        return state ^ event

    def risk(self, output: int, *inputs: int) -> float:
        return 0.001


def measure(size: int, seed: int, *, threaded: bool) -> dict[str, float | int]:
    """Run a reproducible fixed-size state stream; include event creation cost."""
    if size <= 0:
        raise ValueError("size must be positive")
    rng = random.Random(seed)
    transition = Transition()
    route = Apply(transition, (Given("state", 0), Given("event", 1)))
    state = Message("state", 0, "input")
    workspace = Workspace()
    ledger = RiskLedger()
    runner = Process(route, transition.manifest.contract, state, workspace, ledger=ledger)
    expected = 0
    start = perf_counter()
    for _ in range(size):
        value = rng.getrandbits(32)
        expected ^= value
        event = Message("event", value, "input")
        state = (runner.step((event,), budget=1) if threaded else
                 execute(route, (state, event), workspace, 1, ledger=ledger))
    elapsed = perf_counter() - start
    assert state.payload == expected
    assert len(workspace) == 1 + 2 * size
    assert len(ledger.invocations) == size
    assert workspace.spent == size
    assert abs(ledger.charge - size * 0.001) < 1e-8
    return {"seconds": elapsed, "messages": len(workspace), "invocations": size}


def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--sizes", type=int, nargs="+", default=[100, 1000, 10000])
    parser.add_argument("--seeds", type=int, nargs="+", default=[3662, 3663, 3664])
    parser.add_argument("--profile", action="store_true")
    args = parser.parse_args()
    if any(size <= 0 for size in args.sizes):
        parser.error("sizes must be positive")
    for size in args.sizes:
        samples: dict[str, list[float]] = {"direct": [], "process": []}
        for index, seed in enumerate(args.seeds):
            order = (False, True) if index % 2 == 0 else (True, False)
            for threaded in order:
                result = measure(size, seed, threaded=threaded)
                samples["process" if threaded else "direct"].append(float(result["seconds"]))
        print(json.dumps({
            "size": size, "messages": 1 + 2 * size, "seeds": args.seeds,
            "timing": {name: {"mean_seconds": statistics.mean(values),
                               "stdev_seconds": statistics.stdev(values) if len(values) > 1 else 0,
                               "samples": values} for name, values in samples.items()},
        }))
    if args.profile:
        cProfile.runctx("measure(max(args.sizes), args.seeds[0], threaded=True)",
                        globals(), locals(), sort="cumtime")


if __name__ == "__main__":
    main()
