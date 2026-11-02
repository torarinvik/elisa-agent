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

    uv run --extra vision python -m nca.domains.arithmetic.complementarity --baseline checkpoints/baseline_mixed.pt
"""

from __future__ import annotations

import argparse
from collections import Counter
from pathlib import Path

import torch

from nca.domains.arithmetic.accumulation import answers_for, comparison_modules
from nca.domains.arithmetic.baseline import TASKS as BASELINE_TASKS, build_network as build_baseline
from nca.domains.arithmetic.expressions import OPERATORS, RELATIONS, ExpressionDataset
from nca.domains.arithmetic.digit_recognizer import DigitRecognizer
from nca.domains.arithmetic.operator_recognizer import RELATION_SET, SymbolRecognizer
from nca.domains.arithmetic.segmenter import EXPRESSION_IMAGE, Segmenter
from nca.domains.arithmetic.symbols import (
    BOOLEAN, INTEGER, Evaluator, ExpressionParser, MixedSymbolFuser, RelationalEvaluator,
    RelationalParser, SymbolFuser,
)
from nca.planner import plan
from nca.registry import Registry
from nca.router import Router, sign_test
from nca.stats import format_interval, paired_difference, wilson

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


@torch.no_grad()
def monolithic_correct(path: Path, dataset: ExpressionDataset) -> list[bool]:
    network = build_baseline(*BASELINE_TASKS["mixed"])
    network.load_state_dict(torch.load(path, map_location="cpu"))
    network.eval()
    correct: list[bool] = []
    for images, labels in torch.utils.data.DataLoader(dataset, batch_size=500):
        correct += (network(images).argmax(dim=1) == labels).tolist()
    return correct


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
    validation = [task_dataset(t, "validation", args.size // 2, args.data, args.seed)
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
          + f" {'majority':>9s} {'mono':>7s}")
    gains = []
    for (task, split), dataset in datasets.items():
        values = truth[(task, split)]
        correct: dict[str, list[bool]] = {}
        for name, modules in systems.items():
            registry = full if name == "A⊕B" else registry_of(modules)
            route = (router if name == "A⊕B" else Router()).route(
                registry.modules(), (EXPRESSION_IMAGE,), TASKS[task])
            correct[name] = ([False] * len(values) if route is None else
                             [a == v for a, v in zip(answers_for(route, dataset), values)])
        majority_value = Counter(values).most_common(1)[0][0]
        correct["majority"] = [v == majority_value for v in values]
        if task == "mixed" and args.baseline:
            correct["mono"] = monolithic_correct(args.baseline, dataset)
        rate = {k: sum(v) / len(v) for k, v in correct.items()}
        cells = " ".join(f"{rate[n]:8.4f}" for n in systems)
        mono_cell = f"{rate['mono']:.4f}" if "mono" in rate else "-"
        print(f"{task:12s} {split:12s} {cells} {rate['majority']:9.4f} {mono_cell:>7s}")
        if task == "mixed":
            best = max((k for k in correct if k != "A⊕B"), key=rate.__getitem__)
            gains.append((split, correct["A⊕B"], best, correct[best]))

    print("\nmixed task, 95% intervals (Wilson for accuracy; paired for gain):")
    for split, ours, best, theirs in gains:
        low, high = wilson(sum(ours), len(ours))
        print(f"  {split:12s} A⊕B {format_interval(sum(ours) / len(ours), low, high)}; "
              f"gain over {best}: {format_interval(*paired_difference(theirs, ours))}")


def integration_modules_of(registry: Registry) -> list:
    """The installed integration modules, to plan with them preferred."""
    ids = {m.manifest.module_id for m in integration_modules()}
    return [m for m in registry.modules() if m.manifest.module_id in ids]


if __name__ == "__main__":
    main()
