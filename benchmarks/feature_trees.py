"""Endpoint acquisition requiring several feature branches (§36.60).

Run: python benchmarks/feature_trees.py. Domain semantics stay in this benchmark.
"""

from __future__ import annotations

import json
import random
from time import process_time
from typing import Any

from nca.abi import Contract, Manifest, Message, Module
from nca.learning.discovery import propose_corrections
from nca.learning.features import compose_features
from nca.planner import Apply, Given, Plan
from nca.retention.ensembles import EnsembleSearch, VoteCase, VoteFailure


class Base:
    manifest = Manifest("benchmark.base", "1", Contract(("sample",), "label"),
                        cost=0, effects=frozenset())

    def invoke(self, value: Any) -> Any:
        return "unlearned"


class Component:
    def __init__(self, axis: int) -> None:
        self.axis, self.calls = axis, 0
        self.manifest = Manifest(f"benchmark.component.{axis}", "1",
                                 Contract(("sample",), ("first", "second")[axis]),
                                 cost=1, effects=frozenset())

    def invoke(self, value: Any) -> Any:
        self.calls += 1
        return value[self.axis]


class Join:
    manifest = Manifest("benchmark.join", "1", Contract(("first", "second"), "joint"),
                        cost=1, effects=frozenset())

    def __init__(self) -> None:
        self.calls = 0

    def invoke(self, first: Any, second: Any) -> Any:
        self.calls += 1
        return first, second


def trial(seed: int, multi: bool) -> dict[str, float]:
    started = process_time()
    task_rng = random.Random(seed)
    labels = task_rng.sample(range(16), 16)
    rng = random.Random(seed + 60000)
    components, join, base = [Component(0), Component(1)], Join(), Base()
    features = compose_features(components, [join] if multi else [], max_depth=1, limit=16)
    search = EnsembleSearch(counts=(1,) * 32, tolerance=0.05, confidence=0.05, budget=8)
    current: Module = base
    fits = fit_rows = 0

    def propose(cap: int, failures: tuple[VoteFailure, ...]) -> tuple[Plan, ...]:
        nonlocal current, fits, fit_rows
        if failures:
            rows, targets = [], []
            for failure in failures:
                inputs, target = failure.case
                assert not isinstance(inputs, dict)
                rows.append((inputs[0].payload,))
                targets.append(target)
            fits += len(features)
            fit_rows += len(rows) * len(features)
            candidates = propose_corrections(base, features, rows, targets,
                                              correction_cost=0, preserve_successes=True)
            if candidates:
                def score(candidate: Any) -> tuple[int, float]:
                    model = candidate.expert
                    return (sum(model.invoke(*row) != target
                                for row, target in zip(rows, targets, strict=True)),
                            model.manifest.cost)

                current = min(candidates, key=score).expert
        return (Apply(current, (Given("sample"),)),)

    def case(first: int, second: int, nonce: int) -> VoteCase:
        value = f"a:{first}", f"b:{second}", nonce
        return (Message("sample", value, "input"),), f"target:{labels[4 * first + second]}"

    def sample(count: int) -> list[VoteCase]:
        return [case(rng.randrange(4), rng.randrange(4), rng.getrandbits(64)) for _ in range(count)]

    result = search.revise(base.manifest.contract, propose, sample)
    learning_cpu = process_time() - started
    errors = 0
    for first in range(4):
        for second in range(4):
            inputs, target = case(first, second, -1)
            assert not isinstance(inputs, dict)
            errors += current.invoke(inputs[0].payload) != target
    return {"certified": float(result is not None), "unseen_error": errors / 16,
            "features": float(len(features)), "requests": float(search.requests),
            "fits": float(fits), "fit_rows": float(fit_rows),
            "validation_labels": float(search.labels), "audit_labels": 16.0,
            "feature_calls": float(sum(c.calls for c in components)), "head_calls": float(join.calls),
            "learning_cpu": learning_cpu, "total_cpu": process_time() - started}


if __name__ == "__main__":
    for multi in (False, True):
        for seed in (3716, 3717, 3718):
            print(json.dumps({"multi": multi, "seed": seed, **trial(seed, multi)}), flush=True)
