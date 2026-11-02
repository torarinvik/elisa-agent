"""Results of pure, identified experts reused by content (§28.5)."""

from typing import Any

import numpy as np
import pytest
import torch

from nca.abi import Choice, Contract, Manifest, Message, Request
from nca.cache import ResultCache, value_digest
from nca.planner import Apply, Given
from nca.runtime import BudgetExceeded, execute
from nca.workspace import Workspace


def test_digests_identify_values_by_content() -> None:
    assert value_digest((1, "a", None)) == value_digest([1, "a", None])
    assert value_digest({"b": 1, "a": 2}) == value_digest({"a": 2, "b": 1})
    assert value_digest(1) != value_digest(1.0) != value_digest(True)
    assert value_digest("1") != value_digest(1)
    assert value_digest(["ab"]) != value_digest(["a", "b"])
    assert value_digest(Choice(0, 3)) != value_digest(Choice(1, 3))
    array = np.arange(6, dtype=np.float32).reshape(2, 3)
    assert value_digest(array) == value_digest(array.copy())
    assert value_digest(array) != value_digest(array.reshape(3, 2))
    assert value_digest(array) != value_digest(array.astype(np.float64))
    assert value_digest(array.T) == value_digest(np.ascontiguousarray(array.T))
    assert value_digest(torch.from_numpy(array)) == value_digest(array)


@pytest.mark.parametrize("value", [float("nan"), {1: 2}, object(), np.array([object()]),
                                   [1, object()]])
def test_values_without_a_canonical_encoding_have_no_digest(value: Any) -> None:
    assert value_digest(value) is None


def test_cache_evicts_the_least_recently_used_entry() -> None:
    cache = ResultCache(limit=2)
    cache.store("a", 1)
    cache.store("b", 2)
    assert cache.lookup("a") == (True, 1)
    cache.store("c", 3)
    assert cache.lookup("b") == (False, None)
    assert len(cache) == 2 and cache.stats.hits == 1 and cache.stats.misses == 1


class Counting:
    def __init__(self, effects: frozenset[str] | None = frozenset(),
                 identity: str | None = "sha256:square", request: bool = False) -> None:
        self.manifest = Manifest("square", "1.0.0", Contract(("int",), "int"), cost=2.0,
                                 effects=effects)
        self.identity = identity
        self.request = request
        self.calls = 0

    def invoke(self, value: int) -> Any:
        self.calls += 1
        return Request("int", (("int", value),), value) if self.request else value * value


class Square:
    manifest = Manifest("square-root", "1.0.0", Contract(("int",), "int"), cost=1.0,
                        effects=frozenset())

    def invoke(self, value: int) -> int:
        return value * value


class Kernel:
    def resolve(self, request: Request, chain: tuple[str, ...]) -> Apply:
        return Apply(Square(), (Given("int"),))


def run(module: Counting, value: Any, cache: ResultCache, budget: int = 10,
        workspace: Workspace | None = None) -> Any:
    route = Apply(module, (Given("int"),))
    return execute(route, [Message("int", value, "input")],
                   workspace if workspace is not None else Workspace(), budget,
                   Kernel(), cache=cache).payload


def test_a_hit_skips_the_invocation_and_charges_nothing() -> None:
    module, cache, workspace = Counting(), ResultCache(), Workspace()
    assert run(module, 7, cache, workspace=workspace) == 49
    assert run(module, 7, cache, budget=0, workspace=workspace) == 49
    assert module.calls == 1 and workspace.spent == 2.0
    assert run(module, 8, cache) == 64 and module.calls == 2
    with pytest.raises(BudgetExceeded):
        run(module, 9, cache, budget=0)


@pytest.mark.parametrize("module", [Counting(effects=None), Counting(effects=frozenset({"io"})),
                                    Counting(identity=None)],
                         ids=["undeclared", "effectful", "unidentified"])
def test_only_pure_identified_experts_are_cached(module: Counting) -> None:
    cache = ResultCache()
    run(module, 3, cache)
    run(module, 3, cache)
    assert module.calls == 2 and len(cache) == 0


def test_inputs_without_digests_and_results_from_requests_are_not_cached() -> None:
    module, cache = Counting(), ResultCache()
    run(module, float("nan"), cache)
    assert len(cache) == 0
    asking = Counting(request=True)
    assert run(asking, 4, cache) == 16
    assert run(asking, 4, cache) == 16
    assert asking.calls == 2 and len(cache) == 0
