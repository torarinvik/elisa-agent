import numpy as np
import pytest

torch = pytest.importorskip("torch")

from nca.domains.arithmetic.expressions import GLYPH, compose, render_operator
from nca.domains.arithmetic.digit_recognizer import DigitRecognizer, build_network as digit_net
from nca.domains.arithmetic.operator_recognizer import SymbolRecognizer, build_network as op_net
from nca.domains.arithmetic.segmenter import Segmenter, column_runs
from nca.domains.arithmetic.symbols import Evaluator, ExpressionParser, SymbolFuser
from nca.domains.arithmetic.pipeline import build_registry, compose as compose_plan
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
    image = np.zeros((4, 16))
    image[:, [1, 2, 4, 12]] = 1.0
    assert column_runs(image) == [(1, 5), (12, 13)]


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
    from nca.domains.arithmetic.accumulation import comparison_modules
    from nca.domains.arithmetic.operator_recognizer import RELATION_SET
    from nca.domains.arithmetic.segmenter import EXPRESSION_IMAGE
    from nca.domains.arithmetic.symbols import BOOLEAN, INTEGER
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
    from nca.domains.arithmetic.symbols import ComparisonEvaluator

    assert ComparisonEvaluator().invoke(("1", "<", "3", "=", "3"))
    assert not ComparisonEvaluator().invoke(("4", ">", "5"))


def test_encoder_install_reroutes_plain_planner_but_not_stable() -> None:
    from nca.domains.arithmetic.segmenter import EXPRESSION_IMAGE
    from nca.domains.arithmetic.symbol_classifier import (
        GlyphEncoder, SymbolClassifier, build_classifier, build_encoder,
    )
    from nca.domains.arithmetic.symbols import INTEGER
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
    from nca.domains.arithmetic.segmenter import EXPRESSION_IMAGE
    from nca.domains.arithmetic.symbols import INTEGER
    from nca.router import infer
    from nca.domains.arithmetic.substitution import shape

    registry = build_registry(DigitRecognizer(digit_net()), SymbolRecognizer(op_net()))
    before = compose_plan(registry)
    registry.replace(DigitRecognizer(digit_net("mlp"), version="2.0.0"))
    after = compose_plan(registry)
    assert after != before
    assert shape(after) == shape(before)
    assert infer(registry.modules(), (EXPRESSION_IMAGE,), after) == INTEGER


def test_relational_parser_forces_one_relation() -> None:
    from nca.domains.arithmetic.symbols import RelationalEvaluator, RelationalParser

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
    from nca.domains.arithmetic.symbols import MixedSymbolFuser

    fused = MixedSymbolFuser().invoke(tuple([0.1] * 10), (0.1, 0.1, 0.1, 0.7),
                                      (0.2, 0.0, 0.0, 0.8))
    assert np.isclose(sum(fused.values()), 1.0)
    assert fused["<"] > fused["+"]


def test_integration_route_is_an_explicit_upgrade() -> None:
    from nca.domains.arithmetic.complementarity import build_systems, integration_modules_of, registry_of
    from nca.domains.arithmetic.operator_recognizer import RELATION_SET
    from nca.domains.arithmetic.segmenter import EXPRESSION_IMAGE
    from nca.domains.arithmetic.symbols import BOOLEAN
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


def test_parser_demand_is_sound() -> None:
    from nca.abi import NOTHING, SequenceDemand

    rng = np.random.default_rng(0)
    keys = "0123456789+-*"
    parser, fuser = ExpressionParser(), SymbolFuser()
    for n in range(1, 8):
        demand = parser.demand(0, None)
        assert isinstance(demand, SequenceDemand)
        for _ in range(20):
            symbols = [dict(zip(keys, rng.random(len(keys)))) for _ in range(n)]
            altered = []
            for i, dist in enumerate(symbols):
                read = demand.element(i, n)
                noise = dict(zip(keys, rng.random(len(keys))))
                # Replace everything outside the demanded fields.
                fields = {"digits": "0123456789", "operators": "+-*"}
                kept = set().union(*(fields[f] for f in read)) if read else set()
                altered.append({k: dist[k] if k in kept else noise[k] for k in keys})
            assert parser.invoke(altered) == parser.invoke(symbols)
            for i in range(n):
                read = demand.element(i, n)
                if read == NOTHING or "digits" not in read:
                    assert fuser.demand(0, read) == NOTHING


def test_fuser_decision_demand_is_sound() -> None:
    from nca.abi import SequenceDemand

    rng = np.random.default_rng(1)
    parser, fuser = ExpressionParser(), SymbolFuser()
    for n in (1, 3, 5, 7):
        demand = parser.demand(0, None)
        assert isinstance(demand, SequenceDemand)
        for _ in range(50):
            digits = [tuple(rng.dirichlet(np.ones(10))) for _ in range(n)]
            operators = [tuple(rng.dirichlet(np.ones(4))) for _ in range(n)]
            full = [fuser.invoke(d, o) for d, o in zip(digits, operators)]
            decided = []
            for i, (d, o) in enumerate(zip(digits, operators)):
                read = demand.element(i, n)
                decided.append(fuser.invoke(d if fuser.decides(0, read) is None else None,
                                            o if fuser.decides(1, read) is None else None))
            assert parser.invoke(decided) == parser.invoke(full)


def test_library_map_matches_built_in_map() -> None:
    """``NCA.embed_wellTyped``: ``map`` as a library expert gives the same
    answers at the same cost, with the parser's demand passed through."""
    from nca.abi import Message
    from nca.cost import costed
    from nca.modules.combinators import MapExpert, embed_maps
    from nca.domains.arithmetic.segmenter import EXPRESSION_IMAGE
    from nca.domains.arithmetic.symbols import INTEGER
    from nca.planner import output_type, plan_stable
    from nca.runtime import execute
    from nca.workspace import Workspace

    torch.manual_seed(0)
    digit = costed(DigitRecognizer(digit_net()), 1000.0, "digit")
    operator = costed(SymbolRecognizer(op_net()), 10.0, "operator")
    registry = build_registry(digit, operator)
    built_in = compose_plan(registry)
    embedded = embed_maps(built_in)
    mapped = built_in.args[0].args[0]
    library = [MapExpert(mapped.element, output_type(mapped.body)), *registry.modules()]
    assert plan_stable(library, (EXPRESSION_IMAGE,), INTEGER) == embedded
    rng = np.random.default_rng(1)
    for operands in (2, 4):
        tokens = tuple("3" if i % 2 == 0 else "+" for i in range(2 * operands - 1))
        glyphs = [(rng.random((GLYPH, GLYPH)) < 0.3).astype(np.float32) if t == "3"
                  else render_operator(t, rng) for t in tokens]
        image = torch.from_numpy(compose(glyphs, tokens, rng, width=40 * len(glyphs)).image)
        results = []
        for route in (built_in, embedded):
            workspace = Workspace()
            out = execute(route, {EXPRESSION_IMAGE: Message(EXPRESSION_IMAGE, image, "input")},
                          workspace, 1000)
            results.append((out.payload, workspace.spent))
        assert results[0] == results[1]
        assert results[0][1] < 1000.0 * len(tokens)


def test_parser_preserves_order_when_positive_fusion_scale_rounds_to_a_tie() -> None:
    import math
    from nca.ladder import RankedReading

    probabilities = (0.75, 1.0) + (0.0,) * 8
    digits = RankedReading(probabilities, probabilities)
    fused = SymbolFuser().invoke(digits, (0.0, 0.0, 0.0, math.ulp(0.0)))
    assert fused["0"] == fused["1"] > 0
    assert ExpressionParser().invoke([fused]) == ("1",)


def test_batched_ranked_symbol_choices_match_fallback(monkeypatch) -> None:
    import nca.domains.arithmetic.symbols as symbols
    from nca.ladder import RankedReading

    if getattr(symbols._NATIVE, "row_argmax", None) is None:
        pytest.skip("Elisa argmax kernel is not built")
    rng = np.random.default_rng(661)
    fuser, parser = SymbolFuser(), ExpressionParser()
    entries = []
    for i in range(101):
        width = 4 if i % 2 else 10
        weights = tuple(rng.random(width))
        if i % 9 == 0:
            weights = tuple([0.5] * width)
        reading = RankedReading(weights, weights)
        dist = fuser.invoke(None, reading) if i % 2 else fuser.invoke(reading, None)
        entries.append(None if i % 17 == 0 else dict(dist) if i % 11 == 0 else dist)
    batched = parser.invoke(entries)
    monkeypatch.setattr(symbols, "_NATIVE", None)
    assert batched == parser.invoke(entries)


def test_batched_ranked_symbol_choices_reject_short_weight_vectors(monkeypatch) -> None:
    import nca.domains.arithmetic.symbols as symbols
    from nca.ladder import RankedReading

    if getattr(symbols._NATIVE, "row_argmax", None) is None:
        pytest.skip("Elisa argmax kernel is not built")
    reading = RankedReading((0.2,) * 5, (0.2,) * 5)
    malformed = SymbolFuser().invoke(reading, None)
    values = [malformed, None, malformed]
    with pytest.raises(ValueError, match="valid class indices"):
        ExpressionParser().invoke(values)
    monkeypatch.setattr(symbols, "_NATIVE", None)
    with pytest.raises(ValueError, match="valid class indices"):
        ExpressionParser().invoke(values)


def test_arithmetic_package_answers_like_the_flat_pipeline() -> None:
    """§28.3: the package is an expert whose requirements the planner fills
    with whatever glyph readers are installed."""
    from nca.abi import Message
    from nca.domains.arithmetic.package import arithmetic
    from nca.domains.arithmetic.segmenter import EXPRESSION_IMAGE
    from nca.domains.arithmetic.symbols import INTEGER
    from nca.objects import Store
    from nca.packages import Export, install
    from nca.planner import plan_stable
    from nca.runtime import execute
    from nca.workspace import Workspace

    torch.manual_seed(0)
    digit, operator = DigitRecognizer(digit_net()), SymbolRecognizer(op_net())
    flat = compose_plan(build_registry(digit, operator))
    store = Store()
    modules = [digit, operator, *install(store, arithmetic(store))]
    route = plan_stable(modules, (EXPRESSION_IMAGE,), INTEGER)
    assert isinstance(route, Apply) and isinstance(route.module, Export)
    assert [s.module for s in route.slots] == [digit, operator]
    rng = np.random.default_rng(3)
    for operands in (2, 3, 5):
        tokens = tuple(str(rng.integers(10)) if i % 2 == 0 else "+-*"[rng.integers(3)]
                       for i in range(2 * operands - 1))
        glyphs = [(rng.random((GLYPH, GLYPH)) < 0.3).astype(np.float32) if t.isdigit()
                  else render_operator(t, rng) for t in tokens]
        image = torch.from_numpy(compose(glyphs, tokens, rng, width=40 * len(glyphs)).image)
        answers = [execute(r, {EXPRESSION_IMAGE: Message(EXPRESSION_IMAGE, image, "input")},
                           Workspace(), 1000).payload for r in (flat, route)]
        assert answers[0] == answers[1]


def test_relevant_risk_charges_each_reader_only_where_the_parser_reads_it() -> None:
    """§31.6: the parser reads digits at even and operators at odd positions."""
    from nca.domains.arithmetic.digit_recognizer import DIGIT_DISTRIBUTION
    from nca.domains.arithmetic.operator_recognizer import OPERATOR_DISTRIBUTION
    from nca.evidence import route_risk

    route = compose_plan(build_registry(DigitRecognizer(digit_net()), SymbolRecognizer(op_net())))
    rates = {DIGIT_DISTRIBUTION: 0.02, OPERATOR_DISTRIBUTION: 0.01}

    def rate(module: object) -> float:
        return rates.get(module.manifest.contract.output, 0.0)

    for glyphs in (1, 5, 9):
        plain = route_risk(route, rate, glyphs)
        relevant = route_risk(route, rate, glyphs, relevant=True)
        assert plain == pytest.approx(glyphs * 0.03)
        assert relevant == pytest.approx((glyphs + 1) / 2 * 0.02 + (glyphs - 1) / 2 * 0.01)
    assert route_risk(route, rate, 4, relevant=True) == 0.0  # Even lengths are never parsed.
