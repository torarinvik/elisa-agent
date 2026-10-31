"""Procedural handwritten-expression images ``a op b``.

Digits are MNIST glyphs; operators (``+``, ``-``, ``*``) are rendered as
jittered pen strokes, since MNIST has none. Glyphs are laid out left to right
with random spacing and vertical offset on a fixed canvas.

Compositional hold-out: digit pairs ``(a, b)`` with ``(a + 2 * b) % 7 == 0``
never appear in the ``train`` split, though every digit and operator does.
``test_unseen`` contains only those pairs, so a model that learned
composition rather than memorizing pairs should do as well there as on
``test``.
"""

from __future__ import annotations

from dataclasses import dataclass
from pathlib import Path

import numpy as np

HEIGHT, WIDTH, GLYPH = 32, 96, 28
OPERATORS = ("+", "-", "*")
SPLITS = ("train", "test", "test_unseen")
MIN_VALUE, MAX_VALUE = -9, 81
NUM_VALUES = MAX_VALUE - MIN_VALUE + 1

_STROKES = {
    "+": [((0.5, 0.15), (0.5, 0.85)), ((0.15, 0.5), (0.85, 0.5))],
    "-": [((0.15, 0.5), (0.85, 0.5))],
    "*": [((0.2, 0.2), (0.8, 0.8)), ((0.8, 0.2), (0.2, 0.8))],
}


def is_held_out(a: int, b: int) -> bool:
    return (a + 2 * b) % 7 == 0


def evaluate(a: int, op: str, b: int) -> int:
    return {"+": a + b, "-": a - b, "*": a * b}[op]


def render_operator(op: str, rng: np.random.Generator) -> np.ndarray:
    """A 28x28 operator glyph in [0, 1], white ink on black."""
    yy, xx = np.mgrid[0:GLYPH, 0:GLYPH] / (GLYPH - 1)
    angle = rng.normal(0.0, 0.12)
    scale = rng.uniform(0.7, 1.0)
    width = rng.uniform(0.035, 0.06)
    rot = np.array([[np.cos(angle), -np.sin(angle)], [np.sin(angle), np.cos(angle)]])
    image = np.zeros((GLYPH, GLYPH))
    for start, end in _STROKES[op]:
        p0, p1 = (
            rot @ ((np.array(pt) - 0.5) * scale) + 0.5 + rng.normal(0.0, 0.03, 2)
            for pt in (start, end)
        )
        d = p1 - p0
        t = np.clip(((xx - p0[0]) * d[0] + (yy - p0[1]) * d[1]) / (d @ d), 0.0, 1.0)
        dist = np.hypot(xx - p0[0] - t * d[0], yy - p0[1] - t * d[1])
        image = np.maximum(image, np.clip(1.5 - dist / width, 0.0, 1.0))
    return image


@dataclass(frozen=True)
class Sample:
    image: np.ndarray
    """(HEIGHT, WIDTH) float32 in [0, 1]."""
    tokens: tuple[str, str, str]
    value: int
    boxes: tuple[tuple[int, int], ...]
    """Top-left (x, y) of each glyph's 28x28 box, in token order."""


def compose(glyphs: list[np.ndarray], tokens: tuple[str, str, str],
            rng: np.random.Generator) -> Sample:
    gaps = rng.integers(1, WIDTH - GLYPH * len(glyphs), size=len(glyphs) + 1)
    gaps = gaps * (WIDTH - GLYPH * len(glyphs)) // gaps.sum()
    image = np.zeros((HEIGHT, WIDTH), dtype=np.float32)
    boxes = []
    x = int(gaps[0])
    for glyph, gap in zip(glyphs, gaps[1:]):
        y = int(rng.integers(0, HEIGHT - GLYPH + 1))
        image[y:y + GLYPH, x:x + GLYPH] = np.maximum(image[y:y + GLYPH, x:x + GLYPH], glyph)
        boxes.append((x, y))
        x += GLYPH + int(gap)
    a, op, b = tokens
    return Sample(image, tokens, evaluate(int(a), op, int(b)), tuple(boxes))


class ExpressionDataset:
    """``torch.utils.data.Dataset`` of (image[1, H, W], value - MIN_VALUE)."""

    def __init__(self, split: str, size: int, data_dir: Path = Path("data"),
                 seed: int = 0) -> None:
        from torchvision import datasets

        if split not in SPLITS:
            raise ValueError(f"unknown split {split!r}")
        mnist = datasets.MNIST(data_dir, train=split == "train", download=True)
        self.images = mnist.data.numpy().astype(np.float32) / 255.0
        labels = mnist.targets.numpy()
        self.by_digit = [np.flatnonzero(labels == d) for d in range(10)]
        self.pairs = [(a, b) for a in range(10) for b in range(10)
                      if is_held_out(a, b) == (split == "test_unseen")]
        self.size = size
        self.seed = seed + SPLITS.index(split) * 1_000_003

    def __len__(self) -> int:
        return self.size

    def sample(self, index: int) -> Sample:
        rng = np.random.default_rng((self.seed, index))
        a, b = self.pairs[rng.integers(len(self.pairs))]
        op = OPERATORS[rng.integers(len(OPERATORS))]
        glyphs = [
            self.images[rng.choice(self.by_digit[a])],
            render_operator(op, rng),
            self.images[rng.choice(self.by_digit[b])],
        ]
        return compose(glyphs, (str(a), op, str(b)), rng)

    def __getitem__(self, index: int):
        import torch

        s = self.sample(index)
        return torch.from_numpy(s.image)[None], s.value - MIN_VALUE
