import json
from pathlib import Path

import numpy as np
import pytest

from nca.memory.blocks import BlockLibrary, KeyIndex, PartStore, choose


class Scaled:
    """A stand-in block: its input times a number."""

    def __init__(self, by: int) -> None:
        self.by = by

    def __call__(self, given: int) -> int:
        return given * self.by


def save(block: object, path: Path) -> None:
    assert isinstance(block, Scaled)
    path.write_text(json.dumps(block.by))


def load(path: Path) -> object:
    return Scaled(json.loads(path.read_text()))


def library(folder: Path, resident: int = 8) -> BlockLibrary:
    return BlockLibrary(folder, save, load, resident)


def test_an_experts_reading_is_unchanged_by_any_blocks_added_after(tmp_path: Path) -> None:
    held = library(tmp_path)
    held.add("a", Scaled(2))
    held.add("b", Scaled(3))
    held.register("first", ["a", "b"])
    before = [held.read(held.reading("first"), given) for given in range(-5, 6)]
    for extra in range(40):
        held.add(f"later {extra}", Scaled(extra))
    again = library(tmp_path)
    assert [again.read(again.reading("first"), given) for given in range(-5, 6)] == before
    assert before[7] == [4, 6]


def test_a_name_that_has_a_block_keeps_it(tmp_path: Path) -> None:
    held = library(tmp_path)
    held.add("a", Scaled(2))
    with pytest.raises(ValueError):
        held.add("a", Scaled(9))
    assert library(tmp_path).read(["a"], 5) == [10]


def test_only_the_blocks_read_are_loaded_and_no_more_than_allowed_are_held(tmp_path: Path) -> None:
    held = library(tmp_path)
    for at in range(100):
        held.add(str(at), Scaled(at))
    again = library(tmp_path, resident=3)
    assert again.read(["7", "50"], 2) == [14, 100] and again.loads == 2
    assert again.read(["50", "7"], 1) == [50, 7] and again.loads == 2
    for at in range(20):
        again.get(str(at))
        assert len(again.held()) <= 3
    with pytest.raises(ValueError):
        again.read(["1", "2", "3", "4"], 1)


def test_a_block_is_taken_away_only_when_no_expert_reads_it(tmp_path: Path) -> None:
    held = library(tmp_path)
    for name, by in (("a", 2), ("b", 3), ("c", 5)):
        held.add(name, Scaled(by))
    held.register("first", ["a", "b"])
    with pytest.raises(ValueError):
        held.remove("a")
    held.remove("c")
    assert held.read(held.reading("first"), 4) == [8, 12] and "c" not in held
    with pytest.raises(KeyError):
        held.register("second", ["c"])
    held.forget("first")
    held.remove("a")
    assert library(tmp_path).names() == ("b",)


def test_the_chosen_reading_has_no_more_loss_than_the_experts_own() -> None:
    assert choose({"own": 0.5, "few": 0.3, "all": 0.4}, "own") == "few"
    assert choose({"own": 0.2, "few": 0.2, "all": 0.4}, "own") == "own"
    for losses in ({"own": 0.1, "few": 0.9}, {"own": 0.9, "few": 0.1}, {"own": 0.5}):
        picked = choose(losses, "own")
        assert losses[picked] <= losses["own"] and all(losses[picked] <= loss for loss in losses.values())


def test_the_blocks_most_read_are_given_first(tmp_path: Path) -> None:
    held = library(tmp_path)
    for name in "abc":
        held.add(name, Scaled(1))
    held.register("first", ["a", "b"])
    held.register("second", ["b"])
    assert held.most_read(2) == ("b", "a") and held.most_read(5) == ("b", "a")
    held.forget("second")
    held.forget("first")
    assert library(tmp_path).most_read(3) == ()


def test_the_names_nearest_a_query_are_found_after_reopening(tmp_path: Path) -> None:
    index = KeyIndex(tmp_path, 3)
    assert index.nearest(np.zeros(3), 2) == ()
    for at in range(50):
        index.add(f"name {at}", np.array([at, 0.0, 1.0]))
    again = KeyIndex(tmp_path, 3)
    assert len(again) == 50
    assert again.nearest(np.array([20.2, 0.0, 1.0]), 3) == ("name 20", "name 21", "name 19")
    assert len(again.nearest(np.zeros(3), 80)) == 50
    with pytest.raises(ValueError):
        again.add("wide", np.zeros(4))


def test_a_part_that_changes_is_written_back_and_few_are_held(tmp_path: Path) -> None:
    parts = PartStore(tmp_path, save, load, resident=2)
    for at in range(6):
        parts.put(str(at), Scaled(at))
        assert len(parts.held()) <= 2
    part = parts.get("1")
    assert isinstance(part, Scaled) and part.by == 1
    parts.put("1", Scaled(11))
    again = PartStore(tmp_path, save, load, resident=2).get("1")
    assert isinstance(again, Scaled) and again.by == 11 and "5" in parts and "9" not in parts
    with pytest.raises(KeyError):
        parts.get("9")
