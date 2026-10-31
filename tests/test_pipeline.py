import numpy as np
import pytest

torch = pytest.importorskip("torch")

from nca.expressions import GLYPH, compose, render_operator
from nca.modules.digit_recognizer import DigitRecognizer, build_network as digit_net
from nca.modules.operator_recognizer import SymbolRecognizer, build_network as op_net
from nca.modules.segmenter import Segmenter, column_runs
from nca.modules.symbols import Evaluator, ExpressionParser, SymbolFuser
from nca.pipeline import build_registry, compose as compose_plan
from nca.planner import Apply, Map


def test_planner_composes_full_pipeline_with_map() -> None:
    registry = build_registry(DigitRecognizer(digit_net()), SymbolRecognizer(op_net()))
    graph = compose_plan(registry)
    assert isinstance(graph, Apply) and graph.module.manifest.module_id == "nca.evaluator"
    parser = graph.args[0]
    assert parser.module.manifest.module_id == "nca.expression-parser"
    mapped = parser.args[0]
    assert isinstance(mapped, Map)
    assert mapped.body.module.manifest.module_id == "nca.symbol-fuser"
    assert mapped.source.module.manifest.module_id == "nca.segmenter"


def test_segmenter_recovers_glyphs_in_order() -> None:
    rng = np.random.default_rng(0)
    for _ in range(50):
        glyphs = [render_operator(op, rng) for op in ("+", "*", "-")]
        sample = compose(glyphs, ("1", "+", "2"), rng)
        crops = Segmenter().invoke(torch.from_numpy(sample.image))
        assert len(crops) == 3
        for crop, glyph in zip(crops, glyphs):
            assert crop.shape == (GLYPH, GLYPH)
            assert np.isclose(crop.sum().item(), glyph.sum(), rtol=1e-2)


def test_column_runs_merges_narrow_gaps() -> None:
    image = np.zeros((4, 12))
    image[:, [1, 2, 4, 8]] = 1.0
    assert column_runs(image) == [(1, 5), (8, 9)]


def test_fuser_is_a_distribution() -> None:
    digits = tuple(np.full(10, 0.1))
    fused = SymbolFuser().invoke(digits, (0.1, 0.2, 0.3, 0.4))
    assert np.isclose(sum(fused.values()), 1.0)
    assert np.isclose(fused["7"], 0.04) and fused["*"] == 0.3


def test_parser_respects_grammar_and_evaluator_precedence() -> None:
    def peaked(s: str) -> dict[str, float]:
        return {k: float(k == s) for k in "0123456789+-*"}

    # The middle glyph looks most like a digit, but grammar forces an operator.
    middle = {**peaked("1"), "-": 0.2, "1": 0.8}
    tokens = ExpressionParser().invoke([peaked("2"), middle, peaked("3"), peaked("*"), peaked("4")])
    assert tokens == ("2", "-", "3", "*", "4")
    assert Evaluator().invoke(tokens) == -10
    assert ExpressionParser().invoke([peaked("2"), peaked("+")]) is None


def test_installing_comparison_keeps_arithmetic_route_and_adds_coverage() -> None:
    from nca.accumulation import comparison_modules
    from nca.modules.operator_recognizer import RELATION_SET
    from nca.modules.segmenter import EXPRESSION_IMAGE
    from nca.modules.symbols import BOOLEAN, INTEGER
    from nca.planner import plan_stable

    registry = build_registry(DigitRecognizer(digit_net()), SymbolRecognizer(op_net()))
    before = plan_stable(registry.modules(), (EXPRESSION_IMAGE,), INTEGER)
    assert plan_stable(registry.modules(), (EXPRESSION_IMAGE,), BOOLEAN) is None

    for module in comparison_modules(SymbolRecognizer(op_net(RELATION_SET), RELATION_SET)):
        registry.install(module)

    assert plan_stable(registry.modules(), (EXPRESSION_IMAGE,), INTEGER) == before
    comparison = plan_stable(registry.modules(), (EXPRESSION_IMAGE,), BOOLEAN)
    assert comparison.module.manifest.module_id == "nca.comparison.evaluator"


def test_comparison_evaluator_chains() -> None:
    from nca.modules.symbols import ComparisonEvaluator

    assert ComparisonEvaluator().invoke(("1", "<", "3", "=", "3"))
    assert not ComparisonEvaluator().invoke(("4", ">", "5"))


def test_encoder_install_reroutes_plain_planner_but_not_stable() -> None:
    from nca.modules.segmenter import EXPRESSION_IMAGE
    from nca.modules.symbol_classifier import (
        GlyphEncoder, SymbolClassifier, build_classifier, build_encoder,
    )
    from nca.modules.symbols import INTEGER
    from nca.planner import plan, plan_stable
    from nca.registry import Registry

    registry = Registry()
    for module in (Segmenter(), DigitRecognizer(digit_net()), SymbolRecognizer(op_net()),
                   SymbolClassifier(build_classifier()), SymbolFuser(), ExpressionParser(),
                   Evaluator()):
        registry.install(module)
    def body(route: Apply) -> str:
        return route.args[0].args[0].body.module.manifest.module_id

    before = plan_stable(registry.modules(), (EXPRESSION_IMAGE,), INTEGER)
    assert before == plan(registry.modules(), (EXPRESSION_IMAGE,), INTEGER)
    assert body(before) == "nca.symbol-fuser"

    registry.install(GlyphEncoder(build_encoder()))

    assert body(plan(registry.modules(), (EXPRESSION_IMAGE,), INTEGER)) == "nca.symbol-classifier"
    assert plan_stable(registry.modules(), (EXPRESSION_IMAGE,), INTEGER) == before


def test_substitute_recognizer_keeps_route_shape_and_types() -> None:
    from nca.modules.segmenter import EXPRESSION_IMAGE
    from nca.modules.symbols import INTEGER
    from nca.router import infer
    from nca.substitution import shape

    registry = build_registry(DigitRecognizer(digit_net()), SymbolRecognizer(op_net()))
    before = compose_plan(registry)
    registry.replace(DigitRecognizer(digit_net("mlp"), version="2.0.0"))
    after = compose_plan(registry)
    assert after != before
    assert shape(after) == shape(before)
    assert infer(registry.modules(), (EXPRESSION_IMAGE,), after) == INTEGER


def test_relational_parser_forces_one_relation() -> None:
    from nca.modules.symbols import RelationalEvaluator, RelationalParser

    def dist(**probs: float) -> dict[str, float]:
        base = {k: 0.0 for k in "0123456789+-*<>="}
        return {**base, **probs}

    # Both operator slots prefer operators; the cheaper switch is position 3.
    symbols = [dist(**{"3": 1}), dist(**{"+": 0.9, "<": 0.1}), dist(**{"4": 1}),
               dist(**{"-": 0.6, ">": 0.4}), dist(**{"6": 1})]
    tokens = RelationalParser().invoke(symbols)
    assert tokens == ("3", "+", "4", ">", "6")
    assert RelationalEvaluator().invoke(tokens) is True
    assert RelationalParser().invoke(symbols[:1]) is None


def test_mixed_fuser_normalizes() -> None:
    from nca.modules.symbols import MixedSymbolFuser

    fused = MixedSymbolFuser().invoke(tuple([0.1] * 10), (0.1, 0.1, 0.1, 0.7),
                                      (0.2, 0.0, 0.0, 0.8))
    assert np.isclose(sum(fused.values()), 1.0)
    assert fused["<"] > fused["+"]


def test_integration_route_is_an_explicit_upgrade() -> None:
    from nca.complementarity import build_systems, integration_modules_of, registry_of
    from nca.modules.operator_recognizer import RELATION_SET
    from nca.modules.segmenter import EXPRESSION_IMAGE
    from nca.modules.symbols import BOOLEAN
    from nca.planner import plan, plan_stable
    from nca.router import infer

    systems = build_systems(DigitRecognizer(digit_net()), SymbolRecognizer(op_net()),
                            SymbolRecognizer(op_net(RELATION_SET), RELATION_SET))
    def root(route: Apply) -> str:
        return route.module.manifest.module_id

    assert plan_stable(systems["A"], (EXPRESSION_IMAGE,), BOOLEAN) is None

    full = registry_of(systems["A⊕B"])
    assert root(plan_stable(full.modules(), (EXPRESSION_IMAGE,), BOOLEAN)) == \
        "nca.comparison.evaluator"
    candidate = plan(integration_modules_of(full) + full.modules(), (EXPRESSION_IMAGE,), BOOLEAN)
    assert root(candidate) == "nca.relational-evaluator"
    assert infer(full.modules(), (EXPRESSION_IMAGE,), candidate) == BOOLEAN
