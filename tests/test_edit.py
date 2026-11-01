import itertools

import numpy as np
import pytest

pytest.importorskip("torch")

from nca.modules import words


@pytest.mark.parametrize("reference", [False, True])
def test_edit_distance_matches_full_table_exhaustively(
        reference: bool, monkeypatch: pytest.MonkeyPatch) -> None:
    if reference:
        monkeypatch.setattr(words, "_EDIT_NATIVE", None)
    texts = ["".join(s) for n in range(5) for s in itertools.product("ab", repeat=n)]
    texts += ["åβ", "βå", "🙂x", "x🙂", "\0a", "a\0", "e\u0301", "é", "CA", "ABC"]
    for a, b in itertools.product(texts, repeat=2):
        distance = words.edit_distance(a, b)
        assert distance == words._edit_distance_reference(a, b)
        assert distance == words.edit_distance(b, a)
        assert abs(len(a) - len(b)) <= distance <= max(len(a), len(b))
        if a == b:
            assert distance == 0
    assert words.edit_distance("CA", "ABC") == 3  # Unrestricted Damerau distance is 2.
    assert words.edit_distance("🙂x", "x🙂") == 1
    assert words.edit_distance("é", "e\u0301") == 2  # No Unicode normalization.


def test_batched_edit_reader_preserves_probabilities(
        monkeypatch: pytest.MonkeyPatch) -> None:
    native = words._EDIT_NATIVE
    if getattr(native, "edit_distances", None) is None:
        pytest.skip("requires the native edit kernel")
    rng = np.random.default_rng(1703)
    texts = ["", "true", "ture", "nto", "åβ", "🙂x", "\0"]
    texts += ["".join(rng.choice(list("truefalsnox🙂"), size=int(rng.integers(1, 25))))
              for _ in range(100)]
    reader = words.EditReader()
    for text in texts:
        monkeypatch.setattr(words, "_EDIT_NATIVE", None)
        expected = reader.invoke(text)
        monkeypatch.setattr(words, "_EDIT_NATIVE", native)
        assert reader.invoke(text) == expected
    np.testing.assert_array_equal(words._VOCABULARY_CODES,
                                  [ord(c) for word in words.VOCABULARY for c in word])
    assert not words._VOCABULARY_CODES.flags.writeable
    assert not words._VOCABULARY_OFFSETS.flags.writeable


def test_native_edit_handles_unequal_lengths_in_both_orders() -> None:
    native = words._EDIT_NATIVE
    if getattr(native, "edit_distance", None) is None:
        pytest.skip("requires the native edit kernel")
    rng = np.random.default_rng(61)
    for short, long in ((0, 500), (1, 500), (8, 500), (40, 1000)):
        a = "".join(rng.choice(list("ab🙂"), size=short))
        b = "".join(rng.choice(list("ab🙂"), size=long))
        expected = words._edit_distance_reference(a, b)
        assert words.edit_distance(a, b) == expected
        assert words.edit_distance(b, a) == expected
