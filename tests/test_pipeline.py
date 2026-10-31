import numpy as np
import pytest

torch = pytest.importorskip("torch")

from nca.expressions import GLYPH, compose, render_operator
from nca.modules.digit_recognizer import DigitRecognizer, build_network as digit_net
from nca.modules.operator_recognizer import OperatorRecognizer, build_network as op_net
from nca.modules.segmenter import Segmenter, column_runs
from nca.modules.symbols import Evaluator, ExpressionParser, SymbolFuser
from nca.pipeline import build_registry, compose as compose_plan
from nca.planner import Apply, Map


def test_planner_composes_full_pipeline_with_map():
    registry = build_registry(DigitRecognizer(digit_net()), OperatorRecognizer(op_net()))
    graph = compose_plan(registry)
    assert isinstance(graph, Apply) and graph.module.manifest.module_id == "nca.evaluator"
    parser = graph.args[0]
    assert parser.module.manifest.module_id == "nca.expression-parser"
    mapped = parser.args[0]
    assert isinstance(mapped, Map)
    assert mapped.body.module.manifest.module_id == "nca.symbol-fuser"
    assert mapped.source.module.manifest.module_id == "nca.segmenter"


def test_segmenter_recovers_glyphs_in_order():
    rng = np.random.default_rng(0)
    for _ in range(50):
        glyphs = [render_operator(op, rng) for op in ("+", "*", "-")]
        sample = compose(glyphs, ("1", "+", "2"), rng)
        crops = Segmenter().invoke(torch.from_numpy(sample.image))
        assert len(crops) == 3
        for crop, glyph in zip(crops, glyphs):
            assert crop.shape == (GLYPH, GLYPH)
            assert np.isclose(crop.sum().item(), glyph.sum(), rtol=1e-2)


def test_column_runs_merges_narrow_gaps():
    image = np.zeros((4, 12))
    image[:, [1, 2, 4, 8]] = 1.0
    assert column_runs(image) == [(1, 5), (8, 9)]


def test_fuser_is_a_distribution():
    digits = tuple(np.full(10, 0.1))
    fused = SymbolFuser().invoke(digits, (0.1, 0.2, 0.3, 0.4))
    assert np.isclose(sum(fused.values()), 1.0)
    assert np.isclose(fused["7"], 0.04) and fused["*"] == 0.3


def test_parser_respects_grammar_and_evaluator_precedence():
    peaked = lambda s: {k: float(k == s) for k in "0123456789+-*"}
    # The middle glyph looks most like a digit, but grammar forces an operator.
    middle = {**peaked("1"), "-": 0.2, "1": 0.8}
    tokens = ExpressionParser().invoke([peaked("2"), middle, peaked("3"), peaked("*"), peaked("4")])
    assert tokens == ("2", "-", "3", "*", "4")
    assert Evaluator().invoke(tokens) == -10
    assert ExpressionParser().invoke([peaked("2"), peaked("+")]) is None
