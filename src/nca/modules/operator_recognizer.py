"""Operator and relation recognizers.

Each classifies a glyph as one of its symbols or as none of them. A
recognizer is trained only on rendered glyphs of its own symbols and, as
negatives, MNIST digits and the other symbol set's glyphs. It never sees
expressions, the digit recognizer, or arithmetic. With ``--normalized`` it is
trained on, and consumes, normalized glyphs (``nca.modules.normalizer``).

    uv run --extra vision python -m nca.modules.operator_recognizer --symbols operators
    uv run --extra vision python -m nca.modules.operator_recognizer --symbols relations
"""

from __future__ import annotations

import argparse
from dataclasses import dataclass
from pathlib import Path

import numpy as np
import torch
from torch import nn

from nca.abi import Contract, Manifest, TypeId
from nca.expressions import OPERATORS, RELATIONS, render_operator
from nca.modules.digit_recognizer import GLYPH, build_network as _digit_network

OPERATOR_DISTRIBUTION = "operator.distribution.v1"
"""Tuple of 4 probabilities over ``("+", "-", "*", None)``; ``None`` = not an operator."""

RELATION_DISTRIBUTION = "relation.distribution.v1"
"""Tuple of 4 probabilities over ``("<", ">", "=", None)``; ``None`` = not a relation."""


@dataclass(frozen=True)
class SymbolSet:
    name: str
    symbols: tuple[str, ...]
    output: TypeId
    module_id: str
    negatives: tuple[str, ...]
    """Rendered symbols used as "none of these" examples besides digits."""


OPERATOR_SET = SymbolSet("operators", OPERATORS, OPERATOR_DISTRIBUTION,
                         "nca.operator-recognizer", ())
RELATION_SET = SymbolSet("relations", RELATIONS, RELATION_DISTRIBUTION,
                         "nca.relation-recognizer", OPERATORS)
SYMBOL_SETS = {s.name: s for s in (OPERATOR_SET, RELATION_SET)}


def build_network(symbol_set: SymbolSet = OPERATOR_SET) -> nn.Module:
    network = _digit_network()
    network[-1] = nn.Linear(network[-1].in_features, len(symbol_set.symbols) + 1)
    return network


class SymbolRecognizer:
    def __init__(self, network: nn.Module, symbol_set: SymbolSet = OPERATOR_SET,
                 version: str = "1.0.0", normalized: bool = False) -> None:
        from nca.modules.normalizer import NORMALIZED_GLYPH

        self.symbol_set = symbol_set
        self.manifest = Manifest(symbol_set.module_id, version,
                                 Contract((NORMALIZED_GLYPH if normalized else GLYPH,),
                                          symbol_set.output))
        self.network = network.eval()
        self.normalized = normalized

    @classmethod
    def load(cls, path: Path, symbol_set: SymbolSet = OPERATOR_SET,
             version: str = "1.0.0") -> SymbolRecognizer:
        network = build_network(symbol_set)
        checkpoint = torch.load(path, map_location="cpu")
        normalized = checkpoint.pop("normalized", False)
        network.load_state_dict(checkpoint.get("state_dict", checkpoint))
        return cls(network, symbol_set, version, normalized)

    @torch.no_grad()
    def invoke(self, glyph: torch.Tensor) -> tuple[float, ...]:
        logits = self.network(glyph.reshape(1, 1, 28, 28))
        return tuple(torch.softmax(logits, dim=1)[0].tolist())



def make_dataset(mnist_images: np.ndarray, size: int, seed: int,
                 symbol_set: SymbolSet = OPERATOR_SET,
                 normalized: bool = False) -> torch.utils.data.TensorDataset:
    """Balanced glyphs: each symbol and "none of these" with equal frequency.

    Negatives are MNIST digits, plus rendered ``symbol_set.negatives`` glyphs
    for a third of them when that set is non-empty.
    """
    from nca.modules.normalizer import normalize_all

    rng = np.random.default_rng(seed)
    n = len(symbol_set.symbols)
    labels = rng.integers(n + 1, size=size)

    def negative() -> np.ndarray:
        if symbol_set.negatives and rng.random() < 1 / 3:
            others = symbol_set.negatives
            return render_operator(others[rng.integers(len(others))], rng)
        return mnist_images[rng.integers(len(mnist_images))]

    images = np.stack([
        render_operator(symbol_set.symbols[y], rng) if y < n else negative()
        for y in labels
    ]).astype(np.float32)
    if normalized:
        images = normalize_all(images)
    return torch.utils.data.TensorDataset(
        torch.from_numpy(images)[:, None], torch.from_numpy(labels))


def train(data_dir: Path, out: Path, epochs: int, seed: int,
          symbol_set: SymbolSet = OPERATOR_SET, normalized: bool = False) -> float:
    """Train and return held-out accuracy (digits from the MNIST test set)."""
    from torchvision import datasets

    torch.manual_seed(seed)

    def load(train: bool) -> np.ndarray:
        return datasets.MNIST(data_dir, train=train, download=True).data.numpy() / 255.0

    train_set = make_dataset(load(True), 40_000, seed, symbol_set, normalized)
    test_set = make_dataset(load(False), 10_000, seed + 1, symbol_set, normalized)

    network = build_network(symbol_set)
    optimizer = torch.optim.Adam(network.parameters(), lr=1e-3)
    loss_fn = nn.CrossEntropyLoss()
    for _ in range(epochs):
        network.train()
        for images, labels in torch.utils.data.DataLoader(train_set, batch_size=128, shuffle=True):
            optimizer.zero_grad()
            loss_fn(network(images), labels).backward()
            optimizer.step()

    network.eval()
    with torch.no_grad():
        images, labels = test_set.tensors
        accuracy = (network(images).argmax(dim=1) == labels).float().mean().item()
    out.parent.mkdir(parents=True, exist_ok=True)
    torch.save({"normalized": normalized, "state_dict": network.state_dict()}, out)
    return accuracy


def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__.splitlines()[0])
    parser.add_argument("--symbols", choices=sorted(SYMBOL_SETS), default="operators")
    parser.add_argument("--data", type=Path, default=Path("data"))
    parser.add_argument("--out", type=Path)
    parser.add_argument("--epochs", type=int, default=2)
    parser.add_argument("--seed", type=int, default=0)
    parser.add_argument("--normalized", action="store_true")
    args = parser.parse_args()
    symbol_set = SYMBOL_SETS[args.symbols]
    out = args.out or Path(f"checkpoints/{symbol_set.name}.pt")
    accuracy = train(args.data, out, args.epochs, args.seed, symbol_set, args.normalized)
    print(f"test accuracy: {accuracy:.4f}")


if __name__ == "__main__":
    main()
