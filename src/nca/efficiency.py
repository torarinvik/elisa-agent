"""Efficiency experiments: cost-optimal routes and linear scaling in input length.

Part A, cost versus accuracy. Three digit recognizers with different costs
(counted floating-point operations) and failure rates (measured in situ on the
validation split) are installed side by side. For each error target, the
Pareto planner (``nca.optimize``) selects the cheapest route whose union-bound
error is within the target; the route is then run on the test split.

Part B, input length. Expressions with 2 to 32 operands. Every route's cost is
affine in the number of glyphs (``NCA.Plan.cost_linear``: no nested maps), but
its error bound also grows linearly, so the expert that meets a fixed error
target depends on the length. For each length the planner re-selects the
cheapest route within ``--target`` at that length, or reports the target
infeasible and runs the lowest-error route. Measured cost, wall time, and
error are reported with a transformer's analytic cost on the same inputs, at
glyph-token and image-patch granularity.

    uv run --extra vision python -m nca.efficiency
"""

from __future__ import annotations

import argparse
import math
import time
from dataclasses import replace
from pathlib import Path

import torch
from torch import nn

from nca.abi import Message, Module
from nca.expressions import HEIGHT, ExpressionDataset
from nca.modules.digit_recognizer import DigitRecognizer
from nca.modules.operator_recognizer import SymbolRecognizer
from nca.modules.segmenter import EXPRESSION_IMAGE, Segmenter
from nca.modules.symbols import INTEGER, Evaluator, ExpressionParser, SymbolFuser
from nca.optimize import cheapest_within, plan_min, plan_pareto
from nca.planner import Apply, Map, Plan
from nca.runtime import execute
from nca.stats import wilson
from nca.workspace import Workspace

SEGMENTER_FLOPS_PER_PIXEL = 10
SYMBOLIC_FLOPS = 100
"""Nominal cost of one invocation of an exact symbolic module."""


def network_flops(network: nn.Module, shape: tuple[int, ...]) -> int:
    """Floating-point operations of one forward pass (multiply-adds count as two)."""
    total = 0

    def count(module: nn.Module, inputs: tuple[torch.Tensor, ...], output: torch.Tensor) -> None:
        nonlocal total
        if isinstance(module, nn.Conv2d):
            kh, kw = module.kernel_size
            total += 2 * output.numel() * module.in_channels // module.groups * kh * kw
        elif isinstance(module, nn.Linear):
            total += 2 * module.in_features * module.out_features

    hooks = [m.register_forward_hook(count) for m in network.modules()]
    with torch.no_grad():
        network(torch.zeros(1, *shape))
    for hook in hooks:
        hook.remove()
    return total


def costed(module: Module, cost: float, module_id: str | None = None) -> Module:
    module.manifest = replace(module.manifest, cost=cost,
                              module_id=module_id or module.manifest.module_id)
    return module


def solve(route: Plan, image: torch.Tensor) -> tuple[object, float]:
    workspace = Workspace()
    message = Message(EXPRESSION_IMAGE, image, "input")
    result = execute(route, {EXPRESSION_IMAGE: message}, workspace, budget=1_000)
    return result.payload, workspace.spent


def digit_expert(route: Plan) -> str:
    if isinstance(route, Apply):
        if route.module.manifest.module_id.startswith("nca.digit-recognizer"):
            return route.module.manifest.module_id.rsplit(".", 1)[-1]
        return next((d for a in route.args if (d := digit_expert(a)) != "-"), "-")
    if isinstance(route, Map):
        return digit_expert(route.body)
    return "-"


def in_situ_failure_rates(digits: dict[str, DigitRecognizer], operator: SymbolRecognizer,
                          dataset: ExpressionDataset) -> tuple[float, dict[str, float], float]:
    """Per-invocation failure rates on segmented glyphs: segmenter, each digit
    recognizer, and the operator recognizer (an invocation fails if it causes a
    wrong token where its output is read)."""
    segmenter = Segmenter()
    seg_failures, glyphs = 0, 0
    digit_failures = {name: 0 for name in digits}
    operator_failures = 0
    for index in range(len(dataset)):
        sample = dataset.sample(index)
        crops = segmenter.invoke(torch.from_numpy(sample.image))
        if len(crops) != len(sample.tokens):
            seg_failures += 1
            continue
        glyphs += len(crops)
        batch = torch.stack(crops)[:, None]
        with torch.no_grad():
            for name, recognizer in digits.items():
                predicted = recognizer.network(batch).argmax(dim=1).tolist()
                digit_failures[name] += sum(
                    str(p) != t for p, t in zip(predicted[::2], sample.tokens[::2]))
            ops = operator.network(batch)[:, :3].argmax(dim=1).tolist()
        operator_failures += sum("+-*"[o] != t for o, t in zip(ops[1::2], sample.tokens[1::2]))
    return (seg_failures / len(dataset), {n: f / glyphs for n, f in digit_failures.items()},
            operator_failures / glyphs)


def transformer_flops(tokens: int, width: int = 256, layers: int = 6) -> float:
    """Forward cost of a standard transformer: projections and MLP grow linearly
    in the number of tokens, attention scores quadratically."""
    return layers * (24 * tokens * width * width + 4 * tokens * tokens * width)


def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__.splitlines()[0])
    parser.add_argument("--data", type=Path, default=Path("data"))
    parser.add_argument("--digits", type=Path, nargs="+", required=True,
                        help="digit recognizer checkpoints, named by file stem")
    parser.add_argument("--operator", type=Path, default=Path("checkpoints/operators.pt"))
    parser.add_argument("--samples", type=int, default=1_000)
    parser.add_argument("--seed", type=int, default=0)
    parser.add_argument("--target", type=float, default=0.25,
                        help="error target for the length experiment")
    args = parser.parse_args()

    glyph_shape = (1, 28, 28)
    digits = {p.stem: DigitRecognizer.load(p) for p in args.digits}
    operator = SymbolRecognizer.load(args.operator)
    segmenter = Segmenter()
    validation = ExpressionDataset("validation", args.samples, args.data, args.seed)
    seg_rate, digit_rates, operator_rate = in_situ_failure_rates(digits, operator, validation)

    modules: list[Module] = [costed(segmenter, SEGMENTER_FLOPS_PER_PIXEL * HEIGHT * 96)]
    for name, recognizer in digits.items():
        modules.append(costed(recognizer, network_flops(recognizer.network, glyph_shape),
                              f"nca.digit-recognizer.{name}"))
    modules.append(costed(operator, network_flops(operator.network, glyph_shape)))
    modules += [costed(m, SYMBOLIC_FLOPS) for m in (SymbolFuser(), ExpressionParser(),
                                                     Evaluator())]
    errors = {segmenter.manifest.ref: seg_rate, operator.manifest.ref: operator_rate}
    for module in modules:
        name = module.manifest.module_id.rsplit(".", 1)[-1]
        if name in digit_rates:
            errors[module.manifest.ref] = digit_rates[name]

    print("Part A: cheapest route meeting an error target (3 glyphs per expression)")
    print("per-invocation failure rates (validation): segmenter "
          f"{seg_rate:.4f}, operator {operator_rate:.4f}, digits "
          + ", ".join(f"{n} {r:.4f}" for n, r in digit_rates.items()))
    for module in modules:
        print(f"  cost {module.manifest.module_id:32s} {module.manifest.cost:>12,.0f} FLOPs")
    frontier = plan_pareto(modules, (EXPRESSION_IMAGE,), INTEGER, 3, errors)
    test = ExpressionDataset("test", args.samples, args.data, args.seed)
    print(f"\n{'target':>7s} {'digit expert':>18s} {'cost MFLOPs':>12s} {'error bound':>12s} "
          f"{'test error [95% CI]':>26s}")
    for target in (0.02, 0.05, 0.10, 0.20, math.inf):
        option = cheapest_within(frontier, target)
        if option is None:
            print(f"{target:7.2f} {'infeasible':>18s}")
            continue
        wrong = sum(solve(option.plan, torch.from_numpy(s.image))[0] != s.value
                    for s in (test.sample(i) for i in range(len(test))))
        low, high = wilson(wrong, len(test))
        print(f"{target:7.2f} {digit_expert(option.plan):>18s} {option.cost / 1e6:12.2f} "
              f"{option.error:12.4f}   {wrong / len(test):.4f} [{low:.4f}, {high:.4f}]")

    print(f"\nPart B: cost versus expression length (error target {args.target})")
    print(f"{'glyphs':>7s} {'digit expert':>16s} {'bound':>7s} {'planned':>9s} {'measured':>9s} "
          f"{'ms/expr':>8s} {'error':>7s} {'xfmr glyph':>11s} {'xfmr patch':>11s}"
          "   (costs in MFLOPs per expression)")
    samples = max(100, args.samples // 5)
    for operands in (2, 4, 8, 16, 32):
        glyphs = 2 * operands - 1
        dataset = ExpressionDataset("test", samples, args.data, args.seed, operands=operands)
        frontier = plan_pareto(modules, (EXPRESSION_IMAGE,), INTEGER, glyphs, errors)
        option = cheapest_within(frontier, args.target)
        expert_note = ""
        if option is None:
            option = frontier[-1]
            expert_note = "*"
        assert plan_min(modules, (EXPRESSION_IMAGE,), INTEGER, glyphs) is not None
        spent, wrong = 0.0, 0
        start = time.perf_counter()
        for index in range(len(dataset)):
            sample = dataset.sample(index)
            answer, cost = solve(option.plan, torch.from_numpy(sample.image))
            spent += cost
            wrong += answer != sample.value
        elapsed = (time.perf_counter() - start) * 1e3 / len(dataset)
        patches = (HEIGHT // 4) * (dataset.width // 4)
        expert = digit_expert(option.plan) + expert_note
        print(f"{glyphs:7d} {expert:>16s} {option.error:7.3f} {option.cost / 1e6:9.2f} "
              f"{spent / len(dataset) / 1e6:9.2f} {elapsed:8.2f} {wrong / len(dataset):7.3f} "
              f"{transformer_flops(glyphs) / 1e6:11.2f} {transformer_flops(patches) / 1e6:11.2f}")
    print("* target infeasible at this length; lowest-error route shown")


if __name__ == "__main__":
    main()
