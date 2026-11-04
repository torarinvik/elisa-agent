"""Endpoint acquisition requiring several feature branches (§36.60).

Run: python benchmarks/feature_trees.py. Domain semantics stay in this benchmark.
"""

from __future__ import annotations

import json
import argparse
import random
import tracemalloc
from pathlib import Path
from tempfile import TemporaryDirectory
from time import process_time
from typing import Any

from nca.abi import Contract, Manifest, Message, Module
from nca.learning.discovery import Decoded, fit_decoder, propose_corrections
from nca.learning.acquisition_objects import store_acquired_model
from nca.learning.features import compose_features
from nca.planner import Apply, Given, Plan
from nca.objects import Primitive, Store
from nca.packages import install
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


def retention_trial(seed: int, retain: bool) -> dict[str, float]:
    """Reopen an ordered application graph; always freshly test its whole output."""
    started = process_time()
    labels = random.Random(seed).sample(range(16), 16)
    saved: tuple[str, int] | None = None
    training_labels = fits = validation_labels = requests = admitted = errors = stored_bytes = 0

    def case(first: int, second: int, nonce: int) -> VoteCase:
        value = f"a:{first}", f"b:{second}", nonce
        return (Message("sample", value, "input"),), f"target:{labels[4 * first + second]}"

    audit = [case(a, b, -1) for a in range(4) for b in range(4)]
    with TemporaryDirectory() as directory:
        path = Path(directory)
        for session in range(3):
            if saved is not None:
                store = Store.open(path)
                model = install(store, saved[0])[saved[1]]
            else:
                store = Store()
                refs = [store.put(Primitive(Component(i).manifest, "feature_trees:Component",
                                           {"axis": i}, size=0)) for i in range(2)]
                join_ref = store.put(Primitive(Join.manifest, "feature_trees:Join", size=0))
                branches = [install(store, ref)[0] for ref in refs]
                join = install(store, join_ref)[0]
                feature = compose_features(branches, [join], max_depth=1, limit=16)[-1]
                keys, targets = [], []
                for a in range(4):
                    for b in range(4):
                        inputs, target = case(a, b, 0)
                        assert not isinstance(inputs, dict)
                        keys.append(feature.invoke(inputs[0].payload))
                        targets.append(target)
                head = fit_decoder(Contract(("joint",), "label"), keys, targets, cost=1)
                model = Decoded(feature, head, Contract(("sample",), "label"))
                fits += 1
                training_labels += len(targets)
            rng = random.Random(seed + 70000 + session * 1000)

            def sample(count: int) -> list[VoteCase]:
                return [case(rng.randrange(4), rng.randrange(4), rng.getrandbits(64))
                        for _ in range(count)]

            search = EnsembleSearch(counts=(1,), tolerance=0.05, confidence=0.05 / 3, budget=8)
            result = search(model.manifest.contract,
                            lambda old: Apply(model, (Given("sample"),)), sample)
            admitted += result is not None
            validation_labels += search.labels
            requests += search.requests
            for inputs, target in audit:
                assert not isinstance(inputs, dict)
                errors += model.invoke(inputs[0].payload) != target
            if retain and saved is None and result is not None:
                saved = store_acquired_model(store, model, lambda m: (m.identity, 0),
                                             size=lambda m: 0)
                store.save(path)
                stored_bytes = sum(p.stat().st_size for p in path.glob("*.json"))
    return {"certified_sessions": float(admitted), "audit_errors": float(errors),
            "head_fits": float(fits), "training_labels": float(training_labels),
            "validation_labels": float(validation_labels), "requests": float(requests),
            "audit_labels": 48.0, "stored_bytes": float(stored_bytes),
            "cpu_seconds": process_time() - started}


class CandidateJoin:
    """Same public signature; only observations reveal predictive sufficiency."""

    def __init__(self, index: int, mode: int) -> None:
        self.mode, self.calls = mode, 0
        self.manifest = Manifest(f"benchmark.candidate.{index}", "1", Join.manifest.contract,
                                 cost=1, effects=frozenset())

    def invoke(self, first: Any, second: Any) -> Any:
        self.calls += 1
        if self.mode == 0:
            return first, None
        if self.mode == 1:
            return None, second
        return first, second


def priority_trials(seed: int, policy: str) -> dict[str, float]:
    """Learn priorities on a separate task; charge its labels and fitting work."""
    started = process_time()
    heads = [CandidateJoin(i, i % 2) for i in range(64)] + [CandidateJoin(64, 2)]
    components, base = [Component(0), Component(1)], Base()
    warmup_labels = probe_fits = probe_rows = 0
    scores: dict[int, float] = {}
    if policy == "ranked":
        labels = random.Random(seed + 80000).sample(range(16), 16)
        inputs = [(f"a:{a}", f"b:{b}", 0) for a in range(4) for b in range(4)]
        observations = [tuple(c.invoke(value) for c in components) for value in inputs]
        targets = [f"warmup:{label}" for label in labels]
        warmup_labels = len(targets)
        for head in heads:
            keys = [head.invoke(*values) for values in observations]
            decoder = fit_decoder(Contract(("joint",), "label"), keys, targets, cost=0)
            scores[id(head)] = sum(decoder.invoke(key) == target
                                   for key, target in zip(keys, targets, strict=True)) / len(targets)
            probe_fits += 1
            probe_rows += len(keys)
    fits = rows_fit = requests = validation_labels = admitted = errors = score_calls = 0
    for task in range(3):
        targets = random.Random(seed + 90000 + task).sample(range(16), 16)
        rng = random.Random(seed + 100000 + task * 1000)
        search = EnsembleSearch(counts=(1,) * 32, tolerance=0.05, confidence=0.05 / 3, budget=8)
        current: Module = base

        def priority(module: Module) -> float:
            nonlocal score_calls
            score_calls += 1
            return scores[id(module)]

        def propose(cap: int, failures: tuple[VoteFailure, ...]) -> tuple[Plan, ...]:
            nonlocal current, fits, rows_fit
            features = compose_features(components, heads, max_depth=1,
                limit=67 if policy == "wide" else 3,
                priority=priority if policy == "ranked" else None)
            if failures:
                rows, labels = [], []
                for failure in failures:
                    inputs, label = failure.case
                    assert not isinstance(inputs, dict)
                    rows.append((inputs[0].payload,))
                    labels.append(label)
                candidates = propose_corrections(base, features, rows, labels,
                                                  correction_cost=0, preserve_successes=True)
                fits += len(features)
                rows_fit += len(rows) * len(features)
                if candidates:
                    def score(candidate: Any) -> tuple[int, float]:
                        model = candidate.expert
                        return (sum(model.invoke(*row) != label
                                    for row, label in zip(rows, labels, strict=True)),
                                model.manifest.cost)

                    current = min(candidates, key=score).expert
            return (Apply(current, (Given("sample"),)),)

        def case(a: int, b: int, nonce: int) -> VoteCase:
            return (Message("sample", (f"a:{a}", f"b:{b}", nonce), "input"),), targets[4 * a + b]

        def sample(count: int) -> list[VoteCase]:
            return [case(rng.randrange(4), rng.randrange(4), rng.getrandbits(64)) for _ in range(count)]

        result = search.revise(base.manifest.contract, propose, sample)
        admitted += result is not None
        requests += search.requests
        validation_labels += search.labels
        for a in range(4):
            for b in range(4):
                inputs, label = case(a, b, -1)
                assert not isinstance(inputs, dict)
                errors += current.invoke(inputs[0].payload) != label
    return {"certified_tasks": float(admitted), "audit_errors": float(errors),
            "warmup_labels": float(warmup_labels), "validation_labels": float(validation_labels),
            "probe_fits": float(probe_fits), "correction_fits": float(fits),
            "total_fits": float(fits + probe_fits), "fit_rows": float(rows_fit + probe_rows),
            "requests": float(requests), "priority_calls": float(score_calls), "audit_labels": 48.0,
            "head_calls": float(sum(head.calls for head in heads)),
            "cpu_seconds": process_time() - started}


class TargetTransform:
    def __init__(self, name: str, inputs: tuple[str, ...], output: str) -> None:
        self._manifest = Manifest(name, "1", Contract(inputs, output), cost=1, effects=frozenset())
        self.reads = self.calls = 0

    @property
    def manifest(self) -> Manifest:
        self.reads += 1
        return self._manifest

    def invoke(self, *values: Any) -> Any:
        self.calls += 1
        return values[0] if len(values) == 1 else tuple(values)


def target_trial(seed: int, policy: str, decoys: int) -> dict[str, float]:
    """Charge metadata, search memory and fresh certification on one task.

    The output type is supplied, not discovered. Irrelevant alternatives share
    one type and form many distinct paths; no semantic deduplication is assumed.
    """
    heads = [TargetTransform(f"decoy-{i}", ("first",), "unused") for i in range(decoys)]
    heads += [TargetTransform(f"loop-{i}", ("unused",), "unused") for i in range(decoys)]
    heads += [TargetTransform("join", ("first", "second"), "joint")]
    components = [Component(0), Component(1)]
    started = process_time()
    tracemalloc.start()
    pool = compose_features(components, heads, max_depth=2,
                            limit=5000 if policy == "wide" else 16,
                            targets=("joint",) if policy == "targeted" else None)
    _, peak = tracemalloc.get_traced_memory()
    tracemalloc.stop()
    construction_cpu = process_time() - started
    construction_calls = sum(h.calls for h in heads) + sum(c.calls for c in components)
    features = [f for f in pool if f.manifest.contract.output == "joint"]
    targets = random.Random(seed).sample(range(16), 16)
    inputs = [(f"a:{a}", f"b:{b}", 0) for a in range(4) for b in range(4)]
    labels = [f"label:{value}" for value in targets]
    models = [Decoded(feature, fit_decoder(Contract(("joint",), "label"),
                                          [feature.invoke(value) for value in inputs], labels, cost=0),
                      Base.manifest.contract) for feature in features]
    search = EnsembleSearch(counts=(1,), tolerance=0.05, confidence=0.05, budget=8)
    rng = random.Random(seed + 110000)

    def sample(count: int) -> list[VoteCase]:
        cases = []
        for _ in range(count):
            i = rng.randrange(16)
            value = (*inputs[i][:2], rng.getrandbits(64))
            cases.append(((Message("sample", value, "input"),), labels[i]))
        return cases

    result = search.revise(Base.manifest.contract,
        lambda cap, failures: None if not models else (Apply(models[0], (Given("sample"),)),), sample)
    errors = sum((models[0].invoke(value) if models else "unlearned") != label
                 for value, label in zip(inputs, labels, strict=True))
    return {"requests": search.requests, "fits": len(models), "training_labels": len(labels),
            "validation_labels": search.labels, "audit_labels": len(inputs), "audit_errors": errors,
            "certified_tasks": int(result is not None), "returned_features": len(pool),
            "target_features": len(features), "metadata_reads": sum(h.reads for h in heads),
            "construction_expert_calls": construction_calls, "peak_search_bytes": peak,
            "construction_cpu_seconds": construction_cpu, "cpu_seconds": process_time() - started}


if __name__ == "__main__":
    parser = argparse.ArgumentParser()
    parser.add_argument("--targeted", action="store_true")
    args = parser.parse_args()
    if args.targeted:
        for decoys in (0, 64):
            for policy in ("narrow", "wide", "targeted"):
                for seed in (3716, 3717, 3718):
                    print(json.dumps({"policy": policy, "decoys": decoys, "seed": seed,
                                      **target_trial(seed, policy, decoys)}), flush=True)
        raise SystemExit
    for multi in (False, True):
        for seed in (3716, 3717, 3718):
            print(json.dumps({"multi": multi, "seed": seed, **trial(seed, multi)}), flush=True)
    for retain in (False, True):
        for seed in (3716, 3717, 3718):
            print(json.dumps({"retain": retain, "seed": seed,
                              **retention_trial(seed, retain)}), flush=True)
    for policy in ("narrow", "wide", "ranked"):
        for seed in (3716, 3717, 3718):
            print(json.dumps({"policy": policy, "seed": seed,
                              **priority_trials(seed, policy)}), flush=True)
