"""Lazy loading at scale.

Part 1, library size. The arithmetic experts are installed lazily among
``n`` decoy experts (half before, half after). Decoys consume only decoy
types that nothing can produce, so no plan can use them, and their loaders
fail if ever called. For each ``n`` the runner reports planning time (linear
layered planning versus indexed binary search), the experts loaded while
solving the task, peak resident bytes, and whether every answer matches the
decoy-free system. ``NCA.WellTyped.contracts_subset`` and
``NCA.route_contracts_append`` predict that the loaded set equals the
route's working set for every ``n``; ``NCA.planIdx_eq`` and
``NCA.plan_prefix_mono`` justify the indexed binary search.

Part 2, memory budget. Arithmetic and comparison tasks alternate under
budgets that fit both routes, only the larger one, and less. The runner
reports loads, evictions, and time spent loading.

    uv run --extra vision python -m nca.scaling
"""

from __future__ import annotations

import argparse
import random
import time
from pathlib import Path
from typing import Callable

import torch

from nca.abi import Contract, Manifest, Message, TypeId
from nca.expressions import RELATIONS, ExpressionDataset
from nca.loader import ExpertStore, LazyExpert
from nca.modules.digit_recognizer import CONTRACT as DIGIT_CONTRACT, DigitRecognizer
from nca.modules.operator_recognizer import (
    OPERATOR_SET, RELATION_SET, SymbolRecognizer, SymbolSet,
)
from nca.modules.digit_recognizer import GLYPH
from nca.modules.segmenter import EXPRESSION_IMAGE, Segmenter
from nca.modules.symbols import (
    BOOLEAN, COMPARISON, INTEGER, ComparisonEvaluator, Evaluator, ExpressionParser,
    SymbolFuser,
)
from nca.planner import Apply, Map, Plan, ProducerIndex, plan, plan_stable_indexed
from nca.registry import Module
from nca.runtime import execute
from nca.workspace import Workspace
from typing import Never

ALGORITHM_BYTES = 1024
"""Nominal resident size of an exact (non-learned) module."""


def checkpoint_expert(manifest: Manifest, load: Callable[[], Module], path: Path,
                      store: ExpertStore) -> LazyExpert:
    return LazyExpert(manifest, load, path.stat().st_size, store)


def algorithm_expert(module: Module, store: ExpertStore) -> LazyExpert:
    return LazyExpert(module.manifest, lambda: module, ALGORITHM_BYTES, store)


def real_experts(args: argparse.Namespace, store: ExpertStore) -> dict[str, list[LazyExpert]]:
    def recognizer(symbol_set: SymbolSet, path: Path) -> LazyExpert:
        manifest = Manifest(symbol_set.module_id, "1.0.0", Contract((GLYPH,), symbol_set.output))
        return checkpoint_expert(manifest, lambda: SymbolRecognizer.load(path, symbol_set),
                                 path, store)

    digit = checkpoint_expert(Manifest("nca.digit-recognizer", "1.0.0", DIGIT_CONTRACT),
                              lambda: DigitRecognizer.load(args.digit), args.digit, store)
    arithmetic = [algorithm_expert(Segmenter(), store), digit,
                  recognizer(OPERATOR_SET, args.operator),
                  *(algorithm_expert(m, store)
                    for m in (SymbolFuser(), ExpressionParser(), Evaluator()))]
    comparison = [recognizer(RELATION_SET, args.relation),
                  *(algorithm_expert(m, store) for m in
                    (SymbolFuser(COMPARISON), ExpressionParser(COMPARISON),
                     ComparisonEvaluator()))]
    return {"arithmetic": arithmetic, "comparison": comparison}


def decoys(n: int, store: ExpertStore, seed: int) -> list[LazyExpert]:
    """Unusable experts: each needs at least one decoy type, which nothing produces
    from available inputs. A fifth produce real intermediate types, so the planner
    must consider and reject them."""
    rng = random.Random(seed)
    real_outputs = [INTEGER, BOOLEAN, "symbol.distribution.v1", "expression.infix.v1"]
    types = [f"decoy.t{j}.v1" for j in range(max(1, n // 4))]

    def never_loaded() -> Never:
        raise AssertionError("a decoy expert was loaded")

    experts = []
    for i in range(n):
        inputs = tuple(rng.sample(types, min(len(types), rng.randint(1, 2))))
        output = rng.choice(real_outputs) if rng.random() < 0.2 else rng.choice(types)
        manifest = Manifest(f"decoy.{i}", "1.0.0", Contract(inputs, output))
        experts.append(LazyExpert(manifest, never_loaded, 1_000_000, store))
    return experts


def working_set(node: Plan) -> set[str]:
    if isinstance(node, Apply):
        return {node.module.manifest.module_id}.union(*(working_set(a) for a in node.args))
    if isinstance(node, Map):
        return working_set(node.body) | working_set(node.source)
    return set()


def linear_stable(modules: list[LazyExpert], goal: TypeId) -> Plan | None:
    for k in range(len(modules) + 1):
        result = plan(modules[:k], (EXPRESSION_IMAGE,), goal)
        if result is not None:
            return result
    return None


def solve(route: Plan, dataset: ExpressionDataset, count: int) -> list:
    return [
        execute(route, {EXPRESSION_IMAGE: Message(
            EXPRESSION_IMAGE, torch.from_numpy(dataset.sample(i).image), "input")},
            Workspace(), budget=64).payload
        for i in range(count)
    ]


def library_scaling(args: argparse.Namespace) -> None:
    dataset = ExpressionDataset("test", args.samples, args.data, args.seed)
    reference = None
    print(f"{'experts':>8s} {'linear plan':>12s} {'index build':>12s} {'indexed plan':>13s} {'loaded':>7s} "
          f"{'= route':>8s} {'peak MB':>8s} {'same answers':>13s}")
    for n in args.sizes:
        store = ExpertStore()
        real = real_experts(args, store)["arithmetic"]
        extra = decoys(n, store, args.seed)
        modules = extra[: n // 2] + real + extra[n // 2:]

        start = time.perf_counter()
        index = ProducerIndex(modules)
        build_ms = (time.perf_counter() - start) * 1e3
        start = time.perf_counter()
        route = plan_stable_indexed(index, (EXPRESSION_IMAGE,), INTEGER)
        indexed_ms = (time.perf_counter() - start) * 1e3
        if n <= args.linear_limit:
            start = time.perf_counter()
            assert linear_stable(modules, INTEGER) == route
            linear = f"{(time.perf_counter() - start) * 1e3:9.2f} ms"
        else:
            linear = "skipped"

        answers = solve(route, dataset, args.samples)
        reference = reference or answers
        loaded = store.stats.loaded_ids
        print(f"{n:8d} {linear:>12s} {build_ms:9.2f} ms {indexed_ms:10.2f} ms {len(loaded):7d} "
              f"{str(loaded == working_set(route)):>8s} {store.stats.peak_bytes / 1e6:8.2f} "
              f"{str(answers == reference):>13s}")


def budget_experiment(args: argparse.Namespace) -> None:
    datasets = {"arithmetic": ExpressionDataset("test", args.samples, args.data, args.seed),
                "comparison": ExpressionDataset("test", args.samples, args.data, args.seed,
                                                RELATIONS)}
    goals = {"arithmetic": INTEGER, "comparison": BOOLEAN}
    probe = real_experts(args, ExpertStore())
    sizes = {task: sum(e.size for e in experts) for task, experts in probe.items()}
    route_bytes = {"arithmetic": sizes["arithmetic"],
                   "comparison": sizes["comparison"] + sum(
                       e.size for e in probe["arithmetic"][:2])}
    union = sizes["arithmetic"] + sizes["comparison"]
    budgets = {"both routes": union, "larger route": max(route_bytes.values()),
               "unbounded": None}
    print(f"\n{'budget':14s} {'bytes':>10s} {'loads':>6s} {'evictions':>10s} "
          f"{'load time':>10s} {'accuracy':>9s}")
    for name, budget in budgets.items():
        store = ExpertStore(budget)
        experts = real_experts(args, store)
        modules = experts["arithmetic"] + experts["comparison"]
        index = ProducerIndex(modules)
        routes = {t: plan_stable_indexed(index, (EXPRESSION_IMAGE,), g) for t, g in goals.items()}
        correct = 0
        for i in range(args.samples):
            for task in ("arithmetic", "comparison"):
                sample = datasets[task].sample(i)
                result = execute(routes[task], {EXPRESSION_IMAGE: Message(
                    EXPRESSION_IMAGE, torch.from_numpy(sample.image), "input")},
                    Workspace(), budget=64)
                correct += result.payload == sample.value
        stats = store.stats
        shown = "-" if budget is None else str(budget)
        print(f"{name:14s} {shown:>10s} {stats.loads:6d} {stats.evictions:10d} "
              f"{stats.load_seconds:8.2f} s {correct / (2 * args.samples):9.4f}")
    print(f"\nroute sizes: arithmetic {route_bytes['arithmetic']} B, "
          f"comparison {route_bytes['comparison']} B")


def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__.splitlines()[0])
    parser.add_argument("--data", type=Path, default=Path("data"))
    parser.add_argument("--digit", type=Path, default=Path("checkpoints/digit.pt"))
    parser.add_argument("--operator", type=Path, default=Path("checkpoints/operators.pt"))
    parser.add_argument("--relation", type=Path, default=Path("checkpoints/relations.pt"))
    parser.add_argument("--sizes", type=int, nargs="+", default=[0, 10, 100, 1_000, 10_000])
    parser.add_argument("--linear-limit", type=int, default=1_000)
    parser.add_argument("--samples", type=int, default=200)
    parser.add_argument("--seed", type=int, default=0)
    args = parser.parse_args()
    library_scaling(args)
    budget_experiment(args)


if __name__ == "__main__":
    main()
