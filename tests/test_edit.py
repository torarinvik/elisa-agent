import itertools

import numpy as np
import pytest

pytest.importorskip("torch")

from nca.abi import Contract
from nca.modules import edit

VOCABULARY = ("true", "false", "not", "and", "or", "xor")


@pytest.mark.parametrize("reference", [False, True])
def test_edit_distance_matches_full_table_exhaustively(
        reference: bool, monkeypatch: pytest.MonkeyPatch) -> None:
    if reference:
        monkeypatch.setattr(edit, "_EDIT_NATIVE", None)
    texts = ["".join(s) for n in range(5) for s in itertools.product("ab", repeat=n)]
    texts += ["åβ", "βå", "🙂x", "x🙂", "\0a", "a\0", "e\u0301", "é", "CA", "ABC"]
    for a, b in itertools.product(texts, repeat=2):
        distance = edit.edit_distance(a, b)
        assert distance == edit._edit_distance_reference(a, b)
        assert distance == edit.edit_distance(b, a)
        assert abs(len(a) - len(b)) <= distance <= max(len(a), len(b))
        if a == b:
            assert distance == 0
    assert edit.edit_distance("CA", "ABC") == 3  # Unrestricted Damerau distance is 2.
    assert edit.edit_distance("🙂x", "x🙂") == 1
    assert edit.edit_distance("é", "e\u0301") == 2  # No Unicode normalization.


def test_batched_edit_reader_preserves_probabilities(
        monkeypatch: pytest.MonkeyPatch) -> None:
    native = edit._EDIT_NATIVE
    if getattr(native, "edit_distances", None) is None:
        pytest.skip("requires the native edit kernel")
    rng = np.random.default_rng(1703)
    texts = ["", "true", "ture", "nto", "åβ", "🙂x", "\0"]
    texts += ["".join(rng.choice(list("truefalsnox🙂"), size=int(rng.integers(1, 25))))
              for _ in range(100)]
    reader = edit.EditDistanceReader(VOCABULARY, Contract(("text.v1",), "distribution.v1"),
                                     "test.edit-reader")
    for text in texts:
        monkeypatch.setattr(edit, "_EDIT_NATIVE", None)
        expected = reader.invoke(text)
        monkeypatch.setattr(edit, "_EDIT_NATIVE", native)
        assert reader.invoke(text) == expected
    np.testing.assert_array_equal(reader.codes, [ord(c) for word in VOCABULARY for c in word])
    assert not reader.codes.flags.writeable
    assert not reader.offsets.flags.writeable


def test_native_edit_handles_unequal_lengths_in_both_orders() -> None:
    native = edit._EDIT_NATIVE
    if getattr(native, "edit_distance", None) is None:
        pytest.skip("requires the native edit kernel")
    rng = np.random.default_rng(61)
    for short, long in ((0, 500), (1, 500), (8, 500), (40, 1000)):
        a = "".join(rng.choice(list("ab🙂"), size=short))
        b = "".join(rng.choice(list("ab🙂"), size=long))
        expected = edit._edit_distance_reference(a, b)
        assert edit.edit_distance(a, b) == expected
        assert edit.edit_distance(b, a) == expected


def test_native_edit_empty_inputs_and_batch() -> None:
    native = edit._EDIT_NATIVE
    if getattr(native, "edit_distances", None) is None:
        pytest.skip("requires the native edit kernel")
    empty = np.array([], dtype=np.int64)
    text = np.array([ord("🙂")] * 100_000, dtype=np.int64)
    assert native.edit_distance(empty, empty) == 0
    assert native.edit_distance(empty, text) == len(text)
    assert native.edit_distance(text, empty) == len(text)
    assert native.edit_distances(empty, text, [0, 0, len(text)]) == [0, len(text)]


def test_native_edit_identical_and_near_identical_sequences() -> None:
    native = edit._EDIT_NATIVE
    if getattr(native, "edit_distance", None) is None:
        pytest.skip("requires the native edit kernel")
    rng = np.random.default_rng(162)
    values = rng.integers(0, 500, size=500, dtype=np.int64)
    assert native.edit_distance(values, values.copy()) == 0
    for index in (0, len(values) // 2, len(values) - 1):
        changed = values.copy()
        changed[index] = 1000
        assert native.edit_distance(values, changed) == 1
        assert native.edit_distance(changed, values) == 1
