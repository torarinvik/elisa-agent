"""Modular handwritten-arithmetic pipeline (Experiments 2-3).

Installs independently trained or implemented modules, lets the stable
planner compose them for the goal ``int.v1`` from an expression image, and
evaluates on the expression splits alongside the reliability bounds of
``lean/NCA/Reliability/Reliability.lean``:

* per-invocation failure rates are measured in situ (segmentation, each
  glyph's symbol);
* the union bound ``P(wrong) <= sum of failure rates`` is a theorem for any
  measure, so on the empirical measure it can only fail if the propagation
  hypothesis (no module failure implies a correct answer) is false;
* the independent product bound predicts accuracy from the failure rates;
* accuracies carry 95% Wilson intervals, and every split is also evaluated
  in the ``hard`` style (a deliberate distribution shift);
* each recognizer's in-situ failure rate is compared with its offline rate
  on its own test distribution. By ``NCA.shift_ge_gap`` the excess is a lower
  bound on the shift between the input distribution the composition feeds it
  and the one it was evaluated on (``lean/NCA/Reliability/Shift.lean``).

At digit positions the parser's restricted argmax equals the digit
recognizer's argmax, and at operator positions the operator recognizer's
argmax over operators, so positional failures are exactly module failures.

    uv run --extra vision python -m nca.domains.arithmetic.pipeline
"""

from __future__ import annotations

import argparse
from dataclasses import dataclass
from pathlib import Path

import torch

from nca.abi import Message
from nca.domains.arithmetic.expressions import ExpressionDataset
from nca.domains.arithmetic.digit_recognizer import DigitRecognizer
from nca.domains.arithmetic.operator_recognizer import SymbolRecognizer, make_dataset
from nca.domains.arithmetic.normalizer import GlyphNormalizer, normalize_all
from nca.domains.arithmetic.segmenter import EXPRESSION_IMAGE, Segmenter
from nca.domains.arithmetic.symbols import (
    INTEGER, SYMBOL_DISTRIBUTION, Evaluator, ExpressionParser, SymbolFuser,
)
from nca.planner import Plan, plan_stable
from nca.registry import Registry
from nca.runtime import execute
from nca.stats import wilson
from nca.workspace import Workspace


def build_registry(digit: DigitRecognizer, operator: SymbolRecognizer) -> Registry:
    registry = Registry()
    for module in (Segmenter(), GlyphNormalizer(), digit, operator, SymbolFuser(),
                   ExpressionParser(), Evaluator()):
        registry.install(module)
    return registry


def compose(registry: Registry) -> Plan:
    graph = plan_stable(registry.modules(), (EXPRESSION_IMAGE,), INTEGER)
    if graph is None:
        raise RuntimeError("installed modules cannot produce int.v1 from an image")
    return graph


@dataclass
class Report:
    samples: int = 0
    correct: int = 0
    segmentation_failures: int = 0
    symbol_failures: tuple[int, int, int] = (0, 0, 0)

    @property
    def accuracy(self) -> float:
        return self.correct / self.samples

    def failure_rates(self) -> list[float]:
        return [self.segmentation_failures / self.samples,
                *(f / self.samples for f in self.symbol_failures)]

    @property
    def union_bound(self) -> float:
        return max(0.0, 1.0 - sum(self.failure_rates()))

    @property
    def product_bound(self) -> float:
        result = 1.0
        for rate in self.failure_rates():
            result *= 1.0 - rate
        return result


def evaluate(graph: Plan, dataset: ExpressionDataset) -> Report:
    report = Report()
    failures = [0, 0, 0]
    for index in range(len(dataset)):
        sample = dataset.sample(index)
        workspace = Workspace()
        image = Message(EXPRESSION_IMAGE, torch.from_numpy(sample.image), "input")
        result = execute(graph, {EXPRESSION_IMAGE: image}, workspace, budget=64)

        symbols = [m.payload for m in workspace.messages()
                   if m.type_id == SYMBOL_DISTRIBUTION]
        report.samples += 1
        report.correct += result.payload == sample.value
        if len(symbols) != len(sample.tokens):
            report.segmentation_failures += 1
            continue
        for position, (dist, token) in enumerate(zip(symbols, sample.tokens)):
            classes = "0123456789" if position % 2 == 0 else "+-*"
            failures[position] += max(classes, key=dist.__getitem__) != token
    report.symbol_failures = tuple(failures)
    return report


@torch.no_grad()
def offline_failure_rates(digit: DigitRecognizer, operator: SymbolRecognizer,
                          data_dir: Path, seed: int) -> tuple[float, float]:
    """(digit, operator) failure rates on each recognizer's own test distribution.

    The operator rate counts the argmax over operators only, on operator glyphs,
    matching how the parser uses the operator recognizer.
    """
    from torchvision import datasets

    mnist = datasets.MNIST(data_dir, train=False, download=True)
    raw = mnist.data.numpy() / 255.0
    images = torch.from_numpy(normalize_all(raw) if digit.normalized else raw).float()[:, None]
    digit_error = (digit.network(images).argmax(dim=1) != mnist.targets).float().mean()

    glyphs, labels = make_dataset(raw, 10_000, seed + 1, normalized=operator.normalized).tensors
    is_operator = labels < 3
    logits = operator.network(glyphs[is_operator])[:, :3]
    operator_error = (logits.argmax(dim=1) != labels[is_operator]).float().mean()
    return digit_error.item(), operator_error.item()


def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__.splitlines()[0])
    parser.add_argument("--data", type=Path, default=Path("data"))
    parser.add_argument("--digit", type=Path, default=Path("checkpoints/digit.pt"))
    parser.add_argument("--operator", type=Path, default=Path("checkpoints/operators.pt"))
    parser.add_argument("--size", type=int, default=10_000)
    parser.add_argument("--seed", type=int, default=0)
    args = parser.parse_args()

    digit = DigitRecognizer.load(args.digit)
    operator = SymbolRecognizer.load(args.operator)
    graph = compose(build_registry(digit, operator))
    offline_digit, offline_operator = offline_failure_rates(digit, operator, args.data,
                                                            args.seed)
    print(f"offline failure rates: digit {offline_digit:.4f}, "
          f"operator {offline_operator:.4f}\n")
    print(f"{'split':17s} {'accuracy [95% CI]':>26s} {'union':>7s} {'product':>8s}  "
          "failure rates (segment, digit, operator, digit)")
    for split, hard in (("test", False), ("test_unseen", False),
                        ("test", True), ("test_unseen", True)):
        dataset = ExpressionDataset(split, args.size, args.data, args.seed, hard=hard)
        report = evaluate(graph, dataset)
        rates = ", ".join(f"{r:.4f}" for r in report.failure_rates())
        low, high = wilson(report.correct, report.samples)
        name = f"{split}{' (hard)' if hard else ''}"
        print(f"{name:17s} {report.accuracy:.4f} [{low:.4f}, {high:.4f}]".ljust(44)
              + f" {report.union_bound:7.4f} {report.product_bound:8.4f}  {rates}")
        _, d1, op, d2 = report.failure_rates()
        print(f"{'':17s} shift lower bounds: digit {max(0.0, (d1 + d2) / 2 - offline_digit):.4f}, "
              f"operator {max(0.0, op - offline_operator):.4f}")


if __name__ == "__main__":
    main()
