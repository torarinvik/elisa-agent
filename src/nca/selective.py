"""Selective answering with budgeted refinement.

Every glyph is read by the cheapest expert first, with temperature-calibrated
probabilities (fitted on the ``validation`` split). The answer's error bound
is the sum of the glyphs' estimated error probabilities ``1 - max p``, by the
union bound. While the bound exceeds a target ``δ``, the least confident glyph
moves one rung up its ladder:

* digits: cheap recognizer, expensive recognizer, expensive recognizer looking
  again at four one-pixel shifts of the glyph (averaged with its first look);
* operators: operator recognizer, then the same second look.

If no rung remains, the system abstains. For calibrated bounds the error rate
among answered expressions is at most ``δ`` (``NCA.selective_risk_le``);
refining where the bound falls most per unit of compute is the
``NCA.threshold_optimal`` rule, with a glyph's current error estimate as its
expected reduction. Odd-length segmentations are parsed as in the pipeline
(digits at even positions, operators at odd ones); even-length ones are
unparseable and abstained on.

Reports, per expression length and target: coverage, error among answered
expressions, mean bound among answered (a calibration check), error when the
system must answer after refining as far as the target asks, and compute per
expression. References: each ladder's bottom rung and top rung everywhere.

Segmentation is repaired with the same structural knowledge: an expression
has an odd number of glyphs, so an even count means a glyph was split (or two
merged). The repair merges the two adjacent ink runs separated by the
narrowest gap, the likeliest split, before reading.

    uv run --extra vision python -m nca.selective --cheap checkpoints/digit_mlp.pt \\
        --expensive checkpoints/digit_cnn.pt
"""

from __future__ import annotations

import argparse
from dataclasses import dataclass
from pathlib import Path

import numpy as np
import torch
from torch import nn

from nca.efficiency import network_flops
from nca.expressions import OPERATORS, ExpressionDataset
from nca.modules.digit_recognizer import DigitRecognizer
from nca.modules.operator_recognizer import SymbolRecognizer, make_dataset
from nca.modules.segmenter import column_runs, crop
from nca.modules.symbols import DIGITS, Evaluator
from nca.stats import wilson

SHIFTS = ((1, 0), (-1, 0), (0, 1), (0, -1))
GLYPH_SHAPE = (1, 28, 28)


@dataclass
class Reader:
    """A network's probabilities over a slice of its classes."""

    network: nn.Module
    classes: slice

    def __post_init__(self) -> None:
        self.cost = float(network_flops(self.network, GLYPH_SHAPE))

    @torch.no_grad()
    def probabilities(self, glyphs: torch.Tensor) -> torch.Tensor:
        return torch.softmax(self.network(glyphs[:, None])[:, self.classes], dim=1)


@dataclass
class Rung:
    """One reading of a glyph, with its own calibration temperature."""

    reader: Reader
    second_look: bool = False
    temperature: float = 1.0

    @property
    def cost(self) -> float:
        return self.reader.cost * (len(SHIFTS) if self.second_look else 1)

    def read(self, glyphs: torch.Tensor, previous: torch.Tensor | None) -> torch.Tensor:
        """Uncalibrated probabilities for a batch; a second look averages the
        previous reading with four shifted views."""
        if not self.second_look:
            return self.reader.probabilities(glyphs)
        assert previous is not None
        looks = sum(self.reader.probabilities(torch.roll(glyphs, shift, dims=(1, 2)))
                    for shift in SHIFTS)
        return (previous + looks) / (len(SHIFTS) + 1)

    def calibrated(self, raw: torch.Tensor) -> torch.Tensor:
        return torch.softmax(raw.clamp_min(1e-12).log() / self.temperature, dim=-1)

    def calibrate(self, raw: torch.Tensor, labels: torch.Tensor) -> None:
        """Fit the temperature minimizing negative log-likelihood on held-out glyphs."""
        log = raw.clamp_min(1e-12).log()

        def nll(t: float) -> float:
            return nn.functional.cross_entropy(log / t, labels).item()

        self.temperature = float(min(np.geomspace(0.1, 8.0, 120), key=nll))


def segment(image: np.ndarray, repair: bool) -> list[torch.Tensor]:
    runs = column_runs(image)
    if repair and len(runs) % 2 == 0 and len(runs) > 1:
        i = min(range(len(runs) - 1), key=lambda k: runs[k + 1][0] - runs[k][1])
        runs[i:i + 2] = [(runs[i][0], runs[i + 1][1])]
    return [torch.from_numpy(crop(image, s, e).astype(np.float32)) for s, e in runs]


@dataclass
class Outcome:
    tokens: tuple[str, ...] | None
    cost: float
    bound: float
    abstained: bool


def solve(glyphs: list[torch.Tensor], digit_ladder: list[Rung], operator_ladder: list[Rung],
          delta: float, start: int = 0, abstain: bool = True) -> Outcome:
    if len(glyphs) % 2 == 0:
        return Outcome(None, 0.0, 1.0, True)
    ladders = [digit_ladder if i % 2 == 0 else operator_ladder for i in range(len(glyphs))]
    levels = [0] * len(glyphs)
    raws: list[torch.Tensor] = [torch.empty(0)] * len(glyphs)
    probs: list[torch.Tensor] = [torch.empty(0)] * len(glyphs)
    cost = 0.0

    def climb(i: int) -> None:
        nonlocal cost
        rung = ladders[i][levels[i]]
        raws[i] = rung.read(glyphs[i][None], raws[i][None] if levels[i] else None)[0]
        probs[i] = rung.calibrated(raws[i])
        cost += rung.cost

    for i in range(len(glyphs)):
        climb(i)
        while levels[i] < min(start, len(ladders[i]) - 1):
            levels[i] += 1
            climb(i)
    risks = [1.0 - p.max().item() for p in probs]
    while sum(risks) > delta:
        open_ = [i for i in range(len(glyphs)) if levels[i] + 1 < len(ladders[i])]
        if not open_:
            break
        i = max(open_, key=risks.__getitem__)
        levels[i] += 1
        climb(i)
        risks[i] = 1.0 - probs[i].max().item()
    bound = sum(risks)
    tokens = tuple((DIGITS if i % 2 == 0 else OPERATORS)[int(p.argmax())]
                   for i, p in enumerate(probs))
    return Outcome(tokens, cost, bound, abstain and bound > delta)


def calibrate(digit_ladder: list[Rung], operator_ladder: list[Rung], data: Path,
              seed: int) -> None:
    """Fit every rung's temperature on the validation half of the MNIST test set.

    Rungs read in sequence, so a second look is calibrated on top of the
    reading it refines."""
    from torchvision import datasets

    mnist = datasets.MNIST(data, train=False, download=True)
    half = len(mnist) // 2
    digits = mnist.data[:half].float() / 255.0
    glyphs, labels = make_dataset(digits.numpy(), half, seed).tensors
    is_operator = labels < len(OPERATORS)
    for ladder, images, targets in ((digit_ladder, digits, mnist.targets[:half]),
                                    (operator_ladder, glyphs[is_operator, 0],
                                     labels[is_operator])):
        previous: torch.Tensor | None = None
        for rung in ladder:
            raw = rung.read(images, previous)
            rung.calibrate(raw, targets)
            previous = raw


def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__.splitlines()[0])
    parser.add_argument("--data", type=Path, default=Path("data"))
    parser.add_argument("--cheap", type=Path, required=True)
    parser.add_argument("--expensive", type=Path, required=True)
    parser.add_argument("--operator", type=Path, default=Path("checkpoints/operators.pt"))
    parser.add_argument("--samples", type=int, default=300)
    parser.add_argument("--seed", type=int, default=0)
    parser.add_argument("--operands", type=int, nargs="+", default=[2, 8, 32])
    parser.add_argument("--targets", type=float, nargs="+", default=[0.2, 0.05, 0.01])
    args = parser.parse_args()

    cheap = Reader(DigitRecognizer.load(args.cheap).network, slice(None))
    expensive = Reader(DigitRecognizer.load(args.expensive).network, slice(None))
    operator = Reader(SymbolRecognizer.load(args.operator).network, slice(0, len(OPERATORS)))
    digit_ladder = [Rung(cheap), Rung(expensive), Rung(expensive, second_look=True)]
    operator_ladder = [Rung(operator), Rung(operator, second_look=True)]
    calibrate(digit_ladder, operator_ladder, args.data, args.seed)
    print("temperatures: digits " + ", ".join(f"{r.temperature:.2f}" for r in digit_ladder)
          + "; operators " + ", ".join(f"{r.temperature:.2f}" for r in operator_ladder))

    evaluator = Evaluator()
    print(f"{'glyphs':>7s} {'system':>16s} {'coverage':>9s} {'error answered [95% CI]':>27s} "
          f"{'mean bound':>11s} {'error forced':>13s} {'MFLOPs/expr':>12s}")
    for operands in args.operands:
        dataset = ExpressionDataset("test", args.samples, args.data, args.seed,
                                    operands=operands)
        samples = [dataset.sample(i) for i in range(len(dataset))]
        segmentations = {repair: [segment(s.image, repair) for s in samples]
                         for repair in (False, True)}
        systems = {"bottom rungs": (float("inf"), 0, False),
                   "top rungs": (float("inf"), 2, False),
                   "top, repaired": (float("inf"), 2, True)}
        systems |= {f"δ={d:g}, repaired": (d, 0, True) for d in args.targets}
        for name, (delta, start, repair) in systems.items():
            crops = segmentations[repair]
            answered = wrong_answered = wrong_forced = 0
            spent = bound_sum = 0.0
            for sample, glyphs in zip(samples, crops):
                outcome = solve(glyphs, digit_ladder, operator_ladder, delta, start)
                value = None if outcome.tokens is None else evaluator.invoke(outcome.tokens)
                wrong = value != sample.value
                spent += outcome.cost
                wrong_forced += wrong
                if not outcome.abstained:
                    answered += 1
                    wrong_answered += wrong
                    bound_sum += outcome.bound
            n = len(samples)
            low, high = wilson(wrong_answered, answered) if answered else (0.0, 1.0)
            rate = wrong_answered / answered if answered else float("nan")
            mean_bound = bound_sum / answered if answered else float("nan")
            print(f"{2 * operands - 1:7d} {name:>16s} {answered / n:9.3f} "
                  f"{rate:.4f} [{low:.4f}, {high:.4f}]".ljust(62)
                  + f" {mean_bound:11.4f} {wrong_forced / n:13.4f} {spent / n / 1e6:12.2f}")


if __name__ == "__main__":
    main()
