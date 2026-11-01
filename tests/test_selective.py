from collections.abc import Callable, Iterator, Sequence
from dataclasses import dataclass
from typing import Any

import numpy as np
import pytest

torch = pytest.importorskip("torch")

from torch import nn

from nca.abi import NOTHING, Contract, Demand, Manifest, SequenceDemand
from nca.ladder import Rung, SecondLook, allocate_risk, ladder, refine
from nca.planner import plan_stable
from nca.selective import build_ladders, solve


@dataclass
class Constant:
    """An expert whose output distribution ignores its input."""

    manifest: Manifest
    output: tuple[float, ...]

    def invoke(self, value: Any) -> tuple[float, ...]:
        return self.output


def constant(module_id: str, output: tuple[float, ...], cost: float,
             contract: Contract = Contract(("x",), "dist")) -> Constant:
    return Constant(Manifest(module_id, "1.0.0", contract, cost=cost), output)


def test_ladder_orders_experts_by_cost_and_refines_until_target() -> None:
    sure = constant("sure", (0.001, 0.999), 10.0)
    unsure = constant("unsure", (0.4, 0.6), 1.0)
    other = constant("other", (0.5, 0.5), 0.1, Contract(("y",), "dist"))
    rungs = ladder([sure, other, unsure], Contract(("x",), "dist"))
    assert [r.module for r in rungs] == [unsure, sure]

    result = refine([0, 0, 0], [rungs] * 3, delta=0.01)
    assert not result.abstained and result.bound <= 0.01
    assert result.cost == pytest.approx(3 * 1.0 + 3 * 10.0)
    assert refine([0, 0], [rungs[:1]] * 2, delta=0.01).abstained


def test_second_look_averages_views_and_costs_more() -> None:
    @dataclass
    class Echo:
        manifest: Manifest

        def invoke(self, value: float) -> tuple[float, ...]:
            return (value, 1.0 - value)

    base = Echo(Manifest("echo", "1.0.0", Contract(("x",), "dist"), cost=2.0))
    look = SecondLook(base, lambda v: [0.0, 1.0], count=2)
    assert look.manifest.contract == base.manifest.contract
    assert look.manifest.cost == pytest.approx(6.0)
    assert look.invoke(0.5) == pytest.approx((0.5, 0.5))


def test_calibration_fits_temperature() -> None:
    overconfident = constant("over", (0.01, 0.99), 1.0)
    rung = Rung(overconfident)
    labels = torch.tensor([1] * 7 + [0] * 3)
    rung.calibrate([0] * 10, labels)
    assert rung.temperature() > 1.0
    assert rung.reading(rung.observe(0))[1].item() == pytest.approx(0.7, abs=0.02)


def test_segmenter_alternatives_merge_narrowest_gap_first() -> None:
    from nca.modules.segmenter import Segmenter

    image = np.zeros((28, 80), dtype=np.float32)
    for start, end in ((2, 10), (20, 24), (29, 33), (50, 58)):
        image[5:20, start:end] = 1.0
    alternatives = list(Segmenter().alternatives(torch.from_numpy(image)))
    assert [len(a) for a in alternatives] == [4, 3, 3, 3]
    assert np.isclose(alternatives[1][1].sum().item(), 15 * 8, rtol=1e-2)


@dataclass
class Splitter:
    """Splits a string into characters; alternatives drop the last character."""

    manifest: Manifest = Manifest("split", "1.0.0", Contract(("text",), "seq[ch]"))

    def invoke(self, text: str) -> list[str]:
        return list(text)

    def alternatives(self, text: str) -> Iterator[list[str]]:
        yield list(text)
        yield list(text[:-1])


@dataclass
class Joiner:
    """Reads elements at even positions of odd-length sequences only."""

    manifest: Manifest = Manifest("join", "1.0.0", Contract(("seq[read]",), "out"))

    def demand(self, index: int, demand: Demand) -> Demand:
        def element(i: int, n: int) -> Demand:
            return None if n % 2 and i % 2 == 0 else NOTHING
        return SequenceDemand(element)

    def invoke(self, readings: list[int | None]) -> tuple[int | None, ...]:
        return tuple(readings)


@dataclass
class Argmax:
    manifest: Manifest = Manifest("argmax", "1.0.0", Contract(("dist",), "read"))

    def invoke(self, dist: tuple[float, ...] | None) -> int | None:
        return None if dist is None else int(np.argmax(dist))


def test_solve_reads_only_demanded_elements_of_an_accepted_alternative() -> None:
    reader = constant("reader", (0.001, 0.999), 5.0, Contract(("ch",), "dist"))
    modules = [Splitter(), Joiner(), Argmax(), reader]
    route = plan_stable(modules, ("text",), "out")
    assert route is not None
    ladders = build_ladders(modules, route, {"dist": ([0, 0], torch.tensor([1, 1]))})
    answer = solve(route, ladders, "abcd", delta=1.0)
    # "abcd" has even length, so the consumer reads nothing; "abc" is accepted
    # and only its two even positions are read.
    assert answer.value == (1, None, 1)
    assert answer.cost == pytest.approx(2 * 5.0)
    assert not answer.abstained


def test_practice_queue_and_fine_tuning() -> None:
    from nca.practice import practice, proportional, queue

    torch.manual_seed(0)
    risks = torch.tensor([0.05, 0.6, 0.2, 0.9])
    assert queue(risks, 0.2).tolist() == [1, 2, 3]
    drawn = proportional(torch.tensor([0.0, 0.0, 1.0, 1.0]), 2, seed=0)
    assert sorted(drawn.tolist()) == [2, 3]

    network = nn.Sequential(nn.Flatten(), nn.Linear(28 * 28, 10))
    glyphs, labels = torch.rand(16, 28, 28), torch.full((16,), 3)
    student = practice(network, glyphs, labels, (glyphs[:8], labels[:8]), epochs=3, seed=0)
    assert student is not network and not student.training
    with torch.no_grad():
        assert (student(glyphs[:, None]).argmax(dim=1) == 3).float().mean() > \
            (network(glyphs[:, None]).argmax(dim=1) == 3).float().mean()


def test_risk_is_measured_against_the_decision() -> None:
    from nca.ladder import risk

    reading = torch.tensor([0.27, 0.02, 0.01, 0.70])  # three operators and "none"
    assert risk(reading) == pytest.approx(0.30)
    assert risk(reading, range(3)) == pytest.approx(0.10)


def test_restricted_decision_gets_its_own_temperature() -> None:
    # Among operator-labeled inputs the expert is right 60% of the time,
    # though its output looks sure; the restricted temperature reflects that.
    rung = Rung(constant("op", (0.9, 0.05, 0.03, 0.02), 1.0))
    labels = torch.tensor([0] * 6 + [1] * 4 + [3] * 10)
    rung.calibrate([0] * 20, labels)
    assert rung.risk(rung.observe(0), range(3)) == pytest.approx(0.4, abs=0.05)
    assert set(rung.temperatures) == {None, (0, 1, 2)}


@dataclass
class Table:
    """An expert reading item ``value`` as row ``value`` of a fixed table."""

    manifest: Manifest
    rows: list[tuple[float, ...]]

    def invoke(self, value: int) -> tuple[float, ...]:
        return self.rows[value]


def test_floors_never_change_answers() -> None:
    """Abstaining early by a floor gives the same answers and abstentions,
    never at greater cost (§22.3)."""
    rng = np.random.default_rng(0)
    contract = Contract(("x",), "dist")
    early_stops = 0
    for _ in range(200):
        n = int(rng.integers(1, 6))
        rungs = ladder([Table(Manifest(f"r{c}", "1.0.0", contract, cost=float(10 ** c)),
                              [tuple(rng.dirichlet([0.3, 0.3, 0.3]).tolist()) for _ in range(n)])
                        for c in range(3)], contract)
        delta = float(rng.choice([0.3, 0.1, 0.01]))
        plain = refine(list(range(n)), [rungs] * n, delta)
        early = refine(list(range(n)), [rungs] * n, delta, additive_floor=True)
        assert early.abstained == plain.abstained and early.cost <= plain.cost
        if not plain.abstained:
            assert early.bound == plain.bound
            assert all(torch.equal(a, b) for a, b in zip(early.readings, plain.readings))
        early_stops += early.cost < plain.cost

        def floor(readings: list[torch.Tensor], risk: Any, fixed: frozenset[int]) -> float:
            return sum(risk(i, None) for i in fixed)

        declared = refine(list(range(n)), [rungs] * n, delta, floor=floor)
        assert declared.abstained == plain.abstained and declared.cost == early.cost
    assert early_stops > 0


def test_stopping_rule_only_abstains() -> None:
    contract = Contract(("x",), "dist")
    rungs = ladder([constant("unsure", (0.4, 0.6), 1.0, contract),
                    constant("sure", (0.01, 0.99), 10.0, contract)], contract)
    assert not refine([0, 0], [rungs] * 2, 0.05, stop=lambda state: False).abstained
    stopped = refine([0, 0], [rungs] * 2, 0.05, stop=lambda state: True)
    assert stopped.abstained and stopped.cost == pytest.approx(2.0)


@pytest.mark.parametrize("priorities", [[0.0, 0.0], [0.0, 3.0, 1.0],
                                       [1e308, 1e308], [1e-320, 2e-320]])
def test_risk_allocation_uses_current_bound(priorities: list[float]) -> None:
    # Reuse the same priorities while the current posterior risk changes.
    for bound in (0.0, 0.001, 0.4, 1.0):
        charges = allocate_risk(bound, priorities)
        assert all(c >= 0 for c in charges)
        assert sum(charges) == pytest.approx(bound)
        assert len(charges) == len(priorities)


@pytest.mark.parametrize("bound, priorities", [(float("nan"), [1.0]),
                                               (-0.1, [1.0]), (0.1, []),
                                               (0.1, [-1.0]), (0.1, [float("inf")])])
def test_risk_allocation_rejects_invalid_inputs(bound: float, priorities: list[float]) -> None:
    with pytest.raises(ValueError):
        allocate_risk(bound, priorities)


def test_distribution_revision_changes_even_for_identical_readings() -> None:
    from nca.ladder import Distribution

    rungs = [Rung(constant(str(i), (0.4, 0.6), float(i + 1))) for i in range(2)]
    revisions: list[int] = []
    observations: list[torch.Tensor] = []

    def account(readings: Sequence[torch.Tensor],
                risk: Callable[[int, Any], float],
                distribution: Callable[[int, Any], torch.Tensor],
                ) -> dict[int, float]:
        assert isinstance(distribution, Distribution)
        revisions.append(distribution.revision(0))
        observations.append(readings[0].clone())
        return {0: 1.0}

    refine([0], [rungs], 0.01, certificate=account)
    assert revisions == [0, 1]
    assert torch.equal(*observations)


def test_native_risk_shares_match_reference(monkeypatch: pytest.MonkeyPatch) -> None:
    from nca import ladder as ladder_module

    if getattr(ladder_module._NATIVE, "risk_shares", None) is None:
        pytest.skip("native risk shares are not built")
    rng = np.random.default_rng(30)
    cases = [rng.lognormal(0, 100, size=575).tolist() for _ in range(30)]
    native = [allocate_risk(0.2, priorities) for priorities in cases]
    monkeypatch.setattr(ladder_module, "_NATIVE", None)
    for priorities, actual in zip(cases, native):
        assert actual == pytest.approx(allocate_risk(0.2, priorities), abs=1e-15)
        assert sum(actual) == pytest.approx(0.2, abs=1e-15)
