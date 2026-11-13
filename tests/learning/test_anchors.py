from random import Random

from nca.learning.anchors import Scene, at, beside, pool, read, toward, turns
from nca.learning.inquiry import Inquiry


def test_a_value_forming_one_solid_block_marks_a_place_and_a_scattered_one_does_not() -> None:
    scene = Scene({(0, 0): "a", (1, 0): "b", (2, 1): "b", (0, 1): "c", (1, 1): "d", (2, 0): "d"})
    assert scene.where("a") == (0, 0) and scene.where("b") is None and scene.where("z") is None
    block = {(x, y): "plain" for x in range(6) for y in range(6)} | {(x, y): "block" for x in (2, 3) for y in (3, 4)}
    assert Scene(block).where("block") == (2, 3) and Scene(block).where("plain") is None
    assert Scene(block | {(5, 5): "block"}).where("block") is None


def test_probes_read_fixed_places_offsets_from_anchors_and_bearings() -> None:
    scene = Scene({(0, 0): "a", (1, 0): "b", (2, 1): "b", (0, 1): "c", (1, 1): "d", (2, 0): "d"})
    assert read(scene, at((1, 0))) == "b" and read(scene, at((5, 5))) is None
    assert read(scene, beside("a", (1, 0))) == "b" and read(scene, beside("a", (-1, 0))) is None
    assert read(scene, beside("b", (1, 0))) is None
    assert read(scene, toward("a", "c", 1)) == 1 and read(scene, toward("c", "a", 1)) == -1
    assert read(scene, toward("a", "c", 0)) == 0 and read(scene, toward("a", "b", 0)) is None


def test_the_pool_does_not_grow_with_the_scene() -> None:
    probes = pool(("a", "b", "c"), 1, 2)
    assert len(probes) == len(set(probes)) == 3 * 8 + 2 * 6


def test_the_turns_of_a_pool_are_its_axis_maps() -> None:
    probes = pool(("a", "b"), 1, 2)
    found = turns(probes, 2)
    assert len(found) == 8 and found[0] == tuple(range(len(probes)))
    right = probes.index(beside("a", (1, 0)))
    assert {probes[turn[right]] for turn in found} == {beside("a", step) for step in ((1, 0), (-1, 0), (0, 1), (0, -1))}
    along = probes.index(toward("a", "b", 0))
    assert {probes[turn[along]] for turn in found} == {toward("a", "b", 0), toward("b", "a", 0), toward("a", "b", 1),
                                                       toward("b", "a", 1)}


def test_a_learner_takes_up_the_offset_from_the_value_the_target_follows() -> None:
    """A marker stands anywhere among two kinds of cell; a scene is good when the cell to its right is of one kind."""
    rng, inquiry = Random(4), Inquiry(pool(("marker", "plain", "odd"), 1, 2), read, largest=2)
    for _ in range(120):
        cells = {(x, y): rng.choice(("plain", "odd")) for x in range(6) for y in range(6)}
        cells[rng.randrange(5), rng.randrange(6)] = "marker"
        scene = Scene(cells)
        inquiry.judge(scene, "take", read(scene, beside("marker", (1, 0))) == "odd")
    assert inquiry.looking_at == (beside("marker", (1, 0)),)
    fresh = {(x, y): "plain" for x in range(6) for y in range(6)} | {(2, 2): "marker", (3, 2): "odd"}
    good, bad = inquiry.votes(Scene(fresh), "take")
    assert good > bad


def test_a_scene_moved_as_a_whole_reads_the_same() -> None:
    """Every probe placed by an anchor reads the same wherever the scene lies (THEORY 54.12)."""
    rng, probes = Random(2), pool(("marker", "mark", "plain", "odd"), 2, 2)
    places = [(x, y) for x in range(7) for y in range(7)]
    for _ in range(20):
        cells = {place: rng.choice(("plain", "odd")) for place in places}
        cells.update(zip(rng.sample(places, 2), ("marker", "mark"), strict=True))
        move = (rng.randrange(-9, 10), rng.randrange(-9, 10))
        moved = Scene({(x + move[0], y + move[1]): value for (x, y), value in cells.items()})
        scene = Scene(cells)
        assert read(scene, toward("marker", "mark", 0)) is not None
        assert [read(scene, probe) for probe in probes] == [read(moved, probe) for probe in probes]
