"""Measure independent artifact views against catalog size at fixed record size."""

from __future__ import annotations

import argparse
import cProfile
import json
import random
import statistics
import sys
from time import perf_counter, process_time

from nca.abi import Contract, Manifest
from nca.objects import Composite, Object, Primitive, Store, canonical
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


def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--sizes", type=int, nargs="+", default=[100, 1000, 10000])
    parser.add_argument("--seeds", type=int, nargs="+", default=[4111, 4112, 4113])
    parser.add_argument("--queries", type=int, default=1000)
    parser.add_argument("--profile", action="store_true")
    parser.add_argument("--traversal", action="store_true")
    args = parser.parse_args()
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
