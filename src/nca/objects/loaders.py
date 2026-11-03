"""Stable loader identifiers for primitive entries (THEORY §28.9).

A primitive's ``entry`` is part of its reference, so it must not change when
code moves. Distributions register loaders under the ``nca.loaders``
entry-point group: the name is the identifier stored in primitives (a stable
name such as ``"vendor/model@1"``, or a legacy import path kept as an alias)
and the value is the factory's current location. An identifier registered
with two different locations is ambiguous and refused, so no installed
distribution can redirect another's loader; other identifiers still resolve
(``NCA.resolveLoader_unrelated``). Unregistered ``"module:attribute"``
entries are imported directly.
"""

from __future__ import annotations

import importlib
from collections.abc import Callable, Iterable, Mapping
from functools import lru_cache
from importlib import metadata
from typing import Any

GROUP = "nca.loaders"


def location(registrations: Iterable[tuple[str, str]], name: str) -> str | None:
    """The one location registered for ``name``, or ``None`` if it has none or
    several (``NCA.resolveLoader``)."""
    found = {place for registered, place in registrations if registered == name}
    return next(iter(found)) if len(found) == 1 else None


@lru_cache(maxsize=1)
def registered() -> Mapping[str, frozenset[str]]:
    """Every location registered for each identifier by installed distributions."""
    found: dict[str, set[str]] = {}
    for entry in metadata.entry_points(group=GROUP):
        found.setdefault(entry.name, set()).add(entry.value)
    return {name: frozenset(places) for name, places in found.items()}


def refresh() -> None:
    """Forget cached registrations, after installing or removing distributions."""
    registered.cache_clear()


def _import(place: str) -> Any:
    module_name, separator, attribute = place.partition(":")
    if not separator or not module_name or not attribute:
        raise LookupError(f"loader {place!r} is not registered under {GROUP}")
    target: Any = importlib.import_module(module_name)
    for part in attribute.split("."):
        target = getattr(target, part)
    return target


def resolve(entry: str) -> Callable[..., Any]:
    """The factory for ``entry``: its registered location if any, otherwise
    ``entry`` itself read as ``"module:attribute"``."""
    places = registered().get(entry)
    if places is None:
        return _import(entry)
    if len(places) != 1:
        raise ValueError(f"loader {entry!r} is registered at {sorted(places)}")
    return _import(next(iter(places)))
