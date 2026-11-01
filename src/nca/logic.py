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

With ``--floors`` every system also runs with early abstention by the
evaluator's floor (§22.3), checking that the answers are identical and
reporting compute overall and on abstained formulas. ``--frontier`` traces
the coverage–compute frontier of the predictive stopping rule (§22.4) for
one account (``--account``), fitted on validation formulas of each depth.

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

import numpy as np
import torch

from nca.abi import TypeId
from nca.certify import INFLATIONS
from nca.formulas import (ARITY, VOCABULARY, FormulaDataset, FormulaSample, decode,
                          labeled_words, parse)
from nca.ladder import (Rung, State, Stop, certification_order, certification_possible, certify,
                        stopping_rule)
from nca.modules.symbols import BOOLEAN
from nca.modules.words import (ARITY_DECISION, ARITY_ORDER, WORD_DISTRIBUTION, CharReader,
                               EditReader, FormulaEvaluator, FORMULA_TEXT, Tokenizer)
from nca.planner import Plan, plan_stable
from nca.registry import Module
from nca.selective import Answer, build_ladders, solve, solve_many
from nca.stats import clopper_pearson_upper, poisson_binomial_tails, wilson


ACCOUNTS = {"static": (False, "none", False), "certificate": (True, "none", False),
            "markov": (True, "markov", False), "pairs": (True, "pairs", False),
            "correction": (True, "none", True)}
"""Evaluator settings compared: short-circuit certificates, credit for error
detection (§19), and decoding by the format (§21)."""


def library(reader: Path, short_circuit: bool, detection: str = "none",
            decoding: bool = False, band_slack: float | None = None) -> list[Module]:
    return [Tokenizer(), EditReader(), CharReader.load(reader),
            FormulaEvaluator(short_circuit, detection, decoding, band_slack)]


def certificate_leaves(sample: FormulaSample) -> int:
    """Leaves of the smallest valid certificate of the true formula."""
    arities = [ARITY[VOCABULARY.index(w)] for w in sample.words]
    children = parse(arities)
    assert children is not None
    leaves = [float(a == 0) for a in arities]
    kept = FormulaEvaluator.evaluated(sample.words, children, leaves, [0.0] * len(leaves))
    return int(sum(leaves[k] for k in kept))


def outcomes(route: Plan, ladders: dict[TypeId, list[Rung]], samples: Sequence[FormulaSample],
             delta: float, *, reject_above: float | None = None,
             alpha: float = 0.1) -> tuple[int, int]:
    """Answer/error counts; checking may stop only on irreversible rejection."""
    answered = wrong = 0
    for sample in samples:
        answer = solve(route, ladders, sample.text, delta)
        if not answer.abstained:
            answered += 1
            incorrect = answer.value != sample.value
            wrong += incorrect
            if (incorrect and reject_above is not None
                    and clopper_pearson_upper(wrong, len(samples), alpha) > reject_above):
                break
    return answered, wrong


def outcomes_many(route: Plan, ladders: dict[TypeId, list[Rung]],
                  samples: Sequence[FormulaSample], targets: Sequence[float]) -> list[tuple[int, int]]:
    """Fit-half counts for several policies sharing target-independent inference."""
    counts = [[0, 0] for _ in targets]
    for sample in samples:
        for count, answer in zip(counts, solve_many(route, ladders, sample.text, targets)):
            if not answer.abstained:
                count[0] += 1
                count[1] += answer.value != sample.value
    return [(answered, wrong) for answered, wrong in counts]


def run(route: Plan, ladders: dict[TypeId, list[Rung]], samples: Sequence[FormulaSample],
        delta: float, start: int = 0, floors: bool = False,
        stop: Stop | None = None) -> list[Answer]:
    return [solve(route, ladders, s.text, delta, start, floors, stop) for s in samples]


def summary(answers: Sequence[Answer], samples: Sequence[FormulaSample]) -> str:
    """Coverage, error among answered [95% CI], mean bound, error forced, kFLOPs."""
    n = len(samples)
    answered = [a for a in answers if not a.abstained]
    wrong_answered = sum(a.value != s.value for a, s in zip(answers, samples) if not a.abstained)
    wrong_forced = sum(a.value != s.value for a, s in zip(answers, samples))
    low, high = wilson(wrong_answered, len(answered)) if answered else (0.0, 1.0)
    rate = wrong_answered / len(answered) if answered else float("nan")
    mean_bound = sum(a.bound for a in answered) / len(answered) if answered else float("nan")
    return (f"{len(answered) / n:9.3f} {rate:.4f} [{low:.4f}, {high:.4f}]".ljust(37)
            + f" {mean_bound:11.4f} {wrong_forced / n:13.4f} "
            f"{sum(a.cost for a in answers) / n / 1e3:8.1f}")


def abstained_cost(answers: Sequence[Answer]) -> float:
    """Mean kFLOPs on abstained formulas."""
    spent = [a.cost for a in answers if a.abstained]
    return sum(spent) / len(spent) / 1e3 if spent else float("nan")


def selective(routes: dict[str, Plan], ladders: dict[TypeId, list[Rung]],
              args: argparse.Namespace) -> None:
    extra = (f" {'abst kFLOPs':>11s} {'floor kFLOPs':>12s} {'floor abst':>10s} {'same':>5s}"
             if args.floors else "")
    print(f"{'depth':>5s} {'words':>6s} {'system':>18s} {'coverage':>9s} "
          f"{'error answered [95% CI]':>27s} {'mean bound':>11s} {'error forced':>13s} "
          f"{'kFLOPs':>8s}" + extra)
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
            answers = run(routes[name], ladders, samples, delta, start)
            line = (f"{depth:5d} {words:6.1f} {system.replace('certificate', 'cert'):>18s} "
                    + summary(answers, samples))
            if args.floors:
                early = run(routes[name], ladders, samples, delta, start, floors=True)
                same = all(a.abstained == b.abstained and (a.abstained or a.value == b.value)
                           for a, b in zip(answers, early))
                line += (f" {abstained_cost(answers):11.1f} "
                         f"{sum(a.cost for a in early) / len(early) / 1e3:12.1f} "
                         f"{abstained_cost(early):10.1f} {str(same):>5s}")
            print(line, flush=True)


def frontier(route: Plan, ladders: dict[TypeId, list[Rung]], args: argparse.Namespace) -> None:
    """Coverage and compute of the predictive stopping rule as ``λ`` varies."""
    print(f"{'depth':>5s} {'δ':>5s} {'λ':>8s} {'coverage':>9s} {'error answered [95% CI]':>27s} "
          f"{'mean bound':>11s} {'error forced':>13s} {'kFLOPs':>8s}")
    for depth in args.depths:
        fit = FormulaDataset("validation", args.fit, depth, args.noise, args.seed + 1, args.xor)
        test = FormulaDataset("test", args.samples, depth, args.noise, args.seed, args.xor)
        samples = [test.sample(i) for i in range(len(test))]
        for delta in args.targets:
            runs = []
            for i in range(len(fit)):
                trace: list[State] = []
                answer = solve(route, ladders, fit.sample(i).text, delta, floors=True,
                               trace=trace)
                runs.append((trace, not answer.abstained, answer.cost))
            for lam in (0.0, *args.lambdas):
                stop = stopping_rule(runs, delta, lam) if lam > 0 else None
                answers = run(route, ladders, samples, delta, floors=True, stop=stop)
                print(f"{depth:5d} {delta:5g} {lam:8.1e} " + summary(answers, samples),
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
                chosen = None
                if certification_possible(args.audit, delta, args.alpha):
                    order = certification_order(
                        outcomes_many(route, ladders, fit, [delta / lam for lam in INFLATIONS]),
                        args.alpha)
                    stats: dict[int, tuple[int, int]] = {}
                    accepted = []
                    for i in order:
                        stats[i] = outcomes(route, ladders, check, delta / INFLATIONS[i],
                                            reject_above=delta, alpha=args.alpha)
                        if not certify([stats[i]], delta, args.alpha):
                            break
                        accepted.append(i)
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
    parser.add_argument("--band-slack", type=float, help="certified band slack for answer selection")
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
    parser.add_argument("--floors", action="store_true", help="compare early abstention")
    parser.add_argument("--frontier", action="store_true",
                        help="trace the predictive stopping rule for --account")
    parser.add_argument("--fit", type=int, default=200, help="formulas to fit the rule")
    parser.add_argument("--lambdas", type=float, nargs="+",
                        default=[1e-8, 3e-8, 1e-7, 3e-7, 1e-6, 3e-6])
    parser.add_argument("--premises", action="store_true", help="test the premises of §21.8")
    args = parser.parse_args()

    routes = {}
    for name, (short_circuit, detection, decoding) in ACCOUNTS.items():
        route = plan_stable(library(args.reader, short_circuit, detection, decoding, args.band_slack),
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

    if args.frontier:
        frontier(routes[args.account], ladders, args)
    elif args.shift is None:
        selective(routes, ladders, args)
    else:
        shifted(routes[args.account], ladders, args)


if __name__ == "__main__":
    main()
