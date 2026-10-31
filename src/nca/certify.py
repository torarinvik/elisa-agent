"""Risk-controlled selective answering under distribution shift (§17).

Rungs are calibrated on the reference distribution (the ``validation``
half of the MNIST test set) but deployed on another (the ``test`` half,
other writers). The test half is divided into disjoint parts: an *audit*,
labeled by a teacher, and an evaluation set. The audit is split again:

* its first half supplies labeled glyphs to recalibrate every rung
  (``nca.ladder.recalibrated``);
* both halves run every candidate inflation ``λ`` (the controller with
  target ``δ / λ``). The first half fixes the testing order, most
  certifiable first; on the second half each candidate in that order is
  declared safe when the Clopper–Pearson upper bound on its error rate among
  answered audit expressions is at most ``δ``, stopping at the first failure
  (``nca.ladder.certify``, ``NCA.fixed_sequence_le``). With probability at
  least ``1 - α`` over the audit, every accepted candidate's error rate among
  answered inputs is at most ``δ``; the one answering most is deployed.

For each length, target, calibration (reference or audit) and control (none
or risk control), and for several independent audit draws, it reports the
certified ``λ``, coverage and error among answered evaluation expressions,
and whether the error met the target.

    uv run --extra vision python -m nca.certify --cheap checkpoints/digit_mlp.pt \\
        --expensive checkpoints/digit_cnn.pt
"""

from __future__ import annotations

import argparse
from collections.abc import Sequence
from pathlib import Path
from typing import Any

import torch

from nca.abi import TypeId
from nca.expressions import OPERATORS, ExpressionDataset, Sample
from nca.ladder import Rung, certification_order, certify, recalibrated
from nca.modules.digit_recognizer import DIGIT_DISTRIBUTION
from nca.modules.operator_recognizer import OPERATOR_DISTRIBUTION
from nca.modules.segmenter import EXPRESSION_IMAGE, Segmenter
from nca.modules.symbols import INTEGER
from nca.planner import Plan, plan_stable
from nca.selective import build_ladders, library, solve, validation_data
from nca.stats import wilson

INFLATIONS = (4.0, 2.0, 1.5, 1.25, 1.0, 0.75, 0.5)
"""Candidate inflation factors; below 1 the policy answers above its bound."""


def labeled_glyphs(samples: Sequence[Sample]) -> dict[TypeId, tuple[list[Any], torch.Tensor]]:
    """Teacher-labeled glyphs of audit expressions, by the reading type they train."""
    values: dict[TypeId, list[Any]] = {DIGIT_DISTRIBUTION: [], OPERATOR_DISTRIBUTION: []}
    labels: dict[TypeId, list[int]] = {DIGIT_DISTRIBUTION: [], OPERATOR_DISTRIBUTION: []}
    segmenter = Segmenter()
    for sample in samples:
        crops = next((c for c in segmenter.alternatives(torch.from_numpy(sample.image))
                      if len(c) == len(sample.tokens)), None)
        if crops is None:
            continue
        for crop, token in zip(crops, sample.tokens):
            if token.isdigit():
                values[DIGIT_DISTRIBUTION].append(crop)
                labels[DIGIT_DISTRIBUTION].append(int(token))
            else:
                values[OPERATOR_DISTRIBUTION].append(crop)
                labels[OPERATOR_DISTRIBUTION].append(OPERATORS.index(token))
    return {t: (values[t], torch.tensor(labels[t])) for t in values}


def outcomes(route: Plan, ladders: dict[TypeId, list[Rung]], samples: Sequence[Sample],
             delta: float) -> tuple[int, int]:
    """Expressions answered and answered wrongly under target ``delta``."""
    answered = wrong = 0
    for sample in samples:
        answer = solve(route, ladders, torch.from_numpy(sample.image), delta)
        if not answer.abstained:
            answered += 1
            wrong += answer.value != sample.value
    return answered, wrong


def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__.splitlines()[0])
    parser.add_argument("--data", type=Path, default=Path("data"))
    parser.add_argument("--cheap", type=Path, required=True)
    parser.add_argument("--expensive", type=Path, required=True)
    parser.add_argument("--strong", type=Path, help="a stronger digit recognizer")
    parser.add_argument("--operator", type=Path, default=Path("checkpoints/operators.pt"))
    parser.add_argument("--calibration", type=int, default=2000)
    parser.add_argument("--audit", type=int, default=200, help="expressions per audit half")
    parser.add_argument("--samples", type=int, default=300, help="evaluation expressions")
    parser.add_argument("--draws", type=int, default=3, help="independent audits")
    parser.add_argument("--alpha", type=float, default=0.1)
    parser.add_argument("--seed", type=int, default=0)
    parser.add_argument("--operands", type=int, nargs="+", default=[8, 32])
    parser.add_argument("--targets", type=float, nargs="+", default=[0.2, 0.05])
    args = parser.parse_args()

    modules = library(args)
    route = plan_stable(modules, (EXPRESSION_IMAGE,), INTEGER)
    assert route is not None
    reference = build_ladders(modules, route,
                              validation_data(args.data, args.seed, args.calibration))
    print(f"{'glyphs':>7s} {'draw':>5s} {'calibration':>12s} {'δ':>5s} {'control':>8s} "
          f"{'λ':>5s} {'coverage':>9s} {'error answered [95% CI]':>27s} {'≤ δ':>5s}")
    for operands in args.operands:
        evaluation = [ExpressionDataset("test", args.samples, args.data, args.seed,
                                        operands=operands, part=(1, 2)).sample(i)
                      for i in range(args.samples)]
        for draw in range(args.draws):
            audit = ExpressionDataset("test", 2 * args.audit, args.data,
                                      args.seed + 1 + draw, operands=operands, part=(0, 2))
            fit = [audit.sample(i) for i in range(args.audit)]
            check = [audit.sample(i) for i in range(args.audit, 2 * args.audit)]
            glyphs = labeled_glyphs(fit)
            calibrations = {"reference": reference,
                            "audit": {t: recalibrated(r, *glyphs[t])
                                      for t, r in reference.items()}}
            for name, ladders in calibrations.items():
                for delta in args.targets:
                    order = certification_order(
                        [outcomes(route, ladders, fit, delta / lam) for lam in INFLATIONS],
                        args.alpha)
                    stats = [outcomes(route, ladders, check, delta / lam) for lam in INFLATIONS]
                    accepted = certify(stats, delta, args.alpha, order)
                    chosen = max(accepted, key=lambda i: stats[i][0], default=None)
                    for control, lam in (("none", 1.0),
                                         ("risk", None if chosen is None
                                          else INFLATIONS[chosen])):
                        if lam is None:
                            answered, wrong = 0, 0
                        else:
                            answered, wrong = outcomes(route, ladders, evaluation, delta / lam)
                        rate = wrong / answered if answered else 0.0
                        low, high = wilson(wrong, answered) if answered else (0.0, 1.0)
                        shown = "-" if lam is None else f"{lam:g}"
                        print(f"{2 * operands - 1:7d} {draw:5d} {name:>12s} {delta:5g} "
                              f"{control:>8s} {shown:>5s} {answered / len(evaluation):9.3f} "
                              f"{rate:.4f} [{low:.4f}, {high:.4f}]".ljust(84)
                              + f" {str(rate <= delta):>5s}", flush=True)


if __name__ == "__main__":
    main()
