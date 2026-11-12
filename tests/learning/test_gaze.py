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
    glimpse.studying = True
    assert glimpse.get((31, 31)) == "plain" and glimpse.looks == 20 and glimpse.studied == 1
    assert glimpse.get((31, 31)) == "plain" and glimpse.studied == 1


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
