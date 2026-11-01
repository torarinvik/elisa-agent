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
  decision of the words its least-risk valid certificate evaluates.

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

    ``short_circuit=False`` demands every word's full decision, the static
    certificate, for comparison.
    """

    def __init__(self, short_circuit: bool = True) -> None:
        self.short_circuit = short_circuit
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

    def certificate(self, readings: Sequence[Sequence[float]],
                    risk: Callable[[int, Decision], float]) -> dict[int, Decision] | None:
        """Least-risk certificate (``NCA.bestCert``): weights are full-decision
        risks at evaluated words and arity-decision risks in skipped subtrees;
        a child is skipped only if its sibling's value absorbs the connective."""
        words = self.words(readings)
        children = parse([ARITY[VOCABULARY.index(w)] for w in words])
        if children is None:
            return None
        if not self.short_circuit:
            return dict.fromkeys(range(len(words)))
        n = len(words)
        values = [False] * n
        weight = [0.0] * n
        shape = [0.0] * n
        choice = [""] * n
        for k in reversed(range(n)):
            kids = children[k]
            values[k] = apply(words[k], [values[c] for c in kids])
            shape[k] = risk(k, ARITY_DECISION) + sum(shape[c] for c in kids)
            weight[k] = risk(k, None) + sum(weight[c] for c in kids)
            choice[k] = "both"
            if len(kids) == 2:
                absorbing = {"and": False, "or": True}.get(words[k])
                a, b = kids
                for side, kept, skipped in (("left", a, b), ("right", b, a)):
                    alternative = risk(k, None) + weight[kept] + shape[skipped]
                    if values[kept] == absorbing and alternative <= weight[k]:
                        weight[k], choice[k] = alternative, side
        demanded: dict[int, Decision] = dict.fromkeys(range(n), ARITY_DECISION)
        stack = [0]
        while stack:
            k = stack.pop()
            demanded[k] = None
            kids = children[k]
            stack += kids if choice[k] == "both" else [kids[choice[k] == "right"]]
        return demanded


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
