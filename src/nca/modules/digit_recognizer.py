"""Handwritten digit recognizer (Experiment 1).

Consumes a single 28x28 grayscale glyph and emits a probability distribution
over the digits 0-9. It knows nothing about arithmetic or layout.

Train with::

    uv run --extra vision python -m nca.modules.digit_recognizer --out checkpoints/digit.pt
"""

from __future__ import annotations

import argparse
from pathlib import Path

import torch
from torch import nn

from nca.abi import Contract, Manifest

GLYPH = "image.glyph.gray28.v1"
"""``torch.Tensor`` of shape (28, 28), float in [0, 1], white ink on black."""

DIGIT_DISTRIBUTION = "digit.distribution.v1"
"""Tuple of 10 probabilities summing to 1, indexed by digit value."""

CONTRACT = Contract(inputs=(GLYPH,), output=DIGIT_DISTRIBUTION)


def build_network() -> nn.Module:
    return nn.Sequential(
        nn.Conv2d(1, 32, 3, padding=1), nn.ReLU(), nn.MaxPool2d(2),
        nn.Conv2d(32, 64, 3, padding=1), nn.ReLU(), nn.MaxPool2d(2),
        nn.Flatten(), nn.Linear(64 * 7 * 7, 128), nn.ReLU(), nn.Linear(128, 10),
    )


class DigitRecognizer:
    def __init__(self, network: nn.Module, version: str = "1.0.0") -> None:
        self.manifest = Manifest("nca.digit-recognizer", version, CONTRACT)
        self.network = network.eval()

    @classmethod
    def load(cls, path: Path, version: str = "1.0.0") -> DigitRecognizer:
        network = build_network()
        network.load_state_dict(torch.load(path, map_location="cpu"))
        return cls(network, version)

    @torch.no_grad()
    def invoke(self, glyph: torch.Tensor) -> tuple[float, ...]:
        logits = self.network(glyph.reshape(1, 1, 28, 28))
        return tuple(torch.softmax(logits, dim=1)[0].tolist())


def train(data_dir: Path, out: Path, epochs: int, seed: int) -> float:
    """Train on MNIST and return held-out test accuracy."""
    from torchvision import datasets, transforms

    torch.manual_seed(seed)
    to_tensor = transforms.ToTensor()
    train_set = datasets.MNIST(data_dir, train=True, download=True, transform=to_tensor)
    test_set = datasets.MNIST(data_dir, train=False, download=True, transform=to_tensor)
    train_loader = torch.utils.data.DataLoader(train_set, batch_size=128, shuffle=True)
    test_loader = torch.utils.data.DataLoader(test_set, batch_size=1000)

    network = build_network()
    optimizer = torch.optim.Adam(network.parameters(), lr=1e-3)
    loss_fn = nn.CrossEntropyLoss()
    for epoch in range(epochs):
        network.train()
        for images, labels in train_loader:
            optimizer.zero_grad()
            loss_fn(network(images), labels).backward()
            optimizer.step()

    network.eval()
    correct = 0
    with torch.no_grad():
        for images, labels in test_loader:
            correct += (network(images).argmax(dim=1) == labels).sum().item()
    out.parent.mkdir(parents=True, exist_ok=True)
    torch.save(network.state_dict(), out)
    return correct / len(test_set)


def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__.splitlines()[0])
    parser.add_argument("--data", type=Path, default=Path("data"))
    parser.add_argument("--out", type=Path, default=Path("checkpoints/digit.pt"))
    parser.add_argument("--epochs", type=int, default=2)
    parser.add_argument("--seed", type=int, default=0)
    args = parser.parse_args()
    accuracy = train(args.data, args.out, args.epochs, args.seed)
    print(f"test accuracy: {accuracy:.4f}")


if __name__ == "__main__":
    main()
