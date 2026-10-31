"""Confidence-triggered refinement experiment.

A cheap digit recognizer answers when confident and otherwise delegates its
output to the kernel, which routes the glyph to an expensive recognizer.

Part A, glyph level (digit glyphs of segmented test expressions). For each
confidence threshold: the deferral rate, confident errors ``μ(C ∩ W₁)`` and
deferred errors ``μ(Cᶜ ∩ W₂)``, the composite error (``NCA.cascade_error_eq``
states it equals their sum), the selectivity condition of
``NCA.cascade_le_fallback`` and whether the composite is at least as accurate
as the fallback, and the expected cost ``κ₁ + κ₂ · P(defer)``
(``NCA.cascade_expected_cost``).

Part B, end to end through the runtime and kernel. Arithmetic expressions of
several lengths are solved with the cheap recognizer alone, the expensive one
alone, and the requesting cheap recognizer at chosen thresholds, reporting
error, cost per expression, and requests per expression, including requests
spent on operator glyphs, whose digit reading the parser never uses.

    uv run --extra vision python -m nca.cascade --cheap checkpoints/digit_mlp.pt \\
        --expensive checkpoints/digit_cnn.pt
"""

from __future__ import annotations

import argparse
from pathlib import Path

import torch

from nca.abi import Message
from nca.efficiency import costed, network_flops
from nca.expressions import ExpressionDataset
from nca.kernel import Kernel
from nca.modules.digit_recognizer import GLYPH, DigitRecognizer
from nca.modules.operator_recognizer import SymbolRecognizer
from nca.modules.refinement import RequestingRecognizer
from nca.modules.segmenter import EXPRESSION_IMAGE, Segmenter
from nca.modules.symbols import INTEGER, Evaluator, ExpressionParser, SymbolFuser
from nca.planner import plan_stable
from nca.registry import Module
from nca.runtime import execute
from nca.stats import wilson
from nca.workspace import Workspace

GLYPH_SHAPE = (1, 28, 28)


@torch.no_grad()
def glyph_level(cheap: DigitRecognizer, expensive: DigitRecognizer,
                dataset: ExpressionDataset, thresholds: list[float]) -> None:
    segmenter = Segmenter()
    crops, labels = [], []
    for index in range(len(dataset)):
        sample = dataset.sample(index)
        pieces = segmenter.invoke(torch.from_numpy(sample.image))
        if len(pieces) == len(sample.tokens):
            crops += pieces[::2]
            labels += [int(t) for t in sample.tokens[::2]]
    batch = torch.stack(crops)[:, None]
    truth = torch.tensor(labels)
    p1 = torch.softmax(cheap.network(batch), dim=1)
    w1 = p1.argmax(dim=1) != truth
    w2 = expensive.network(batch).argmax(dim=1) != truth
    k1, k2 = cheap.manifest.cost, expensive.manifest.cost
    n = len(truth)
    print(f"Part A: {n} digit glyphs; cheap error {w1.float().mean():.4f}, "
          f"expensive error {w2.float().mean():.4f}, costs {k1:,.0f} / {k2:,.0f} FLOPs")
    print(f"{'τ':>5s} {'defer':>7s} {'μ(C∩W1)':>8s} {'μ(Cᶜ∩W2)':>9s} {'composite':>10s} "
          f"{'selective':>10s} {'≤ fallback':>11s} {'cost/glyph':>11s} {'vs expensive':>13s}")
    for tau in thresholds:
        confident = p1.max(dim=1).values >= tau
        confident_errors = (confident & w1).float().mean().item()
        deferred_errors = (~confident & w2).float().mean().item()
        composite = torch.where(confident, w1, w2).float().mean().item()
        assert abs(composite - (confident_errors + deferred_errors)) < 1e-9
        selective = confident_errors <= (confident & w2).float().mean().item()
        defer = (~confident).float().mean().item()
        cost = k1 + k2 * defer
        print(f"{tau:5.2f} {defer:7.3f} {confident_errors:8.4f} {deferred_errors:9.4f} "
              f"{composite:10.4f} {str(selective):>10s} "
              f"{str(composite <= w2.float().mean().item()):>11s} {cost:11,.0f} "
              f"{cost / k2:12.1%}")


def build(modules_before: list[Module], digit: Module, operator: SymbolRecognizer,
          extra: list[Module]) -> list[Module]:
    return [*modules_before, digit, operator, SymbolFuser(), ExpressionParser(), Evaluator(),
            *extra]


def end_to_end(cheap: DigitRecognizer, expensive: DigitRecognizer, operator: SymbolRecognizer,
               args: argparse.Namespace) -> None:
    print("\nPart B: end to end through the runtime and kernel")
    print(f"{'glyphs':>7s} {'system':>18s} {'error [95% CI]':>26s} {'MFLOPs/expr':>12s} "
          f"{'requests/expr':>14s} {'on operators':>13s}")
    segmenter = Segmenter()
    for operands in (2, 8, 32):
        glyphs = 2 * operands - 1
        dataset = ExpressionDataset("test", args.samples, args.data, args.seed,
                                    operands=operands)
        systems: dict[str, list[Module]] = {
            "cheap only": build([segmenter], cheap, operator, []),
            "expensive only": build([segmenter], expensive, operator, []),
        }
        for tau in args.end_to_end:
            requester = RequestingRecognizer(cheap, tau)
            systems[f"refine τ={tau}"] = build([segmenter], requester, operator, [expensive])
        for name, modules in systems.items():
            kernel = Kernel(modules)
            route = plan_stable(modules, (EXPRESSION_IMAGE,), INTEGER)
            assert route is not None
            wrong, spent, operator_requests = 0, 0.0, 0
            for index in range(len(dataset)):
                sample = dataset.sample(index)
                workspace = Workspace()
                image = Message(EXPRESSION_IMAGE, torch.from_numpy(sample.image), "input")
                result = execute(route, {EXPRESSION_IMAGE: image}, workspace, 10_000, kernel)
                wrong += result.payload != sample.value
                spent += workspace.spent
                glyphs_in_order = [m.message_id for m in workspace.messages()
                                   if m.producer == "map" and m.type_id == GLYPH]
                requested = {m.parents[0] for m in workspace.messages()
                             if m.type_id == "kernel.request"}
                operator_requests += sum(1 for g in glyphs_in_order[1::2] if g in requested)
            low, high = wilson(wrong, len(dataset))
            print(f"{glyphs:7d} {name:>18s} {wrong / len(dataset):.4f} [{low:.4f}, {high:.4f}]"
                  f" {spent / len(dataset) / 1e6:12.2f} {kernel.requests / len(dataset):14.2f}"
                  f" {operator_requests / len(dataset):13.2f}")


def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__.splitlines()[0])
    parser.add_argument("--data", type=Path, default=Path("data"))
    parser.add_argument("--cheap", type=Path, required=True)
    parser.add_argument("--expensive", type=Path, required=True)
    parser.add_argument("--operator", type=Path, default=Path("checkpoints/operators.pt"))
    parser.add_argument("--samples", type=int, default=500)
    parser.add_argument("--seed", type=int, default=0)
    parser.add_argument("--thresholds", type=float, nargs="+",
                        default=[0.5, 0.7, 0.9, 0.95, 0.99, 0.999])
    parser.add_argument("--end-to-end", type=float, nargs="+", default=[0.9, 0.99])
    args = parser.parse_args()

    cheap = DigitRecognizer.load(args.cheap)
    expensive = DigitRecognizer.load(args.expensive)
    costed(cheap, network_flops(cheap.network, GLYPH_SHAPE), "nca.digit-recognizer.cheap")
    costed(expensive, network_flops(expensive.network, GLYPH_SHAPE),
           "nca.digit-recognizer.expensive")
    operator = SymbolRecognizer.load(args.operator)
    costed(operator, network_flops(operator.network, GLYPH_SHAPE))
    glyph_level(cheap, expensive, ExpressionDataset("test", args.samples * 4, args.data,
                                                    args.seed), args.thresholds)
    end_to_end(cheap, expensive, operator, args)


if __name__ == "__main__":
    main()
