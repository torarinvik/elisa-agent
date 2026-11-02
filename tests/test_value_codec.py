"""Structural model values round-trip without string conversion or type loss."""

from typing import Any

import pytest

from nca.value_codec import decode_value, encode_value


@pytest.mark.parametrize("value", [None, True, 3, 1.5, "$tuple", (), (1,),
                                    ((None, False), ("é", (2, 3.5)))])
def test_structural_round_trip(value: Any) -> None:
    restored = decode_value(encode_value(value))
    assert restored == value and type(restored) is type(value)


@pytest.mark.parametrize("value", [[], {}, frozenset({1}), float("nan")])
def test_unsupported_values_fail(value: Any) -> None:
    with pytest.raises((TypeError, ValueError)):
        encode_value(value)


@pytest.mark.parametrize("data", [{"$tuple": "wrong"}, {"unknown": []}, []])
def test_malformed_records_fail(data: Any) -> None:
    with pytest.raises(ValueError):
        decode_value(data)


def test_learned_decoder_uses_the_structural_codec() -> None:
    from nca.abi import Contract
    from nca.discovery import Decoder, decoder_object

    key = (("$tuple", None), 3)
    head = Decoder(Contract(("state",), "target"), {key: ("label", True)}, ("missing",), 1)
    restored = decoder_object(head, size=0).load()
    assert restored.invoke(key) == ("label", True)
    assert restored.invoke(("new",)) == ("missing",)
