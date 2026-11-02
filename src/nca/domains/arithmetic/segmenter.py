"""Glyph segmenter: splits an expression image into glyph images.

A classical algorithm, not a learned model. Ink columns are grouped into runs
(runs separated by fewer than ``MIN_GAP`` blank columns are merged), and each
run is cropped and centered on a 28x28 canvas by its center of ink mass, the
convention MNIST digits follow, so crops match the recognizers' training
distribution.

The first segmentation cuts each run into as many glyphs as its width
holds, so glyphs that touch are separated. ``alternatives`` offers further
segmentations: the uncut runs, each merging one pair of adjacent runs,
narrowest gap first, then each splitting one run too wide for a glyph,
widest first. A consumer that cannot use a
segmentation (one it would read nothing of) lets the kernel try the next.
"""

from __future__ import annotations

from collections.abc import Iterator

import numpy as np
import torch

from nca.abi import Contract, Manifest, seq_type
from nca.domains.arithmetic import types
from nca.domains.arithmetic.digit_recognizer import GLYPH

EXPRESSION_IMAGE = types.EXPRESSION_IMAGE.type()

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
SPLITS = 2
SPLIT_WIDTH = 3 * SIZE // 2
PITCH = 20
"""The widest ink of one glyph: MNIST centers digits in a 20-pixel box."""


class Segmenter:
    manifest = Manifest(
        "nca.segmenter", "1.0.0", Contract((EXPRESSION_IMAGE,), seq_type(GLYPH)),
        effects=frozenset())

    def invoke(self, image: torch.Tensor) -> list[torch.Tensor]:
        return next(self.alternatives(image))

    def alternatives(self, image: torch.Tensor) -> Iterator[list[torch.Tensor]]:
        array = image.numpy()
        for segments in segmentations(array):
            yield [torch.from_numpy(crop(array, s, e).astype(np.float32)) for s, e in segments]


def pitched(image: np.ndarray, runs: list[tuple[int, int]]) -> list[tuple[int, int]]:
    """Each run cut into ``round(width / PITCH)`` parts at its faintest
    columns near equal spacing: touching glyphs share a run, and no glyph's
    ink is wider than ``PITCH``."""
    ink = image.sum(axis=0)
    spans = []
    for start, end in runs:
        parts = max(1, round((end - start) / PITCH))
        cuts = [start]
        for j in range(1, parts):
            target = start + (end - start) * j // parts
            low, high = max(cuts[-1] + 4, target - 6), min(end - 4, target + 7)
            cuts.append(low + int(np.argmin(ink[low:high])) if high > low else target)
        spans += list(zip(cuts, [*cuts[1:], end]))
    return spans


def segmentations(image: np.ndarray) -> Iterator[list[tuple[int, int]]]:
    """Column spans of the segmentations ``Segmenter.alternatives`` crops, in
    its order, without repeats: the runs cut by ``pitched``; the runs; each
    merging one pair of adjacent runs, narrowest gap first; each splitting
    one run wider than ``SPLIT_WIDTH`` at its faintest column in the middle
    third, widest first."""
    runs = column_runs(image)
    seen: list[list[tuple[int, int]]] = []

    def candidates() -> Iterator[list[tuple[int, int]]]:
        yield pitched(image, runs)
        yield runs
        gaps = sorted(range(len(runs) - 1), key=lambda k: runs[k + 1][0] - runs[k][1])
        for k in gaps[:ALTERNATIVES]:
            yield [*runs[:k], (runs[k][0], runs[k + 1][1]), *runs[k + 2:]]
        wide = sorted((k for k, (s, e) in enumerate(runs) if e - s > SPLIT_WIDTH),
                      key=lambda k: runs[k][0] - runs[k][1])
        ink = (image > INK).sum(axis=0)
        for k in wide[:SPLITS]:
            start, end = runs[k]
            third = (end - start) // 3
            cut = start + third + int(np.argmin(ink[start + third:end - third]))
            yield [*runs[:k], (start, cut), (cut, end), *runs[k + 1:]]

    for segments in candidates():
        if segments not in seen:
            seen.append(segments)
            yield segments
