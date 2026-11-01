"""Experts for noisy Boolean formulas (§18).

* ``Tokenizer``: formula text to its sequence of noisy words.
* ``EditReader`` and ``CharReader``: a noisy word to a distribution over the
  vocabulary. The edit reader is symbolic, ``p(w) ∝ exp(-d(x, w))`` with
  ``d`` the edit distance counting adjacent transpositions; the character
  reader is a small network on one-hot characters, trained on the noisy
  words of training formulas (with ``xor`` connectives, so it knows every
  word). Sharing a contract, they form one ladder.
* ``FormulaEvaluator``: word distributions to the formula's truth value. It
  declares a certificate (§18.5): every word's arity decision, and the full
  decision of the words its least-risk valid certificate evaluates, charged
  optionally with credit for the format's error detection (§19), or, when
  decoding, the posterior risk of the corrected arity sequence (§21).

Train the character reader with::

    uv run --extra vision python -m nca.modules.words --out checkpoints/words.pt
"""

from __future__ import annotations

import argparse
import math
from dataclasses import dataclass, field
from collections.abc import Callable, Sequence
from pathlib import Path
from functools import lru_cache

import numpy as np
import torch
from torch import nn

from nca.abi import Calls, Contract, Manifest, seq_type
from nca.efficiency import network_flops
from nca.formulas import (ALPHABET, ARITY, VOCABULARY, ArityPrior, Banded, CertifiedSplit, FormulaDataset, Split, apply, decode,
                          complete_prior, height_prior, labeled_words, parse, sequence_log_weight)
from nca.ladder import Decision, allocate_risk
from nca.native import load

_NATIVE = load("decoding")
from nca.modules.symbols import BOOLEAN

FORMULA_TEXT = "text.formula.prefix.v1"
"""``str``: words separated by single spaces."""

NOISY_WORD = "text.word.noisy.v1"
"""``str`` of lowercase letters."""

WORD_DISTRIBUTION = "logic.word.distribution.v1"
"""Tuple of probabilities over ``VOCABULARY``."""

FORMULA_LENGTH = "logic.formula.length.v1"
"""Positive integer count of words in a prefix formula."""

ARITY_PRIOR = "logic.arity.prior.v1"
"""Weighted arity automaton, including the formula syntax restriction."""


class CompleteTreePrior:
    """Independent length-to-prior expert for complete binary skeletons (§27).

    Unsupported lengths produce empty support, never a format-only fallback.
    """

    manifest = Manifest("nca.logic.complete-tree-prior", "1.0.0",
                        Contract((FORMULA_LENGTH,), ARITY_PRIOR))

    def __init__(self) -> None:
        self._empty = ArityPrior((0, 1, 2), np.full((1, 3), -1, dtype=np.int64),
                                 np.zeros((1, 3)), np.array([-np.inf]))

    def invoke(self, length: int) -> ArityPrior:
        prior = complete_prior(length)
        return self._empty if prior is None else prior


class HeightBoundedPrior:
    """Independent prior expert with an explicit edge-height budget (§27.7)."""

    def __init__(self, height: int) -> None:
        self.prior = height_prior(height)
        self.manifest = Manifest(f"nca.logic.height-prior.{height}", "1.0.0",
                                 Contract((FORMULA_LENGTH,), ARITY_PRIOR))

    def invoke(self, length: int) -> ArityPrior:
        if not isinstance(length, int) or length < 1:
            raise ValueError("length must be a positive integer")
        return self.prior


READER = Contract((NOISY_WORD,), WORD_DISTRIBUTION)

ARITY_DECISION: tuple[tuple[int, ...], ...] = tuple(
    tuple(c for c, a in enumerate(ARITY) if a == arity) for arity in sorted(set(ARITY)))
"""The grouped decision a parser needs of every word: its arity."""

ARITY_ORDER: tuple[int, ...] = tuple(sorted(set(ARITY)))
"""The arity of each entry of ``ARITY_DECISION``."""

DETECTION = ("none", "markov", "pairs")

MAX_LENGTH = 10
TYPICAL_LENGTH = 4
EDIT_OPERATIONS_PER_CELL = 5


class Tokenizer:
    manifest = Manifest("nca.logic.tokenizer", "1.0.0",
                        Contract((FORMULA_TEXT,), seq_type(NOISY_WORD)))

    def invoke(self, text: str) -> list[str]:
        return text.split(" ")


def edit_distance(a: str, b: str) -> int:
    """Edits (substitution, deletion, insertion, adjacent transposition)
    turning ``a`` into ``b``, each substring edited at most once."""
    d = [[i + j if i * j == 0 else 0 for j in range(len(b) + 1)] for i in range(len(a) + 1)]
    for i in range(1, len(a) + 1):
        for j in range(1, len(b) + 1):
            d[i][j] = min(d[i - 1][j] + 1, d[i][j - 1] + 1,
                          d[i - 1][j - 1] + (a[i - 1] != b[j - 1]))
            if i > 1 and j > 1 and a[i - 1] == b[j - 2] and a[i - 2] == b[j - 1]:
                d[i][j] = min(d[i][j], d[i - 2][j - 2] + 1)
    return d[len(a)][len(b)]


class EditReader:
    """``p(w) ∝ exp(-d(x, w))``. Its cost counts the dynamic program's cells
    for a word of typical length."""

    manifest = Manifest(
        "nca.logic.edit-reader", "1.0.0", READER,
        cost=EDIT_OPERATIONS_PER_CELL * (TYPICAL_LENGTH + 1) * sum(len(w) + 1 for w in VOCABULARY))

    def invoke(self, word: str) -> tuple[float, ...]:
        distances = torch.tensor([float(edit_distance(word, w)) for w in VOCABULARY])
        return tuple(torch.softmax(-distances, dim=0).tolist())


def encode(words: Sequence[str]) -> torch.Tensor:
    """One-hot characters, shape ``(n, MAX_LENGTH, 27)``; the last symbol pads."""
    codes = torch.full((len(words), MAX_LENGTH), len(ALPHABET))
    for n, word in enumerate(words):
        for i, ch in enumerate(word[:MAX_LENGTH]):
            codes[n, i] = ALPHABET.index(ch)
    return nn.functional.one_hot(codes, len(ALPHABET) + 1).float()


def build_network(hidden: int = 128) -> nn.Module:
    return nn.Sequential(
        nn.Flatten(), nn.Linear(MAX_LENGTH * (len(ALPHABET) + 1), hidden), nn.ReLU(),
        nn.Linear(hidden, hidden), nn.ReLU(), nn.Linear(hidden, len(VOCABULARY)),
    )


class CharReader:
    def __init__(self, network: nn.Module, module_id: str = "nca.logic.char-reader") -> None:
        self.network = network.eval()
        self.manifest = Manifest(module_id, "1.0.0", READER,
                                 cost=network_flops(network, (MAX_LENGTH, len(ALPHABET) + 1)))

    @classmethod
    def load(cls, path: Path, module_id: str = "nca.logic.char-reader") -> CharReader:
        checkpoint = torch.load(path, map_location="cpu")
        network = build_network(checkpoint["hidden"])
        network.load_state_dict(checkpoint["state_dict"])
        return cls(network, module_id)

    @torch.no_grad()
    def invoke(self, word: str) -> tuple[float, ...]:
        return tuple(torch.softmax(self.network(encode([word])), dim=1)[0].tolist())


def train(out: Path, noise: float, formulas: int, xor: float, epochs: int, hidden: int,
          seed: int) -> float:
    """Train on the words of depth-4 training formulas and return word accuracy
    on validation formulas."""
    torch.manual_seed(seed)
    words, labels = labeled_words(FormulaDataset("train", formulas, 4, noise, seed, xor))
    loader = torch.utils.data.DataLoader(
        torch.utils.data.TensorDataset(encode(words), torch.from_numpy(labels)),
        batch_size=256, shuffle=True)
    network = build_network(hidden)
    optimizer = torch.optim.Adam(network.parameters(), lr=1e-3)
    for _ in range(epochs):
        network.train()
        for x, y in loader:
            optimizer.zero_grad()
            nn.functional.cross_entropy(network(x), y).backward()
            optimizer.step()
    network.eval()
    test, test_labels = labeled_words(FormulaDataset("validation", 300, 4, noise, seed, xor))
    with torch.no_grad():
        predicted = network(encode(test)).argmax(dim=1)
        accuracy = (predicted == torch.from_numpy(test_labels)).float().mean().item()
    out.parent.mkdir(parents=True, exist_ok=True)
    torch.save({"hidden": hidden, "noise": noise, "state_dict": network.state_dict()}, out)
    return accuracy


@dataclass
class CorrectionState:
    """Per-solve cursor and priorities; never shared between formulas."""

    answer_band: CertifiedSplit | None = None
    answer_band_result: Banded | None = None
    answer_cursor: Split | None = None
    answer_readings: np.ndarray | None = None
    cursor: Split | None = None
    risk_band: CertifiedSplit | None = None
    prior_log_probs: np.ndarray | None = None
    priorities: list[float] | None = None
    steps: int = 0
    changed: tuple[int, ...] = ()
    revisions: tuple[int, ...] | None = None
    within: dict[tuple[int, int], float] = field(default_factory=dict)


class FormulaEvaluator:
    """The value of the most probable words, read as a prefix formula; ``None``
    if their arities form no formula.

    Its certificate is a risk account over the words. By default each word is
    charged its arity risk, plus the rest of its full-decision risk if the
    least-risk valid certificate evaluates it (§18.5). ``short_circuit=False``
    evaluates every word, the static account, for comparison.

    ``detection`` credits the format's error detection (§19): a single wrong
    arity breaks the parse, so only two arity failures can go unnoticed.
    ``"markov"`` charges half of each word's arity risk (no further premise);
    ``"pairs"`` charges the smaller of that and each word's share
    ``ρ_k (S − ρ_k) / 2`` of the pairs bound (premise: failures at different
    words are not positively correlated). Evaluated words are then charged
    only the risk of their decision restricted to their arity group.

    ``decode=True`` corrects instead of refusing (§21): the arity sequence is
    the most probable parseable one under the readings' arity masses, and each
    word the most probable class of its decoded arity group, so every reading
    is answered. The certificate decodes the same readings the same way, so the
    answer is exactly the formula its bound is about; it then charges the
    posterior probability ``R`` that this arity sequence is wrong, under the
    *calibrated* arity distributions and the format (premise P), shared among
    the words in proportion to their posterior arity risks, plus each evaluated
    word's restricted risk.

    An optional ``prior(length)`` provider supplies a stable, syntax-constrained
    ``ArityPrior`` over ``ARITY_ORDER`` for both selection and correction risk.
    Unsupported lengths have no certificate. This path uses full native prior
    decoding and cannot yet be combined with the format-only banded cursor.

    Its ``floor`` (§22.3) bounds every account refinement can still reach
    from the words whose readings are fixed: the smaller of their full and
    arity risks (certificate account), their full risks (static account), or
    ``min(S / 2, e₂)`` over them (detection accounts,
    ``NCA.detection_account_mono``). Decoding has only the trivial floor 0,
    since a later climb can change the decoded sequence.
    """

    def __init__(self, short_circuit: bool = True, detection: str = "none",
                 decode: bool = False, band_slack: float | None = None,
                 prior: Callable[[int], ArityPrior | None] | None = None) -> None:
        if band_slack is not None and not 0 < band_slack < 1:
            raise ValueError("band_slack must be strictly between zero and one")
        if prior is not None and (not decode or band_slack is not None):
            raise ValueError("prior requires decoding without banding")
        self.prior = prior
        self.band_slack = band_slack
        assert detection in DETECTION
        self.short_circuit = short_circuit
        self.detection = detection
        self.decode = decode
        self.manifest = Manifest("nca.logic.formula-evaluator", "1.0.0",
                                 Contract((seq_type(WORD_DISTRIBUTION),), BOOLEAN))

    def _arity_prior(self, length: int) -> ArityPrior | None:
        prior = None if self.prior is None else self.prior(length)
        if prior is not None and prior.alphabet != ARITY_ORDER:
            raise ValueError("evaluator prior must use ARITY_ORDER")
        return prior

    def words(self, readings: Sequence[Sequence[float]],
              state: CorrectionState | None = None) -> list[str]:
        """The words read: each word's most probable class, or, when decoding,
        the most probable class within its decoded arity group."""
        if not self.decode:
            return [VOCABULARY[int(np.argmax(r))] for r in readings]
        if state is None or self.prior is not None:
            masses = np.array([[sum(r[c] for c in group) for group in ARITY_DECISION]
                               for r in readings])
            with np.errstate(divide="ignore"):
                prior = None if self.prior is None else self._arity_prior(len(readings))
                if self.prior is None:
                    decoded = decode(np.log(masses), ARITY_ORDER)
                    arities = None if decoded is None else decoded.arities
                else:
                    arities = None if prior is None else prior.best(np.log(masses))
            if arities is None:
                return [VOCABULARY[int(np.argmax(r))] for r in readings]
            if state is not None:
                state.answer_readings = np.asarray(readings, dtype=np.float64).copy()
        elif self.band_slack is not None:
            selected = self._banded_words(readings, state)
            if selected is None:
                return [VOCABULARY[int(np.argmax(r))] for r in readings]
            arities = selected
        else:
            current = np.asarray(readings, dtype=np.float64)
            changed = (() if state.answer_readings is None else
                       np.flatnonzero(np.any(current != state.answer_readings, axis=1)))
            if state.answer_cursor is None:
                masses = np.array([[sum(r[c] for c in group) for group in ARITY_DECISION]
                                   for r in readings])
                with np.errstate(divide="ignore"):
                    state.answer_cursor = Split(np.log(masses), ARITY_ORDER)
            anchor = 0
            scored = None
            for k in changed:
                anchor = int(k)
                row = np.array([sum(readings[k][c] for c in g) for g in ARITY_DECISION])
                with np.errstate(divide="ignore"):
                    scored = state.answer_cursor.climb(anchor, np.log(row))
            state.answer_readings = current.copy()
            log_z, _ = (scored if scored is not None else
                        state.answer_cursor.scores(anchor, state.answer_cursor.log_probs[anchor]))
            if not math.isfinite(log_z):
                return [VOCABULARY[int(np.argmax(r))] for r in readings]
            _, arities = state.answer_cursor.best(anchor)
        native = getattr(_NATIVE, "grouped_argmax", None)
        if native is not None:
            scores = (state.answer_readings if state is not None else
                      np.asarray(readings, dtype=np.float64))
            assert scores is not None
            chosen = native(scores.reshape(-1), np.asarray(ARITY, dtype=np.int64),
                            np.asarray(arities, dtype=np.int64))
            return [VOCABULARY[c] for c in chosen]
        return [VOCABULARY[max(ARITY_DECISION[a], key=r.__getitem__)]
                for r, a in zip(readings, arities)]

    def _banded_words(self, readings: Sequence[Sequence[float]],
                      state: CorrectionState) -> tuple[int, ...] | None:
        current = np.asarray(readings, dtype=np.float64)
        changed = (() if state.answer_readings is None else
                   np.flatnonzero(np.any(current != state.answer_readings, axis=1)))
        if state.answer_band is None:
            masses = np.array([[sum(r[c] for c in g) for g in ARITY_DECISION]
                               for r in readings])
            totals = masses.sum(axis=1, keepdims=True)
            if np.any(totals <= 0):
                return None
            with np.errstate(divide="ignore"):
                weights = np.log(masses / totals)
            assert self.band_slack is not None
            state.answer_band = CertifiedSplit(weights, ARITY_ORDER, self.band_slack)
            state.answer_band_result = state.answer_band.result()
        else:
            for k in changed:
                row = np.array([sum(readings[k][c] for c in g) for g in ARITY_DECISION])
                total = row.sum()
                if total <= 0:
                    state.answer_band = None
                    state.answer_band_result = None
                    return None
                with np.errstate(divide="ignore"):
                    state.answer_band_result = state.answer_band.climb(int(k), np.log(row / total))
        state.answer_readings = current.copy()
        result = state.answer_band_result
        return None if result is None else result.arities

    def invoke(self, readings: Sequence[Sequence[float]]) -> bool | None:
        prior = self._arity_prior(len(readings))
        if self.prior is not None and prior is None:
            return None
        words = self.words(readings)
        arities = [ARITY[VOCABULARY.index(w)] for w in words]
        if prior is not None and not math.isfinite(prior.log_weight(arities)):
            return None
        children = parse(arities)
        if children is None:
            return None
        values = [False] * len(words)
        for k in reversed(range(len(words))):
            values[k] = apply(words[k], [values[c] for c in children[k]])
        return values[0]

    @staticmethod
    def evaluated(words: Sequence[str], children: Sequence[Sequence[int]],
                  full: Sequence[float], shape: Sequence[float]) -> set[int]:
        """Words the least-weight valid certificate evaluates (``NCA.bestCert``),
        with weight ``full[k]`` at evaluated words and ``shape[k]`` in skipped
        subtrees; a child is skipped only if its sibling's value absorbs the
        connective."""
        native = getattr(_NATIVE, "certificate", None)
        if native is not None:
            left = np.array([kids[0] if kids else -1 for kids in children], dtype=np.int64)
            right = np.array([kids[1] if len(kids) == 2 else -1 for kids in children],
                             dtype=np.int64)
            found = native(np.array([VOCABULARY.index(w) for w in words], dtype=np.int64),
                           left, right, np.asarray(full, dtype=np.float64),
                           np.asarray(shape, dtype=np.float64))
            return {k for k, chosen in enumerate(found) if chosen}
        return FormulaEvaluator.evaluated_reference(words, children, full, shape)

    @staticmethod
    def evaluated_reference(words: Sequence[str], children: Sequence[Sequence[int]],
                            full: Sequence[float], shape: Sequence[float]) -> set[int]:
        """Reference recurrence for the optional native certificate kernel."""
        n = len(words)
        values = [False] * n
        weight = [0.0] * n
        skipped = [0.0] * n
        choice = [""] * n
        for k in reversed(range(n)):
            kids = children[k]
            values[k] = apply(words[k], [values[c] for c in kids])
            skipped[k] = shape[k] + sum(skipped[c] for c in kids)
            weight[k] = full[k] + sum(weight[c] for c in kids)
            choice[k] = "both"
            if len(kids) == 2:
                absorbing = {"and": False, "or": True}.get(words[k])
                a, b = kids
                for side, kept, other in (("left", a, b), ("right", b, a)):
                    alternative = full[k] + weight[kept] + skipped[other]
                    if values[kept] == absorbing and alternative <= weight[k]:
                        weight[k], choice[k] = alternative, side
        found: set[int] = set()
        stack = [0]
        while stack:
            k = stack.pop()
            found.add(k)
            kids = children[k]
            stack += kids if choice[k] == "both" else [kids[choice[k] == "right"]]
        return found

    def corrected(self, words: Sequence[str], children: Sequence[Sequence[int]] | None,
                  risk: Callable[[int, Decision], float],
                  distribution: Callable[[int, Decision], torch.Tensor],
                  state: CorrectionState | None = None,
                  ) -> dict[int, float] | None:
        """The correction account (§21.5–21.6) of the decoded ``words``."""
        n = len(words)
        if self.band_slack is not None and state is None:
            state = CorrectionState()
        revision = getattr(distribution, "revision", None)
        versions = tuple(revision(k) for k in range(n)) if revision is not None else None
        invalidated = tuple(k for k in range(n) if state is None or versions is None
                            or state.revisions is None or versions[k] != state.revisions[k])
        cached = None
        if state is not None:
            if self.prior is not None:
                cached = state.prior_log_probs
            elif state.cursor is not None:
                cached = state.cursor.log_probs
        if cached is None or (self.prior is not None and versions is None):
            calibrated = torch.stack([torch.as_tensor(distribution(k, ARITY_DECISION))
                                      for k in range(n)]).double()
            log_probs = calibrated.clamp_min(1e-300).log().numpy()
        else:
            log_probs = cached.copy()
            for k in invalidated:
                row = torch.as_tensor(distribution(k, ARITY_DECISION)).double()
                log_probs[k] = row.clamp_min(1e-300).log().numpy()
        if self.band_slack is not None:
            # Row factors cancel from both the selected weight and normalizer.
            for k in invalidated:
                log_probs[k] -= np.logaddexp.reduce(log_probs[k])
        if state is not None:
            if self.prior is not None:
                state.prior_log_probs = log_probs
            state.revisions = versions
            for k in invalidated:
                for a in ARITY_ORDER:
                    state.within.pop((k, a), None)
        arities = [ARITY[VOCABULARY.index(w)] for w in words]
        if state is None:
            prior = None if self.prior is None else self._arity_prior(n)
            posterior = (decode(log_probs, ARITY_ORDER) if self.prior is None else
                         None if prior is None else prior.decode(log_probs))
            if posterior is None:
                return None
            sequence_risk = posterior.risk(log_probs, ARITY_ORDER, arities)
            priorities = [max(0.0, 1.0 - posterior.marginals[k, ARITY_ORDER.index(a)])
                          for k, a in enumerate(arities)]
        elif self.prior is not None:
            prior = self._arity_prior(n)
            if prior is None:
                return None
            state.steps += len(invalidated)
            if state.priorities is None or state.steps >= math.isqrt(n):
                posterior = prior.decode(log_probs)
                if posterior is None:
                    return None
                log_z = posterior.log_z
                state.priorities = [max(0.0, 1.0 - posterior.marginals[k, ARITY_ORDER.index(a)])
                                    for k, a in enumerate(arities)]
                state.steps = 0
            else:
                log_z = prior.log_normalizer(log_probs)
                if not math.isfinite(log_z):
                    return None
            weight = sequence_log_weight(log_probs, ARITY_ORDER, arities) + prior.log_weight(arities)
            sequence_risk = max(0.0, 1.0 - math.exp(min(0.0, weight - log_z)))
            priorities = state.priorities
        else:
            if state.cursor is None:
                if self.band_slack is None:
                    state.cursor = Split(log_probs, ARITY_ORDER)
                else:
                    state.risk_band = CertifiedSplit(log_probs, ARITY_ORDER, self.band_slack)
                    state.cursor = state.risk_band.split
            changed = np.flatnonzero(np.any(state.cursor.log_probs != log_probs, axis=1))
            state.changed = tuple(int(k) for k in changed)
            if state.risk_band is not None:
                for k in state.changed:
                    if state.risk_band.climb_normalizer(k, log_probs[k]) is None:
                        return None
                if (not state.changed and state.risk_band.log_upper is None
                        and state.risk_band.normalizer() is None):
                    return None
                state.cursor = state.risk_band.split
                sequence_risk = state.risk_band.sequence_risk(arities)
            else:
                scored = None
                for k in state.changed:
                    scored = state.cursor.climb(k, log_probs[k])
                anchor = state.changed[-1] if state.changed else 0
                log_z, _ = (scored if scored is not None else
                            state.cursor.scores(anchor, log_probs[anchor]))
                if not math.isfinite(log_z):
                    return None
                weight = sequence_log_weight(log_probs, ARITY_ORDER, arities)
                sequence_risk = float(-np.expm1(min(0.0, weight - log_z)))
            if state.priorities is None or state.steps >= math.isqrt(n):
                posterior = decode(log_probs, ARITY_ORDER)
                if posterior is None:
                    return None
                state.priorities = [max(0.0, 1.0 - posterior.marginals[k, ARITY_ORDER.index(a)])
                                    for k, a in enumerate(arities)]
                state.steps = 0
            priorities = state.priorities
            state.steps += len(state.changed)
        shares = allocate_risk(sequence_risk, priorities)
        if state is None:
            within = [risk(k, ARITY_DECISION[a]) for k, a in enumerate(arities)]
        else:
            for k, a in enumerate(arities):
                if (k, a) not in state.within:
                    state.within[k, a] = risk(k, ARITY_DECISION[a])
            within = [state.within[k, a] for k, a in enumerate(arities)]
        if children is None:
            native = getattr(_NATIVE, "certificate_words")
            found = native(np.array([VOCABULARY.index(w) for w in words], dtype=np.int64),
                           np.asarray(within, dtype=np.float64), np.zeros(n))
            if not found:
                return None
            kept = {k for k, chosen in enumerate(found) if chosen}
            if not self.short_circuit:
                kept = set(range(n))
        else:
            kept = (self.evaluated(words, children, within, [0.0] * n) if self.short_circuit
                    else set(range(n)))
        return {k: shares[k] + (within[k] if k in kept else 0.0) for k in range(n)}

    def certificate_session(self) -> Callable[..., dict[int, float] | None]:
        """Create certificate state owned by one solve, including its cursor."""
        state = CorrectionState()

        def account(readings: Sequence[Sequence[float]],
                    risk: Callable[[int, Decision], float],
                    distribution: Callable[[int, Decision], torch.Tensor],
                    ) -> dict[int, float] | None:
            return self.certificate(readings, risk, distribution, state)

        return account

    def certificate(self, readings: Sequence[Sequence[float]],
                    risk: Callable[[int, Decision], float],
                    distribution: Callable[[int, Decision], torch.Tensor],
                    state: CorrectionState | None = None,
                    ) -> dict[int, float] | None:
        words = self.words(readings, state)
        fused = self.decode and getattr(_NATIVE, "certificate_words", None) is not None
        children = None if fused else parse([ARITY[VOCABULARY.index(w)] for w in words])
        if children is None and not fused:
            return None
        n = len(words)
        if self.decode:
            return self.corrected(words, children, risk, distribution, state)
        assert children is not None
        arity = [risk(k, ARITY_DECISION) for k in range(n)]
        if self.detection == "none":
            full = [risk(k, None) for k in range(n)]
            kept = (self.evaluated(words, children, full, arity) if self.short_circuit
                    else set(range(n)))
            return {k: full[k] if k in kept else arity[k] for k in range(n)}
        within = [risk(k, ARITY_DECISION[ARITY[VOCABULARY.index(w)]])
                  for k, w in enumerate(words)]
        kept = (self.evaluated(words, children, within, [0.0] * n) if self.short_circuit
                else set(range(n)))
        total = sum(arity)
        shares = [r / 2 for r in arity]
        pairs = [r * (total - r) / 2 for r in arity]
        if self.detection == "pairs" and sum(pairs) < sum(shares):
            shares = pairs
        return {k: shares[k] + (within[k] if k in kept else 0.0) for k in range(n)}

    def floor(self, readings: Sequence[Sequence[float]], risk: Callable[[int, Decision], float],
              fixed: frozenset[int]) -> float:
        if self.decode:
            return 0.0
        if self.detection == "none":
            if not self.short_circuit:
                return sum(risk(k, None) for k in fixed)
            # A word is charged its full or its arity risk; under separately
            # fitted temperatures either may be the smaller (§18.3).
            return sum(min(risk(k, None), risk(k, ARITY_DECISION)) for k in fixed)
        arity = [risk(k, ARITY_DECISION) for k in fixed]
        total = sum(arity)
        markov = total / 2
        if self.detection == "markov":
            return markov
        return min(markov, (total * total - sum(r * r for r in arity)) / 2)


class PriorFormulaEvaluator(FormulaEvaluator):
    """Formula evaluator with a planner-filled length-to-prior slot (§27.3)."""

    def __init__(self, short_circuit: bool = True) -> None:
        super().__init__(short_circuit=short_circuit, decode=True)
        self.manifest = Manifest("nca.logic.prior-formula-evaluator", "1.0.0",
            Contract((seq_type(WORD_DISTRIBUTION),), BOOLEAN,
                     (((FORMULA_LENGTH,), ARITY_PRIOR),)), calls=(Calls(fixed=1),))

    def bind_slots(self, prior: Callable[[int], ArityPrior]) -> FormulaEvaluator:
        # Binding is local to one solve/invocation; the length is constant in it.
        return FormulaEvaluator(self.short_circuit, decode=True,
                                prior=lru_cache(maxsize=32)(prior))

    def invoke(self, prior: Callable[[int], ArityPrior],
               readings: Sequence[Sequence[float]]) -> bool | None:
        return self.bind_slots(prior).invoke(readings)


def main() -> None:
    parser = argparse.ArgumentParser(description="Train the character reader.")
    parser.add_argument("--out", type=Path, default=Path("checkpoints/words.pt"))
    parser.add_argument("--noise", type=float, default=0.1)
    parser.add_argument("--formulas", type=int, default=6000)
    parser.add_argument("--xor", type=float, default=0.25)
    parser.add_argument("--epochs", type=int, default=5)
    parser.add_argument("--hidden", type=int, default=128)
    parser.add_argument("--seed", type=int, default=0)
    args = parser.parse_args()
    accuracy = train(args.out, args.noise, args.formulas, args.xor, args.epochs, args.hidden,
                     args.seed)
    print(f"word accuracy on validation formulas: {accuracy:.4f}")


if __name__ == "__main__":
    main()
