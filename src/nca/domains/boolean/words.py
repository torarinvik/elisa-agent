"""Experts for noisy Boolean formulas (§18).

* ``Tokenizer``: formula text to its sequence of noisy words.
* ``EditReader`` and ``CharReader``: a noisy word to a distribution over the
  vocabulary. The edit reader is symbolic, ``p(w) ∝ exp(-d(x, w))`` with
  ``d`` the edit distance counting adjacent transpositions; the character
  reader is a small network on one-hot characters, trained on the noisy
  words of training formulas (with ``xor`` connectives, so it knows every
  word). Sharing a contract, they form one ladder.
* ``FormulaEvaluator``: word distributions to the formula's truth value, a
  ``nca.prefix.PrefixEvaluator`` with the formula semantics. It declares a certificate (§18.5): every word's arity decision, and the full
  decision of the words its least-risk valid certificate evaluates, charged
  optionally with credit for the format's error detection (§19), or, when
  decoding, the posterior risk of the corrected arity sequence (§21).

Train the character reader with::

    uv run --extra vision python -m nca.domains.boolean.words --out checkpoints/words.pt
"""

from __future__ import annotations

import argparse
from collections.abc import Callable, Sequence
from functools import lru_cache
from pathlib import Path

import numpy as np
import torch
from torch import nn

from nca.abi import Calls, Contract, Manifest, seq_type
from nca.cost import network_flops
from nca.domains.boolean.formulas import ALPHABET, ARITY, VOCABULARY, FormulaDataset, apply, labeled_words
from nca.modules.edit import EditDistanceReader
from nca.native import load
from nca.prefix import PrefixEvaluator, RankedVocabulary
from nca.priors import ArityPrior, complete_prior, height_prior

_KERNELS = load("kernels", "nca.domains.boolean")

BOOLEAN = "bool.v1"
"""``bool``: a truth value, the type every Boolean answer shares."""

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

FORMULA = RankedVocabulary(VOCABULARY, ARITY)
"""The words of a formula and their arities, the alphabet of its prefix format."""

ARITY_DECISION: tuple[tuple[int, ...], ...] = FORMULA.decision
"""The grouped decision a parser needs of every word: its arity."""

ARITY_ORDER: tuple[int, ...] = FORMULA.order
"""The arity of each entry of ``ARITY_DECISION``."""


MAX_LENGTH = 10
TYPICAL_LENGTH = 4


class Tokenizer:
    manifest = Manifest("nca.logic.tokenizer", "1.0.0",
                        Contract((FORMULA_TEXT,), seq_type(NOISY_WORD)))

    def invoke(self, text: str) -> list[str]:
        return text.split(" ")


class EditReader(EditDistanceReader):
    """The edit-distance reader over ``VOCABULARY`` (§18.1)."""

    def __init__(self) -> None:
        super().__init__(VOCABULARY, READER, "nca.logic.edit-reader",
                         typical_length=TYPICAL_LENGTH)


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


class FormulaEvaluator(PrefixEvaluator):
    """The truth value of the most probable words, read as a prefix formula
    (``nca.prefix.PrefixEvaluator`` over ``FORMULA``); ``None`` if their arities
    form no formula. Its certificate skips a child whose sibling's value absorbs
    ``and`` or ``or`` (§18.5)."""

    def __init__(self, short_circuit: bool = True, detection: str = "none",
                 decode: bool = False, band_slack: float | None = None,
                 prior: Callable[[int], ArityPrior | None] | None = None) -> None:
        super().__init__(FORMULA, apply,
                         Manifest("nca.logic.formula-evaluator", "1.0.0",
                                  Contract((seq_type(WORD_DISTRIBUTION),), BOOLEAN)),
                         evaluates=FormulaEvaluator.evaluated, short_circuit=short_circuit,
                         detection=detection, decode=decode, band_slack=band_slack, prior=prior)

    @staticmethod
    def evaluated(words: Sequence[str], children: Sequence[Sequence[int]],
                  full: Sequence[float], shape: Sequence[float]) -> set[int]:
        """Words the least-weight valid certificate evaluates (``NCA.bestCert``),
        with weight ``full[k]`` at evaluated words and ``shape[k]`` in skipped
        subtrees; a child is skipped only if its sibling's value absorbs the
        connective."""
        native = getattr(_KERNELS, "certificate", None)
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
