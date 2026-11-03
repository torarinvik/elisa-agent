"""Plasticity from runtime ledgers and in-situ audits under silent shifts (§43.9).

Each region's expert runs through the runtime with a risk ledger. Broken
regions fail at rate 0.4; an honest break raises the reported risk to 0.4, a
silent one keeps reporting 0.02. ``reports`` feeds the field mean reported risk
only (no labels); ``audited`` also labels a 10% in-situ sample and audits each
region over its last five windows; ``labeled`` observes every case's label.
Repairs and settling follow benchmarks/plasticity.py. This measures detection
and allocation, not learning or the gate. Run: python benchmarks/ledger_signals.py.
"""

from __future__ import annotations

import argparse
import json
import random
import statistics
from collections import deque
from dataclasses import dataclass
from typing import Any

from nca.abi import Contract, Manifest, Message
from nca.evidence import audit
from nca.planner import Apply, Given
from nca.retention.plasticity import PlasticityField, Smoothing
from nca.retention.signals import surprise
from nca.runtime import Invocation, RiskLedger, execute
from nca.workspace import Workspace

HEALTHY, BROKEN, WINDOW, RATE, MEMORY = 0.02, 0.4, 20, 0.1, 5


@dataclass
class Region:
    index: int
    broken: bool = False
    silent: bool = False

    @property
    def manifest(self) -> Manifest:
        return Manifest(f"region-{self.index}", "1", Contract(("input",), "output"),
                        effects=frozenset())

    def invoke(self, draw: float) -> bool:
        return draw >= (BROKEN if self.broken else HEALTHY)  # True: correct

    def risk(self, output: Any, draw: float) -> float:
        return BROKEN if self.broken and not self.silent else HEALTHY


def key(invocation: Invocation) -> int:
    return invocation.expert.index


def run(policy: str, seed: int, regions: int = 64, steps: int = 400, budget: int = 4,
        breaking: float = 0.005) -> dict[str, float]:
    rng = random.Random(seed)
    experts = [Region(i) for i in range(regions)]
    plans = [Apply(expert, (Given("input", 0),)) for expert in experts]
    field = PlasticityField(Smoothing(0.3), open_at=0.4, close_at=0.15)
    samples: list[deque[list[tuple[float, bool]]]] = [deque(maxlen=MEMORY) for _ in experts]
    started: dict[int, tuple[int, bool]] = {}
    recovered: dict[bool, list[int]] = {False: [], True: []}
    labels = broken_steps = 0
    for step in range(steps):
        for expert in experts:
            if not expert.broken and rng.random() < breaking:
                expert.broken, expert.silent = True, rng.random() < 0.5
                started[expert.index] = (step, expert.silent)
        ledgers, failures = [], [0] * regions
        for expert, plan in zip(experts, plans, strict=True):
            window = []
            for _ in range(WINDOW):
                ledger = RiskLedger()
                correct = execute(plan, (Message("input", rng.random(), "input"),),
                                  Workspace(), 1, ledger=ledger).payload
                ledgers.append(ledger)
                failures[expert.index] += not correct
                if policy == "audited" and rng.random() < RATE:
                    window.append((ledger.invocations[0].report, not correct))
            samples[expert.index].append(window)
        if policy == "labeled":
            labels += regions * WINDOW
            signals = {i: min(1.0, max(0.0, (f / WINDOW - HEALTHY) / (BROKEN - HEALTHY)))
                       for i, f in enumerate(failures)}
        else:
            audits = {}
            if policy == "audited":
                for index, history in enumerate(samples):
                    pairs = [pair for window in history for pair in window]
                    labels += len(history[-1])
                    if pairs:
                        audits[index] = audit([r for r, _ in pairs], [f for _, f in pairs])
            raw = surprise(ledgers, key, audits=audits)
            signals = {i: min(1.0, max(0.0, (value - HEALTHY) / (BROKEN - HEALTHY)))
                       for i, value in raw.items()}
        for index, value in signals.items():
            field.observe(index, value, 0.0)
        for index, count in field.allocate(budget).items():
            for _ in range(count):
                expert = experts[index]
                if expert.broken and rng.random() < 0.5:
                    expert.broken = False
                    begun, silent = started.pop(index)
                    recovered[silent].append(step - begun)
                    field.settle(index)
                    samples[index].clear()
        broken_steps += sum(expert.broken for expert in experts)
    return {"labels": labels, "broken_region_steps": broken_steps,
            "honest_recovery": statistics.mean(recovered[False]) if recovered[False] else -1,
            "silent_recovery": statistics.mean(recovered[True]) if recovered[True] else -1,
            "silent_recovered": len(recovered[True]),
            "silent_unrecovered": sum(silent for _, silent in started.values())}


def main() -> None:
    parser = argparse.ArgumentParser()
    parser.add_argument("--seeds", type=int, nargs="+", default=[3689, 3690, 3691])
    args = parser.parse_args()
    for policy in ("reports", "audited", "labeled"):
        runs = [run(policy, seed) for seed in args.seeds]
        print(json.dumps({"policy": policy, **{
            name: (statistics.mean(r[name] for r in runs), statistics.stdev(r[name] for r in runs))
            for name in runs[0]}}))


if __name__ == "__main__":
    main()
