"""Scoped permissions for declared effects and cooperative resource gateways.

These checks mediate kernel calls, not arbitrary Python or native code. Hostile
implementations require process/OS isolation before receiving real resources.
Effect identifiers are supplied by contributors; the kernel defines none.
"""
from __future__ import annotations

from collections.abc import Callable, Iterator
from contextlib import contextmanager
from contextvars import ContextVar
from typing import Any, TypeVar

T = TypeVar("T")
_GRANTED: ContextVar[frozenset[str] | None] = ContextVar("nca_effect_grants", default=None)
_DECLARED: ContextVar[frozenset[str] | None] = ContextVar("nca_effect_declaration", default=frozenset())


class EffectDenied(PermissionError):
    """An invocation or mediated operation lacks declared/granted authority."""


@contextmanager
def effect_scope(granted: frozenset[str] | None) -> Iterator[None]:
    """Restrict permissions for this dynamic scope; nested scopes cannot widen.

    ``None`` inherits the current policy, unrestricted only at the host root.
    An empty set permits only experts explicitly declaring no effects.
    """
    parent = _GRANTED.get()
    allowed = parent if granted is None else granted if parent is None else parent & granted
    token = _GRANTED.set(allowed)
    try:
        yield
    finally:
        _GRANTED.reset(token)


def check_effects(declared: frozenset[str] | None) -> None:
    """Check admission before running any expert callback."""
    granted = _GRANTED.get()
    if granted is not None and (declared is None or not declared <= granted):
        raise EffectDenied("expert effects are unknown or exceed granted permissions")


def require_effect(effect: str) -> None:
    """Resource gateways call this before performing their own operation.

    A successful check requires an active expert declaration and host permission.
    It neither supplies a resource nor verifies that a gateway actually checks.
    """
    declared = _DECLARED.get()
    granted = _GRANTED.get()
    if declared is None or effect not in declared or (granted is not None and effect not in granted):
        raise EffectDenied(f"effect {effect!r} is not declared and granted")


@contextmanager
def expert_scope(declared: frozenset[str] | None) -> Iterator[None]:
    """Install an expert declaration and attenuate any active host policy."""
    check_effects(declared)
    token = _DECLARED.set(declared)
    # Preserve legacy unrestricted execution, but never widen an active policy.
    granted = _GRANTED.get()
    scope = declared if granted is not None else None
    try:
        with effect_scope(scope):
            yield
    finally:
        _DECLARED.reset(token)


def effect_call(declared: frozenset[str] | None, callback: Callable[..., T], *args: Any) -> T:
    """Run one expert callback with its own declaration and attenuated grants."""
    granted = _GRANTED.get()
    if _DECLARED.get() == declared and (granted is None or granted == declared):
        check_effects(declared)
        return callback(*args)
    with expert_scope(declared):
        return callback(*args)
