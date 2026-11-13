from collections.abc import Callable, Hashable

import pytest

from nca.learning.anchors import beside, read
from nca.learning.gaze import Gaze

Position = tuple[int, int]


def scene(blocks: dict[str, Position], side: int = 32) -> Callable[[Position], Hashable]:
    """A plain square with a three-by-three block of each named value at its corner."""
    cells = {(x, y): "plain" for x in range(side) for y in range(side)}
    for value, (left, top) in blocks.items():
        cells.update({(left + x, top + y): value for x in range(3) for y in range(3)})
    return cells.get


def test_a_block_is_found_by_scattering_and_then_followed_for_a_few_looks() -> None:
    gaze, found, late = Gaze((32, 32), 64, reach=5), [], []
    for step in range(60):
        corner = (2 + step // 2, 10) if step < 40 else (21, 10 + min(step - 39, 15))
        glimpse = gaze.frame(scene({"block": corner, "still": (4, 25)}))
        gaze.close(glimpse)
        found.append(glimpse.where("block") == corner)
        late.append(glimpse.looks)
    assert sum(found) >= 40 and all(found[-10:]) and gaze.ignored == {"plain"}
    assert max(late) <= 64 and sum(late[-10:]) / 10 < 20


def test_a_frame_is_never_read_beyond_its_budget_unless_studied() -> None:
    gaze = Gaze((32, 32), 20, reach=5)
    glimpse = gaze.frame(scene({"block": (4, 4)}), reserve=5)
    assert glimpse.looks <= 15
    readings = [glimpse.get((x, 31)) for x in range(32)]
    assert glimpse.looks == 20 and readings[:5] == ["plain"] * 5 and readings[-1] is None
    assert glimpse.where("block") is None
    glimpse.study()
    assert glimpse.get((31, 31)) == "plain" and glimpse.looks == 20 and glimpse.studied == 32 * 32 - 20
    assert glimpse.where("block") == (4, 4) and glimpse.where("plain") is None


def test_a_value_found_at_two_corners_or_running_far_is_not_an_anchor() -> None:
    cells = {(x, y): "plain" for x in range(16) for y in range(16)}
    cells.update({(x, y): "twice" for x in (2, 3, 10, 11) for y in (2, 3)})
    gaze = Gaze((16, 16), 400, reach=4)
    glimpse = gaze.frame(cells.get)
    assert glimpse.where("twice") is None and glimpse.where("plain") is None and gaze.ignored == {"twice", "plain"}


def test_a_glimpse_answers_anchored_probes() -> None:
    gaze = Gaze((32, 32), 2000, reach=5)
    glimpse = gaze.frame(scene({"block": (8, 8), "other": (12, 8)}))
    assert read(glimpse, beside("block", (4, 0))) == "other" and read(glimpse, beside("block", (-9, 0))) is None


def test_malformed_gazes_are_refused() -> None:
    with pytest.raises(ValueError, match="budget"):
        Gaze((8, 8), -1, reach=2)
    with pytest.raises(ValueError, match="reach"):
        Gaze((8, 8), 4, reach=0)


def test_a_block_that_jumps_is_found_on_the_positions_one_of_its_side_must_hold() -> None:
    """A block of side three in a square of side 32 holds one of 121 positions; rings around its old place hold 15."""
    gaze, places = Gaze((32, 32), 160, reach=5), [(4, 4), (25, 7), (10, 28), (20, 13), (1, 22), (29, 29), (14, 2)]
    for _ in range(8):
        gaze.close(gaze.frame(scene({"block": places[0]})))
    assert gaze.sides == {"block": 3}
    for corner in places[1:]:
        glimpse = gaze.frame(scene({"block": corner}))
        gaze.close(glimpse)
        assert glimpse.where("block") == corner and glimpse.looks <= 15 + 121 + 2 * 3 + 16


def test_a_block_smaller_than_it_was_is_found_once_a_pass_has_missed_it() -> None:
    gaze = Gaze((32, 32), 400, reach=5)
    for _ in range(4):
        gaze.close(gaze.frame(scene({"block": (6, 6)})))
    cells = {(x, y): "plain" for x in range(32) for y in range(32)} | {(22, 19): "block"}
    found = []
    for _ in range(6):
        glimpse = gaze.frame(cells.get)
        gaze.close(glimpse)
        found.append(glimpse.where("block") == (22, 19))
    assert not found[0] and found[-1] and gaze.sides == {"block": 1}


def test_a_block_seen_only_at_every_fourth_position_is_looked_for_only_there() -> None:
    """Corners on multiples of four: 64 positions of a square of side 32 where the side alone marks 121."""
    gaze, places = Gaze((32, 32), 90, reach=5), [(4, 4), (24, 8), (8, 28), (20, 12), (0, 20), (28, 28), (12, 0)]
    for corner in places[:4]:
        for _ in range(6):
            gaze.close(gaze.frame(scene({"block": corner})))
    assert gaze.strides["block"] == ((4, 4), (4, 4))
    for corner in places[4:]:
        glimpse = gaze.frame(scene({"block": corner}))
        gaze.close(glimpse)
        assert glimpse.where("block") == corner and glimpse.looks <= 15 + 64 + 2 * 3 + 9


def test_a_block_off_its_stride_is_found_on_the_positions_of_its_side() -> None:
    gaze = Gaze((32, 32), 250, reach=5)
    for corner in ((4, 4), (24, 8), (8, 28)):
        for _ in range(6):
            gaze.close(gaze.frame(scene({"block": corner})))
    glimpse = gaze.frame(scene({"block": (17, 22)}))
    assert glimpse.where("block") == (17, 22) and gaze.sides == {"block": 3}
    assert gaze.strides["block"] == ((4, 4), (1, 2))
