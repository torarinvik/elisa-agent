"""Endpoint repair across nuisance variation using supplied features (§31.12).

Run: python benchmarks/repair_features.py. Audits never enter the learner.
"""

from __future__ import annotations

import json
import random
from collections.abc import Hashable
from time import process_time
from typing import Any

from redundancy import VALUES, LaneFactory

from nca.abi import Contract, Manifest, Message, Module
from nca.learning.discovery import decoder_object, propose_corrections
from nca.objects import Composite, Store
from nca.packages import install
from nca.planner import Apply, Given, Plan
from nca.retention.ensembles import EnsembleSearch, VoteCase, VoteFailure


class TaskBase:
    manifest = Manifest("benchmark.base", "1", Contract(("sample",), "g"),
                        effects=frozenset())

    def __init__(self, exported: Module, axis: int) -> None:
        self.exported, self.axis = exported, axis
        self.manifest = Manifest("benchmark.base", "1", self.manifest.contract,
                                 cost=exported.manifest.cost,
                                 effects=exported.manifest.effects)

    def invoke(self, value: tuple[str, str, int]) -> Any:
        return self.exported.invoke(value[self.axis])


class Key:
    def __init__(self, mode: int) -> None:
        self.mode = mode
        self.manifest = Manifest(f"benchmark.key.{mode}", "1",
                                 Contract(("sample",), "key"),
                                 cost=0 if mode == -1 else 3 if mode == 2 else 1,
                                 effects=frozenset())

    def invoke(self, value: tuple[str, str, int]) -> Hashable:
        return () if self.mode == -1 else value if self.mode == 2 else value[self.mode]


def trial(seed: int, policy: str) -> dict[str, float]:
    started = process_time()
    factory = LaneFactory(8, seed, True)
    factory.acquire(())
    store = Store()
    members = tuple(store.put(decoder_object(m, size=0)) for m in factory.modules)
    ref = store.put(Composite("benchmark.base", "1", members,
                              exports=(Contract(("s",), "g"),), effects=frozenset()))
    base = TaskBase(install(store, ref, budget=9, fuel=9)[0], seed % 2)
    features = [Key(2)] if policy == "exact" else [Key(i) for i in (-1, 0, 1, 2)]
    search = EnsembleSearch(counts=(1,) * 32, tolerance=0.02, confidence=0.05,
                            budget=16, retain_controls=16 if policy == "controls" else 0)
    rng = random.Random(seed + 30000)
    fits = fit_rows = 0
    current: Module = base

    def propose(cap: int, failures: tuple[VoteFailure, ...]) -> tuple[Plan, ...]:
        nonlocal current, fits, fit_rows
        cases = [case for failure in failures for case in (*failure.controls, failure.case)]
        if cases:
            rows, labels = [], []
            for inputs, label in cases:
                assert not isinstance(inputs, dict)
                rows.append(tuple(message.payload for message in inputs))
                labels.append(label)
            fits += len(features)
            fit_rows += len(rows) * len(features)
            candidates = propose_corrections(base, features, rows, labels,
                                              correction_cost=0, preserve_successes=True)
            if candidates:
                def score(candidate: Any) -> tuple[int, float]:
                    model = candidate.expert
                    errors = sum(model.invoke(*row) != label
                                 for row, label in zip(rows, labels, strict=True))
                    return errors, len(model.corrections) + model.feature.manifest.cost

                current = min(candidates, key=score).expert
        return (Apply(current, (Given("sample"),)),)

    def case(a: int, b: int, nonce: int) -> VoteCase:
        value = (factory.code("s", a), factory.code("s", b), nonce)
        return (Message("sample", value, "input"),), factory.code("g", (a, b)[seed % 2])

    def sample(count: int) -> list[VoteCase]:
        return [case(rng.randrange(VALUES), rng.randrange(VALUES), rng.getrandbits(64))
                for _ in range(count)]

    result = search.revise(base.manifest.contract, propose, sample)
    learning_cpu = process_time() - started
    errors = 0
    for a in range(VALUES):
        for b in range(VALUES):
            inputs, label = case(a, b, -1)
            assert not isinstance(inputs, dict)
            errors += current.invoke(inputs[0].payload) != label
    return {"certified": float(result is not None), "unseen_error": errors / VALUES ** 2,
            "requests": float(search.requests), "correction_fits": float(fits),
            "fit_rows": float(fit_rows), "initial_labels": float(factory.labels),
            "validation_labels": float(search.labels), "audit_labels": float(VALUES ** 2),
            "learning_cpu": learning_cpu, "total_cpu": process_time() - started}


if __name__ == "__main__":
    for policy in ("exact", "failures", "controls"):
        for seed in (3716, 3717, 3718):
            print(json.dumps({"policy": policy, "seed": seed, **trial(seed, policy)}), flush=True)
