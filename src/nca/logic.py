"""Selective answering on noisy Boolean formulas (§18).

Installs the formula library (tokenizer, edit reader, character reader,
formula evaluator), plans a route from formula text to a truth value with the
stable planner, and refines it with the generic controller (``nca.selective``),
calibrating the readers' ladder on the words of validation formulas. For each
depth and target δ it compares the evaluator's risk accounts (``ACCOUNTS``):
static demand (every word decided fully), its certificate, and the
certificate crediting error detection by Markov's inequality or by pairs
(§19), and decoding by the format (§21). It reports coverage, error among
answered formulas, mean bound among answered, error when forced to answer, and
compute per formula.

It first reports certificate sizes on the true formulas: the fewest leaves a
valid certificate evaluates, against the bound ``2^⌈d/2⌉`` of
``NCA.alternating_cert_leaves``.

With ``--shift ν`` formulas in use have noise ν instead, and the risk control
of §17 (``nca.ladder.certify``) is applied to one account (``--account``)
with audits drawn at that noise.

With ``--premises`` it tests the premises of §21.8 on bottom-rung readings
instead, at the calibration noise and at ``--shift`` if given: calibration of
the decoded arity sequence's posterior risk ``R``, the pairs premise of §19
(formulas with at least two arity failures against ``Σ e₂``), and joint
failures of adjacent and distant word pairs against the products of their
risks.

    uv run --extra vision python -m nca.logic --reader checkpoints/words.pt
"""

from __future__ import annotations

import argparse
from collections.abc import Sequence
from pathlib import Path

import torch

from nca.abi import TypeId
from nca.certify import INFLATIONS
import numpy as np

from nca.formulas import (ARITY, VOCABULARY, FormulaDataset, FormulaSample, decode,
                          labeled_words, parse)
from nca.ladder import Rung, certification_order, certify
from nca.modules.symbols import BOOLEAN
from nca.modules.words import (ARITY_DECISION, ARITY_ORDER, WORD_DISTRIBUTION, CharReader,
                               EditReader, FormulaEvaluator, FORMULA_TEXT, Tokenizer)
from nca.planner import Plan, plan_stable
from nca.registry import Module
from nca.selective import build_ladders, solve
from nca.stats import poisson_binomial_tails, wilson


ACCOUNTS = {"static": (False, "none", False), "certificate": (True, "none", False),
            "markov": (True, "markov", False), "pairs": (True, "pairs", False),
            "correction": (True, "none", True)}
"""Evaluator settings compared: short-circuit certificates, credit for error
detection (§19), and decoding by the format (§21)."""


def library(reader: Path, short_circuit: bool, detection: str = "none",
            decoding: bool = False) -> list[Module]:
    return [Tokenizer(), EditReader(), CharReader.load(reader),
            FormulaEvaluator(short_circuit, detection, decoding)]


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
    print(f"{'depth':>5s} {'words':>6s} {'system':>18s} {'coverage':>9s} "
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
            print(f"{depth:5d} {words:6.1f} {system.replace('certificate', 'cert'):>18s} "
                  f"{answered / n:9.3f} {rate:.4f} [{low:.4f}, {high:.4f}]".ljust(71)
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


def arities(words: Sequence[str]) -> list[int]:
    return [ARITY[VOCABULARY.index(w)] for w in words]


def premises(rung: Rung, args: argparse.Namespace) -> None:
    """The count tests of §21.8 on ``rung``'s readings."""
    decoder = FormulaEvaluator(decode=True)
    near = 10
    for noise in (args.noise, *(() if args.shift is None else (args.shift,))):
        for depth in args.depths:
            dataset = FormulaDataset("test", args.samples, depth, noise, args.seed, args.xor)
            risks: list[float] = []
            wrong: list[bool] = []
            pairs: list[float] = []
            doubled = 0
            failures = predicted = 0.0
            joint = {"adjacent": 0, "distant": 0}
            expected = {"adjacent": 0.0, "distant": 0.0}
            for index in range(len(dataset)):
                sample = dataset.sample(index)
                logs = [rung.observe(w) for w in sample.text.split(" ")]
                readings = [tuple(rung.reading(log).tolist()) for log in logs]
                calibrated = np.log(np.clip(np.array(
                    [rung.distribution(log, ARITY_DECISION).tolist() for log in logs]),
                    1e-300, None))
                truth = arities(sample.words)
                posterior = decode(calibrated, ARITY_ORDER)
                assert posterior is not None
                chosen = arities(decoder.words(readings))
                risks.append(posterior.risk(calibrated, ARITY_ORDER, chosen))
                wrong.append(chosen != truth)
                rho = np.array([rung.risk(log, ARITY_DECISION) for log in logs])
                read = arities(FormulaEvaluator().words(readings))
                failed = np.array([a != t for a, t in zip(read, truth)])
                doubled += int(failed.sum() >= 2)
                pairs.append(float((rho.sum() ** 2 - (rho ** 2).sum()) / 2))
                failures += float(failed.sum())
                predicted += float(rho.sum())
                close = sum(float(rho[:-g] @ rho[g:]) for g in range(1, near) if g < len(rho))
                expected["adjacent"] += float(rho[:-1] @ rho[1:])
                expected["distant"] += pairs[-1] - close
                where = np.flatnonzero(failed)
                gaps = np.abs(where[:, None] - where[None, :])[np.triu_indices(len(where), 1)]
                joint["adjacent"] += int((gaps == 1).sum())
                joint["distant"] += int((gaps >= near).sum())
            observed = sum(wrong)
            above, below = poisson_binomial_tails(observed, risks)
            print(f"noise {noise:g} depth {depth}: decoded arity sequence wrong {observed} "
                  f"of {len(wrong)}, predicted Σ R = {sum(risks):.1f} "
                  f"(P(X ≥ obs) = {above:.3g}, P(X ≤ obs) = {below:.3g})")
            edges = (0.0, 1e-3, 1e-2, 0.1, 1.0 + 1e-9)
            for low, high in zip(edges, edges[1:]):
                chosen_bin = [i for i, r in enumerate(risks) if low <= r < high]
                if chosen_bin:
                    print(f"  R in [{low:g}, {min(high, 1.0):g}): {len(chosen_bin):5d} formulas, "
                          f"mean R {np.mean([risks[i] for i in chosen_bin]):.4f}, "
                          f"wrong {np.mean([wrong[i] for i in chosen_bin]):.4f}")
            above, _ = poisson_binomial_tails(doubled, [min(1.0, e) for e in pairs])
            print(f"  ≥ 2 arity failures: {doubled} formulas, Σ e₂ = {sum(pairs):.1f} "
                  f"(P(X ≥ obs) = {above:.3g}); arity failures {failures:.0f}, "
                  f"Σ ρ = {predicted:.1f}")
            for kind in joint:
                print(f"  {kind} joint failures: {joint[kind]}, Σ ρᵢρⱼ = {expected[kind]:.2f}, "
                      f"ratio {joint[kind] / expected[kind]:.2f} against marginal ratio² "
                      f"{(failures / predicted) ** 2:.2f}")


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
    parser.add_argument("--premises", action="store_true", help="test the premises of §21.8")
    args = parser.parse_args()

    routes = {}
    for name, (short_circuit, detection, decoding) in ACCOUNTS.items():
        route = plan_stable(library(args.reader, short_circuit, detection, decoding),
                            (FORMULA_TEXT,), BOOLEAN)
        assert route is not None
        routes[name] = route
    words, labels = labeled_words(FormulaDataset("validation", args.calibration, 4, args.noise,
                                                 args.seed, args.xor))
    ladders = build_ladders(library(args.reader, True), routes["certificate"],
                            {WORD_DISTRIBUTION: (words, torch.from_numpy(labels))})
    print(f"{WORD_DISTRIBUTION}: " + ", ".join(
        f"{r.module.manifest.module_id} (cost {r.cost:g}, T={r.temperature():.2f})"
        for r in ladders[WORD_DISTRIBUTION]))
    if args.premises:
        premises(ladders[WORD_DISTRIBUTION][0], args)
        return

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
