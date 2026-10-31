"""Modular handwritten-arithmetic pipeline (Experiments 2-3).

Installs independently trained or implemented modules, lets the stable
planner compose them for the goal ``int.v1`` from an expression image, and
evaluates on the expression splits alongside the reliability bounds of
``lean/NCA/Reliability.lean``:

* per-invocation failure rates are measured in situ (segmentation, each
  glyph's symbol);
* the union bound ``P(wrong) <= sum of failure rates`` is a theorem for any
  measure, so on the empirical measure it can only fail if the propagation
  hypothesis (no module failure implies a correct answer) is false;
* the independent product bound predicts accuracy from the failure rates.

    uv run --extra vision python -m nca.pipeline
"""

from __future__ import annotations

import argparse
from dataclasses import dataclass
from pathlib import Path

import torch

from nca.abi import Message
from nca.expressions import SPLITS, ExpressionDataset
from nca.modules.digit_recognizer import DigitRecognizer
from nca.modules.operator_recognizer import OperatorRecognizer
from nca.modules.segmenter import EXPRESSION_IMAGE, Segmenter
from nca.modules.symbols import (
    INTEGER, SYMBOL_DISTRIBUTION, Evaluator, ExpressionParser, SymbolFuser,
)
from nca.planner import Plan, plan_stable
from nca.registry import Registry
from nca.runtime import execute
from nca.workspace import Workspace


def build_registry(digit: DigitRecognizer, operator: OperatorRecognizer) -> Registry:
    registry = Registry()
    for module in (Segmenter(), digit, operator, SymbolFuser(), ExpressionParser(),
                   Evaluator()):
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


def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__.splitlines()[0])
    parser.add_argument("--data", type=Path, default=Path("data"))
    parser.add_argument("--digit", type=Path, default=Path("checkpoints/digit.pt"))
    parser.add_argument("--operator", type=Path, default=Path("checkpoints/operator.pt"))
    parser.add_argument("--size", type=int, default=10_000)
    parser.add_argument("--seed", type=int, default=0)
    args = parser.parse_args()

    registry = build_registry(DigitRecognizer.load(args.digit),
                              OperatorRecognizer.load(args.operator))
    graph = compose(registry)
    print(f"{'split':12s} {'accuracy':>9s} {'union':>7s} {'product':>8s}  "
          "failure rates (segment, digit, operator, digit)")
    for split in SPLITS:
        report = evaluate(graph, ExpressionDataset(split, args.size, args.data, args.seed))
        rates = ", ".join(f"{r:.4f}" for r in report.failure_rates())
        print(f"{split:12s} {report.accuracy:9.4f} {report.union_bound:7.4f} "
              f"{report.product_bound:8.4f}  {rates}")


if __name__ == "__main__":
    main()
