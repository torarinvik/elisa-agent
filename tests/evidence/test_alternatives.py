"""Answering over alternatives (§39)."""

from typing import Any

import pytest

from nca.abi import Contract, Manifest
from nca.evidence.alternatives import Tabled, answer_over_alternatives, fit_table
from nca.planner import Apply, Given, Map

TEXT, WORD, LENGTH, TOTAL = "text.v1", "word.v1", "len.v1", "total.v1"


class Expert:
    def __init__(self, name: str, inputs: tuple[str, ...], output: str, function: Any) -> None:
        self.manifest = Manifest(name, "1", Contract(inputs, output))
        self.function = function

    def invoke(self, *values: Any) -> Any:
        return self.function(*values)


class Splitter(Expert):
    """Offers fixed candidate splittings of a text."""

    def __init__(self, options: list[tuple[Any, float]]) -> None:
        super().__init__("split", (TEXT,), f"list[{WORD}]", str.split)
        self.options = options

    def candidates(self, text: str) -> list[tuple[list[str], float]]:
        return [(split(text), q) for split, q in self.options]


class Measure(Expert):
    def __init__(self, risk: float) -> None:
        super().__init__("measure", (WORD,), LENGTH, len)
        self.reported = risk

    def risk(self, output: int, *inputs: Any) -> float:
        return self.reported


def route(splitter: Expert, measure: Expert) -> Apply:
    total = Expert("total", (f"list[{LENGTH}]",), TOTAL, sum)
    return Apply(total, (Map(WORD, Apply(measure, (Given(WORD),)),
                             Apply(splitter, (Given(TEXT),))),))


def exact(module: Any) -> bool:
    return module.manifest.module_id in {"total"}


def test_supports_add_over_agreeing_candidates_and_charges_reduce_them() -> None:
    def by_space(text: str) -> list[str]:
        return text.split()

    def whole(text: str) -> list[str]:
        return [text]

    def halves(text: str) -> list[str]:
        return [text[:1], text[1:2], *text[3:].split()]  # "a", "b", "cd"

    plan = route(Splitter([(by_space, 0.6), (whole, 0.3)]), Measure(0.0))
    (choice,) = answer_over_alternatives(plan, (TEXT,), [("ab cd",)], 0.5, exact)
    assert choice.answer == 4 and choice.bound == pytest.approx(0.4) and choice.candidates == 2
    (abstained,) = answer_over_alternatives(plan, (TEXT,), [("ab cd",)], 0.3, exact)
    assert abstained.answer is None and abstained.bound == pytest.approx(0.4)
    agreeing = route(Splitter([(by_space, 0.6), (halves, 0.3)]), Measure(0.0))
    (both,) = answer_over_alternatives(agreeing, (TEXT,), [("ab cd",)], 0.2, exact)
    assert both.answer == 4 and both.bound == pytest.approx(0.1)
    # Each word read charges 0.05: by_space has 2 words, halves 3.
    charged = route(Splitter([(by_space, 0.6), (halves, 0.3)]), Measure(0.05))
    (less,) = answer_over_alternatives(charged, (TEXT,), [("ab cd",)], 1.0, exact)
    assert less.bound == pytest.approx(1 - 0.6 * 0.9 - 0.3 * 0.85)


def test_a_route_needs_exactly_one_fork() -> None:
    plan = route(Expert("split", (TEXT,), f"list[{WORD}]", str.split), Measure(0.0))
    with pytest.raises(ValueError, match="exactly one fork"):
        answer_over_alternatives(plan, (TEXT,), [("ab",)], 0.1, exact)


class Ranked(Expert):
    """Ranks the right splitting first on short texts, second on long ones."""

    def __init__(self) -> None:
        super().__init__("split", (TEXT,), f"list[{WORD}]", str.split)

    def alternatives(self, text: str) -> list[list[str]]:
        right, wrong = text.split(), [text]
        return [right, wrong] if len(text) < 10 else [wrong, right]


def test_tabled_candidates_get_lower_bounds_per_stratum_and_rank() -> None:
    texts = [("ab cd" if i % 2 else "abcde fghij klm") for i in range(400)]
    module: Any = Ranked()

    def stratum(text: str) -> bool:
        return len(text) < 10

    table = fit_table(module, texts, [t.split() for t in texts],
                      lambda candidate, label: candidate == label, stratum, 0.05, 2)
    # Short texts: the first candidate (two words) is always right.
    assert table[(True, 0)] > 0.95 and table[(True, 1)] == 0.0
    # Long texts: the first candidate (one word) is always wrong.
    assert table[(False, 0)] == 0.0 and table[(False, 1)] > 0.95
    tabled = Tabled(module, table, stratum)
    plan = route(tabled, Measure(0.0))
    choices = answer_over_alternatives(plan, (TEXT,), [("ab cd",), ("abcde fghij klm",)], 0.05,
                                       exact)
    assert [c.answer for c in choices] == [4, 13]
