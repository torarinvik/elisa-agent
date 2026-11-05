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


def test_each_class_is_identified_with_few_labels() -> None:
    built = table()
    for name, vector in zip(built.hypotheses, built.vectors, strict=True):
        found = built.identify(lambda position, known=vector: known[position])
        assert found.hypothesis == name
        assert len(found.asked) <= 2


def test_goal_outside_the_table_is_refused_from_labels() -> None:
    found = table().identify(lambda position: 9)
    assert found.hypothesis is None
    assert len(found.asked) == 1


def test_single_class_needs_no_label_and_still_only_proposes() -> None:
    built: BehaviourTable[str] = BehaviourTable((0,), lambda value: value)
    built.add("only", (5,))
    assert built.identify(lambda position: 9) .hypothesis == "only"
