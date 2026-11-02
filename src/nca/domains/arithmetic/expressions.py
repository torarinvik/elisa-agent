"""Procedural handwritten-expression images ``a op b`` and ``a op b rel c``.

Digits are MNIST glyphs; arithmetic operators (``+``, ``-``, ``*``) and
relations (``<``, ``>``, ``=``) are rendered as jittered pen strokes, since
MNIST has none. A dataset draws operators from one of the two sets: the
arithmetic task has integer values, the comparison task boolean ones. The mixed task ``a op b rel c`` uses both
sets on a wider canvas and has boolean values. Glyphs are laid out left to
right with random spacing and vertical offset on a fixed canvas.

Compositional hold-out: digit pairs ``(a, b)`` with ``(a + 2 * b) % 7 == 0``
never appear in the ``train`` split, though every digit and operator does.
``test_unseen`` contains only those pairs, so a model that learned
composition rather than memorizing pairs should do as well there as on
``test``.

Digit images: ``train`` draws from the MNIST training set; ``validation``
from the first half of the MNIST test set; ``test`` and ``test_unseen`` from
its second half, so no digit image is shared between validation (used for
decisions such as route upgrades) and the reported test splits.

``operands`` lengthens arithmetic expressions to ``a op b op c ...`` with that
many single-digit operands on a canvas widened to fit; the first two operands
follow the split's pair policy and the rest are uniform.

``hard`` renders a shifted style for robustness tests: operators with three
times the usual jitter, and digits randomly thickened or thinned.

``part=(k, m)`` keeps only the split's images whose MNIST index is ``k`` modulo
``m``, so one split can be divided into disjoint parts, such as an audit drawn
from the deployment distribution and the evaluation set.
"""

from __future__ import annotations

from dataclasses import dataclass
from pathlib import Path
from typing import TYPE_CHECKING

import numpy as np

if TYPE_CHECKING:
    import torch

HEIGHT, WIDTH, GLYPH = 32, 96, 28
MIXED_WIDTH = 160
OPERATORS = ("+", "-", "*")
RELATIONS = ("<", ">", "=")
SPLITS = ("train", "test", "test_unseen", "validation")
MNIST_TEST_HALF = 5_000
MIN_VALUE, MAX_VALUE = -9, 81
NUM_VALUES = MAX_VALUE - MIN_VALUE + 1

_STROKES = {
    "+": [((0.5, 0.15), (0.5, 0.85)), ((0.15, 0.5), (0.85, 0.5))],
    "-": [((0.15, 0.5), (0.85, 0.5))],
    "*": [((0.2, 0.2), (0.8, 0.8)), ((0.8, 0.2), (0.2, 0.8))],
    "<": [((0.8, 0.2), (0.2, 0.5)), ((0.2, 0.5), (0.8, 0.8))],
    ">": [((0.2, 0.2), (0.8, 0.5)), ((0.8, 0.5), (0.2, 0.8))],
    "=": [((0.15, 0.35), (0.85, 0.35)), ((0.15, 0.65), (0.85, 0.65))],
}


def is_held_out(a: int, b: int) -> bool:
    return (a + 2 * b) % 7 == 0


def evaluate(a: int, op: str, b: int) -> int | bool:
    return {"+": a + b, "-": a - b, "*": a * b,
            "<": a < b, ">": a > b, "=": a == b}[op]


def value_of(tokens: tuple[str, ...]) -> int | bool:
    """Ground truth for ``digit ((op | rel) digit)*``.

    Sides between relations are evaluated with ``*`` binding tighter than
    ``+`` and ``-``. Without relations the value is that integer; otherwise
    it is whether every adjacent pair of sides satisfies its relation.
    """
    sides: list[int] = []
    relations: list[str] = []
    terms, signs = [int(tokens[0])], [1]
    for op, digit in zip(tokens[1::2], tokens[2::2]):
        if op in RELATIONS:
            sides.append(sum(s * t for s, t in zip(signs, terms)))
            relations.append(op)
            terms, signs = [int(digit)], [1]
        elif op == "*":
            terms[-1] *= int(digit)
        else:
            terms.append(int(digit))
            signs.append(1 if op == "+" else -1)
    sides.append(sum(s * t for s, t in zip(signs, terms)))
    if not relations:
        return sides[0]
    return all(evaluate(a, r, b) for a, r, b in zip(sides, relations, sides[1:]))


def render_operator(op: str, rng: np.random.Generator, jitter: float = 1.0) -> np.ndarray:
    """A 28x28 operator or relation glyph in [0, 1], white ink on black.

    ``jitter`` scales the random rotation, endpoint noise, and size variation.
    """
    yy, xx = np.mgrid[0:GLYPH, 0:GLYPH] / (GLYPH - 1)
    angle = rng.normal(0.0, 0.12 * jitter)
    scale = 1.0 - rng.uniform(0.0, min(0.3 * jitter, 0.6))
    width = rng.uniform(0.035, 0.06)
    rot = np.array([[np.cos(angle), -np.sin(angle)], [np.sin(angle), np.cos(angle)]])
    image = np.zeros((GLYPH, GLYPH))
    for start, end in _STROKES[op]:
        p0, p1 = (
            rot @ ((np.array(pt) - 0.5) * scale) + 0.5 + rng.normal(0.0, 0.03 * jitter, 2)
            for pt in (start, end)
        )
        d = p1 - p0
        t = np.clip(((xx - p0[0]) * d[0] + (yy - p0[1]) * d[1]) / (d @ d), 0.0, 1.0)
        dist = np.hypot(xx - p0[0] - t * d[0], yy - p0[1] - t * d[1])
        image = np.maximum(image, np.clip(1.5 - dist / width, 0.0, 1.0))
    return image


def restyle_digit(image: np.ndarray, rng: np.random.Generator) -> np.ndarray:
    """Thicken (3x3 max) or thin (3x3 min) a glyph's strokes, with equal chance."""
    padded = np.pad(image, 1)
    windows = np.stack([padded[dy:dy + GLYPH, dx:dx + GLYPH]
                        for dy in range(3) for dx in range(3)])
    return windows.max(axis=0) if rng.random() < 0.5 else windows.min(axis=0)


@dataclass(frozen=True)
class Sample:
    image: np.ndarray
    """(HEIGHT, width) float32 in [0, 1]."""
    tokens: tuple[str, ...]
    value: int | bool
    boxes: tuple[tuple[int, int], ...]
    """Top-left (x, y) of each glyph's 28x28 box, in token order."""


def compose(glyphs: list[np.ndarray], tokens: tuple[str, ...],
            rng: np.random.Generator, width: int = WIDTH) -> Sample:
    gaps = rng.integers(1, width - GLYPH * len(glyphs), size=len(glyphs) + 1)
    gaps = gaps * (width - GLYPH * len(glyphs)) // gaps.sum()
    image = np.zeros((HEIGHT, width), dtype=np.float32)
    boxes = []
    x = int(gaps[0])
    for glyph, gap in zip(glyphs, gaps[1:]):
        y = int(rng.integers(0, HEIGHT - GLYPH + 1))
        image[y:y + GLYPH, x:x + GLYPH] = np.maximum(image[y:y + GLYPH, x:x + GLYPH], glyph)
        boxes.append((x, y))
        x += GLYPH + int(gap)
    return Sample(image, tokens, value_of(tokens), tuple(boxes))


class ExpressionDataset:
    """``torch.utils.data.Dataset`` of (image[1, H, W], label).

    ``operators`` selects ``OPERATORS`` (arithmetic) or ``RELATIONS``
    (comparison) for ``a op b``; ``mixed`` instead draws ``a op b rel c`` with
    ``op`` from ``OPERATORS`` and ``rel`` from ``RELATIONS``. Labels are
    ``value - MIN_VALUE`` for integer values and ``int(value)`` for booleans.
    """

    def __init__(self, split: str, size: int, data_dir: Path = Path("data"),
                 seed: int = 0, operators: tuple[str, ...] = OPERATORS,
                 mixed: bool = False, hard: bool = False, operands: int = 2,
                 part: tuple[int, int] | None = None) -> None:
        from torchvision import datasets

        if split not in SPLITS:
            raise ValueError(f"unknown split {split!r}")
        mnist = datasets.MNIST(data_dir, train=split == "train", download=True)
        self.images = mnist.data.numpy().astype(np.float32) / 255.0
        labels = mnist.targets.numpy()
        pool = np.arange(len(labels))
        if split == "validation":
            pool = pool[:MNIST_TEST_HALF]
        elif split != "train":
            pool = pool[MNIST_TEST_HALF:]
        if part is not None:
            index, parts = part
            pool = pool[pool % parts == index]
        self.by_digit = [pool[labels[pool] == d] for d in range(10)]
        self.pairs = [(a, b) for a in range(10) for b in range(10)
                      if is_held_out(a, b) == (split == "test_unseen")]
        self.size = size
        self.operators = operators
        self.mixed = mixed
        self.hard = hard
        self.operands = operands
        glyphs = 2 * operands - 1
        self.width = MIXED_WIDTH if mixed else max(WIDTH, glyphs * (GLYPH + 4) + 4)
        self.seed = seed + SPLITS.index(split) * 1_000_003

    def __len__(self) -> int:
        return self.size

    def sample(self, index: int) -> Sample:
        rng = np.random.default_rng((self.seed, index))
        a, b = self.pairs[rng.integers(len(self.pairs))]
        if self.mixed:
            op = OPERATORS[rng.integers(len(OPERATORS))]
            rel = RELATIONS[rng.integers(len(RELATIONS))]
            c = int(rng.integers(10))
            tokens = (str(a), op, str(b), rel, str(c))
        else:
            op = self.operators[rng.integers(len(self.operators))]
            tokens = (str(a), op, str(b))
            for _ in range(self.operands - 2):
                tokens += (self.operators[rng.integers(len(self.operators))],
                           str(rng.integers(10)))
        glyphs = [
            self.images[rng.choice(self.by_digit[int(t)])] if t.isdigit()
            else render_operator(t, rng, 3.0 if self.hard else 1.0)
            for t in tokens
        ]
        if self.hard:
            glyphs = [restyle_digit(g, rng) if t.isdigit() else g
                      for g, t in zip(glyphs, tokens)]
        return compose(glyphs, tokens, rng, self.width)

    def __getitem__(self, index: int) -> tuple[torch.Tensor, int]:
        import torch

        s = self.sample(index)
        label = int(s.value) if isinstance(s.value, bool) else s.value - MIN_VALUE
        return torch.from_numpy(s.image)[None], label
