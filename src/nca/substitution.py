"""Module substitution (Experiment 6): replaceable implementations behind one contract.

The first digit recognizer is the reference. Each other recognizer replaces it
in the frozen arithmetic system (``Registry.replace`` requires an identical
contract). For each substitute the runner reports:

* whether the composed route has the same shape and type-checks (``infer``);
* accuracy, and the fraction of answers that differ from the reference;
* ``Σ d``: the expected number of digit-recognizer invocations per sample
  whose argmax disagrees with the reference's, measured in situ on the
  segmented glyphs at even (digit) positions. The parser reads digit
  probabilities only there, and only through their argmax, so the answer can
  change only if one of these invocations disagrees; invocations on operator
  glyphs cannot change it and are excluded.

``NCA.substitution_change_le`` predicts ``changed ≤ Σ d`` and
``NCA.substitution_accuracy_ge`` predicts ``reference − accuracy ≤ Σ d``.

    uv run --extra vision python -m nca.substitution \\
        --digits checkpoints/digit_cnn.pt checkpoints/digit_mlp.pt ...
"""

from __future__ import annotations

import argparse
from pathlib import Path

import torch

from nca.abi import Message
from nca.expressions import ExpressionDataset
from nca.modules.digit_recognizer import DigitRecognizer
from nca.modules.operator_recognizer import SymbolRecognizer
from nca.modules.segmenter import EXPRESSION_IMAGE, Segmenter
from nca.modules.symbols import INTEGER
from nca.pipeline import build_registry, compose
from nca.planner import Apply, Given, Plan
from nca.router import infer
from nca.runtime import execute
from nca.workspace import Workspace


def shape(node: Plan) -> tuple:
    """A plan's structure with modules identified by id, ignoring implementation."""
    if isinstance(node, Given):
        return ("given", node.type_id)
    if isinstance(node, Apply):
        return ("apply", node.module.manifest.module_id, tuple(shape(a) for a in node.args))
    return ("map", node.element, shape(node.body), shape(node.source))


@torch.no_grad()
def digit_predictions(recognizer: DigitRecognizer, crops: list[torch.Tensor]) -> list[int]:
    if not crops:
        return []
    batch = torch.stack(crops)[:, None]
    return recognizer.network(batch).argmax(dim=1).tolist()


def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__.splitlines()[0])
    parser.add_argument("--digits", type=Path, nargs="+", required=True,
                        help="digit recognizer checkpoints; the first is the reference")
    parser.add_argument("--operator", type=Path, default=Path("checkpoints/operators.pt"))
    parser.add_argument("--data", type=Path, default=Path("data"))
    parser.add_argument("--size", type=int, default=5_000)
    parser.add_argument("--seed", type=int, default=0)
    args = parser.parse_args()

    recognizers = [DigitRecognizer.load(p, version=f"{i + 1}.0.0")
                   for i, p in enumerate(args.digits)]
    registry = build_registry(recognizers[0], SymbolRecognizer.load(args.operator))
    reference_route = compose(registry)
    segmenter = Segmenter()

    for split in ("test", "test_unseen"):
        dataset = ExpressionDataset(split, args.size, args.data, args.seed)
        samples = [dataset.sample(i) for i in range(len(dataset))]
        crops = [segmenter.invoke(torch.from_numpy(s.image)) for s in samples]
        reference_digits = [digit_predictions(recognizers[0], c) for c in crops]
        reference_answers = None
        print(f"\nsplit {split} ({len(samples)} samples)")
        print(f"{'recognizer':28s} {'same shape':>10s} {'checks':>7s} {'accuracy':>9s} "
              f"{'changed':>8s} {'sum d':>7s} {'acc drop':>9s}")
        for path, recognizer in zip(args.digits, recognizers):
            registry.replace(recognizer)
            route = compose(registry)
            checks = infer(registry.modules(), (EXPRESSION_IMAGE,), route) == INTEGER
            answers = [
                execute(route, {EXPRESSION_IMAGE: Message(
                    EXPRESSION_IMAGE, torch.from_numpy(s.image), "input")},
                    Workspace(), budget=64).payload
                for s in samples
            ]
            reference_answers = reference_answers or answers
            accuracy = sum(a == s.value for a, s in zip(answers, samples)) / len(samples)
            reference_accuracy = sum(
                a == s.value for a, s in zip(reference_answers, samples)) / len(samples)
            changed = sum(a != r for a, r in zip(answers, reference_answers)) / len(samples)
            disagreements = sum(
                sum(x != y for x, y in
                    zip(digit_predictions(recognizer, c)[::2], ref[::2]))
                for c, ref in zip(crops, reference_digits)
            ) / len(samples)
            print(f"{path.stem:28s} {str(shape(route) == shape(reference_route)):>10s} "
                  f"{str(checks):>7s} {accuracy:9.4f} {changed:8.4f} {disagreements:7.4f} "
                  f"{reference_accuracy - accuracy:9.4f}")


if __name__ == "__main__":
    main()
