"""Faithful immutable scalar/tuple values in canonical model data (§36.11)."""

from collections.abc import Hashable
from typing import Any

from nca.objects import Json, canonical


def encode_value(value: Any) -> Json:
    """Keep scalars unchanged; recursively tag tuples. Unsupported values fail."""
    if type(value) is tuple:
        return {"$tuple": [encode_value(item) for item in value]}
    if type(value) not in (str, int, float, bool, type(None)):
        raise TypeError("model values must be JSON scalars or tuples")
    canonical(value)
    return value


def decode_value(data: Json) -> Hashable:
    """Decode supported model data without coercing scalar values or tuple shape."""
    if type(data) is dict and set(data) == {"$tuple"} and type(data["$tuple"]) is list:
        return tuple(decode_value(item) for item in data["$tuple"])
    if type(data) not in (str, int, float, bool, type(None)):
        raise ValueError("invalid encoded model value")
    canonical(data)
    return data
