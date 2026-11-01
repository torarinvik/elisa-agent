"""Selective answering with budgeted refinement along a route.

The kernel plans a route and refines it generically (``nca.ladder``). The
route must end in a chain of single-input consumers applied to a ``map``
whose body either reads the element with one expert, or applies one module
to several readings of the element. Nothing below is specific to glyphs:

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
* a consumer reading the readings directly may declare a ``certificate``:
  given the readings and each one's risk and calibrated entry probabilities
  under any decision, a risk account
  charging each reading its share of a bound on the answer's error, which
  may depend on the readings' values (``NCA.certificate_error_le``);
* such a consumer may also declare a ``floor``: given the readings, their
  risks and the elements whose readings can no longer change, a lower bound
  on every bound refinement can still reach, so that refinement abstains as
  soon as it exceeds the target (§22);
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
import math
from collections.abc import Callable, Sequence
from dataclasses import dataclass
from pathlib import Path
from typing import Any

import torch

from nca.abi import NOTHING, Contract, SequenceDemand, TypeId
from nca.efficiency import costed, network_flops
from nca.expressions import ExpressionDataset
from nca.ladder import (Distribution, Certificate, Decision, Floor, Refinement, Rung, SecondLook, State, Stop, ladder,
                        refine)
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


def readers(mapped: Map) -> list[Apply]:
    """The expert applications reading each element: the body itself if it
    reads the element directly, otherwise its arguments."""
    body = mapped.body
    assert isinstance(body, Apply)
    if body.args == (Given(mapped.element),):
        return [body]
    assert all(isinstance(a, Apply) and a.args == (Given(mapped.element),) for a in body.args)
    return list(body.args)


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
          start: int = 0, floors: bool = False, stop: Stop | None = None,
          trace: list[State] | None = None) -> Answer:
    """Answer ``value`` along ``route`` within target ``delta``, or abstain.

    With ``floors`` refinement abstains as soon as the consumer's floor (or,
    without a certificate, the additive floor) exceeds ``delta``; ``stop`` and
    ``trace`` are passed to ``refine``.
    """
    return _solve_targets(route, ladders, value, [delta], start, floors, stop, trace)[0]


def solve_many(route: Plan, ladders: dict[TypeId, list[Rung]], value: Any,
               targets: Sequence[float], start: int = 0) -> list[Answer]:
    """Answer several targets from one target-independent refinement path.

    Consumers must be deterministic. Floors and predictive stopping are not
    enabled; answers retain the cost at their own first qualifying state.
    """
    if any(math.isnan(target) or target < 0 for target in targets):
        raise ValueError("targets must be nonnegative and not NaN")
    if not targets:
        return []
    return _solve_targets(route, ladders, value, targets, start)


def _solve_targets(route: Plan, ladders: dict[TypeId, list[Rung]], value: Any,
                   targets: Sequence[float], start: int = 0, floors: bool = False,
                   stop: Stop | None = None, trace: list[State] | None = None) -> list[Answer]:
    delta = min(targets)
    chain, mapped = split_route(route)
    consumer, body, source = chain[-1], mapped.body, mapped.source
    experts = readers(mapped)
    fuse = None if experts == [body] else body.module
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
        return [Answer(None, 0.0, 1.0, True) for _ in targets]
    declare = getattr(fuse, "decides", getattr(fuse, "demand", None))
    items = [(i, k) for i, read in enumerate(reads) if read != NOTHING
             for k in range(len(experts))
             if declare is None or declare(k, read) != NOTHING]
    types = [r.module.manifest.contract.output for r in experts]
    ranges = getattr(fuse, "decision_classes", lambda k, d: None)
    certificate = element_certificate(consumer, items, len(elements))
    assert certificate is None or fuse is None, "certificates are declared on direct readings"
    floor = element_floor(consumer, items, len(elements)) if floors else None
    selected: dict[float, Refinement] = {}

    def observe(state: Refinement) -> None:
        for target in targets:
            if target not in selected and state.bound <= target:
                selected[target] = state

    refined = refine([elements[i] for i, _ in items], [ladders[types[k]] for _, k in items],
                     delta, start, [ranges(k, reads[i]) for i, k in items], certificate,
                     floor, floors, stop, trace, observe if len(targets) > 1 else None)

    def answer(state: Refinement, target: float) -> Answer:
        inputs: list[list[Any]] = [[None] * len(experts) for _ in elements]
        for (i, k), observed in zip(items, state.readings):
            inputs[i][k] = tuple(observed.tolist())
        result: Any = ([args[0] for args in inputs] if fuse is None else
                       [fuse.invoke(*args) if read != NOTHING else None
                        for args, read in zip(inputs, reads)])
        for module in reversed(chain):
            result = module.invoke(result)
        return Answer(result, state.cost, state.bound, state.bound > target)

    return [answer(selected.get(target, refined), target) for target in targets]


def element_certificate(consumer: Module, items: Sequence[tuple[int, int]],
                        count: int) -> Certificate | None:
    """The consumer's certificate over its elements, as one over refined items."""
    declared = getattr(consumer, "certificate", None)
    if declared is None:
        return None
    session = getattr(consumer, "certificate_session", None)
    if session is not None:
        declared = session()
    position = {i: j for j, (i, _) in enumerate(items)}
    elements: list[Any] = [None] * count
    revisions: dict[int, int] = {}

    def certificate(readings: Sequence[torch.Tensor], risk: Callable[[int, Decision], float],
                    distribution: Callable[[int, Decision], torch.Tensor],
                    ) -> dict[int, float] | None:
        revision = getattr(distribution, "revision", None)
        if revision is None:
            revisions.clear()
        for j, ((i, _), value) in enumerate(zip(items, readings)):
            version = revision(j) if revision is not None else None
            if version is None or revisions.get(i) != version:
                elements[i] = tuple(value.tolist())
                if version is not None:
                    revisions[i] = version

        def mapped_distribution(i: int, d: Decision) -> torch.Tensor:
            return distribution(position[i], d)

        revision = getattr(distribution, "revision", None)
        calibrated = (Distribution(mapped_distribution, lambda i: revision(position[i]))
                      if revision is not None else mapped_distribution)
        chosen = declared(list(elements), lambda i, d: risk(position[i], d), calibrated)
        return None if chosen is None else {position[i]: c for i, c in chosen.items()}

    return certificate


def element_floor(consumer: Module, items: Sequence[tuple[int, int]],
                  count: int) -> Floor | None:
    """The consumer's floor over its elements, as one over refined items."""
    declared = getattr(consumer, "floor", None)
    if declared is None:
        return None
    position = {i: j for j, (i, _) in enumerate(items)}

    def floor(readings: Sequence[torch.Tensor], risk: Callable[[int, Decision], float],
              fixed: frozenset[int]) -> float:
        elements: list[Any] = [None] * count
        for (i, _), value in zip(items, readings):
            elements[i] = tuple(value.tolist())
        return declared(elements, lambda i, d: risk(position[i], d),
                        frozenset(items[j][0] for j in fixed))

    return floor


def build_ladders(modules: Sequence[Module], route: Plan,
                  validation: dict[TypeId, tuple[list[Any], torch.Tensor]],
                  ) -> dict[TypeId, list[Rung]]:
    """A calibrated ladder for every input type of the route's map body."""
    _, mapped = split_route(route)
    ladders = {}
    for t in (r.module.manifest.contract.output for r in readers(mapped)):
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
