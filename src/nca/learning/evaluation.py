"""Explicit continuations for recognized unary compositions (§36.69)."""

from collections.abc import Callable, Sequence
from contextlib import ExitStack
from typing import Any

from nca.abi import Module
from nca.effects import expert_scope, invoke_scoped, same_effect_scope


def invoke_unary(module: Module, inputs: Sequence[Any],
                 split: Callable[[Module], tuple[Module, Module] | None]) -> Any:
    """Evaluate a composition body under its caller's existing owner scope.

    ``split`` recognizes structural source/head pairs, returning None for opaque
    implementations. Descending enters the source's declaration; completing it
    restores the parent before its unary head runs. Every remaining scope is
    restored on failure. Inputs and metadata must stay frozen. Only the source
    spine is unfolded; heads and opaque implementations may themselves recurse.
    """
    frames: list[tuple[Module, ExitStack | None]] = []
    seen: set[int] = set()
    with ExitStack() as cleanup:
        while (parts := split(module)) is not None:
            if id(module) in seen:
                raise ValueError("cyclic unary composition")
            seen.add(id(module))
            source, head = parts
            scope = None
            declared = source.manifest.effects
            if not same_effect_scope(declared):
                scope = cleanup.enter_context(ExitStack())
                scope.enter_context(expert_scope(declared))
            frames.append((head, scope))
            module = source
        result = module.invoke(*inputs)
        while frames:
            head, scope = frames.pop()
            if scope is not None:
                scope.close()
            result = invoke_scoped(head, result)
        return result
