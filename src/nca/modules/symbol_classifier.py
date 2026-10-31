"""Glyph encoder and symbol classifier: a two-module alternative symbol reader.

The encoder maps a glyph to a shared embedding; the classifier maps an
embedding to a distribution over the 13 arithmetic symbols. They are trained
jointly but installed as separate modules, so the classifier can be installed
before any encoder exists. It is then dormant: its input type is unavailable,
so no plan can use it. Installing the encoder later activates it, which is
the routing conflict studied by ``nca.accumulation --scenario conflict``.

    uv run --extra vision python -m nca.modules.symbol_classifier
"""

from __future__ import annotations

import argparse
from pathlib import Path

import numpy as np
import torch
from torch import nn

from nca.abi import Contract, Manifest
from nca.expressions import OPERATORS, render_operator
from nca.modules.digit_recognizer import GLYPH
from nca.modules.symbols import SYMBOL_DISTRIBUTION

GLYPH_EMBEDDING = "glyph.embedding.v1"
"""``torch.Tensor`` of shape (128,) from ``nca.glyph-encoder`` version 1."""

SYMBOLS = (*"0123456789", *OPERATORS)


def build_encoder() -> nn.Module:
    return nn.Sequential(
        nn.Conv2d(1, 32, 3, padding=1), nn.ReLU(), nn.MaxPool2d(2),
        nn.Conv2d(32, 64, 3, padding=1), nn.ReLU(), nn.MaxPool2d(2),
        nn.Flatten(), nn.Linear(64 * 7 * 7, 128), nn.ReLU(),
    )


def build_classifier() -> nn.Module:
    return nn.Linear(128, len(SYMBOLS))


class GlyphEncoder:
    manifest = Manifest("nca.glyph-encoder", "1.0.0", Contract((GLYPH,), GLYPH_EMBEDDING))

    def __init__(self, network: nn.Module) -> None:
        self.network = network.eval()

    @torch.no_grad()
    def invoke(self, glyph: torch.Tensor) -> torch.Tensor:
        return self.network(glyph.reshape(1, 1, 28, 28))[0]


class SymbolClassifier:
    manifest = Manifest("nca.symbol-classifier", "1.0.0",
                        Contract((GLYPH_EMBEDDING,), SYMBOL_DISTRIBUTION))

    def __init__(self, network: nn.Module) -> None:
        self.network = network.eval()

    @torch.no_grad()
    def invoke(self, embedding: torch.Tensor) -> dict[str, float]:
        probabilities = torch.softmax(self.network(embedding), dim=0).tolist()
        return dict(zip(SYMBOLS, probabilities))


def load(path: Path) -> tuple[GlyphEncoder, SymbolClassifier]:
    state = torch.load(path, map_location="cpu")
    encoder, classifier = build_encoder(), build_classifier()
    encoder.load_state_dict(state["encoder"])
    classifier.load_state_dict(state["classifier"])
    return GlyphEncoder(encoder), SymbolClassifier(classifier)


def make_dataset(mnist_images: np.ndarray, mnist_labels: np.ndarray, size: int, seed: int):
    """Digits and operators in proportion 10:3, as in a uniform symbol draw."""
    rng = np.random.default_rng(seed)
    labels = rng.integers(len(SYMBOLS), size=size)
    by_digit = [np.flatnonzero(mnist_labels == d) for d in range(10)]
    images = np.stack([
        mnist_images[rng.choice(by_digit[y])] if y < 10
        else render_operator(OPERATORS[y - 10], rng)
        for y in labels
    ]).astype(np.float32)
    return torch.utils.data.TensorDataset(
        torch.from_numpy(images)[:, None], torch.from_numpy(labels))


def train(data_dir: Path, out: Path, epochs: int, seed: int) -> float:
    """Train encoder and classifier jointly; return held-out symbol accuracy."""
    from torchvision import datasets

    torch.manual_seed(seed)
    mnist = {t: datasets.MNIST(data_dir, train=t, download=True) for t in (True, False)}
    data = {t: (m.data.numpy() / 255.0, m.targets.numpy()) for t, m in mnist.items()}
    train_set = make_dataset(*data[True], 60_000, seed)
    test_set = make_dataset(*data[False], 10_000, seed + 1)

    network = nn.Sequential(build_encoder(), build_classifier())
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
    torch.save({"encoder": network[0].state_dict(), "classifier": network[1].state_dict()}, out)
    return accuracy


def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__.splitlines()[0])
    parser.add_argument("--data", type=Path, default=Path("data"))
    parser.add_argument("--out", type=Path, default=Path("checkpoints/symbol_classifier.pt"))
    parser.add_argument("--epochs", type=int, default=1)
    parser.add_argument("--seed", type=int, default=0)
    args = parser.parse_args()
    print(f"test accuracy: {train(args.data, args.out, args.epochs, args.seed):.4f}")


if __name__ == "__main__":
    main()
