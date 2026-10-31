"""Monolithic baseline: one CNN trained end to end from expression image to value.

The comparison point required by the architecture's add-and-freeze protocol:
a modular system must beat this on ``test_unseen`` to show compositional gain.
Test splits are also evaluated in the ``hard`` style, a shift neither system
was trained on.
``--task arithmetic`` classifies ``a op b`` by value; ``--task mixed``
classifies ``a op b rel c`` as true or false.

    uv run --extra vision python -m nca.baseline --epochs 5
"""

from __future__ import annotations

import argparse
from pathlib import Path

import torch
from torch import nn

from nca.expressions import HEIGHT, MIXED_WIDTH, NUM_VALUES, SPLITS, WIDTH, ExpressionDataset

TASKS = {"arithmetic": (WIDTH, NUM_VALUES), "mixed": (MIXED_WIDTH, 2)}


def build_network(width: int = WIDTH, classes: int = NUM_VALUES) -> nn.Module:
    return nn.Sequential(
        nn.Conv2d(1, 32, 3, padding=1), nn.ReLU(), nn.MaxPool2d(2),
        nn.Conv2d(32, 64, 3, padding=1), nn.ReLU(), nn.MaxPool2d(2),
        nn.Conv2d(64, 128, 3, padding=1), nn.ReLU(), nn.MaxPool2d(2),
        nn.Flatten(),
        nn.Linear(128 * (HEIGHT // 8) * (width // 8), 256), nn.ReLU(),
        nn.Linear(256, classes),
    )


@torch.no_grad()
def accuracy(network: nn.Module, dataset: ExpressionDataset, device: str) -> float:
    network.eval()
    correct = 0
    for images, values in torch.utils.data.DataLoader(dataset, batch_size=500):
        predicted = network(images.to(device)).argmax(dim=1).cpu()
        correct += (predicted == values).sum().item()
    return correct / len(dataset)


def train(data_dir: Path, out: Path, epochs: int, train_size: int, test_size: int,
          seed: int, task: str = "arithmetic") -> dict[str, float]:
    """Train the baseline and return accuracy on every split, and on the test
splits in the hard style."""
    torch.manual_seed(seed)
    device = "mps" if torch.backends.mps.is_available() else "cpu"
    splits = {
        split: ExpressionDataset(split, train_size if split == "train" else test_size,
                                 data_dir, seed, mixed=task == "mixed")
        for split in SPLITS
    }
    loader = torch.utils.data.DataLoader(splits["train"], batch_size=128, shuffle=True)
    network = build_network(*TASKS[task]).to(device)
    optimizer = torch.optim.Adam(network.parameters(), lr=1e-3)
    loss_fn = nn.CrossEntropyLoss()
    for _ in range(epochs):
        network.train()
        for images, values in loader:
            optimizer.zero_grad()
            loss_fn(network(images.to(device)), values.to(device)).backward()
            optimizer.step()
    out.parent.mkdir(parents=True, exist_ok=True)
    torch.save(network.state_dict(), out)
    results = {split: accuracy(network, dataset, device) for split, dataset in splits.items()}
    for split in ("test", "test_unseen"):
        hard = ExpressionDataset(split, test_size, data_dir, seed, mixed=task == "mixed",
                                 hard=True)
        results[f"{split} (hard)"] = accuracy(network, hard, device)
    return results


def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__.splitlines()[0])
    parser.add_argument("--data", type=Path, default=Path("data"))
    parser.add_argument("--out", type=Path, default=Path("checkpoints/baseline.pt"))
    parser.add_argument("--epochs", type=int, default=5)
    parser.add_argument("--train-size", type=int, default=60_000)
    parser.add_argument("--test-size", type=int, default=10_000)
    parser.add_argument("--seed", type=int, default=0)
    parser.add_argument("--task", choices=sorted(TASKS), default="arithmetic")
    args = parser.parse_args()
    results = train(args.data, args.out, args.epochs, args.train_size, args.test_size,
                    args.seed, args.task)
    for split, acc in results.items():
        print(f"{split:18s} accuracy: {acc:.4f}")


if __name__ == "__main__":
    main()
