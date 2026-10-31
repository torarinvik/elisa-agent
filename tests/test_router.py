from dataclasses import dataclass, field
from typing import Any, Callable

import pytest

from nca.abi import Contract, Manifest
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
