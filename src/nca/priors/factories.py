"""Cached constructors for structural tree-shape prior automata."""

from __future__ import annotations

from functools import lru_cache

import numpy as np

from nca.priors import ArityPrior


@lru_cache(maxsize=32)
def format_prior(length: int) -> ArityPrior:
    """Unit-weight prefix counter as a prior automaton for a fixed length."""
    if not isinstance(length, int) or length < 1:
        raise ValueError("length must be a positive integer")
    states = length + 2
    transitions = np.full((states, 3), -1, dtype=np.int64)
    for state in range(1, states):
        for arity in range(3):
            if state - 1 + arity < states:
                transitions[state, arity] = state - 1 + arity
    final = np.full(states, -np.inf)
    final[0] = 0.0
    return ArityPrior((0, 1, 2), transitions, np.zeros((states, 3)), final, start=1)


@lru_cache(maxsize=32)
def complete_prior(length: int) -> ArityPrior | None:
    """Unit-weight complete binary skeleton prior inferred from length (§27.4).

    Leaves may be constants or unary negations of constants. Unsupported
    lengths return None. This is a structural prior, not a reader calibration.
    """
    if not isinstance(length, int) or length < 1:
        raise ValueError("length must be a positive integer")
    depth = (length + 1).bit_length() - 2
    if length + 1 > 3 * 2 ** depth:
        return None
    pending = [(depth,)]
    indices = {pending[0]: 0}
    transitions: list[list[int]] = []
    for stack in pending:
        row = [-1, -1, -1]
        if stack:
            head, rest = stack[0], stack[1:]
            successors = ({2: (head - 1, head - 1, *rest)} if head > 0 else
                          {0: rest, 1: (-1, *rest)} if head == 0 else {0: rest})
            for arity, target in successors.items():
                if target not in indices:
                    indices[target] = len(pending)
                    pending.append(target)
                row[arity] = indices[target]
        transitions.append(row)
    final = np.full(len(pending), -np.inf)
    final[indices[()]] = 0.0
    return ArityPrior((0, 1, 2), np.array(transitions, dtype=np.int64),
                      np.zeros((len(pending), 3)), final)


@lru_cache(maxsize=16)
def height_prior(height: int) -> ArityPrior:
    """Unit-weight prefix trees of height at most ``height`` (§27.4).

    Height counts edges; a constant has height zero. Unlike the complete-tree
    prior, branches may end early and unary nodes may occur at any level.
    """
    if not isinstance(height, int) or height < 0:
        raise ValueError("height must be a nonnegative integer")
    pending = [(height,)]
    indices = {pending[0]: 0}
    transitions: list[list[int]] = []
    for stack in pending:
        row = [-1, -1, -1]
        if stack:
            head, rest = stack[0], stack[1:]
            successors = {0: rest}
            if head:
                successors |= {1: (head - 1, *rest), 2: (head - 1, head - 1, *rest)}
            for arity, target in successors.items():
                if target not in indices:
                    indices[target] = len(pending)
                    pending.append(target)
                row[arity] = indices[target]
        transitions.append(row)
    final = np.full(len(pending), -np.inf)
    final[indices[()]] = 0.0
    return ArityPrior((0, 1, 2), np.array(transitions, dtype=np.int64),
                      np.zeros((len(pending), 3)), final)
