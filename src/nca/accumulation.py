"""Add-and-freeze protocol (Experiment 5): capability accumulation without regression.

1. Install a base system and evaluate every task in the suite.
2. Install new modules; no existing module is modified (verified by weight
   fingerprints).
3. Re-evaluate the full suite. For each task and for both planners (``plan``
   and ``plan_stable``) report coverage, accuracy, whether the route changed,
   and how many individual answers changed.

Scenarios:

* ``comparison``: install the comparison modules into the arithmetic system.
* ``conflict``: the base system also contains a dormant symbol classifier
  (its input type, a glyph embedding, has no producer); install a glyph
  encoder. This is ``NCA.plan_not_stable`` on real modules: ``plan`` reroutes
  the arithmetic task through the newly activated classifier.

``NCA.planStable_append`` predicts zero route changes and therefore zero
changed answers for tasks that were already solvable under ``plan_stable``.

Afterwards, wherever ``plan`` now proposes a different route than the stable
one, that route is considered as an explicit upgrade: both are evaluated on the
validation split (digit images disjoint from the test splits) and the candidate is pinned only if a one-sided
sign test on paired correctness accepts it (``nca.router``).

    uv run --extra vision python -m nca.accumulation --scenario conflict
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
from nca.modules import symbol_classifier
from nca.modules.operator_recognizer import RELATION_SET, SymbolRecognizer
from nca.modules.segmenter import EXPRESSION_IMAGE, Segmenter
from nca.modules.symbols import (
    BOOLEAN, COMPARISON, INTEGER, ComparisonEvaluator, Evaluator, ExpressionParser,
    SymbolFuser,
)
from nca.planner import Plan, plan, plan_stable
from nca.registry import Registry
from nca.router import Router, sign_test
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
    routes: dict[str, Plan | None]
    """Route chosen by each planner, keyed ``"stable"`` and ``"plain"``."""
    answers: dict[str, list]


PLANNERS = {"stable": plan_stable, "plain": plan}


def run_task(registry: Registry, goal: str, dataset: ExpressionDataset) -> TaskResult:
    modules = registry.modules()
    routes = {name: planner(modules, (EXPRESSION_IMAGE,), goal)
              for name, planner in PLANNERS.items()}
    answers: dict[str, list] = {}
    for name, route in routes.items():
        reused = [n for n in answers if routes[n] == route]
        if reused:
            answers[name] = answers[reused[0]]
            continue
        answers[name] = []
        for index in range(len(dataset)):
            if route is None:
                answers[name].append(None)
                continue
            image = torch.from_numpy(dataset.sample(index).image)
            inputs = {EXPRESSION_IMAGE: Message(EXPRESSION_IMAGE, image, "input")}
            answers[name].append(execute(route, inputs, Workspace(), budget=64).payload)
    return TaskResult(routes, answers)


def answers_for(route: Plan, dataset: ExpressionDataset) -> list:
    answers = []
    for index in range(len(dataset)):
        image = torch.from_numpy(dataset.sample(index).image)
        inputs = {EXPRESSION_IMAGE: Message(EXPRESSION_IMAGE, image, "input")}
        answers.append(execute(route, inputs, Workspace(), budget=64).payload)
    return answers


def consider_upgrades(registry: Registry, router: Router, validation: dict) -> None:
    """Pin ``plan``'s route where it differs from the current one and wins a sign test."""
    for task, dataset in validation.items():
        goal = TASKS[task][0]
        current = router.route(registry.modules(), (EXPRESSION_IMAGE,), goal)
        candidate = plan(registry.modules(), (EXPRESSION_IMAGE,), goal)
        if current is None or candidate is None or candidate == current:
            continue
        truth = [dataset.sample(i).value for i in range(len(dataset))]

        def correct(route: Plan) -> list[bool]:
            return [a == t for a, t in zip(answers_for(route, dataset), truth)]

        current_ok, candidate_ok = correct(current), correct(candidate)
        accept, p_value = sign_test(current_ok, candidate_ok)
        wins = sum(c and not o for o, c in zip(current_ok, candidate_ok))
        losses = sum(o and not c for o, c in zip(current_ok, candidate_ok))
        print(f"upgrade candidate for {task}: validation accuracy "
              f"{sum(current_ok) / len(truth):.4f} -> {sum(candidate_ok) / len(truth):.4f}, "
              f"wins {wins}, losses {losses}, p = {p_value:.3g}: "
              + ("accepted" if accept else "rejected"))
        if accept:
            router.upgrade(registry.modules(), (EXPRESSION_IMAGE,), goal, candidate)


def build_scenario(name: str, args: argparse.Namespace) -> tuple[Registry, list]:
    """Base registry and the modules installed into it."""
    digit = DigitRecognizer.load(args.digit)
    operator = SymbolRecognizer.load(args.operator)
    base = [Segmenter(), digit, operator]
    if name == "comparison":
        new = comparison_modules(SymbolRecognizer.load(args.relation, RELATION_SET))
    else:
        encoder, classifier = symbol_classifier.load(args.symbol_classifier)
        base.append(classifier)
        new = [encoder]
    base += [SymbolFuser(), ExpressionParser(), Evaluator()]
    registry = Registry()
    for module in base:
        registry.install(module)
    return registry, new


def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__.splitlines()[0])
    parser.add_argument("--scenario", choices=("comparison", "conflict"), default="comparison")
    parser.add_argument("--data", type=Path, default=Path("data"))
    parser.add_argument("--digit", type=Path, default=Path("checkpoints/digit.pt"))
    parser.add_argument("--operator", type=Path, default=Path("checkpoints/operators.pt"))
    parser.add_argument("--relation", type=Path, default=Path("checkpoints/relations.pt"))
    parser.add_argument("--symbol-classifier", type=Path,
                        default=Path("checkpoints/symbol_classifier.pt"))
    parser.add_argument("--size", type=int, default=5_000)
    parser.add_argument("--seed", type=int, default=0)
    args = parser.parse_args()

    registry, new_modules = build_scenario(args.scenario, args)
    splits = ("test", "test_unseen")
    datasets = {(task, split): ExpressionDataset(split, args.size, args.data, args.seed, ops)
                for task, (_, ops) in TASKS.items() for split in splits}
    truth = {key: [ds.sample(i).value for i in range(len(ds))] for key, ds in datasets.items()}

    def evaluate_suite() -> dict:
        return {key: run_task(registry, TASKS[key[0]][0], ds) for key, ds in datasets.items()}

    before_prints = fingerprint(registry)
    before = evaluate_suite()
    for module in new_modules:
        registry.install(module)
    after_prints = fingerprint(registry)
    after = evaluate_suite()

    frozen = all(after_prints[k] == v for k, v in before_prints.items())
    print(f"scenario: {args.scenario}; installed: "
          + ", ".join(m.manifest.module_id for m in new_modules))
    print(f"existing module weights unchanged: {frozen}\n")
    print(f"{'task':12s} {'split':12s} {'planner':8s} {'before':>8s} {'after':>8s} "
          f"{'route kept':>11s} {'changed answers':>16s}")
    for key in datasets:
        for name in PLANNERS:
            b_route, a_route = before[key].routes[name], after[key].routes[name]
            b, a = before[key].answers[name], after[key].answers[name]

            def acc(route: Plan | None, ans: list) -> str:
                if route is None:
                    return "-"
                return f"{sum(x == t for x, t in zip(ans, truth[key])) / len(ans):.4f}"

            kept = "n/a" if b_route is None else str(b_route == a_route)
            changed = "n/a" if b_route is None else str(sum(x != y for x, y in zip(b, a)))
            print(f"{key[0]:12s} {key[1]:12s} {name:8s} {acc(b_route, b):>8s} "
                  f"{acc(a_route, a):>8s} {kept:>11s} {changed:>16s}")

    print()
    validation = {task: ExpressionDataset("validation", args.size, args.data, args.seed, ops)
                  for task, (_, ops) in TASKS.items()}
    router = Router()
    consider_upgrades(registry, router, validation)
    if not router.pins:
        print("no upgrades pinned; routes unchanged")
    for key, dataset in datasets.items():
        goal = TASKS[key[0]][0]
        if goal in router.pins:
            answers = answers_for(router.pins[goal], dataset)
            accuracy = sum(a == t for a, t in zip(answers, truth[key])) / len(answers)
            print(f"after upgrade: {key[0]} {key[1]} accuracy {accuracy:.4f}")


if __name__ == "__main__":
    main()
