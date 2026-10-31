"""Complementarity and unseen combinations (Experiment 7).

The mixed task ``a op b rel c`` needs both arithmetic and comparison; neither
capability alone solves it. Systems, each built from frozen modules:

* ``A``: arithmetic modules only;
* ``B``: comparison modules only;
* ``A+B``: both installed (Experiment 5);
* ``A⊕B``: both plus three exact integration modules (mixed symbol fuser,
  relational parser, relational evaluator). No module is trained on the
  mixed task.

``A⊕B`` produces the same goal type (``bool.v1``) as comparison, so stable
routing keeps the comparison route for it. The integration route is proposed
as an explicit upgrade, evaluated on a validation suite mixing both boolean
tasks, and pinned only if a sign test accepts it.

Reports accuracy of every system on every task, the majority-class baseline,
an optional monolithic CNN trained on the mixed task, and the composition gain
``G = Q(A⊕B) − max(Q(A), Q(B), Q(A+B), baselines)`` on the mixed task.

    uv run --extra vision python -m nca.complementarity --baseline checkpoints/baseline_mixed.pt
"""

from __future__ import annotations

import argparse
from collections import Counter
from pathlib import Path

import torch

from nca.accumulation import answers_for, comparison_modules
from nca.baseline import TASKS as BASELINE_TASKS, build_network as build_baseline
from nca.expressions import OPERATORS, RELATIONS, ExpressionDataset
from nca.modules.digit_recognizer import DigitRecognizer
from nca.modules.operator_recognizer import RELATION_SET, SymbolRecognizer
from nca.modules.segmenter import EXPRESSION_IMAGE, Segmenter
from nca.modules.symbols import (
    BOOLEAN, INTEGER, Evaluator, ExpressionParser, MixedSymbolFuser, RelationalEvaluator,
    RelationalParser, SymbolFuser,
)
from nca.planner import plan
from nca.registry import Registry
from nca.router import Router, sign_test

TASKS = {"arithmetic": INTEGER, "comparison": BOOLEAN, "mixed": BOOLEAN}


def integration_modules() -> list:
    return [MixedSymbolFuser(), RelationalParser(), RelationalEvaluator()]


def task_dataset(task: str, split: str, size: int, data_dir: Path, seed: int) -> ExpressionDataset:
    if task == "mixed":
        return ExpressionDataset(split, size, data_dir, seed, mixed=True)
    operators = RELATIONS if task == "comparison" else OPERATORS
    return ExpressionDataset(split, size, data_dir, seed, operators)


def build_systems(digit: DigitRecognizer, operator: SymbolRecognizer,
                  relation: SymbolRecognizer) -> dict[str, list]:
    arithmetic = [Segmenter(), digit, operator, SymbolFuser(), ExpressionParser(), Evaluator()]
    comparison = comparison_modules(relation)
    return {
        "A": arithmetic,
        "B": [Segmenter(), digit, *comparison],
        "A+B": arithmetic + comparison,
        "A⊕B": arithmetic + comparison + integration_modules(),
    }


def registry_of(modules: list) -> Registry:
    registry = Registry()
    for module in modules:
        registry.install(module)
    return registry


def accuracy(answers: list, truth: list) -> float:
    return sum(a == t for a, t in zip(answers, truth)) / len(truth)


@torch.no_grad()
def monolithic_accuracy(path: Path, dataset: ExpressionDataset) -> float:
    network = build_baseline(*BASELINE_TASKS["mixed"])
    network.load_state_dict(torch.load(path, map_location="cpu"))
    network.eval()
    correct = 0
    for images, labels in torch.utils.data.DataLoader(dataset, batch_size=500):
        correct += (network(images).argmax(dim=1) == labels).sum().item()
    return correct / len(dataset)


def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__.splitlines()[0])
    parser.add_argument("--data", type=Path, default=Path("data"))
    parser.add_argument("--digit", type=Path, default=Path("checkpoints/digit.pt"))
    parser.add_argument("--operator", type=Path, default=Path("checkpoints/operators.pt"))
    parser.add_argument("--relation", type=Path, default=Path("checkpoints/relations.pt"))
    parser.add_argument("--baseline", type=Path, help="monolithic mixed-task checkpoint")
    parser.add_argument("--size", type=int, default=2_000)
    parser.add_argument("--seed", type=int, default=0)
    args = parser.parse_args()

    systems = build_systems(DigitRecognizer.load(args.digit),
                            SymbolRecognizer.load(args.operator),
                            SymbolRecognizer.load(args.relation, RELATION_SET))
    splits = ("test", "test_unseen")
    datasets = {(t, s): task_dataset(t, s, args.size, args.data, args.seed)
                for t in TASKS for s in splits}
    truth = {k: [ds.sample(i).value for i in range(len(ds))] for k, ds in datasets.items()}

    full = registry_of(systems["A⊕B"])
    router = Router()
    candidate = plan(integration_modules_of(full) + full.modules(), (EXPRESSION_IMAGE,), BOOLEAN)
    current = router.route(full.modules(), (EXPRESSION_IMAGE,), BOOLEAN)
    validation = [task_dataset(t, "test", args.size // 2, args.data, args.seed + 1)
                  for t in ("comparison", "mixed")]
    current_ok, candidate_ok = [], []
    for dataset in validation:
        values = [dataset.sample(i).value for i in range(len(dataset))]
        current_ok += [a == v for a, v in zip(answers_for(current, dataset), values)]
        candidate_ok += [a == v for a, v in zip(answers_for(candidate, dataset), values)]
    accept, p_value = sign_test(current_ok, candidate_ok)
    print(f"upgrade bool.v1 to the integration route: validation accuracy "
          f"{sum(current_ok) / len(current_ok):.4f} -> {sum(candidate_ok) / len(candidate_ok):.4f}, "
          f"p = {p_value:.3g}: {'accepted' if accept else 'rejected'}\n")
    if accept:
        router.upgrade(full.modules(), (EXPRESSION_IMAGE,), BOOLEAN, candidate)

    print(f"{'task':12s} {'split':12s} " + " ".join(f"{name:>8s}" for name in systems)
          + f" {'majority':>9s} {'mono':>7s} {'gain':>7s}")
    for (task, split), dataset in datasets.items():
        scores = {}
        for name, modules in systems.items():
            registry = full if name == "A⊕B" else registry_of(modules)
            route = (router if name == "A⊕B" else Router()).route(
                registry.modules(), (EXPRESSION_IMAGE,), TASKS[task])
            scores[name] = 0.0 if route is None else accuracy(
                answers_for(route, dataset), truth[(task, split)])
        majority = Counter(truth[(task, split)]).most_common(1)[0][1] / len(dataset)
        mono = (monolithic_accuracy(args.baseline, dataset)
                if task == "mixed" and args.baseline else None)
        baselines = [scores["A"], scores["B"], scores["A+B"], majority] + (
            [mono] if mono is not None else [])
        gain = scores["A⊕B"] - max(baselines)
        cells = " ".join(f"{scores[n]:8.4f}" for n in systems)
        mono_cell = "-" if mono is None else f"{mono:.4f}"
        print(f"{task:12s} {split:12s} {cells} {majority:9.4f} {mono_cell:>7s} {gain:+7.4f}")


def integration_modules_of(registry: Registry) -> list:
    """The installed integration modules, to plan with them preferred."""
    ids = {m.manifest.module_id for m in integration_modules()}
    return [m for m in registry.modules() if m.manifest.module_id in ids]


if __name__ == "__main__":
    main()
