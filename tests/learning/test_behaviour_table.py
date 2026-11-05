from nca.learning.behaviour_table import BehaviourTable


def table() -> BehaviourTable[str]:
    built: BehaviourTable[str] = BehaviourTable((0, 1, 2), lambda value: value)
    for name, outputs in (("a", (0, 0, 0)), ("b", (0, 1, 0)), ("c", (1, 1, 0)), ("d", (1, 2, 3))):
        assert built.add(name, outputs)
    return built


def test_duplicate_behaviour_keeps_the_earliest() -> None:
    built = table()
    assert not built.add("later", (0, 0, 0))
    assert built.hypotheses == ["a", "b", "c", "d"]


def test_narrowing_uses_a_goals_own_cases_and_stops_early() -> None:
    built: BehaviourTable[int] = BehaviourTable((0,), lambda value: value)
    for factor in (1, 2, 3):
        built.add(factor, (factor,))
    found = built.narrow([(1, 2), (5, 10), (6, 12)], lambda factor, item: factor * item)
    assert (found.hypothesis, found.labels, found.evaluations) == (2, 1, 3)
    missing = built.narrow([(1, 9), (5, 10)], lambda factor, item: factor * item)
    assert (missing.hypothesis, missing.labels, missing.evaluations) == (None, 1, 3)
