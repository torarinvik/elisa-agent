"""Endpoint repair across nuisance variation using supplied features (§31.12).

Run: python benchmarks/repair_features.py. Audits never enter the learner.
"""

from __future__ import annotations

import json
import math
import random
from collections.abc import Hashable
from dataclasses import replace
from time import process_time
from typing import Any

from redundancy import VALUES, LaneFactory

from nca.abi import Contract, Manifest, Message, Module
from nca.learning.discovery import decoder_object, propose_corrections
from nca.learning.features import compose_features
from nca.learning.projections import propose_projections
from nca.learning.numeric import midpoint_boundary
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


class Transform:
    """Public typed parts; no completed external feature or hidden target axis."""

    def __init__(self, axis: int | None) -> None:
        self.axis = axis
        contract = Contract(("raw",), "boxed") if axis is None else Contract(("boxed",), "key")
        self.manifest = Manifest(f"benchmark.transform.{axis}", "1", contract,
                                 cost=0, effects=frozenset())

    def invoke(self, value: Any) -> Any:
        return (value,) if self.axis is None else value[0][self.axis]


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
    if policy.startswith("compose"):
        seed_feature = Key(2)
        seed_feature.manifest = replace(seed_feature.manifest, contract=Contract(("sample",), "raw"))
        features = compose_features([seed_feature], [Transform(None), Transform(0), Transform(1)],
                                    max_depth=int(policy[-1]), limit=16)
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


class ConstantBase:
    manifest = Manifest("benchmark.constant", "1", Contract(("observation",), "label"),
                        cost=0, effects=frozenset())

    def invoke(self, value: Any) -> str:
        return "lower"


class Observation:
    manifest = Manifest("benchmark.measurement", "1", Contract(("observation",), "vector"),
                        cost=0, effects=frozenset())

    def invoke(self, value: Any) -> Any:
        return value


def learned_trial(seed: int, policy: str) -> dict[str, float]:
    """Fit an oblique feature using endpoint labels; no hidden direction is passed."""
    started = process_time()
    direction_rng = random.Random(seed)
    angle = direction_rng.uniform(0, 2 * math.pi)
    direction = math.cos(angle), math.sin(angle)
    rng = random.Random(seed + 40000)
    base, measurement = ConstantBase(), Observation()
    current: Module = base
    search = EnsembleSearch(counts=(1,) * 32, tolerance=0.12, confidence=0.05, budget=8,
                            retain_controls=16 if policy == "controls" else 0,
                            retain_training=64 if policy == "drawn" else 0)
    fits = fit_rows = cursor = 0

    def propose(cap: int, failures: tuple[VoteFailure, ...]) -> tuple[Plan, ...]:
        nonlocal current, fits, fit_rows
        examples: dict[str, tuple[tuple[Any, ...], Any]] = {}
        for failure in failures:
            for inputs, label in (*failure.controls, *failure.training, failure.case):
                assert not isinstance(inputs, dict)
                examples[inputs[0].message_id] = ((inputs[0].payload,), label)
        if len(examples) >= 2:
            rows, labels = zip(*examples.values(), strict=True)
            if len(set(labels)) > 1:
                fits += 1
                fit_rows += len(rows)
                candidates = propose_projections(
                    base, measurement, rows, labels, limit=1, projection_cost=0,
                    encoding_cost=0, decoder_cost=0, place_boundary=midpoint_boundary,
                    reuse_observations=True)
                if candidates:
                    current = candidates[0].expert
        return (Apply(current, (Given("observation"),)),)

    def target(value: tuple[float, float]) -> str:
        return "upper" if sum(a * b for a, b in zip(value, direction, strict=True)) >= 0.2 else "lower"

    def sample(count: int) -> list[VoteCase]:
        nonlocal cursor
        cases = []
        for _ in range(count):
            value = rng.uniform(-1, 1), rng.uniform(-1, 1)
            cases.append(((Message("observation", value, "input", message_id=str(cursor)),),
                          target(value)))
            cursor += 1
        return cases

    result = search.revise(base.manifest.contract, propose, sample)
    learning_cpu = process_time() - started
    audit_rng = random.Random(seed + 50000)
    errors = 0
    for _ in range(4096):
        value = audit_rng.uniform(-1, 1), audit_rng.uniform(-1, 1)
        errors += current.invoke(value) != target(value)
    return {"certified": float(result is not None), "audit_error": errors / 4096,
            "requests": float(search.requests), "fits": float(fits), "fit_rows": float(fit_rows),
            "validation_labels": float(search.labels), "audit_labels": 4096.0,
            "learning_cpu": learning_cpu, "total_cpu": process_time() - started}


if __name__ == "__main__":
    for policy in ("exact", "failures", "controls", "compose1", "compose2"):
        for seed in (3716, 3717, 3718):
            print(json.dumps({"policy": policy, "seed": seed, **trial(seed, policy)}), flush=True)
    for policy in ("failures", "controls", "drawn"):
        for seed in (3716, 3717, 3718):
            print(json.dumps({"policy": f"learned-{policy}", "seed": seed,
                              **learned_trial(seed, policy)}), flush=True)
