"""Measure independent artifact views against catalog size at fixed record size."""

from __future__ import annotations

import argparse
import cProfile
import json
import random
import statistics
from time import perf_counter

from nca.abi import Contract, Manifest
from nca.objects import Primitive, Store, canonical


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


def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--sizes", type=int, nargs="+", default=[100, 1000, 10000])
    parser.add_argument("--seeds", type=int, nargs="+", default=[4111, 4112, 4113])
    parser.add_argument("--queries", type=int, default=1000)
    parser.add_argument("--profile", action="store_true")
    args = parser.parse_args()
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
