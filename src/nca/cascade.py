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
alone, and the requesting cheap recognizer at chosen thresholds: ungated,
gated by the symbol fuser's heuristic relevance declaration (the digit reading
is irrelevant on glyphs the operator recognizer judges to be operators), and
gated by demand-driven evaluation (the parser reads digits only at even
positions, so the digit recognizer never runs on odd ones). Reports error, cost
per expression, requests resolved and skipped or unread per expression,
resolved requests on operator glyphs (whose digit reading the parser never
uses), and answers that differ from ungated refinement. ``NCA.gated_error_le``
bounds these by the relevant requests a gate skips; demand soundness
(``NCA.DemandSound.exact``) makes them zero for the demand gate. Finally the
consulting recognizer, which continues with the second opinion and answers
with a mixture of both instead of delegating (``NCA.Prog``), under the demand
gate.

Part C, the cascade built by the planner (§20). The library holds the two
recognizers and the higher-order ``Fallback`` expert at each threshold, whose
slots the Pareto planner fills; each recognizer's error and each pair's
cascade error are measured on validation glyphs. For error targets, the
cheapest plan within the target is executed on the test glyphs and compared
with the hand-built requesting recognizer at the same threshold.

    uv run --extra vision python -m nca.cascade --cheap checkpoints/digit_mlp.pt \\
        --expensive checkpoints/digit_cnn.pt
"""

from __future__ import annotations

import argparse
from pathlib import Path

import torch

from nca.abi import Message, Module
from nca.modules.combinators import Fallback
from nca.optimize import cheapest_within, plan_pareto
from nca.planner import Apply, Given, Plan
from nca.efficiency import costed, network_flops
from nca.expressions import ExpressionDataset
from nca.kernel import Kernel
from nca.modules.digit_recognizer import DIGIT_DISTRIBUTION, GLYPH, DigitRecognizer
from nca.modules.operator_recognizer import SymbolRecognizer
from nca.modules.refinement import ConsultingRecognizer, RequestingRecognizer
from nca.modules.segmenter import EXPRESSION_IMAGE, Segmenter
from nca.modules.symbols import INTEGER, Evaluator, ExpressionParser, SymbolFuser
from nca.planner import plan_stable
from nca.runtime import execute
from nca.stats import wilson
from nca.workspace import Workspace

GLYPH_SHAPE = (1, 28, 28)


def digit_glyphs(dataset: ExpressionDataset) -> tuple[list[torch.Tensor], list[int]]:
    """Digit crops of correctly segmented expressions, with their labels."""
    segmenter = Segmenter()
    crops, labels = [], []
    for index in range(len(dataset)):
        sample = dataset.sample(index)
        pieces = segmenter.invoke(torch.from_numpy(sample.image))
        if len(pieces) == len(sample.tokens):
            crops += pieces[::2]
            labels += [int(t) for t in sample.tokens[::2]]
    return crops, labels


@torch.no_grad()
def glyph_level(cheap: DigitRecognizer, expensive: DigitRecognizer,
                dataset: ExpressionDataset, thresholds: list[float]) -> None:
    crops, labels = digit_glyphs(dataset)
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
          extra: list[Module], gate: str = "") -> list[Module]:
    fuser = SymbolFuser(digit_relevance=0.5 if gate == "gated" else 0.0,
                        demand_driven=gate == "demand")
    return [*modules_before, digit, operator, fuser, ExpressionParser(), Evaluator(), *extra]


def end_to_end(cheap: DigitRecognizer, expensive: DigitRecognizer, operator: SymbolRecognizer,
               args: argparse.Namespace) -> None:
    print("\nPart B: end to end through the runtime and kernel")
    print(f"{'glyphs':>7s} {'system':>22s} {'error [95% CI]':>26s} {'MFLOPs/expr':>12s} "
          f"{'resolved':>9s} {'skipped':>8s} {'on operators':>13s} {'changed':>8s}")
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
            for gate in ("gated", "demand"):
                systems[f"refine τ={tau} {gate}"] = build([segmenter], requester, operator,
                                                          [expensive], gate)
            for weight in args.weights:
                consulter = ConsultingRecognizer(cheap, tau, weight)
                systems[f"consult τ={tau} w={weight}"] = build(
                    [segmenter], consulter, operator, [expensive], "demand")
        answers: dict[str, list] = {}
        for name, modules in systems.items():
            kernel = Kernel(modules)
            route = plan_stable(modules, (EXPRESSION_IMAGE,), INTEGER)
            assert route is not None
            wrong, spent, operator_requests, skipped = 0, 0.0, 0, 0
            answers[name] = []
            for index in range(len(dataset)):
                sample = dataset.sample(index)
                workspace = Workspace()
                image = Message(EXPRESSION_IMAGE, torch.from_numpy(sample.image), "input")
                result = execute(route, {EXPRESSION_IMAGE: image}, workspace, 10_000, kernel)
                wrong += result.payload != sample.value
                answers[name].append(result.payload)
                spent += workspace.spent
                skipped += sum(m.type_id == "kernel.skipped" or m.producer == "kernel.unread"
                               for m in workspace.messages())
                glyphs_in_order = [m.message_id for m in workspace.messages()
                                   if m.producer == "map" and m.type_id == GLYPH]
                requested = {m.parents[0] for m in workspace.messages()
                             if m.type_id == "kernel.request"}
                operator_requests += sum(1 for g in glyphs_in_order[1::2] if g in requested)
            low, high = wilson(wrong, len(dataset))
            base, _, gate = name.rpartition(" ")
            ungated = answers.get(base) if gate in ("gated", "demand") else None
            changed = ("-" if ungated is None else
                       str(sum(a != b for a, b in zip(answers[name], ungated))))
            n = len(dataset)
            print(f"{glyphs:7d} {name:>22s} {wrong / n:.4f} [{low:.4f}, {high:.4f}]"
                  f" {spent / n / 1e6:12.2f} {kernel.requests / n:9.2f} {skipped / n:8.2f}"
                  f" {operator_requests / n:13.2f} {changed:>8s}")


def describe(plan: Plan) -> str:
    if isinstance(plan, Given):
        return "glyph"
    assert isinstance(plan, Apply)
    name = plan.module.manifest.module_id.rpartition(".")[2]
    if isinstance(plan.module, Fallback):
        name = f"fallback τ={plan.module.threshold:g}"
    return name if not plan.slots else f"{name}({', '.join(describe(f) for f in plan.slots)})"


@torch.no_grad()
def measure(route: Plan, crops: list[torch.Tensor], labels: list[int],
            kernel: Kernel | None = None) -> tuple[float, float]:
    """Error and cost per glyph of ``route`` run through the runtime."""
    wrong, spent = 0, 0.0
    for crop, label in zip(crops, labels):
        workspace = Workspace()
        result = execute(route, {GLYPH: Message(GLYPH, crop, "input")}, workspace, 100, kernel)
        wrong += int(torch.tensor(result.payload).argmax()) != label
        spent += workspace.spent
    return wrong / len(labels), spent / len(labels)


def planned_cascade(cheap: DigitRecognizer, expensive: DigitRecognizer,
                    args: argparse.Namespace) -> None:
    print("\nPart C: the cascade built by the planner")
    audit, audit_labels = digit_glyphs(ExpressionDataset("validation", args.samples * 2,
                                                         args.data, args.seed))
    crops, labels = digit_glyphs(ExpressionDataset("test", args.samples * 4, args.data,
                                                   args.seed))
    errors = {m.manifest.ref: measure(Apply(m, (Given(GLYPH),)), audit, audit_labels)[0]
              for m in (cheap, expensive)}
    library: list[Module] = [cheap, expensive, *(
        Fallback(GLYPH, DIGIT_DISTRIBUTION, tau, audit, audit_labels) for tau in args.thresholds)]
    frontier = plan_pareto(library, (GLYPH,), DIGIT_DISTRIBUTION, 1, errors, fuel=args.fuel)
    print(f"{len(audit)} validation and {len(crops)} test digit glyphs; frontier "
          f"(validation error, expected FLOPs per glyph):")
    for option in frontier:
        print(f"  {describe(option.plan):>50s} {option.error:.4f} {option.cost:12,.0f}")
    expensive_error = errors[expensive.manifest.ref]
    print(f"{'target':>7s} {'chosen plan':>50s} {'test error':>11s} {'cost/glyph':>11s} "
          f"{'hand-built error':>17s} {'cost/glyph':>11s}")
    for factor in args.targets:
        target = factor * expensive_error
        chosen = cheapest_within(frontier, target)
        if chosen is None:
            print(f"{target:7.4f} {'-':>50s}")
            continue
        error, cost = measure(chosen.plan, crops, labels)
        hand = "-"
        node = chosen.plan
        if (isinstance(node, Apply) and isinstance(node.module, Fallback)
                and [f.module for f in node.slots if isinstance(f, Apply)] == [cheap, expensive]):
            requester = RequestingRecognizer(cheap, node.module.threshold)
            hand_error, hand_cost = measure(Apply(requester, (Given(GLYPH),)), crops, labels,
                                            Kernel([requester, expensive]))
            hand = f"{hand_error:17.4f} {hand_cost:11,.0f}"
        print(f"{target:7.4f} {describe(chosen.plan):>50s} {error:11.4f} {cost:11,.0f} {hand}")


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
    parser.add_argument("--end-to-end", type=float, nargs="+", default=[0.9])
    parser.add_argument("--weights", type=float, nargs="+", default=[0.5],
                        help="second-opinion weights of the consulting recognizer")
    parser.add_argument("--targets", type=float, nargs="+", default=[1.0, 1.1, 1.5, 2.0, 4.0],
                        help="error targets of Part C, as multiples of the expensive error")
    parser.add_argument("--fuel", type=int, default=3, help="planning depth of Part C")
    parser.add_argument("--parts", default="ABC")
    args = parser.parse_args()

    cheap = DigitRecognizer.load(args.cheap)
    expensive = DigitRecognizer.load(args.expensive)
    costed(cheap, network_flops(cheap.network, GLYPH_SHAPE), "nca.digit-recognizer.cheap")
    costed(expensive, network_flops(expensive.network, GLYPH_SHAPE),
           "nca.digit-recognizer.expensive")
    operator = SymbolRecognizer.load(args.operator)
    costed(operator, network_flops(operator.network, GLYPH_SHAPE))
    if "A" in args.parts:
        glyph_level(cheap, expensive, ExpressionDataset("test", args.samples * 4, args.data,
                                                        args.seed), args.thresholds)
    if "B" in args.parts:
        end_to_end(cheap, expensive, operator, args)
    if "C" in args.parts:
        planned_cascade(cheap, expensive, args)


if __name__ == "__main__":
    main()
