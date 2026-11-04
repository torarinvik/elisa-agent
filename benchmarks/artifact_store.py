"""Measure independent artifact views against catalog size at fixed record size."""

from __future__ import annotations

import argparse
import cProfile
import json
import random
import statistics
import sys
from pathlib import Path
from tempfile import TemporaryDirectory
from unittest.mock import patch
from collections.abc import Sequence
from time import perf_counter, process_time

from nca.abi import Contract, Manifest, Module
from nca.loader import ExpertStore, LazyExpert
from nca.objects import Composite, Constructor, Object, Primitive, Ref, Store, canonical
from nca.packages import Export, Upcast, _forward, install_scopes
from nca.objects import store as storage


def measure(size: int, seed: int, queries: int) -> dict[str, float | int]:
    if size <= 0 or queries <= 0:
        raise ValueError("size and queries must be positive")
    rng = random.Random(seed)
    store = Store()
    references, snapshots = [], []
    start = perf_counter()
    for _ in range(size):
        arguments = {"values": [rng.randrange(65536) for _ in range(16)],
                     "identity": rng.randbytes(32).hex()}
        obj = Primitive(Manifest("hypothetical", "1", Contract(("source",), "result")),
                        "hypothetical:Expert", arguments)
        snapshots.append(canonical(obj.data()))
        references.append(store.put(obj))
        arguments["values"].append(-1)
    setup_seconds = perf_counter() - start
    assert len(store) == size
    selected = [rng.randrange(size) for _ in range(queries)]
    start = perf_counter()
    for index in selected:
        reference = references[index]
        view = store.get(reference)
        assert view.ref == reference and canonical(view.data()) == snapshots[index]
        view.arguments["values"].append(-2)
        again = store.get(reference)
        assert again.ref == reference and canonical(again.data()) == snapshots[index]
    query_seconds = perf_counter() - start
    return {"setup_seconds": setup_seconds, "query_seconds": query_seconds,
            "queries": queries, "reads": queries * 2, "records": len(store)}


class TraversalStore(Store):
    def __init__(self) -> None:
        super().__init__()
        self.reads = 0

    def get(self, reference: str) -> Object:
        self.reads += 1
        return super().get(reference)


def recursive_traversal(store: Store, root: str, flatten: bool) -> list[str]:
    """Pre-28.10 recursive baseline, including repeated composite expansion."""
    seen: set[str] = set()
    output: list[str] = []

    def visit(node: str) -> None:
        if not flatten and node in seen:
            return
        obj = store.get(node)
        if flatten:
            if isinstance(obj, Primitive) and node not in seen:
                seen.add(node)
                output.append(node)
            elif isinstance(obj, Composite):
                for child in obj.members:
                    visit(child)
        else:
            seen.add(node)
            for child in storage._requires(obj):
                visit(child)
            output.append(node)

    visit(root)
    return output


def traversal_trial(shape: str, iterative: bool, flatten: bool) -> dict[str, float | int]:
    """Traversal-only CPU and decoding work; setup performs no expert loads."""
    store = TraversalStore()
    reference = store.put(Primitive(Manifest("hypothetical", "1", Contract(("a",), "b")),
                                    "hypothetical:Expert"))
    depth = sys.getrecursionlimit() + 100 if shape == "deep" else (14 if shape == "shared" else 16)
    expected = [reference]
    for level in range(depth):
        members = (reference, reference) if shape == "shared" else (reference,)
        reference = store.put(Composite(f"node-{level}", "1", members))
        expected.append(reference)
    store.reads = 0
    started = process_time()
    failed = 0
    output: list[str] = []
    try:
        if iterative:
            output = store.flatten(reference) if flatten else list(store.walk(reference))
        else:
            output = recursive_traversal(store, reference, flatten)
    except RecursionError:
        failed = 1
    if not failed:
        assert output == (expected[:1] if flatten else expected)
    elapsed = process_time() - started
    return {"depth": depth, "returned": len(output), "recursion_failures": failed,
            "reads": store.reads, "cpu_seconds": elapsed, "labels": 0, "expert_requests": 0}


def recursive_install_scopes(store: Store, references: Sequence[Ref],
                             experts: ExpertStore | None = None, *, budget: int = 10_000,
                             length: int = 1, fuel: int = 8) -> tuple[list[Module], ...]:
    """Pre-28.11 recursive installer, retained solely as a benchmark reference."""
    experts = experts if experts is not None else ExpertStore()
    made: dict[Ref, Module] = {}
    made_upcasts: dict[Ref, list[Module]] = {}

    def module(node: Ref) -> Module:
        if node not in made:
            obj = store.get(node)
            assert isinstance(obj, Primitive)
            resolved: dict[Ref, tuple[Module, ...]] = {}
            for dependency in obj.dependencies:
                if dependency not in resolved:
                    resolved[dependency] = tuple(scope(dependency))
            prerequisites = dict.fromkeys(
                ref for dependency in obj.dependencies for ref in store.walk(dependency)
                if isinstance(store.get(ref), Primitive))
            expert = LazyExpert(obj.manifest, lambda: obj.load(resolved.__getitem__),
                                obj.size, experts, identity=node,
                                dependencies=tuple(module(ref) for ref in prerequisites),
                                accounts_inside=obj.accounts_inside)
            expert.demand = _forward(expert, "demand", None)
            expert.relevant = _forward(expert, "relevant", True)
            expert.risk = _forward(expert, "risk", None)
            made[node] = expert
        return made[node]

    def members(obj: Composite) -> list[Module]:
        seen: set[int] = set()
        ordered = []
        for member in obj.members:
            for expert in scope(member):
                if id(expert) not in seen:
                    seen.add(id(expert))
                    ordered.append(expert)
        return ordered

    def scope(node: Ref) -> list[Module]:
        obj = store.get(node)
        if isinstance(obj, Primitive):
            return [module(node)]
        if isinstance(obj, Constructor):
            if node not in made_upcasts:
                made_upcasts[node] = [Upcast(obj, i) for i in range(len(obj.refines))]
            return made_upcasts[node]
        if not isinstance(obj, Composite):
            raise ValueError("only experts, composites and constructors can be installed")
        if obj.exports is None:
            return members(obj)
        inner = members(obj)
        return [Export(obj, i, inner, budget=budget, length=length, fuel=fuel)
                for i in range(len(obj.exports))]

    return tuple(scope(ref) for ref in tuple(references))


def installation_trial(shape: str, iterative: bool) -> dict[str, float | int]:
    """Installation-only CPU; no implementations are invoked or loaded."""
    store = TraversalStore()
    manifest = Manifest("hypothetical", "1", Contract(("a",), "b"))
    reference = store.put(Primitive(manifest, "hypothetical:Expert"))
    depth = 16 if shape == "small" else sys.getrecursionlimit() + 100
    exported = shape == "exported"
    for level in range(depth):
        reference = store.put(Composite(f"scope-{level}", "1", (reference,),
                                        exports=(manifest.contract,) if exported else None))
    experts = ExpertStore()
    store.reads = 0
    started = process_time()
    failed = 0
    scopes: tuple[list[Module], ...] = ()
    try:
        installer = install_scopes if iterative else recursive_install_scopes
        scopes = installer(store, (reference,), experts=experts)
    except RecursionError:
        failed = 1
    elapsed = process_time() - started
    if not failed:
        assert len(scopes) == 1 and len(scopes[0]) == 1
        assert scopes[0][0].manifest.contract == manifest.contract
        current = scopes[0][0]
        wrappers = 0
        while isinstance(current, Export):
            current = current.members[0]
            wrappers += 1
        assert wrappers == (depth if exported else 0)
    assert experts.stats.loads == 0
    return {"depth": depth, "installed_scopes": len(scopes), "recursion_failures": failed,
            "reads": store.reads, "cpu_seconds": elapsed, "installation_requests": 1,
            "labels": 0, "expert_requests": 0, "loaded_implementations": experts.stats.loads}


def publication_trial(atomic: bool, interrupted: bool, requests: int = 20) -> dict[str, float | int]:
    """Fault before publication completion; no process/power-loss claim.

    The direct-write reference fails after a partial public write. The actual
    staged publisher fails at its flush boundary, before linking a final name.
    Both represent a failed save before publication has completed. Setup of
    the initially valid store is excluded from measured save CPU.
    """
    readable = preserved = failures = final_files = 0
    cpu = wall = 0.0
    with TemporaryDirectory(prefix="nca-publication-") as temporary:
        for index in range(requests):
            directory = Path(temporary) / str(index)
            store = Store()
            obj = Primitive(Manifest("retained", "1", Contract(("source",), "result")),
                            "hypothetical:Expert", {"stage": "initial"})
            original = store.put(obj)
            store.save(directory)
            store.put(Primitive(obj.manifest, obj.entry, {"stage": "added"}))

            def fail_flush(descriptor: int) -> None:
                raise OSError("injected pre-publication failure")

            started = process_time()
            wall_started = perf_counter()
            try:
                if atomic:
                    if interrupted:
                        with patch.object(storage.os, "fsync", fail_flush):
                            store.save(directory)
                    else:
                        store.save(directory)
                else:
                    for reference, encoded in store._objects.items():
                        path = directory / f"{reference.removeprefix('sha256:')}.json"
                        if path.exists():
                            if path.read_bytes() != encoded:
                                raise ValueError("conflicting artifact")
                        elif interrupted:
                            path.write_bytes(encoded[:len(encoded) // 2])
                            raise OSError("injected incomplete public write")
                        else:
                            path.write_bytes(encoded)
            except OSError:
                failures += 1
            cpu += process_time() - started
            wall += perf_counter() - wall_started
            try:
                reopened = Store.open(directory)
                readable += 1
                preserved += canonical(reopened.get(original).data()) == canonical(obj.data())
            except (ValueError, KeyError):
                pass
            final_files += len(list(directory.glob("*.json")))
            assert not list(directory.glob(".nca-*.tmp"))
    return {"save_requests": requests, "labels": 0, "expert_requests": 0,
            "save_failures": failures, "reopen_successes": readable,
            "original_artifacts_accessible": preserved, "final_files": final_files,
            "save_cpu_seconds": cpu, "save_wall_seconds": wall}


def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--sizes", type=int, nargs="+", default=[100, 1000, 10000])
    parser.add_argument("--seeds", type=int, nargs="+", default=[4111, 4112, 4113])
    parser.add_argument("--queries", type=int, default=1000)
    parser.add_argument("--profile", action="store_true")
    parser.add_argument("--traversal", action="store_true")
    parser.add_argument("--installation", action="store_true")
    parser.add_argument("--publication", action="store_true")
    args = parser.parse_args()
    if args.publication:
        for interrupted in (False, True):
            for atomic in (False, True):
                samples = [publication_trial(atomic, interrupted) for _ in range(3)]
                print(json.dumps({"atomic": atomic, "interrupted": interrupted,
                                  **{key: statistics.mean(s[key] for s in samples)
                                     for key in samples[0]}}), flush=True)
        return
    if args.installation:
        for shape in ("small", "deep", "exported"):
            for iterative in (False, True):
                samples = [installation_trial(shape, iterative) for _ in range(3)]
                print(json.dumps({"shape": shape, "iterative": iterative,
                                  **{key: statistics.mean(s[key] for s in samples)
                                     for key in samples[0]}}), flush=True)
        return
    if args.traversal:
        for shape in ("small", "deep", "shared"):
            for flatten in (False, True):
                for iterative in (False, True):
                    samples = [traversal_trial(shape, iterative, flatten) for _ in range(3)]
                    print(json.dumps({"shape": shape, "flatten": flatten, "iterative": iterative,
                                      **{key: statistics.mean(s[key] for s in samples)
                                         for key in samples[0]}}), flush=True)
        return
    if any(size <= 0 for size in args.sizes) or args.queries <= 0:
        parser.error("sizes and queries must be positive")
    for size in args.sizes:
        samples = [measure(size, seed, args.queries) for seed in args.seeds]
        print(json.dumps({"size": size, "seeds": args.seeds, "samples": samples,
                          "timing": {
                              key: {"mean_seconds": statistics.mean(float(s[key]) for s in samples),
                                    "stdev_seconds": statistics.stdev(float(s[key]) for s in samples)
                                    if len(samples) > 1 else 0.0}
                              for key in ("setup_seconds", "query_seconds")}}))
    if args.profile:
        cProfile.runctx("measure(max(args.sizes), args.seeds[0], args.queries)",
                        globals(), locals(), sort="cumtime")


if __name__ == "__main__":
    main()
