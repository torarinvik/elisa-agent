import numpy as np
import pytest

from nca.expressions import (
    GLYPH, HEIGHT, OPERATORS, WIDTH, compose, evaluate, is_held_out, render_operator,
)


def test_every_digit_and_operand_position_seen_in_training():
    train = [(a, b) for a in range(10) for b in range(10) if not is_held_out(a, b)]
    assert {a for a, _ in train} == set(range(10))
    assert {b for _, b in train} == set(range(10))
    assert len(train) < 100


@pytest.mark.parametrize("op", OPERATORS)
def test_operator_glyph_has_ink(op):
    glyph = render_operator(op, np.random.default_rng(0))
    assert glyph.shape == (GLYPH, GLYPH)
    assert 0.0 <= glyph.min() and glyph.max() <= 1.0
    assert glyph.sum() > 20


def test_compose_places_glyphs_without_overlap():
    rng = np.random.default_rng(1)
    for _ in range(100):
        glyphs = [np.ones((GLYPH, GLYPH))] * 3
        sample = compose(glyphs, ("7", "*", "8"), rng)
        assert sample.image.shape == (HEIGHT, WIDTH)
        assert sample.value == evaluate(7, "*", 8) == 56
        xs = [x for x, _ in sample.boxes]
        assert all(b - a >= GLYPH for a, b in zip(xs, xs[1:]))
        assert xs[-1] + GLYPH <= WIDTH
        assert sample.image.sum() == 3 * GLYPH * GLYPH
