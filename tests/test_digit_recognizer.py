import math

import pytest

torch = pytest.importorskip("torch")

from nca.abi import Message
from nca.modules.digit_recognizer import (
    DIGIT_DISTRIBUTION,
    GLYPH,
    DigitRecognizer,
    build_network,
)
from nca.planner import plan
from nca.registry import Registry
from nca.runtime import execute
from nca.workspace import Workspace


def test_untrained_recognizer_honours_contract():
    registry = Registry()
    registry.install(DigitRecognizer(build_network()))
    graph = plan(registry.modules(), frozenset({GLYPH}), DIGIT_DISTRIBUTION)
    glyph = Message(GLYPH, torch.rand(28, 28), producer="input")

    result = execute(graph, {GLYPH: glyph}, Workspace(), budget=1)

    assert result.type_id == DIGIT_DISTRIBUTION
    assert len(result.payload) == 10
    assert math.isclose(sum(result.payload), 1.0, rel_tol=1e-5)
