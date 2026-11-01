"""Selective answering on noisy Boolean formulas (§18).

Installs the formula library (tokenizer, edit reader, character reader,
formula evaluator), plans a route from formula text to a truth value with the
stable planner, and refines it with the generic controller (``nca.selective``),
calibrating the readers' ladder on the words of validation formulas. For each
depth and target δ it compares the evaluator's risk accounts (``ACCOUNTS``):
static demand (every word decided fully), its certificate, and the
certificate crediting error detection by Markov's inequality or by pairs
(§19). It reports coverage, error among answered
formulas, mean bound among answered, error when forced to answer, and compute
per formula.

It first reports certificate sizes on the true formulas: the fewest leaves a
valid certificate evaluates, against the bound ``2^⌈d/2⌉`` of
``NCA.alternating_cert_leaves``.

With ``--shift ν`` formulas in use have noise ν instead, and the risk control
of §17 (``nca.ladder.certify``) is applied to one account (``--account``)
with audits drawn at that noise.

    uv run --extra vision python -m nca.logic --reader checkpoints/words.pt
"""

from __future__ import annotations

import argparse
from collections.abc import Sequence
from pathlib import Path

import torch

from nca.abi import TypeId
from nca.certify import INFLATIONS
from nca.formulas import ARITY, VOCABULARY, FormulaDataset, FormulaSample, labeled_words, parse
from nca.ladder import Rung, certification_order, certify
from nca.modules.symbols import BOOLEAN
from nca.modules.words import (WORD_DISTRIBUTION, CharReader, EditReader, FormulaEvaluator,
                               FORMULA_TEXT, Tokenizer)
from nca.planner import Plan, plan_stable
from nca.registry import Module
from nca.selective import build_ladders, solve
from nca.stats import wilson


ACCOUNTS = {"static": (False, "none"), "certificate": (True, "none"),
            "markov": (True, "markov"), "pairs": (True, "pairs")}
"""Evaluator settings compared: short-circuit certificates, and credit for
error detection (§19)."""


def library(reader: Path, short_circuit: bool, detection: str = "none") -> list[Module]:
    return [Tokenizer(), EditReader(), CharReader.load(reader),
            FormulaEvaluator(short_circuit, detection)]


def certificate_leaves(sample: FormulaSample) -> int:
    """Leaves of the smallest valid certificate of the true formula."""
    arities = [ARITY[VOCABULARY.index(w)] for w in sample.words]
    children = parse(arities)
    assert children is not None
    leaves = [float(a == 0) for a in arities]
    kept = FormulaEvaluator.evaluated(sample.words, children, leaves, [0.0] * len(leaves))
    return int(sum(leaves[k] for k in kept))


def outcomes(route: Plan, ladders: dict[TypeId, list[Rung]], samples: Sequence[FormulaSample],
             delta: float) -> tuple[int, int]:
    """Formulas answered and answered wrongly under target ``delta``."""
    answered = wrong = 0
    for sample in samples:
        answer = solve(route, ladders, sample.text, delta)
        if not answer.abstained:
            answered += 1
            wrong += answer.value != sample.value
    return answered, wrong


def selective(routes: dict[str, Plan], ladders: dict[TypeId, list[Rung]],
              args: argparse.Namespace) -> None:
    print(f"{'depth':>5s} {'words':>6s} {'system':>13s} {'coverage':>9s} "
          f"{'error answered [95% CI]':>27s} {'mean bound':>11s} {'error forced':>13s} "
          f"{'kFLOPs':>8s}")
    top = max(len(rungs) for rungs in ladders.values())
    for depth in args.depths:
        dataset = FormulaDataset("test", args.samples, depth, args.noise, args.seed, args.xor)
        samples = [dataset.sample(i) for i in range(len(dataset))]
        words = sum(len(s.words) for s in samples) / len(samples)
        systems = {"bottom rungs": ("certificate", float("inf"), 0),
                   "top rungs": ("certificate", float("inf"), top)}
        for delta in args.targets:
            systems |= {f"{name} δ={delta:g}": (name, delta, 0) for name in args.accounts}
        for system, (name, delta, start) in systems.items():
            answered = wrong_answered = wrong_forced = 0
            spent = bound_sum = 0.0
            for sample in samples:
                answer = solve(routes[name], ladders, sample.text, delta, start)
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
            print(f"{depth:5d} {words:6.1f} {system.replace('certificate', 'cert'):>13s} "
                  f"{answered / n:9.3f} {rate:.4f} [{low:.4f}, {high:.4f}]".ljust(66)
                  + f" {mean_bound:11.4f} {wrong_forced / n:13.4f} {spent / n / 1e3:8.1f}",
                  flush=True)


def shifted(route: Plan, ladders: dict[TypeId, list[Rung]], args: argparse.Namespace) -> None:
    print(f"{'depth':>5s} {'draw':>5s} {'δ':>5s} {'control':>8s} {'λ':>5s} {'coverage':>9s} "
          f"{'error answered [95% CI]':>27s} {'≤ δ':>5s}")
    for depth in args.depths:
        evaluation = FormulaDataset("test", args.samples, depth, args.shift, args.seed, args.xor)
        samples = [evaluation.sample(i) for i in range(len(evaluation))]
        for draw in range(args.draws):
            audit = FormulaDataset("test", 2 * args.audit, depth, args.shift,
                                   args.seed + 1 + draw, args.xor)
            fit = [audit.sample(i) for i in range(args.audit)]
            check = [audit.sample(i) for i in range(args.audit, 2 * args.audit)]
            for delta in args.targets:
                order = certification_order(
                    [outcomes(route, ladders, fit, delta / lam) for lam in INFLATIONS], args.alpha)
                stats = [outcomes(route, ladders, check, delta / lam) for lam in INFLATIONS]
                accepted = certify(stats, delta, args.alpha, order)
                chosen = max(accepted, key=lambda i: stats[i][0], default=None)
                for control, lam in (("none", 1.0),
                                     ("risk", None if chosen is None else INFLATIONS[chosen])):
                    answered, wrong = ((0, 0) if lam is None
                                       else outcomes(route, ladders, samples, delta / lam))
                    rate = wrong / answered if answered else 0.0
                    low, high = wilson(wrong, answered) if answered else (0.0, 1.0)
                    shown = "-" if lam is None else f"{lam:g}"
                    print(f"{depth:5d} {draw:5d} {delta:5g} {control:>8s} {shown:>5s} "
                          f"{answered / len(samples):9.3f} "
                          f"{rate:.4f} [{low:.4f}, {high:.4f}]".ljust(70)
                          + f" {str(rate <= delta):>5s}", flush=True)


def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__.splitlines()[0])
    parser.add_argument("--reader", type=Path, default=Path("checkpoints/words.pt"))
    parser.add_argument("--noise", type=float, default=0.1)
    parser.add_argument("--xor", type=float, default=0.0)
    parser.add_argument("--calibration", type=int, default=100, help="validation formulas")
    parser.add_argument("--samples", type=int, default=300)
    parser.add_argument("--seed", type=int, default=0)
    parser.add_argument("--depths", type=int, nargs="+", default=[2, 4, 6])
    parser.add_argument("--targets", type=float, nargs="+", default=[0.2, 0.05, 0.01])
    parser.add_argument("--accounts", nargs="+", choices=ACCOUNTS, default=list(ACCOUNTS))
    parser.add_argument("--shift", type=float, help="noise in use, for risk control")
    parser.add_argument("--account", choices=ACCOUNTS, default="certificate",
                        help="the account risk control certifies")
    parser.add_argument("--audit", type=int, default=200, help="formulas per audit half")
    parser.add_argument("--draws", type=int, default=3)
    parser.add_argument("--alpha", type=float, default=0.1)
    args = parser.parse_args()

    routes = {}
    for name, (short_circuit, detection) in ACCOUNTS.items():
        route = plan_stable(library(args.reader, short_circuit, detection), (FORMULA_TEXT,),
                            BOOLEAN)
        assert route is not None
        routes[name] = route
    words, labels = labeled_words(FormulaDataset("validation", args.calibration, 4, args.noise,
                                                 args.seed, args.xor))
    ladders = build_ladders(library(args.reader, True), routes["certificate"],
                            {WORD_DISTRIBUTION: (words, torch.from_numpy(labels))})
    print(f"{WORD_DISTRIBUTION}: " + ", ".join(
        f"{r.module.manifest.module_id} (cost {r.cost:g}, T={r.temperature():.2f})"
        for r in ladders[WORD_DISTRIBUTION]))

    print(f"{'depth':>5s} {'leaves':>7s} {'certificate leaves: mean':>25s} {'max':>5s} "
          f"{'bound 2^⌈d/2⌉':>14s}")
    for depth in args.depths:
        dataset = FormulaDataset("test", args.samples, depth, args.noise, args.seed, args.xor)
        sizes = [certificate_leaves(dataset.sample(i)) for i in range(len(dataset))]
        print(f"{depth:5d} {2 ** depth:7d} {sum(sizes) / len(sizes):25.2f} {max(sizes):5d} "
              f"{2 ** ((depth + 1) // 2):14d}")

    if args.shift is None:
        selective(routes, ladders, args)
    else:
        shifted(routes[args.account], ladders, args)


if __name__ == "__main__":
    main()
