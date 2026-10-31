"""Add-and-freeze protocol (Experiment 5): capability accumulation without regression.

1. Install the arithmetic modules and evaluate every task in the suite.
2. Install independently trained comparison modules; no existing module is
   modified (verified by weight fingerprints).
3. Re-evaluate the full suite, reporting for each task whether it is covered,
   whether its route changed (``plan`` and ``plan_stable``), its accuracy, and
   how many individual answers changed.

``NCA.planStable_append`` predicts zero route changes and therefore zero
changed answers for tasks that were already solvable.

    uv run --extra vision python -m nca.accumulation
"""

from __future__ import annotations

import argparse
import hashlib
from dataclasses import dataclass
from pathlib import Path

import torch

from nca.abi import Message
from nca.expressions import OPERATORS, RELATIONS, ExpressionDataset
from nca.modules.digit_recognizer import DigitRecognizer
from nca.modules.operator_recognizer import RELATION_SET, SymbolRecognizer
from nca.modules.segmenter import EXPRESSION_IMAGE
from nca.modules.symbols import (
    BOOLEAN, COMPARISON, INTEGER, ComparisonEvaluator, ExpressionParser, SymbolFuser,
)
from nca.pipeline import build_registry
from nca.planner import Plan, plan, plan_stable
from nca.registry import Registry
from nca.runtime import execute
from nca.workspace import Workspace

TASKS = {"arithmetic": (INTEGER, OPERATORS), "comparison": (BOOLEAN, RELATIONS)}


def comparison_modules(relation: SymbolRecognizer) -> list:
    return [relation, SymbolFuser(COMPARISON), ExpressionParser(COMPARISON),
            ComparisonEvaluator()]


def fingerprint(registry: Registry) -> dict[str, str]:
    """SHA-256 of each learned module's weights, keyed by module id."""
    prints = {}
    for module in registry.modules():
        network = getattr(module, "network", None)
        if network is not None:
            digest = hashlib.sha256()
            for name, tensor in sorted(network.state_dict().items()):
                digest.update(name.encode())
                digest.update(tensor.numpy().tobytes())
            prints[module.manifest.module_id] = digest.hexdigest()
    return prints


@dataclass
class TaskResult:
    route: Plan | None
    plain_route: Plan | None
    answers: list

    def accuracy(self, truth: list) -> float:
        return sum(a == t for a, t in zip(self.answers, truth)) / len(truth)


def run_task(registry: Registry, goal: str, dataset: ExpressionDataset) -> TaskResult:
    modules = registry.modules()
    route = plan_stable(modules, (EXPRESSION_IMAGE,), goal)
    plain = plan(modules, (EXPRESSION_IMAGE,), goal)
    answers = []
    for index in range(len(dataset)):
        if route is None:
            answers.append(None)
            continue
        image = torch.from_numpy(dataset.sample(index).image)
        result = execute(route, {EXPRESSION_IMAGE: Message(EXPRESSION_IMAGE, image, "input")},
                         Workspace(), budget=64)
        answers.append(result.payload)
    return TaskResult(route, plain, answers)


def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__.splitlines()[0])
    parser.add_argument("--data", type=Path, default=Path("data"))
    parser.add_argument("--digit", type=Path, default=Path("checkpoints/digit.pt"))
    parser.add_argument("--operator", type=Path, default=Path("checkpoints/operators.pt"))
    parser.add_argument("--relation", type=Path, default=Path("checkpoints/relations.pt"))
    parser.add_argument("--size", type=int, default=5_000)
    parser.add_argument("--seed", type=int, default=0)
    args = parser.parse_args()

    registry = build_registry(DigitRecognizer.load(args.digit),
                              SymbolRecognizer.load(args.operator))
    splits = ("test", "test_unseen")
    datasets = {(task, split): ExpressionDataset(split, args.size, args.data, args.seed, ops)
                for task, (_, ops) in TASKS.items() for split in splits}
    truth = {key: [ds.sample(i).value for i in range(len(ds))] for key, ds in datasets.items()}

    def evaluate_suite() -> dict:
        return {key: run_task(registry, TASKS[key[0]][0], ds) for key, ds in datasets.items()}

    before_prints = fingerprint(registry)
    before = evaluate_suite()
    for module in comparison_modules(SymbolRecognizer.load(args.relation, RELATION_SET)):
        registry.install(module)
    after_prints = fingerprint(registry)
    after = evaluate_suite()

    frozen = all(after_prints[k] == v for k, v in before_prints.items())
    print(f"existing module weights unchanged: {frozen}")
    print(f"installed modules: {len(before_prints)} learned before, {len(after_prints)} after\n")
    print(f"{'task':12s} {'split':12s} {'before':>8s} {'after':>8s} "
          f"{'stable route kept':>18s} {'plain route kept':>17s} {'changed answers':>16s}")
    for key in datasets:
        b, a = before[key], after[key]
        kept = "n/a" if b.route is None else str(b.route == a.route)
        plain_kept = "n/a" if b.plain_route is None else str(b.plain_route == a.plain_route)
        changed = sum(x != y for x, y in zip(b.answers, a.answers)) if b.route else "n/a"
        acc = lambda r: "-" if r.route is None else f"{r.accuracy(truth[key]):.4f}"
        print(f"{key[0]:12s} {key[1]:12s} {acc(b):>8s} {acc(a):>8s} "
              f"{kept:>18s} {plain_kept:>17s} {str(changed):>16s}")


if __name__ == "__main__":
    main()
