"""Operator recognizer: classifies a glyph as ``+``, ``-``, ``*`` or not an operator.

Trained only on rendered operator glyphs and, as negatives, MNIST digits. It
never sees expressions, the digit recognizer, or arithmetic.

    uv run --extra vision python -m nca.modules.operator_recognizer
"""

from __future__ import annotations

import argparse
from pathlib import Path

import numpy as np
import torch
from torch import nn

from nca.abi import Contract, Manifest
from nca.expressions import OPERATORS, render_operator
from nca.modules.digit_recognizer import GLYPH, build_network as _digit_network

OPERATOR_DISTRIBUTION = "operator.distribution.v1"
"""Tuple of 4 probabilities over ``("+", "-", "*", None)``; ``None`` = not an operator."""

CLASSES = (*OPERATORS, None)
CONTRACT = Contract(inputs=(GLYPH,), output=OPERATOR_DISTRIBUTION)


def build_network() -> nn.Module:
    network = _digit_network()
    network[-1] = nn.Linear(network[-1].in_features, len(CLASSES))
    return network


class OperatorRecognizer:
    def __init__(self, network: nn.Module, version: str = "1.0.0") -> None:
        self.manifest = Manifest("nca.operator-recognizer", version, CONTRACT)
        self.network = network.eval()

    @classmethod
    def load(cls, path: Path, version: str = "1.0.0") -> OperatorRecognizer:
        network = build_network()
        network.load_state_dict(torch.load(path, map_location="cpu"))
        return cls(network, version)

    @torch.no_grad()
    def invoke(self, glyph: torch.Tensor) -> tuple[float, ...]:
        logits = self.network(glyph.reshape(1, 1, 28, 28))
        return tuple(torch.softmax(logits, dim=1)[0].tolist())


def make_dataset(mnist_images: np.ndarray, size: int, seed: int):
    """Balanced glyphs: each operator and "not an operator" with equal frequency."""
    rng = np.random.default_rng(seed)
    labels = rng.integers(len(CLASSES), size=size)
    images = np.stack([
        render_operator(OPERATORS[y], rng) if y < len(OPERATORS)
        else mnist_images[rng.integers(len(mnist_images))]
        for y in labels
    ]).astype(np.float32)
    return torch.utils.data.TensorDataset(
        torch.from_numpy(images)[:, None], torch.from_numpy(labels))


def train(data_dir: Path, out: Path, epochs: int, seed: int) -> float:
    """Train and return held-out accuracy (digits from the MNIST test set)."""
    from torchvision import datasets

    torch.manual_seed(seed)
    load = lambda train: datasets.MNIST(data_dir, train=train, download=True).data.numpy() / 255.0
    train_set = make_dataset(load(True), 40_000, seed)
    test_set = make_dataset(load(False), 10_000, seed + 1)

    network = build_network()
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
    torch.save(network.state_dict(), out)
    return accuracy


def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__.splitlines()[0])
    parser.add_argument("--data", type=Path, default=Path("data"))
    parser.add_argument("--out", type=Path, default=Path("checkpoints/operator.pt"))
    parser.add_argument("--epochs", type=int, default=2)
    parser.add_argument("--seed", type=int, default=0)
    args = parser.parse_args()
    print(f"test accuracy: {train(args.data, args.out, args.epochs, args.seed):.4f}")


if __name__ == "__main__":
    main()
