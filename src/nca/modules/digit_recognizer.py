"""Handwritten digit recognizer (Experiment 1).

Consumes a single 28x28 grayscale glyph and emits a probability distribution
over the digits 0-9. It knows nothing about arithmetic or layout.

Several independently trained implementations share the contract: the
architecture (``cnn`` or ``mlp``) and the half of the MNIST training set used
(``all``, ``first`` or ``second``) are training options. With ``--normalized``
the recognizer is trained on, and consumes, normalized glyphs
(``nca.modules.normalizer``). Train with::

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


def build_network(arch: str = "cnn") -> nn.Module:
    if arch == "mlp":
        return nn.Sequential(
            nn.Flatten(), nn.Linear(28 * 28, 256), nn.ReLU(),
            nn.Linear(256, 128), nn.ReLU(), nn.Linear(128, 10),
        )
    return nn.Sequential(
        nn.Conv2d(1, 32, 3, padding=1), nn.ReLU(), nn.MaxPool2d(2),
        nn.Conv2d(32, 64, 3, padding=1), nn.ReLU(), nn.MaxPool2d(2),
        nn.Flatten(), nn.Linear(64 * 7 * 7, 128), nn.ReLU(), nn.Linear(128, 10),
    )


ARCHITECTURES = ("cnn", "mlp")
SUBSETS = ("all", "first", "second")


class DigitRecognizer:
    def __init__(self, network: nn.Module, version: str = "1.0.0",
                 normalized: bool = False) -> None:
        from nca.modules.normalizer import NORMALIZED_GLYPH

        contract = Contract((NORMALIZED_GLYPH,), DIGIT_DISTRIBUTION) if normalized else CONTRACT
        self.manifest = Manifest("nca.digit-recognizer", version, contract)
        self.network = network.eval()
        self.normalized = normalized

    @classmethod
    def load(cls, path: Path, version: str = "1.0.0") -> DigitRecognizer:
        checkpoint = torch.load(path, map_location="cpu")
        network = build_network(checkpoint["arch"])
        network.load_state_dict(checkpoint["state_dict"])
        return cls(network, version, checkpoint.get("normalized", False))

    @torch.no_grad()
    def invoke(self, glyph: torch.Tensor) -> tuple[float, ...]:
        logits = self.network(glyph.reshape(1, 1, 28, 28))
        return tuple(torch.softmax(logits, dim=1)[0].tolist())


def train(data_dir: Path, out: Path, epochs: int, seed: int, arch: str = "cnn",
          subset: str = "all", normalized: bool = False) -> float:
    """Train on MNIST (or one half of its training set) and return test accuracy."""
    from torchvision import datasets

    from nca.modules.normalizer import normalize_all

    torch.manual_seed(seed)

    def load(train: bool) -> torch.utils.data.TensorDataset:
        mnist = datasets.MNIST(data_dir, train=train, download=True)
        images = mnist.data.numpy() / 255.0
        if normalized:
            images = normalize_all(images)
        return torch.utils.data.TensorDataset(
            torch.from_numpy(images).float()[:, None], mnist.targets)

    train_set, test_set = load(True), load(False)
    if subset != "all":
        half = len(train_set) // 2
        indices = range(half) if subset == "first" else range(half, len(train_set))
        train_set = torch.utils.data.Subset(train_set, indices)
    train_loader = torch.utils.data.DataLoader(train_set, batch_size=128, shuffle=True)
    test_loader = torch.utils.data.DataLoader(test_set, batch_size=1000)

    network = build_network(arch)
    optimizer = torch.optim.Adam(network.parameters(), lr=1e-3)
    loss_fn = nn.CrossEntropyLoss()
    for _ in range(epochs):
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
    torch.save({"arch": arch, "normalized": normalized, "state_dict": network.state_dict()}, out)
    return correct / len(test_set)


def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__.splitlines()[0])
    parser.add_argument("--data", type=Path, default=Path("data"))
    parser.add_argument("--out", type=Path, default=Path("checkpoints/digit.pt"))
    parser.add_argument("--epochs", type=int, default=2)
    parser.add_argument("--seed", type=int, default=0)
    parser.add_argument("--arch", choices=ARCHITECTURES, default="cnn")
    parser.add_argument("--subset", choices=SUBSETS, default="all")
    parser.add_argument("--normalized", action="store_true")
    args = parser.parse_args()
    accuracy = train(args.data, args.out, args.epochs, args.seed, args.arch, args.subset,
                     args.normalized)
    print(f"test accuracy: {accuracy:.4f}")


if __name__ == "__main__":
    main()
