"""Repeated endpoint repair versus saved-parameter reuse (§31.14).

Run: python benchmarks/repair_retention.py. Each reopened model is freshly
tested; statistical certificates are never serialized by this experiment.
"""

from __future__ import annotations

import json
import random
from pathlib import Path
from tempfile import TemporaryDirectory
from time import process_time

from redundancy import VALUES, InputKey, LaneFactory, endpoint_proposal

from nca.abi import Contract, Module
from nca.learning.acquisition_objects import store_acquired_model
from nca.learning.discovery import decoder_object
from nca.objects import Composite, Primitive, Store
from nca.packages import install
from nca.planner import Apply, Given, Plan
from nca.retention.ensembles import EnsembleSearch, VoteCase, VoteFailure


def trial(seed: int, retain: bool) -> dict[str, float]:
    started = process_time()
    training_labels = validation_labels = fits = fit_rows = requests = errors = admitted = 0
    stored_bytes = 0
    saved: tuple[str, int] | None = None
    resumed_fits = 0
    pretraining_fits = 0
    factory = LaneFactory(4, seed, True)
    factory.acquire(())
    cases = tuple(factory.case(v) for v in range(VALUES))
    with TemporaryDirectory() as directory:
        path = Path(directory)
        for session in range(3):
            if saved is not None:
                store = Store.open(path)
                current = install(store, saved[0])[saved[1]]
                base, feature = current, None
            else:
                if session:
                    factory = LaneFactory(4, seed, True)
                    factory.acquire(())
                training_labels += factory.labels
                pretraining_fits += factory.fit_requests
                store = Store()
                members = tuple(store.put(decoder_object(m, size=0)) for m in factory.modules)
                ref = store.put(Composite("benchmark.retained-base", "1", members,
                    exports=(Contract(("s",), "g"),), effects=frozenset()))
                base = install(store, ref)[0]
                feature_ref = store.put(Primitive(InputKey.manifest, "redundancy:InputKey"))
                feature = install(store, feature_ref)[0]
                current = base
            rng = random.Random(seed + 20000 + session * 1000)
            search = EnsembleSearch(counts=(1,) * 32, tolerance=0.02,
                                    confidence=0.05 / 3, budget=16)
            session_fits = 0

            def propose(cap: int, failures: tuple[VoteFailure, ...]) -> tuple[Plan, ...]:
                nonlocal current, fits, fit_rows, session_fits
                if feature is not None:
                    current = endpoint_proposal(base, feature, failures)
                    if failures:
                        fits += 1
                        session_fits += 1
                        fit_rows += len(failures)
                return (Apply(current, (Given("s"),)),)

            def sample(count: int) -> list[VoteCase]:
                return [cases[rng.randrange(VALUES)] for _ in range(count)]

            result = search.revise(Contract(("s",), "g"), propose, sample)
            admitted += result is not None
            requests += search.requests
            validation_labels += search.labels
            if saved is not None:
                resumed_fits += session_fits
            for inputs, label in cases:
                assert not isinstance(inputs, dict)
                errors += current.invoke(inputs[0].payload) != label
            if retain and saved is None and result is not None:
                def bind(module: Module) -> tuple[str, int]:
                    reference, separator, position = module.identity.partition("#")
                    return reference, int(position) if separator else 0

                # Zero declared resident size asserts no memory-quota result;
                # actual serialized bytes are measured separately below.
                saved = store_acquired_model(store, current, bind, size=lambda module: 0)
                store.save(path)
                stored_bytes = sum(p.stat().st_size for p in path.glob("*.json"))
    return {"certified_sessions": float(admitted), "audit_errors": float(errors),
            "pretraining_labels": float(training_labels), "validation_labels": float(validation_labels),
            "pretraining_fits": float(pretraining_fits),
            "correction_fits": float(fits), "fit_rows": float(fit_rows),
            "resumed_fits": float(resumed_fits), "requests": float(requests),
            "audit_labels": float(3 * VALUES), "stored_bytes": float(stored_bytes),
            "cpu_seconds": process_time() - started}


if __name__ == "__main__":
    for retain in (False, True):
        for seed in (3716, 3717, 3718):
            print(json.dumps({"retain": retain, "seed": seed, **trial(seed, retain)}), flush=True)
