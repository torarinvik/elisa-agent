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
  optionally with credit for the format's error detection (§19).

Train the character reader with::

    uv run --extra vision python -m nca.modules.words --out checkpoints/words.pt
"""

from __future__ import annotations

import argparse
from collections.abc import Callable, Sequence
from pathlib import Path

import numpy as np
import torch
from torch import nn

from nca.abi import Contract, Manifest, seq_type
from nca.efficiency import network_flops
from nca.formulas import ALPHABET, ARITY, VOCABULARY, FormulaDataset, apply, labeled_words, parse
from nca.ladder import Decision
from nca.modules.symbols import BOOLEAN

FORMULA_TEXT = "text.formula.prefix.v1"
"""``str``: words separated by single spaces."""

NOISY_WORD = "text.word.noisy.v1"
"""``str`` of lowercase letters."""

WORD_DISTRIBUTION = "logic.word.distribution.v1"
"""Tuple of probabilities over ``VOCABULARY``."""

READER = Contract((NOISY_WORD,), WORD_DISTRIBUTION)

ARITY_DECISION: tuple[tuple[int, ...], ...] = tuple(
    tuple(c for c, a in enumerate(ARITY) if a == arity) for arity in sorted(set(ARITY)))
"""The grouped decision a parser needs of every word: its arity."""

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

    Its ``floor`` (§22.3) bounds every account refinement can still reach
    from the words whose readings are fixed: the smaller of their full and
    arity risks (certificate account), their full risks (static account), or ``min(S / 2, e₂)`` over them
    (detection accounts, ``NCA.detection_account_mono``).
    """

    def __init__(self, short_circuit: bool = True, detection: str = "none") -> None:
        assert detection in DETECTION
        self.short_circuit = short_circuit
        self.detection = detection
        self.manifest = Manifest("nca.logic.formula-evaluator", "1.0.0",
                                 Contract((seq_type(WORD_DISTRIBUTION),), BOOLEAN))

    @staticmethod
    def words(readings: Sequence[Sequence[float]]) -> list[str]:
        return [VOCABULARY[int(np.argmax(r))] for r in readings]

    def invoke(self, readings: Sequence[Sequence[float]]) -> bool | None:
        words = self.words(readings)
        children = parse([ARITY[VOCABULARY.index(w)] for w in words])
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

    def certificate(self, readings: Sequence[Sequence[float]],
                    risk: Callable[[int, Decision], float]) -> dict[int, float] | None:
        words = self.words(readings)
        children = parse([ARITY[VOCABULARY.index(w)] for w in words])
        if children is None:
            return None
        n = len(words)
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
