"""Selective answering on handwritten arithmetic (§16, §22).

The experiment installs the handwritten-arithmetic library: cheap, expensive
and (optionally) stronger digit recognizers, the operator recognizer, and
``SecondLook`` versions of all but the cheapest, which average readings of
four one-pixel shifts. It reports, per expression length and target δ:
coverage, error among answered expressions, mean bound among answered (a
calibration check), error when forced to answer, and compute per expression.

    uv run --extra vision python -m nca.domains.arithmetic.abstention --cheap checkpoints/digit_mlp.pt \\
        --expensive checkpoints/digit_cnn.pt
"""

from __future__ import annotations

import argparse
from pathlib import Path
from typing import Any

import torch

from nca.abi import Module, TypeId
from nca.cost import costed, network_flops
from nca.domains.arithmetic.digit_recognizer import DIGIT_DISTRIBUTION, DigitRecognizer
from nca.domains.arithmetic.expressions import ExpressionDataset
from nca.domains.arithmetic.operator_recognizer import (OPERATOR_DISTRIBUTION, SymbolRecognizer,
                                                        make_dataset)
from nca.domains.arithmetic.segmenter import EXPRESSION_IMAGE, Segmenter
from nca.domains.arithmetic.symbols import INTEGER, Evaluator, ExpressionParser, SymbolFuser
from nca.ladder import SecondLook
from nca.planner import plan_stable
from nca.selective import build_ladders, solve
from nca.stats import wilson

SHIFTS = ((1, 0), (-1, 0), (0, 1), (0, -1))
GLYPH_SHAPE = (1, 28, 28)


def shifted(glyph: torch.Tensor) -> list[torch.Tensor]:
    return [torch.roll(glyph, shift, dims=(0, 1)) for shift in SHIFTS]



def validation_data(data: Path, seed: int,
                    size: int) -> dict[TypeId, tuple[list[Any], torch.Tensor]]:
    """Held-out labeled glyphs from the validation half of the MNIST test set."""
    from torchvision import datasets

    mnist = datasets.MNIST(data, train=False, download=True)
    digits = mnist.data[:size].float() / 255.0
    glyphs, labels = make_dataset(digits.numpy(), size, seed).tensors
    return {DIGIT_DISTRIBUTION: (list(digits), mnist.targets[:size]),
            OPERATOR_DISTRIBUTION: (list(glyphs[:, 0]), labels)}


def library(args: argparse.Namespace) -> list[Module]:
    def recognizer(path: Path, name: str) -> Module:
        module = DigitRecognizer.load(path)
        return costed(module, network_flops(module.network, GLYPH_SHAPE),
                      f"nca.digit-recognizer.{name}")

    digits = [recognizer(args.cheap, "cheap"), recognizer(args.expensive, "expensive")]
    if args.strong is not None:
        digits.append(recognizer(args.strong, "strong"))
    operator = SymbolRecognizer.load(args.operator)
    costed(operator, network_flops(operator.network, GLYPH_SHAPE))
    looks = [SecondLook(m, shifted, len(SHIFTS)) for m in (*digits[1:], operator)]
    return [Segmenter(), *digits, operator, *looks, SymbolFuser(), ExpressionParser(),
            Evaluator()]


def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__.splitlines()[0])
    parser.add_argument("--data", type=Path, default=Path("data"))
    parser.add_argument("--cheap", type=Path, required=True)
    parser.add_argument("--expensive", type=Path, required=True)
    parser.add_argument("--strong", type=Path, help="a stronger digit recognizer")
    parser.add_argument("--operator", type=Path, default=Path("checkpoints/operators.pt"))
    parser.add_argument("--samples", type=int, default=300)
    parser.add_argument("--calibration", type=int, default=2000)
    parser.add_argument("--seed", type=int, default=0)
    parser.add_argument("--operands", type=int, nargs="+", default=[2, 8, 32])
    parser.add_argument("--targets", type=float, nargs="+", default=[0.2, 0.05, 0.01])
    parser.add_argument("--hard", action="store_true", help="the shifted hard style")
    parser.add_argument("--floors", action="store_true",
                        help="also abstain early by the additive floor, checking answers agree")
    args = parser.parse_args()

    modules = library(args)
    route = plan_stable(modules, (EXPRESSION_IMAGE,), INTEGER)
    assert route is not None
    ladders = build_ladders(modules, route,
                            validation_data(args.data, args.seed, args.calibration))
    for t, rungs in ladders.items():
        print(f"{t}: " + ", ".join(f"{r.module.manifest.module_id} (T={r.temperature():.2f})"
                                   for r in rungs))
    print(f"{'glyphs':>7s} {'system':>13s} {'coverage':>9s} {'error answered [95% CI]':>27s} "
          f"{'mean bound':>11s} {'error forced':>13s} {'MFLOPs/expr':>12s}"
          + (f" {'floor MFLOPs':>12s} {'same':>5s}" if args.floors else ""))
    top = max(len(rungs) for rungs in ladders.values())
    for operands in args.operands:
        dataset = ExpressionDataset("test", args.samples, args.data, args.seed,
                                    hard=args.hard, operands=operands)
        samples = [dataset.sample(i) for i in range(len(dataset))]
        systems = {"bottom rungs": (float("inf"), 0), "top rungs": (float("inf"), top)}
        systems |= {f"δ={d:g}": (d, 0) for d in args.targets}
        for name, (delta, start) in systems.items():
            answered = wrong_answered = wrong_forced = 0
            spent = bound_sum = early_spent = 0.0
            same = True
            for sample in samples:
                answer = solve(route, ladders, torch.from_numpy(sample.image), delta, start)
                if args.floors:
                    early = solve(route, ladders, torch.from_numpy(sample.image), delta, start,
                                  floors=True)
                    early_spent += early.cost
                    same &= early.abstained == answer.abstained and (
                        answer.abstained or early.value == answer.value)
                wrong = answer.value != sample.value
                spent += answer.cost
                wrong_forced += wrong
                if not answer.abstained:
                    answered += 1
                    wrong_answered += wrong
                    bound_sum += answer.bound
            n = len(samples)
            low, high = wilson(wrong_answered, answered) if answered else (0.0, 1.0)
            rate = wrong_answered / answered if answered else float("nan")
            mean_bound = bound_sum / answered if answered else float("nan")
            print(f"{2 * operands - 1:7d} {name:>13s} {answered / n:9.3f} "
                  f"{rate:.4f} [{low:.4f}, {high:.4f}]".ljust(59)
                  + f" {mean_bound:11.4f} {wrong_forced / n:13.4f} {spent / n / 1e6:12.2f}"
                  + (f" {early_spent / n / 1e6:12.2f} {str(same):>5s}" if args.floors else ""),
                  flush=True)


if __name__ == "__main__":
    main()
