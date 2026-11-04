"""Measure state-transition scaling against equivalent direct runtime execution.

Run with an environment containing nca: python benchmarks/state_stream.py.
The synthetic transition is a benchmark fixture, not an installed expert.
"""
from __future__ import annotations

import argparse
import cProfile
import json
import random
from contextlib import nullcontext
import statistics
from dataclasses import dataclass
from time import perf_counter, process_time

from nca.abi import Contract, Manifest, Message
from nca.planner import Apply, Given
from nca.effects import EffectDenied, effect_scope, require_effect
from nca.runtime import Process, RiskLedger, execute
from nca.workspace import Workspace


@dataclass
class Transition:
    manifest: Manifest = Manifest(
        "benchmark-transition", "1", Contract(("state", "event"), "state"),
        effects=frozenset())

    operation: str | None = None
    accesses: int = 0

    def invoke(self, state: int, event: int) -> int:
        if self.operation is not None:
            require_effect(self.operation)
            self.accesses += 1
        return state ^ event

    def risk(self, output: int, *inputs: int) -> float:
        return 0.001


def measure(size: int, seed: int, *, threaded: bool, restricted: bool = False,
            fault_rate: float = 0.0) -> dict[str, float | int]:
    """Run a reproducible fixed-size state stream; include event creation cost."""
    if size <= 0:
        raise ValueError("size must be positive")
    if not 0 <= fault_rate <= 1 or (fault_rate and not restricted):
        raise ValueError("fault_rate requires restricted execution and must be in [0, 1]")
    rng = random.Random(seed)
    transition = Transition()
    if restricted:
        transition.manifest = Manifest("benchmark-transition", "1", transition.manifest.contract,
                                       effects=frozenset({"benchmark.resource"}))
    route = Apply(transition, (Given("state", 0), Given("event", 1)))
    state = Message("state", 0, "input")
    workspace = Workspace()
    ledger = RiskLedger()
    runner = Process(route, transition.manifest.contract, state, workspace, ledger=ledger)
    expected = 0
    accepted = 0
    denied = 0
    start = perf_counter()
    with effect_scope(frozenset({"benchmark.resource"})) if restricted else nullcontext():
        for _ in range(size):
            value = rng.getrandbits(32)
            faulty = rng.random() < fault_rate if restricted else False
            transition.operation = ("benchmark.denied" if faulty else "benchmark.resource"
                                    ) if restricted else None
            event = Message("event", value, "input")
            try:
                state = (runner.step((event,), budget=1) if threaded else
                         execute(route, (state, event), workspace, 1, ledger=ledger))
            except EffectDenied:
                assert faulty
                denied += 1
            else:
                assert not faulty
                expected ^= value
                accepted += 1
    elapsed = perf_counter() - start
    assert state.payload == expected
    assert len(workspace) == (1 + 2 * accepted if accepted else 0)
    assert len(ledger.invocations) == accepted
    assert workspace.spent == size
    assert abs(ledger.charge - accepted * 0.001) < 1e-8
    assert transition.accesses == (accepted if restricted else 0)
    return {"seconds": elapsed, "messages": len(workspace), "invocations": size,
            "accepted": accepted, "denied": denied, "gateway_accesses": transition.accesses}



class LegacyWorkspace(Workspace):
    """Previous admission/rollback behavior, benchmark reference only."""

    def post(self, message: Message) -> None:
        missing = [parent for parent in message.parents if parent not in self._index]
        if missing:
            raise ValueError("unknown parent messages")
        self._log.append(message)
        self._index[message.message_id] = message

    def rollback(self, snapshot: int) -> None:
        for message in self._log[snapshot:]:
            del self._index[message.message_id]
        del self._log[snapshot:]


def workspace_trial(legacy: bool, scenario: str, repeats: int = 1000) -> dict[str, float | int]:
    """Workspace-only identity/rollback traces; no expert calls or labels."""
    started = process_time()
    corrupted = rejected = accepted_collisions = blocked_followups = 0
    for _ in range(repeats):
        workspace = LegacyWorkspace() if legacy else Workspace()
        original = Message("state", "original", "input", message_id="anchor")
        workspace.post(original)
        snapshot = workspace.snapshot()
        try:
            if scenario == "same":
                workspace.post(original)
            elif scenario == "collision":
                workspace.post(Message("state", "replacement", "input", message_id="anchor"))
                accepted_collisions += 1
            else:
                parent = original.message_id
                for _ in range(4):
                    message = Message("state", "fresh", "input", parents=(parent,))
                    workspace.post(message)
                    parent = message.message_id
        except ValueError:
            rejected += 1
        workspace.rollback(snapshot)
        log = workspace.messages()
        stable = (len(log) == 1 and log[0] is original and original.message_id in workspace
                  and workspace.get(original.message_id) is original)
        corrupted += not stable
        try:
            workspace.post(Message("state", "followup", "input", parents=(original.message_id,)))
        except ValueError:
            blocked_followups += 1
    return {"traces": repeats, "prefix_violations": corrupted, "rejected_posts": rejected,
            "accepted_collisions": accepted_collisions, "blocked_followups": blocked_followups,
            "labels": 0, "expert_requests": 0, "cpu_seconds": process_time() - started}


def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--sizes", type=int, nargs="+", default=[100, 1000, 10000])
    parser.add_argument("--seeds", type=int, nargs="+", default=[3662, 3663, 3664])
    parser.add_argument("--profile", action="store_true")
    parser.add_argument("--restricted", action="store_true")
    parser.add_argument("--fault-rate", type=float, default=0.0)
    parser.add_argument("--workspace-identity", action="store_true")
    args = parser.parse_args()
    if args.workspace_identity:
        for scenario in ("fresh", "same", "collision"):
            for legacy in (True, False):
                samples = [workspace_trial(legacy, scenario) for _ in range(3)]
                print(json.dumps({"scenario": scenario, "legacy": legacy,
                                  **{key: statistics.mean(sample[key] for sample in samples)
                                     for key in samples[0]}}), flush=True)
        return
    if any(size <= 0 for size in args.sizes):
        parser.error("sizes must be positive")
    if not 0 <= args.fault_rate <= 1 or (args.fault_rate and not args.restricted):
        parser.error("fault-rate requires --restricted and must be in [0, 1]")
    for size in args.sizes:
        samples: dict[str, list[float]] = {"direct": [], "process": []}
        counts = []
        for index, seed in enumerate(args.seeds):
            order = (False, True) if index % 2 == 0 else (True, False)
            for threaded in order:
                result = measure(size, seed, threaded=threaded, restricted=args.restricted,
                                 fault_rate=args.fault_rate)
                samples["process" if threaded else "direct"].append(float(result["seconds"]))
                if threaded:
                    counts.append({key: result[key] for key in ("accepted", "denied",
                                                               "gateway_accesses", "messages")})
        print(json.dumps({
            "size": size, "seeds": args.seeds, "restricted": args.restricted,
            "fault_rate": args.fault_rate, "counts": counts,
            "timing": {name: {"mean_seconds": statistics.mean(values),
                               "stdev_seconds": statistics.stdev(values) if len(values) > 1 else 0,
                               "samples": values} for name, values in samples.items()},
        }))
    if args.profile:
        cProfile.runctx("measure(max(args.sizes), args.seeds[0], threaded=True, restricted=args.restricted, fault_rate=args.fault_rate)",
                        globals(), locals(), sort="cumtime")


if __name__ == "__main__":
    main()
