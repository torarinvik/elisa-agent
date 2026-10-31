"""Selective answering with budgeted refinement along a route.

The kernel plans a route and refines it generically (``nca.ladder``). The
route must end in a chain of single-input consumers applied to a ``map``
whose body applies one module to readings of the element. Nothing below is
specific to glyphs:

* what is read of element ``i`` comes from the map consumer's ``demand``
  declaration, and what the body reads of each input from its ``decides``
  declaration (decision demand: inputs that can change the consumer's
  decision), falling back to ``demand``. Unread inputs are passed as ``None``,
  so only decision-relevant readings are computed and enter the bound, each
  with risk measured over the classes its decision ranges over
  (``decision_classes``, when declared);
* every demanded input is produced by a ladder: all installed experts with
  that input's contract, ordered by declared cost and calibrated on held-out
  labeled data;
* if the map's source offers ``alternatives`` and the consumer would read
  nothing of a candidate, the next candidate is tried without reading it.

The experiment installs the handwritten-arithmetic library: cheap, expensive
and (optionally) stronger digit recognizers, the operator recognizer, and
``SecondLook`` versions of all but the cheapest, which average readings of
four one-pixel shifts. It reports, per expression length and target δ:
coverage, error among answered expressions, mean bound among answered (a
calibration check), error when forced to answer, and compute per expression.

    uv run --extra vision python -m nca.selective --cheap checkpoints/digit_mlp.pt \\
        --expensive checkpoints/digit_cnn.pt
"""

from __future__ import annotations

import argparse
from collections.abc import Sequence
from dataclasses import dataclass
from pathlib import Path
from typing import Any

import torch

from nca.abi import NOTHING, Contract, SequenceDemand, TypeId
from nca.efficiency import costed, network_flops
from nca.expressions import ExpressionDataset
from nca.ladder import Rung, SecondLook, ladder, refine
from nca.modules.digit_recognizer import DIGIT_DISTRIBUTION, DigitRecognizer
from nca.modules.operator_recognizer import OPERATOR_DISTRIBUTION, SymbolRecognizer, make_dataset
from nca.modules.segmenter import EXPRESSION_IMAGE, Segmenter
from nca.modules.symbols import INTEGER, Evaluator, ExpressionParser, SymbolFuser
from nca.planner import Apply, Given, Map, Plan, plan_stable
from nca.registry import Module
from nca.stats import wilson

SHIFTS = ((1, 0), (-1, 0), (0, 1), (0, -1))
GLYPH_SHAPE = (1, 28, 28)


def shifted(glyph: torch.Tensor) -> list[torch.Tensor]:
    return [torch.roll(glyph, shift, dims=(0, 1)) for shift in SHIFTS]


@dataclass
class Answer:
    value: Any
    cost: float
    bound: float
    abstained: bool


def split_route(route: Plan) -> tuple[list[Module], Map]:
    """The consumer chain (outermost first) and the map it consumes."""
    chain: list[Module] = []
    while isinstance(route, Apply):
        assert len(route.args) == 1, "refinement needs a chain of single-input consumers"
        chain.append(route.module)
        route = route.args[0]
    assert isinstance(route, Map) and isinstance(route.body, Apply)
    return chain, route


def solve(route: Plan, ladders: dict[TypeId, list[Rung]], value: Any, delta: float,
          start: int = 0) -> Answer:
    chain, mapped = split_route(route)
    consumer, body, source = chain[-1], mapped.body, mapped.source
    assert all(isinstance(a, Apply) and a.args == (Given(mapped.element),) for a in body.args)
    assert isinstance(source, Apply) and isinstance(source.args[0], Given)
    producer = source.module
    candidates = getattr(producer, "alternatives", lambda v: iter([producer.invoke(v)]))
    declared = getattr(consumer, "demand", None)
    for elements in candidates(value):
        demand = declared(0, None) if declared is not None else None
        reads = [demand.element(i, len(elements)) if isinstance(demand, SequenceDemand)
                 else demand for i in range(len(elements))]
        if any(r != NOTHING for r in reads):
            break
    else:
        return Answer(None, 0.0, 1.0, True)
    declare = getattr(body.module, "decides", getattr(body.module, "demand", None))
    items = [(i, k) for i, read in enumerate(reads) if read != NOTHING
             for k in range(len(body.args))
             if declare is None or declare(k, read) != NOTHING]
    types = body.module.manifest.contract.inputs
    ranges = getattr(body.module, "decision_classes", lambda k, d: None)
    refined = refine([elements[i] for i, _ in items], [ladders[types[k]] for _, k in items],
                     delta, start, [ranges(k, reads[i]) for i, k in items])
    inputs: list[list[Any]] = [[None] * len(body.args) for _ in elements]
    for (i, k), reading in zip(items, refined.readings):
        inputs[i][k] = tuple(reading.tolist())
    result: Any = [body.module.invoke(*args) if read != NOTHING else None
                   for args, read in zip(inputs, reads)]
    for module in reversed(chain):
        result = module.invoke(result)
    return Answer(result, refined.cost, refined.bound, refined.abstained)


def build_ladders(modules: Sequence[Module], route: Plan,
                  validation: dict[TypeId, tuple[list[Any], torch.Tensor]],
                  ) -> dict[TypeId, list[Rung]]:
    """A calibrated ladder for every input type of the route's map body."""
    _, mapped = split_route(route)
    ladders = {}
    for t in mapped.body.module.manifest.contract.inputs:
        ladders[t] = ladder(modules, Contract((mapped.element,), t))
        values, labels = validation[t]
        for rung in ladders[t]:
            rung.calibrate(values, labels)
    return ladders


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
          f"{'mean bound':>11s} {'error forced':>13s} {'MFLOPs/expr':>12s}")
    top = max(len(rungs) for rungs in ladders.values())
    for operands in args.operands:
        dataset = ExpressionDataset("test", args.samples, args.data, args.seed,
                                    operands=operands)
        samples = [dataset.sample(i) for i in range(len(dataset))]
        systems = {"bottom rungs": (float("inf"), 0), "top rungs": (float("inf"), top)}
        systems |= {f"δ={d:g}": (d, 0) for d in args.targets}
        for name, (delta, start) in systems.items():
            answered = wrong_answered = wrong_forced = 0
            spent = bound_sum = 0.0
            for sample in samples:
                answer = solve(route, ladders, torch.from_numpy(sample.image), delta, start)
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
                  + f" {mean_bound:11.4f} {wrong_forced / n:13.4f} {spent / n / 1e6:12.2f}")


if __name__ == "__main__":
    main()
