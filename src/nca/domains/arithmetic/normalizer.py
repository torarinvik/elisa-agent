"""Glyph normalizer: removes size and stroke-width variation before recognition.

A classical module. The ink bounding box is scaled to fit ``BOX`` pixels and
centered, then strokes are thickened (3x3 max) or thinned (3x3 min) until the
ink fraction lies in ``[LOW, HIGH]``. Recognizers trained on normalized glyphs
consume ``NORMALIZED_GLYPH``. For styles the normalizer undoes, the shift the
recognizer sees is removed; in general it is at most the mass of glyphs it
fails to undo (``lean/NCA/Normalize.lean``).
"""

from __future__ import annotations

import numpy as np
import torch

from nca.abi import Contract, Manifest
from nca.domains.arithmetic.digit_recognizer import GLYPH

NORMALIZED_GLYPH = "image.glyph.normalized28.v1"
"""``torch.Tensor`` of shape (28, 28) in [0, 1]: a glyph after ``normalize``."""

SIZE = 28
BOX = 20
INK = 0.3
LOW, HIGH = 0.10, 0.21
STEPS = 3


def _filter(image: np.ndarray, reduce: np.ufunc) -> np.ndarray:
    padded = np.pad(image, 1)
    return reduce.reduce([padded[dy:dy + SIZE, dx:dx + SIZE]
                          for dy in range(3) for dx in range(3)])


def normalize(image: np.ndarray) -> np.ndarray:
    rows, cols = np.nonzero(image > INK)
    if len(rows) == 0:
        return image.astype(np.float32)
    crop = image[rows.min():rows.max() + 1, cols.min():cols.max() + 1]
    scale = BOX / max(crop.shape)
    height, width = (max(1, round(n * scale)) for n in crop.shape)
    resized = torch.nn.functional.interpolate(
        torch.from_numpy(crop.astype(np.float32))[None, None], size=(height, width),
        mode="bilinear", align_corners=False)[0, 0].numpy()
    out = np.zeros((SIZE, SIZE), dtype=np.float32)
    top, left = (SIZE - height) // 2, (SIZE - width) // 2
    out[top:top + height, left:left + width] = resized
    for _ in range(STEPS):
        ink = (out > INK).mean()
        if ink < LOW:
            out = _filter(out, np.maximum)
        elif ink > HIGH:
            out = _filter(out, np.minimum)
        else:
            break
    return out


def normalize_all(images: np.ndarray) -> np.ndarray:
    return np.stack([normalize(image) for image in images])


class GlyphNormalizer:
    manifest = Manifest("nca.glyph-normalizer", "1.0.0", Contract((GLYPH,), NORMALIZED_GLYPH))

    def invoke(self, glyph: torch.Tensor) -> torch.Tensor:
        return torch.from_numpy(normalize(glyph.numpy()))
