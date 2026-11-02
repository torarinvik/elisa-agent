import numpy as np
import pytest

pytest.importorskip("torch")

from nca.domains.arithmetic.normalizer import HIGH, LOW, normalize


def test_normalizer_removes_size_and_keeps_ink_in_range() -> None:
    from nca.domains.arithmetic.expressions import render_operator

    rng = np.random.default_rng(0)
    for _ in range(20):
        glyph = render_operator("+", rng)
        out = normalize(glyph)
        assert out.shape == (28, 28)
        assert LOW <= (out > 0.3).mean() <= HIGH
        rows, cols = np.nonzero(out > 0.3)
        assert max(rows.max() - rows.min(), cols.max() - cols.min()) + 1 >= 18


def test_normalizer_undoes_rescaling() -> None:
    image = np.zeros((28, 28))
    image[4:24, 13:15] = 1.0
    small = np.zeros((28, 28))
    small[9:19, 13:15] = 1.0
    assert np.abs(normalize(image) - normalize(small)).mean() < 0.05
