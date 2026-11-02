"""Glyph segmentation by connected components, a second segmenter.

``Segmenter`` cuts an expression image into columns of ink. This one finds
8-connected components of ink pixels instead, merges components whose
column spans mostly overlap (a glyph drawn in several strokes, or a digit
whose stroke breaks), and crops each glyph by its own pixels, so ink of a
neighbour that reaches into its columns is left out. It fails on different
images than ``Segmenter``, which makes it useful for checking routes that
use the other one.
"""

from __future__ import annotations

import numpy as np
import torch

from nca.abi import Contract, Manifest, seq_type
from nca.domains.arithmetic.digit_recognizer import GLYPH
from nca.domains.arithmetic.segmenter import EXPRESSION_IMAGE, INK, crop

OVERLAP = 0.5
"""Components are one glyph when their column spans share this fraction of
the narrower span."""


def components(mask: np.ndarray) -> list[list[tuple[int, int]]]:
    """The 8-connected components of ``mask``, as lists of (row, column)."""
    seen = np.zeros_like(mask, dtype=bool)
    found = []
    rows, columns = mask.shape
    for start in zip(*np.nonzero(mask)):
        if seen[start]:
            continue
        seen[start] = True
        stack, pixels = [start], []
        while stack:
            y, x = stack.pop()
            pixels.append((int(y), int(x)))
            for dy in (-1, 0, 1):
                for dx in (-1, 0, 1):
                    ny, nx = y + dy, x + dx
                    if 0 <= ny < rows and 0 <= nx < columns and mask[ny, nx] and not seen[ny, nx]:
                        seen[ny, nx] = True
                        stack.append((ny, nx))
        found.append(pixels)
    return found


def glyph_masks(image: np.ndarray) -> list[np.ndarray]:
    """One pixel mask per glyph, left to right."""
    groups: list[tuple[int, int, list[tuple[int, int]]]] = []
    for pixels in sorted(components(image > INK), key=lambda p: min(x for _, x in p)):
        start, end = min(x for _, x in pixels), max(x for _, x in pixels) + 1
        for k, (s, e, members) in enumerate(groups):
            shared = min(e, end) - max(s, start)
            if shared >= OVERLAP * min(e - s, end - start):
                groups[k] = (min(s, start), max(e, end), members + pixels)
                break
        else:
            groups.append((start, end, pixels))
    masks = []
    for _, _, pixels in sorted(groups, key=lambda g: g[0]):
        mask = np.zeros(image.shape, dtype=bool)
        mask[tuple(np.array(pixels).T)] = True
        masks.append(mask)
    return masks


class ComponentSegmenter:
    manifest = Manifest(
        "nca.component-segmenter", "1.0.0", Contract((EXPRESSION_IMAGE,), seq_type(GLYPH)),
        effects=frozenset())

    def invoke(self, image: torch.Tensor) -> list[torch.Tensor]:
        array = image.numpy()
        return [torch.from_numpy(crop(np.where(mask, array, 0.0), 0, array.shape[1])
                                 .astype(np.float32)) for mask in glyph_masks(array)]
