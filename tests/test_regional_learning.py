"""Training failures acquire conditional experts without restricting target values."""

import random
from collections.abc import Callable, Sequence
from dataclasses import dataclass, replace
from typing import Any

import pytest

from nca.abi import Calls, Contract, Manifest
from nca.affine_learning import fit_affine
from nca.discovery import Proposal, discover
from nca.regional_learning import RegionalExpert, propose_regional_experts


@dataclass
class Expert:
    manifest: Manifest
    function: Callable[..., Any]

    def invoke(self, *values: Any) -> Any:
        return self.function(*values)


CONTRACT = Contract(("input",), "output")


def test_failures_acquire_continuous_specialist_on_training_region_only() -> None:
    incumbent = Expert(Manifest("incumbent", "1", CONTRACT), lambda x: x)
    feature = Expert(Manifest("feature", "1", replace(CONTRACT, output="key")), lambda x: x >= 0)
    rng = random.Random(3630)
    rows = [(rng.uniform(-1, 1),) for _ in range(1000)]
    targets = [x if x < 0 else 2 * x + 1 for x, in rows]
    seen = []

    def acquire(train: Sequence[tuple[Any, ...]], labels: Sequence[Any]) -> list[Proposal]:
        seen.append(tuple(train))
        return [Proposal(fit_affine(CONTRACT, [row[0] for row in train], labels, cost=1))]

    def propose(train: Sequence[tuple[Any, ...]], labels: Sequence[Any]) -> list[Proposal]:
        return propose_regional_experts(incumbent, feature, acquire, train, labels,
                    lambda a, b: abs(a - b) < 1e-9, max_regions=1, overhead_cost=0)

    result = discover(incumbent, propose, rows, targets, lambda a, b: abs(a - b) < 1e-9)
    assert seen == [tuple(row for row in rows[:500] if row[0] >= 0)]
    assert result.chosen is not None
    assert sum(result.trials[0].outcomes) == 500
    assert all(result.chosen.expert.invoke(x) == incumbent.invoke(x) for x in (-0.93, -0.17))


def test_region_budget_uses_error_count_and_keeps_successful_controls() -> None:
    incumbent = Expert(Manifest("incumbent", "1", CONTRACT), lambda x: [x[1]])
    feature = Expert(Manifest("feature", "1", replace(CONTRACT, output="key")), lambda x: x[0])
    rows = [(("a", 0),), (("a", 1),), (("b", 2),), (("b", 3),), (("b", 4),), (("c", 5),)]
    labels = [[0], [99], [88], [77], [4], [5]]  # Targets need not be hashable.
    seen = []

    def acquire(train: Any, targets: Any) -> list[Proposal]:
        seen.append((train, targets))
        return []

    assert propose_regional_experts(incumbent, feature, acquire, rows, labels,
                lambda a, b: a == b, max_regions=1, overhead_cost=0) == []
    assert seen == [(tuple(rows[2:5]), tuple(labels[2:5]))]
    seen.clear()
    propose_regional_experts(incumbent, feature, acquire, rows, [[x[0][1]] for x in rows],
                            lambda a, b: a == b, max_regions=1, overhead_cost=0)
    assert not seen


def test_regional_dispatch_preserves_slots_and_conservative_metadata() -> None:
    contract = replace(CONTRACT, slots=((("input",), "slot-output"),))
    invoked = []

    def branch(name: str) -> Callable[..., Any]:
        def invoke(*values: Any) -> str:
            invoked.append(name)
            return name
        return invoke

    incumbent = Expert(Manifest("a", "1", contract, cost=2, calls=(Calls(1, 2),),
                                effects=frozenset({"io"})), branch("incumbent"))
    specialist = Expert(Manifest("b", "1", contract, cost=5, calls=(Calls(3, 0),)),
                        branch("specialist"))
    feature = Expert(Manifest("f", "1", replace(contract, output="key"), cost=3,
                              calls=(Calls(0, 1),), effects=frozenset()), lambda slot, x: x)
    regional = RegionalExpert(incumbent, feature, True, specialist, 1)
    assert regional.invoke(None, False) == "incumbent"
    assert regional.invoke(None, True) == "specialist"
    assert invoked == ["incumbent", "specialist"]
    assert regional.manifest.contract == contract
    assert regional.manifest.cost == 11
    assert regional.manifest.calls == (Calls(4, 3),)
    assert regional.manifest.effects is None and regional.manifest.expected_calls is None
    with pytest.raises(ValueError, match="external contract"):
        RegionalExpert(incumbent, feature, True, feature, 0)
