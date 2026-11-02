"""The practice queue: learning from a teacher where the system is unsure.

A deployed digit recognizer reads a stream of expressions in a style it was
never trained on (the ``hard`` style, on ``train``-split images). Each digit
glyph's calibrated error probability ``1 - max p`` is its risk; glyphs with
risk at least ``θ`` are queued for a teacher's label; for a label budget ``k``,
``θ`` is the ``k``-th largest risk. Every queued label is
expected to correct at least ``θ`` errors and at most ``θ`` expected errors
per unqueued glyph escape the queue (``NCA.queued_value``,
``NCA.unqueued_errors``).

Practice happens offline: a copy of the recognizer is fine-tuned on the queued
glyphs mixed with replayed MNIST training digits, so the normal style is not
forgotten. The result is a new version, adopted only if it beats the current
one by a one-sided sign test on ``validation`` expressions of both styles
(the upgrade rule of ``lean/NCA/Planning/Upgrade.lean``). Never trained on its own
unverified answers, the system cannot reinforce its errors.

Compared, at each label budget, with practicing on as many glyphs drawn with
probability proportional to risk (each label still expected to find at least
as many errors as a random one, ``NCA.proportional_value``, while every
doubtful glyph can be chosen), on as many randomly chosen labeled glyphs, and
with labeling the whole stream. A
budget of 0 practices on replayed digits alone, a version the sign test should
reject. Reports labels used, digit
error on test glyphs of each style, expression accuracy on ``test`` of each
style, and the adoption decision.

    uv run --extra vision python -m nca.domains.arithmetic.practice --digit checkpoints/digit_cnn.pt
"""

from __future__ import annotations

import argparse
import copy
from pathlib import Path

import numpy as np
import torch
from torch import nn

from nca.abi import Message
from nca.domains.arithmetic.expressions import ExpressionDataset
from nca.domains.arithmetic.digit_recognizer import DigitRecognizer
from nca.domains.arithmetic.operator_recognizer import SymbolRecognizer
from nca.domains.arithmetic.segmenter import EXPRESSION_IMAGE, Segmenter
from nca.domains.arithmetic.pipeline import build_registry, compose
from nca.router import sign_test
from nca.runtime import execute
from nca.ladder import Rung
from nca.stats import wilson
from nca.workspace import Workspace


def digit_glyphs(dataset: ExpressionDataset) -> tuple[torch.Tensor, torch.Tensor]:
    """Digit crops and labels, from the first segmentation alternative with the
    teacher's glyph count."""
    glyphs, labels = [], []
    for index in range(len(dataset)):
        sample = dataset.sample(index)
        crops = next((c for c in Segmenter().alternatives(torch.from_numpy(sample.image))
                      if len(c) == len(sample.tokens)), None)
        if crops is None:
            continue
        for crop, token in zip(crops[::2], sample.tokens[::2]):
            glyphs.append(crop)
            labels.append(int(token))
    return torch.stack(glyphs), torch.tensor(labels)


def queue(risks: torch.Tensor, threshold: float) -> torch.Tensor:
    """Indices of glyphs whose risk is at least ``threshold``."""
    return torch.nonzero(risks >= threshold).flatten()


def proportional(risks: torch.Tensor, budget: int, seed: int) -> torch.Tensor:
    """``budget`` distinct indices drawn with probability proportional to risk."""
    generator = torch.Generator().manual_seed(seed)
    return torch.multinomial(risks.clamp_min(1e-12), budget, replacement=False,
                             generator=generator)


def practice(network: nn.Module, glyphs: torch.Tensor, labels: torch.Tensor,
             replay: tuple[torch.Tensor, torch.Tensor], epochs: int, seed: int) -> nn.Module:
    """Fine-tune a copy of ``network`` on practice glyphs mixed with replayed digits."""
    torch.manual_seed(seed)
    student = copy.deepcopy(network).train()
    images = torch.cat([glyphs, replay[0]])[:, None]
    targets = torch.cat([labels, replay[1]])
    loader = torch.utils.data.DataLoader(torch.utils.data.TensorDataset(images, targets),
                                         batch_size=128, shuffle=True)
    optimizer = torch.optim.Adam(student.parameters(), lr=3e-4)
    for _ in range(epochs):
        for x, y in loader:
            optimizer.zero_grad()
            nn.functional.cross_entropy(student(x), y).backward()
            optimizer.step()
    return student.eval()


@torch.no_grad()
def glyph_error(network: nn.Module, glyphs: torch.Tensor, labels: torch.Tensor) -> float:
    return (network(glyphs[:, None]).argmax(dim=1) != labels).float().mean().item()


def correctness(network: nn.Module, operator: SymbolRecognizer,
                dataset: ExpressionDataset) -> list[bool]:
    route = compose(build_registry(DigitRecognizer(network), operator))
    results = []
    for index in range(len(dataset)):
        sample = dataset.sample(index)
        image = Message(EXPRESSION_IMAGE, torch.from_numpy(sample.image), "input")
        results.append(execute(route, {EXPRESSION_IMAGE: image}, Workspace(),
                               budget=64).payload == sample.value)
    return results


def main() -> None:
    from torchvision import datasets

    parser = argparse.ArgumentParser(description=__doc__.splitlines()[0])
    parser.add_argument("--data", type=Path, default=Path("data"))
    parser.add_argument("--digit", type=Path, default=Path("checkpoints/digit.pt"))
    parser.add_argument("--operator", type=Path, default=Path("checkpoints/operators.pt"))
    parser.add_argument("--stream", type=int, default=4000, help="expressions seen in use")
    parser.add_argument("--budgets", type=int, nargs="+", default=[100, 300, 1000],
                        help="labels the teacher provides")
    parser.add_argument("--replay", type=int, default=10_000)
    parser.add_argument("--epochs", type=int, default=3)
    parser.add_argument("--samples", type=int, default=2000)
    parser.add_argument("--seed", type=int, default=0)
    args = parser.parse_args()

    current = DigitRecognizer.load(args.digit).network
    operator = SymbolRecognizer.load(args.operator)
    rung = Rung(DigitRecognizer(current))
    mnist = datasets.MNIST(args.data, train=False, download=True)
    half = len(mnist) // 2
    rung.calibrate(list(mnist.data[:half].float() / 255.0), mnist.targets[:half])

    stream, stream_labels = digit_glyphs(
        ExpressionDataset("train", args.stream, args.data, args.seed, hard=True))
    readings = torch.stack([rung.reading(rung.observe(glyph)) for glyph in stream])
    risks = 1.0 - readings.max(dim=1).values
    rng = np.random.default_rng(args.seed)
    train = datasets.MNIST(args.data, train=True, download=True)
    pick = torch.from_numpy(rng.choice(len(train), args.replay, replace=False))
    replay = (train.data[pick].float() / 255.0, train.targets[pick])
    stream_errors = readings.argmax(dim=1) != stream_labels
    print(f"stream: {len(stream)} digit glyphs, {int(stream_errors.sum())} misread "
          f"({stream_errors.float().mean():.4f})")
    print(f"{'θ':>6s} {'queued':>7s} {'errors held':>12s} {'expected in':>12s} "
          f"{'errors outside':>15s} {'expected outside':>17s} {'bound θ·n':>10s}")
    candidates: dict[str, tuple[nn.Module, int]] = {"current": (current, 0)}
    for budget in args.budgets:
        threshold = risks.topk(budget).values[-1].item() if budget else float("inf")
        queued = queue(risks, threshold)
        random = torch.from_numpy(rng.choice(len(stream), len(queued), replace=False))
        outside = len(stream) - len(queued)
        print(f"{threshold:6.3f} {len(queued):7d} {int(stream_errors[queued].sum()):12d} "
              f"{risks[queued].sum():12.1f} {int(stream_errors.sum() - stream_errors[queued].sum()):15d}"
              f" {risks.sum() - risks[queued].sum():17.1f} {threshold * outside:10.1f}")
        candidates[f"queue, {len(queued)}"] = (practice(
            current, stream[queued], stream_labels[queued], replay, args.epochs, args.seed),
            len(queued))
        candidates[f"random, {len(queued)}"] = (practice(
            current, stream[random], stream_labels[random], replay, args.epochs, args.seed),
            len(queued))
        if budget:
            sampled = proportional(risks, budget, args.seed)
            print(f"{'':6s} misread among labels: queue {stream_errors[queued].float().mean():.2f},"
                  f" proportional {stream_errors[sampled].float().mean():.2f},"
                  f" random {stream_errors[random].float().mean():.2f}")
            candidates[f"proportional, {budget}"] = (practice(
                current, stream[sampled], stream_labels[sampled], replay, args.epochs,
                args.seed), budget)
    candidates["all labeled"] = (practice(current, stream, stream_labels, replay, args.epochs,
                                          args.seed), len(stream))

    tests = {hard: ExpressionDataset("test", args.samples, args.data, args.seed, hard=hard)
             for hard in (False, True)}
    test_glyphs = {hard: digit_glyphs(tests[hard]) for hard in (False, True)}
    validation = [ExpressionDataset("validation", args.samples // 2, args.data, args.seed,
                                    hard=hard) for hard in (False, True)]

    def validate(network: nn.Module) -> list[bool]:
        return [c for dataset in validation for c in correctness(network, operator, dataset)]

    baseline = validate(current)
    print(f"\n{'version':>16s} {'labels':>7s} {'digit err normal':>17s} {'digit err hard':>15s} "
          f"{'acc normal [95% CI]':>24s} {'acc hard [95% CI]':>24s} {'sign test p':>12s} "
          f"{'adopted':>8s}")
    for name, (network, labels_used) in candidates.items():
        accuracy = []
        for hard in (False, True):
            correct = sum(correctness(network, operator, tests[hard]))
            low, high = wilson(correct, args.samples)
            accuracy.append(f"{correct / args.samples:.4f} [{low:.4f}, {high:.4f}]")
        if name == "current":
            adopted, p = "-", "-"
        else:
            accept, p_value = sign_test(baseline, validate(network))
            adopted, p = str(accept), f"{p_value:.2g}"
        print(f"{name:>16s} {labels_used:7d} "
              f"{glyph_error(network, *test_glyphs[False]):17.4f} "
              f"{glyph_error(network, *test_glyphs[True]):15.4f} "
              f"{accuracy[0]:>24s} {accuracy[1]:>24s} {p:>12s} {adopted:>8s}")


if __name__ == "__main__":
    main()
