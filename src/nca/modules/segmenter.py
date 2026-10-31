"""Glyph segmenter: splits an expression image into glyph images.

A classical algorithm, not a learned model. Ink columns are grouped into runs
(runs separated by fewer than ``MIN_GAP`` blank columns are merged), and each
run is cropped and centered on a 28x28 canvas by its center of ink mass, the
convention MNIST digits follow, so crops match the recognizers' training
distribution.

``alternatives`` offers further segmentations, likeliest first: each merges
one pair of adjacent runs, narrowest gap first. A consumer that cannot use a
segmentation (one it would read nothing of) lets the kernel try the next.
"""

from __future__ import annotations

from collections.abc import Iterator

import numpy as np
import torch

from nca.abi import Contract, Manifest, seq_type
from nca.modules.digit_recognizer import GLYPH

EXPRESSION_IMAGE = "image.expression.gray.v1"
"""``torch.Tensor`` of shape (H, W), float in [0, 1], white ink on black."""

INK = 0.1
MIN_GAP = 4
SIZE = 28


def column_runs(image: np.ndarray) -> list[tuple[int, int]]:
    """Half-open column ranges ``[start, end)`` containing ink."""
    columns = np.flatnonzero((image > INK).any(axis=0))
    runs: list[tuple[int, int]] = []
    for c in columns:
        if runs and c - runs[-1][1] < MIN_GAP:
            runs[-1] = (runs[-1][0], int(c) + 1)
        else:
            runs.append((int(c), int(c) + 1))
    return runs


def crop(image: np.ndarray, start: int, end: int) -> np.ndarray:
    strip = np.where(np.arange(image.shape[1])[None, :] < start, 0.0, image)
    strip = np.where(np.arange(image.shape[1])[None, :] >= end, 0.0, strip)
    ys, xs = np.indices(strip.shape)
    mass = strip.sum()
    cy = int(round((ys * strip).sum() / mass))
    cx = int(round((xs * strip).sum() / mass))
    padded = np.pad(strip, SIZE)
    y0, x0 = cy + SIZE - SIZE // 2, cx + SIZE - SIZE // 2
    return padded[y0:y0 + SIZE, x0:x0 + SIZE]


ALTERNATIVES = 3


class Segmenter:
    manifest = Manifest(
        "nca.segmenter", "1.0.0", Contract((EXPRESSION_IMAGE,), seq_type(GLYPH))
    )

    def invoke(self, image: torch.Tensor) -> list[torch.Tensor]:
        return next(self.alternatives(image))

    def alternatives(self, image: torch.Tensor) -> Iterator[list[torch.Tensor]]:
        array = image.numpy()
        runs = column_runs(array)

        def crops(segments: list[tuple[int, int]]) -> list[torch.Tensor]:
            return [torch.from_numpy(crop(array, s, e).astype(np.float32)) for s, e in segments]

        yield crops(runs)
        gaps = sorted(range(len(runs) - 1), key=lambda k: runs[k + 1][0] - runs[k][1])
        for k in gaps[:ALTERNATIVES]:
            yield crops([*runs[:k], (runs[k][0], runs[k + 1][1]), *runs[k + 2:]])
