import itertools
from dataclasses import dataclass, field
from typing import Any, Callable

import numpy as np
import pytest

from nca.abi import (App, Contract, Manifest, Term, Var, canonical_type, elem_type, format_type,
                     parse_type, resolve, seq_type, substitute, unify)
from nca.planner import Apply, Given, Map
from nca.router import Router, infer, sign_test


@dataclass
class Fn:
    manifest: Manifest
    fn: Callable[..., Any] | None = field(repr=False, default=None)

    def invoke(self, *inputs: Any) -> Any:
        assert self.fn is not None
        return self.fn(*inputs)


def fn(module_id: str, inputs: list[str], output: str) -> Fn:
    return Fn(Manifest(module_id, "1.0.0", Contract(tuple(inputs), output)))


A, B, C = "a.v1", "b.v1", "c.v1"


def test_infer_accepts_exactly_well_typed_plans() -> None:
    ab, bc = fn("ab", [A], B), fn("bc", [B], C)
    modules = [ab, bc]
    good = Apply(bc, (Apply(ab, (Given(A),)),))
    assert infer(modules, (A,), good) == C
    assert infer(modules, (B,), good) is None                     # input unavailable
    assert infer([bc], (A,), good) is None                       # module not installed
    assert infer(modules, (A,), Apply(bc, (Given(A),))) is None  # edge type mismatch
    split = fn("split", [A], "seq[a.v1]")
    mapped = Map(A, Apply(ab, (Given(A),)), Apply(split, (Given(A),)))
    assert infer([ab, split], (A,), mapped) == "seq[b.v1]"
    assert infer([ab, split], (A,), Map(B, Given(B), Apply(split, (Given(A),)))) is None


def test_upgrade_is_local_and_reversible() -> None:
    via_b, direct = fn("via-b", [B], C), fn("direct", [A], C)
    ab = fn("ab", [A], B)
    modules = [ab, via_b, direct, fn("other", [A], "d.v1")]
    router = Router()
    before = {g: router.route(modules, (A,), g) for g in (C, "d.v1")}
    assert before[C].module is via_b

    candidate = Apply(direct, (Given(A),))
    previous = router.upgrade(modules, (A,), C, candidate)
    assert router.route(modules, (A,), C) == candidate
    assert router.route(modules, (A,), "d.v1") == before["d.v1"]

    router.rollback(C, previous)
    assert {g: router.route(modules, (A,), g) for g in (C, "d.v1")} == before

    with pytest.raises(ValueError):
        router.upgrade(modules, (A,), C, Apply(ab, (Given(A),)))


def test_sign_test() -> None:
    current = [True] * 80 + [False] * 20
    better = [True] * 80 + [True] * 15 + [False] * 5
    accept, p = sign_test(current, better)
    assert accept and p == pytest.approx(0.5**15)
    accept, _ = sign_test(better, current)
    assert not accept
    assert sign_test(current, current) == (False, 1.0)


def random_term(rng: np.random.Generator, depth: int) -> Term:
    if depth == 0 or rng.random() < 0.3:
        return Var(f"v{rng.integers(3)}") if rng.random() < 0.3 else App(f"ns.c{rng.integers(3)}.v1")
    name = "seq" if rng.random() < 0.4 else f"ns.k{rng.integers(3)}.v2"
    return App(name, tuple(random_term(rng, depth - 1) for _ in range(int(rng.integers(1, 3)))))


def test_type_terms_round_trip_and_substitution_commutes_with_seq() -> None:
    """Canonical text denotes its term exactly, and substitution commutes with
    the sequence former (the premise of Theorem 1.2)."""
    rng = np.random.default_rng(0)
    for _ in range(500):
        term = random_term(rng, 4)
        text = format_type(term)
        assert parse_type(text) == term
        assert elem_type(seq_type(text)) == text
        binding = {f"v{i}": random_term(rng, 2) for i in range(3)}
        assert (substitute(parse_type(seq_type(text)), binding)
                == parse_type(seq_type(format_type(substitute(term, binding)))))


def test_malformed_and_noncanonical_types_are_rejected() -> None:
    assert canonical_type(" pair[ a.v1 , seq[b.v1] ] ") == "pair[a.v1,seq[b.v1]]"
    for bad in ("", "seq[", "seq[]", "a]", "a b", "seq[a]]", "pair[a,]", "[a]", "a$"):
        with pytest.raises(ValueError):
            parse_type(bad)
    with pytest.raises(ValueError, match="canonical"):
        Contract(("pair[a.v1, b.v1]",), C)
    assert Contract(("seq[?a]",), "length.v1").free == {"a"}


def test_unify_returns_most_general_unifiers() -> None:
    """Whenever a substitution unifies two terms, ``unify`` succeeds and returns
    a unifier ``σ`` with ``τ = τ ∘ σ`` for every unifier ``τ`` (Theorem 2.7).
    Unifiers ``τ`` are enumerated over ground terms of depth at most 1."""
    rng = np.random.default_rng(5)
    names = ["a", "b", "c"]
    constants = [App("k0"), App("k1")]
    ground = [*constants, *(App("box", (t,)) for t in constants),
              *(App("pair", (s, t)) for s in constants for t in constants)]

    def small(depth: int) -> Term:
        if depth == 0 or rng.random() < 0.35:
            return Var(str(rng.choice(names))) if rng.random() < 0.5 else constants[int(rng.integers(2))]
        if rng.random() < 0.5:
            return App("box", (small(depth - 1),))
        return App("pair", (small(depth - 1), small(depth - 1)))

    unified = factored = 0
    for _ in range(300):
        left, right = small(3), small(3)
        binding: dict[str, Term] = {}
        found = unify(left, right, binding)
        unifiers = [dict(zip(names, values)) for values in itertools.product(ground, repeat=3)
                    if substitute(left, dict(zip(names, values)))
                    == substitute(right, dict(zip(names, values)))]
        if not found:
            assert not unifiers
            continue
        unified += 1
        assert resolve(left, binding) == resolve(right, binding)
        factored += bool(unifiers)
        for tau in unifiers:
            assert all(substitute(resolve(Var(v), binding), tau) == tau[v] for v in names)
    assert unified > 50 and factored > 30
