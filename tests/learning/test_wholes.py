from random import Random

from nca.learning.inquiry import Inquiry
from nca.learning.relations import pool, read, value
from nca.learning.wholes import Whole

SLOTS = ("shown", "offered")


def _parts(situation: dict[str, tuple[int, int]]) -> dict[str, tuple[str, dict[str, int]]]:
    return {name: ("pair", dict(zip(SLOTS, pair, strict=True))) for name, pair in situation.items()}


def _whole() -> Whole:
    return Whole(_parts, {"pair": Inquiry((*map(value, SLOTS), *pool({"mark": SLOTS})), read, largest=2)})


def test_a_takeover_teaches_every_part_and_what_one_part_shows_holds_of_the_others() -> None:
    """Good when each part offers what it shows; only the first part is ever offered wrongly (THEORY 57.1, 57.2)."""
    rng, whole = Random(1), _whole()
    for _ in range(40):
        shown = {name: rng.randrange(4) for name in ("first", "second", "third")}
        right = {name: (mark, mark) for name, mark in shown.items()}
        whole.correct(right | {"first": (shown["first"], (shown["first"] + 1) % 4)}, right, "take")
    held = {name: (7, 7) for name in ("first", "second", "third", "fourth")}
    assert whole.against(held, "take")[0] == 0
    assert whole.against(held | {"third": (7, 9)}, "take")[0] == 1
    assert whole.against(held | {"second": (7, 9), "fourth": (5, 6)}, "take")[0] == 2
    offered = [held | {"fourth": (7, 8)}, held, held | {"first": (1, 2), "third": (3, 2)}]
    assert whole.choose([(situation, "take") for situation in offered], Random(0)) == 1


def test_parts_the_proposal_shares_with_the_right_whole_or_has_alone_are_not_blamed() -> None:
    whole, judged = _whole(), []
    whole.learners = {"pair": type("Kept", (), {"judge": lambda _, seen, action, good: judged.append((seen, good)),
                                                 "votes": lambda *_: (0.0, 0.0), "unmet": lambda *_: 0})()}
    whole.correct({"first": (1, 2), "second": (3, 3), "spare": (5, 6)}, {"first": (1, 1), "second": (3, 3)}, "take")
    assert judged == [({"shown": 1, "offered": 1}, True), ({"shown": 3, "offered": 3}, True),
                      ({"shown": 1, "offered": 2}, False)]


def test_where_many_parts_differ_only_those_never_seen_good_are_blamed() -> None:
    """Good when no part offers what it shows; a wrong whole differs from the right one in every part (57.5)."""
    rng, whole = Random(2), _whole()
    names = ("first", "second", "third", "fourth", "fifth")
    for _ in range(60):
        shown = {name: rng.randrange(8) for name in names}
        clash, free = rng.choice(names), rng.choice(sorted(set(range(8)) - set(shown.values())))
        whole.correct({name: (mark, shown[clash]) for name, mark in shown.items()},
                      {name: (mark, free) for name, mark in shown.items()}, "take")
    held = {name: (20 + place, 9) for place, name in enumerate(names)}
    assert whole.against(held, "take")[0] == 0
    assert whole.against(held | {"third": (9, 9)}, "take")[0] == 1


def test_every_whole_offered_teaches_once_the_right_one_is_known_and_what_is_held_is_not_recorded_again() -> None:
    """Each part has one good value: a part any other whole has otherwise is bad (THEORY 57.5)."""
    whole = _whole()
    learner = whole.learners["pair"]
    offered = [{"first": (1, 1), "second": (2, 2)}, {"first": (1, 3), "second": (2, 2)},
               {"first": (1, 1), "second": (2, 5)}, {"first": (1, 3), "second": (2, 5)}]
    again = [{"first": (4, 4), "second": (7, 7)}, {"first": (4, 6), "second": (7, 7)}, {"first": (4, 4), "second": (7, 8)}]
    whole.study(offered, 0, "take")
    whole.study(again, 0, "take")
    kept = learner.judgements
    assert 0 < sum(good for _, _, good in learner.cases) < kept <= 6
    more = [{"first": (9, 9), "second": (0, 0)}, {"first": (9, 0), "second": (0, 0)}, {"first": (9, 9), "second": (0, 3)}]
    assert whole.choose([(seen, "take") for seen in more], Random(0)) == 0
    whole.study(more, 0, "take")
    assert learner.judgements == kept
