from nca.learning.foresight import furthest, lasts


def test_an_action_into_a_dead_end_lasts_as_long_as_the_dead_end() -> None:
    """Places on a line: from 0, ``in`` enters a corridor of three places that ends; ``on`` goes round a ring."""
    corridor, ring = ("c1", "c2", "c3"), ("r1", "r2", "r3", "r4")

    def options(place: str) -> tuple[str, ...]:
        return () if place == "c3" else ("in", "on") if place == "start" else ("on",)

    def follow(place: str, action: str) -> str | None:
        if place == "start":
            return corridor[0] if action == "in" else ring[0]
        row = corridor if place in corridor else ring
        return row[(row.index(place) + 1) % len(row)]

    def never(_: str, __: str) -> bool:
        return False

    reach = {depth: lasts("start", "in", depth, bad=never, follow=follow, options=options) for depth in (1, 2, 3, 6)}
    assert reach == {1: 1, 2: 2, 3: 3, 6: 3}
    assert lasts("start", "on", 6, bad=never, follow=follow, options=options) == 6
    assert furthest("start", ("in", "on"), 3, bad=never, follow=follow, options=options) == ["in", "on"]
    assert furthest("start", ("in", "on"), 4, bad=never, follow=follow, options=options) == ["on"]


def test_an_action_judged_bad_does_not_last_and_one_whose_sequel_is_unknown_is_not_held_back() -> None:
    def bad(place: int, action: str) -> bool:
        return action == "stop" or (place == 1 and action == "go")

    def follow(place: int, action: str) -> int | None:
        return None if action == "leap" else place + 1

    def options(_: int) -> tuple[str, ...]:
        return ("go", "stop")

    assert lasts(0, "stop", 5, bad=bad, follow=follow, options=options) == 0
    assert lasts(0, "go", 5, bad=bad, follow=follow, options=options) == 1
    assert lasts(0, "leap", 5, bad=bad, follow=follow, options=options) == 5
    assert furthest(0, ("stop", "go", "leap"), 5, bad=bad, follow=follow, options=options) == ["leap"]
    assert furthest(1, ("stop", "go"), 5, bad=bad, follow=follow, options=options) == ["stop", "go"]
