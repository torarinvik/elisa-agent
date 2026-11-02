from collections.abc import Callable, Iterator, Sequence
from dataclasses import dataclass
from decimal import Decimal
from fractions import Fraction
import math
import random
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


def test_decision_key_reuses_immutable_tuples_but_copies_mutable_groups() -> None:
    from nca.ladder import decision_key

    immutable = ((0, 1), 2, (3, 4))
    assert decision_key(immutable) is immutable
    group = [0, 1]
    mutable = (group, 2)
    before = decision_key(mutable)
    group.append(3)
    assert before == ((0, 1), 2)
    assert decision_key(mutable) == ((0, 1, 3), 2)


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


def test_largest_charge_can_spend_more_than_a_feasible_alternative() -> None:
    from nca.ladder import charge_per_cost

    a0 = Rung(constant("a0", (0.4, 0.6), 1.0))
    a1 = Rung(constant("a1", (0.001, 0.999), 100.0))
    b0 = Rung(constant("b0", (0.3, 0.7), 1.0))
    b1 = Rung(constant("b1", (0.001, 0.999), 1.0))
    result = refine([0, 0], [[a0, a1], [b0, b1]], 0.41)
    assert not result.abstained and result.cost == 102.0
    alternative_bound = a0.risk(a0.observe(0)) + b1.risk(b1.observe(0))
    assert alternative_bound < 0.41
    assert a0.cost + b0.cost + b1.cost == 3.0
    cost_aware = refine([0, 0], [[a0, a1], [b0, b1]], 0.41, priority=charge_per_cost)
    assert not cost_aware.abstained and cost_aware.cost == 3.0
    assert cost_aware.bound == pytest.approx(alternative_bound)


def test_climb_priorities_are_generic_and_validate_scores() -> None:
    from nca.ladder import charge_per_cost

    assert charge_per_cost(0, 0.1, 0.0) == math.inf
    for cost in (-1.0, math.inf, math.nan):
        with pytest.raises(ValueError, match="cost"):
            charge_per_cost(0, 0.1, cost)
    bottom = Rung(constant("bottom", (0.4, 0.6), 1.0))
    top = Rung(constant("top", (0.01, 0.99), 2.0))
    with pytest.raises(ValueError, match="priority"):
        refine([0], [[bottom, top]], 0.1, priority=lambda *_: math.nan)
    indices: list[int] = []
    def custom(index: int, charge: float, cost: float) -> float:
        indices.append(index)
        return float(index)
    result = refine([0, 0], [[bottom, top]] * 2, 0.5, priority=custom)
    assert result.cost == 4.0 and indices == [0, 1]


def test_cost_aware_priority_resolves_rounded_ratio_ties() -> None:
    from nca.ladder import _cost_aware_choice, _ratio_greater, charge_per_cost

    bottom = Rung(constant("bottom", (0.4, 0.6), 1.0))

    def select(charges: list[float], costs: list[float]) -> int:
        ladders = [[bottom, Rung(constant(f"top-{i}", (0.1, 0.9), cost))]
                   for i, cost in enumerate(costs)]
        return _cost_aware_choice(list(range(len(costs))), dict(enumerate(charges)),
                                  ladders, [0] * len(costs))

    assert select([0.2, 0.4], [5e-324, 5e-324]) == 1  # Both divide to infinity.
    assert select([1e-200, 1e-100], [1e300, 1e300]) == 1  # Both divide to zero.
    assert select([0.25, 0.5], [0.5, 1.0]) == 0  # Exact ties stay stable.
    assert select([0.4, 0.0], [5e-324, 0.0]) == 1  # Free beats an overflow.
    with pytest.raises(ValueError, match="cost"):
        select([0.4, 0.0], [0.0, -1.0])
    first = Rung(constant("first", (0.2, 0.8), 1.0))
    second = Rung(constant("second", (0.4, 0.6), 1.0))
    top = Rung(constant("top", (0.001, 0.999), 5e-324))
    result = refine([0, 0], [[first, top], [second, top]], 0.3,
                    priority=charge_per_cost)
    assert not result.abstained
    assert result.readings[0][0] == pytest.approx(0.2)
    assert result.readings[1][0] == pytest.approx(0.001)
    rng = random.Random(413)
    for _ in range(200):
        a, b, c, d = [math.ldexp(rng.uniform(0.5, 1.0), rng.randint(-1070, 1023))
                      for _ in range(4)]
        assert _ratio_greater(a, b, c, d) == (Fraction(a) / Fraction(b) >
                                               Fraction(c) / Fraction(d))


def test_cost_aware_priority_can_also_spend_more() -> None:
    from nca.ladder import charge_per_cost

    a0 = Rung(constant("a0", (0.4, 0.6), 1.0))
    a1 = Rung(constant("a1", (0.001, 0.999), 2.0))
    b0 = Rung(constant("b0", (0.3, 0.7), 1.0))
    b1 = Rung(constant("b1", (0.29, 0.71), 1.0))
    ladders = [[a0, a1], [b0, b1]]
    assert refine([0, 0], ladders, 0.41).cost == 4.0
    assert refine([0, 0], ladders, 0.41, priority=charge_per_cost).cost == 5.0


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


@pytest.mark.parametrize("native", [False, True])
@pytest.mark.parametrize("dtype", [torch.uint8, torch.uint16, torch.uint32, torch.uint64,
                                  torch.int8, torch.int16, torch.int32, torch.int64])
def test_integer_logit_calibration_preserves_order_and_group_probabilities(native, dtype, monkeypatch) -> None:
    from nca import ladder as ladder_module

    if native and getattr(ladder_module._NATIVE, "calibrated_groups", None) is None:
        pytest.skip("native calibration kernels are not built")
    if not native:
        monkeypatch.setattr(ladder_module, "_NATIVE", None)
    bounds = torch.iinfo(dtype)
    logits = torch.tensor([bounds.max, bounds.max - 1, bounds.min], dtype=dtype)
    scores = torch.tensor([0.0, -1.0, float(bounds.min - bounds.max)], dtype=torch.float64)
    expected = torch.softmax(scores, dim=0)
    rung = Rung(None)
    decision = ((0,), (1,), (2,))
    assert torch.allclose(rung.reading(logits).double(), expected, atol=1e-7)
    assert torch.allclose(rung.distribution(logits, decision).double(), expected, atol=1e-7)
    assert rung.distribution(logits, decision).is_floating_point()
    assert torch.allclose(rung.log_distribution(logits, decision), scores.log_softmax(dim=0), atol=1e-7)
    assert rung.risk(logits, decision) == pytest.approx(expected[1].item(), abs=1e-7)


@pytest.mark.parametrize("native", [False, True])
@pytest.mark.parametrize("dtype", [torch.uint8, torch.uint64, torch.int8, torch.int64])
def test_integer_logit_restriction_preserves_local_differences(native, dtype, monkeypatch) -> None:
    from nca import ladder as ladder_module

    if native and getattr(ladder_module._NATIVE, "calibrated_groups", None) is None:
        pytest.skip("native calibration kernels are not built")
    if not native:
        monkeypatch.setattr(ladder_module, "_NATIVE", None)
    bounds = torch.iinfo(dtype)
    logits = torch.tensor([bounds.max, bounds.min, bounds.min + 1], dtype=dtype)
    expected = torch.softmax(torch.tensor([-1.0, 0.0], dtype=torch.float64), dim=0)
    rung = Rung(None)
    decision = ((1,), (2,))
    assert torch.allclose(rung.distribution(logits, decision).double(), expected, atol=1e-7)
    assert torch.allclose(rung.log_distribution(logits, decision), expected.log(), atol=1e-7)
    assert rung.risk(logits, decision) == pytest.approx(expected[1].item(), abs=1e-7)


@pytest.mark.parametrize("native", [False, True])
def test_unsigned_integer_logits_across_signed_boundary(native, monkeypatch) -> None:
    from nca import ladder as ladder_module

    if native and getattr(ladder_module._NATIVE, "shifted_integer_logits_into", None) is None:
        pytest.skip("native integer shift kernel is not built")
    if not native:
        monkeypatch.setattr(ladder_module, "_NATIVE", None)
    logits = torch.tensor([2**63 - 1, 2**63], dtype=torch.uint64)
    expected = torch.softmax(torch.tensor([-1.0, 0.0], dtype=torch.float64), dim=0)
    rung = Rung(None)
    assert torch.allclose(rung.reading(logits).double(), expected, atol=1e-7)
    assert torch.allclose(rung.distribution(logits, ((0,), (1,))).double(), expected, atol=1e-7)
    assert rung.risk(logits) == pytest.approx(expected[0].item(), abs=1e-7)


@pytest.mark.parametrize("unsigned", [False, True])
def test_native_integer_shift_matches_exact_integer_differences(unsigned) -> None:
    from nca import ladder as ladder_module

    kernel = getattr(ladder_module._NATIVE, "shifted_integer_logits_into", None)
    if kernel is None:
        pytest.skip("native integer shift kernel is not built")
    rng = np.random.default_rng(738)
    for _ in range(100):
        if unsigned:
            values = rng.integers(0, 2**64, size=20, dtype=np.uint64)
        else:
            values = rng.integers(-(2**63), 2**63, size=20, dtype=np.int64)
        integers = [int(value) for value in values]
        expected = np.array([float(value - max(integers)) for value in integers])
        actual = np.empty(len(values), dtype=np.float64)
        assert kernel(values.view(np.int64), actual, unsigned) == 0
        assert np.allclose(actual, expected, rtol=3e-16, atol=0.0)
    assert kernel(np.array([1, 2], dtype=np.int64), np.empty(1), unsigned) == -1


@pytest.mark.parametrize("device", ["mps", "cuda"])
def test_accelerator_integer_logit_reading_preserves_adjacent_values(device) -> None:
    available = (torch.backends.mps.is_available() if device == "mps" else torch.cuda.is_available())
    if not available:
        pytest.skip(f"{device} is unavailable")
    maximum = torch.iinfo(torch.int64).max
    logits = torch.tensor([maximum, maximum - 1], dtype=torch.int64, device=device)
    expected = torch.softmax(torch.tensor([0.0, -1.0], dtype=torch.float64), dim=0)
    rung = Rung(None)
    assert torch.allclose(rung.reading(logits).cpu().double(), expected, atol=1e-7)
    assert torch.allclose(rung.distribution(logits, ((0,), (1,))).cpu().double(), expected, atol=1e-7)


@pytest.mark.parametrize("dtype", [torch.float16, torch.float32, torch.int64, torch.uint64])
def test_mps_calibration_handles_temperature_below_device_range(dtype) -> None:
    if not torch.backends.mps.is_available():
        pytest.skip("mps is unavailable")
    rung = Rung(None)
    decision = ((0,), (1,))
    rung.temperatures[None] = 1e-100
    rung.temperatures[decision] = 1e-100
    logits = torch.tensor([1, 0], dtype=dtype, device="mps")
    assert rung.reading(logits).cpu().tolist() == [1.0, 0.0]
    assert rung.distribution(logits, decision).cpu().tolist() == [1.0, 0.0]
    assert rung.risk(logits, decision) == math.nextafter(0.0, 1.0)
    actual = rung.log_distribution(logits, decision)
    assert actual.device.type == "cpu" and actual.dtype == torch.float64
    assert actual[0].item() == 0.0
    assert actual[1].item() == pytest.approx(-1e100)


def test_mps_calibration_handles_temperature_above_device_range() -> None:
    if not torch.backends.mps.is_available():
        pytest.skip("mps is unavailable")
    rung = Rung(None)
    rung.temperatures[None] = 1e39
    logits = torch.tensor([3e38, -3e38], dtype=torch.float32, device="mps")
    expected = torch.softmax(logits.cpu().double() / 1e39, dim=0)
    assert torch.allclose(rung.reading(logits).cpu().double(), expected, atol=1e-7)


def test_mps_half_temperature_promotion_preserves_gradients() -> None:
    if not torch.backends.mps.is_available():
        pytest.skip("mps is unavailable")
    rung = Rung(None)
    rung.temperatures[None] = 1e-5
    logits = torch.tensor([1e-5, 0.0], dtype=torch.float16, device="mps", requires_grad=True)
    probability = rung.reading(logits)[0]
    probability.backward()
    expected_probability = torch.softmax(logits.detach().cpu().double() / 1e-5, dim=0)[0].item()
    expected_gradient = expected_probability * (1 - expected_probability) / 1e-5
    assert probability.item() == pytest.approx(expected_probability, abs=5e-4)
    assert logits.grad is not None
    assert logits.grad[0].item() == pytest.approx(expected_gradient, rel=1e-3)
    assert logits.grad[1].item() == pytest.approx(-expected_gradient, rel=1e-3)


def test_mps_log_distribution_preserves_gradients_across_cpu_copy() -> None:
    if not torch.backends.mps.is_available():
        pytest.skip("mps is unavailable")
    logits = torch.tensor([1.0, 0.0], dtype=torch.float32, device="mps", requires_grad=True)
    actual = Rung(None).log_distribution(logits, ((0,), (1,)))
    assert actual.device.type == "cpu" and actual.dtype == torch.float64
    actual[0].backward()
    expected = torch.tensor([1.0, 0.0], dtype=torch.float64, requires_grad=True)
    expected.log_softmax(dim=0)[0].backward()
    assert logits.grad is not None and expected.grad is not None
    assert torch.allclose(logits.grad.cpu().double(), expected.grad, atol=1e-7)


@pytest.mark.parametrize("dtype", [torch.int64, torch.uint64])
def test_mps_restricted_log_distribution_preserves_large_integer_differences(dtype) -> None:
    if not torch.backends.mps.is_available():
        pytest.skip("mps is unavailable")
    maximum = torch.iinfo(dtype).max
    logits = torch.tensor([0, maximum - 1, maximum], dtype=dtype, device="mps")
    actual = Rung(None).log_distribution(logits, ((1,), (2,)))
    expected = torch.tensor([-1.0, 0.0], dtype=torch.float64).log_softmax(dim=0)
    assert actual.device.type == "cpu" and torch.allclose(actual, expected)


def test_mps_wide_sparse_log_distribution() -> None:
    if not torch.backends.mps.is_available():
        pytest.skip("mps is unavailable")
    logits = torch.zeros(4_000_001, dtype=torch.float32, device="mps")
    logits[-1] = 1.0
    actual = Rung(None).log_distribution(logits, ((0,), (4_000_000,)))
    expected = torch.tensor([0.0, 1.0], dtype=torch.float64).log_softmax(dim=0)
    assert actual.device.type == "cpu" and torch.allclose(actual, expected)


@pytest.mark.parametrize("dtype", [torch.uint8, torch.uint16, torch.uint32, torch.uint64])
def test_calibration_accepts_unsigned_integer_labels(dtype) -> None:
    rung = Rung(constant("unsigned-labels", (0.4, 0.6), 1.0))
    rung.calibrate([0, 1, 2, 3], torch.tensor([0, 1, 0, 1], dtype=dtype))
    assert rung.held_out is not None
    assert rung.held_out[1].dtype == torch.int64
    assert rung.held_out[1].tolist() == [0, 1, 0, 1]


def test_calibration_rejects_unsigned_labels_outside_signed_range_atomically() -> None:
    rung = Rung(constant("large-unsigned-label", (0.4, 0.6), 1.0))
    rung.calibrate([0], torch.tensor([1], dtype=torch.uint64))
    previous = rung.held_out
    temperatures = dict(rung.temperatures)
    with pytest.raises(ValueError, match="valid class indices"):
        rung.calibrate([0], torch.tensor([2**64 - 1], dtype=torch.uint64))
    assert rung.held_out is previous
    assert rung.temperatures == temperatures


def test_native_calibration_subset_matches_label_mapping() -> None:
    from nca import ladder as ladder_module

    native = getattr(ladder_module._NATIVE, "calibration_subset", None)
    if native is None:
        pytest.skip("native calibration subset kernel is not built")
    labels = np.array([3, 5, 4, 0, 2], dtype=np.int64)
    classes = np.array([5, 0, 2, 3], dtype=np.int64)
    groups = np.array([0, 0, 1, 1], dtype=np.int64)
    assert native(labels, classes, groups, 6, 2) == [0, 1, 3, 4, 1, 0, 0, 1]
    assert native(np.array([4], dtype=np.int64), classes, groups, 6, 2) == []
    assert native(labels, np.array([7], dtype=np.int64), np.array([0], dtype=np.int64), 6, 2) == [-1]
    assert native(labels, np.array([0, 0], dtype=np.int64), np.array([0, 1], dtype=np.int64), 6, 2) == [-1]
    rng = np.random.default_rng(412)
    for _ in range(30):
        labels = rng.integers(-2, 34, size=100, dtype=np.int64)
        classes = rng.choice(32, size=20, replace=False).astype(np.int64)
        groups = rng.integers(0, 4, size=20, dtype=np.int64)
        mapping = dict(zip(classes.tolist(), groups.tolist()))
        rows = [i for i, label in enumerate(labels) if int(label) in mapping]
        expected = rows + [mapping[int(labels[i])] for i in rows]
        assert native(labels, classes, groups, 32, 4) == expected


def test_native_sparse_calibration_subset_matches_dense_and_validates() -> None:
    from nca import ladder as ladder_module

    native = getattr(ladder_module._NATIVE, "calibration_subset", None)
    if native is None:
        pytest.skip("native calibration subset kernel is not built")
    rng = np.random.default_rng(732)
    classes = np.array([3, 42, 1000, 17], dtype=np.int64)
    groups = np.array([0, 1, 1, 0], dtype=np.int64)
    labels = np.concatenate((rng.integers(-2, 1100, size=1000, dtype=np.int64), classes))
    assert native(labels, classes, groups, 1_000_000, 2) == native(labels, classes, groups, 4096, 2)
    assert native(labels, np.array([3, 3]), np.array([0, 1]), 1_000_000, 2) == [-1]
    assert native(labels, np.array([1_000_000]), np.array([0]), 1_000_000, 2) == [-1]
    assert native(labels, np.array([], dtype=np.int64), np.array([], dtype=np.int64), 1_000_000, 2) == []


def test_restricted_calibration_subset_matches_reference(monkeypatch) -> None:
    from types import SimpleNamespace
    from nca import ladder as ladder_module

    native = ladder_module._NATIVE
    if getattr(native, "calibration_subset", None) is None:
        pytest.skip("native calibration subset kernel is not built")
    rng = np.random.default_rng(638)
    logits = torch.tensor(rng.normal(size=(100, 8)), dtype=torch.float64)
    labels = torch.tensor(rng.integers(0, 8, size=100), dtype=torch.int64)
    decision = ((7, 0, 4), (2, 3))
    first = Rung(None)
    first.held_out = (logits, labels)
    actual = first.temperature(decision)
    monkeypatch.setattr(ladder_module, "_NATIVE", SimpleNamespace(
        calibration_loss_grid=getattr(native, "calibration_loss_grid", None)))
    second = Rung(None)
    second.held_out = (logits, labels)
    assert actual == second.temperature(decision)


def test_restricted_calibration_subset_falls_back_for_out_of_range_classes(monkeypatch) -> None:
    from nca import ladder as ladder_module

    if getattr(ladder_module._NATIVE, "calibration_subset", None) is None:
        pytest.skip("native calibration subset kernel is not built")
    rung = Rung(None)
    rung.held_out = (torch.zeros((2, 3), dtype=torch.float64), torch.tensor([0, 1]))
    with pytest.raises(IndexError):
        rung.temperature(((0,), (7,)))
    monkeypatch.setattr(ladder_module, "_NATIVE", None)
    with pytest.raises(IndexError):
        rung.temperature(((0,), (7,)))


def test_missing_restricted_calibration_is_cached_and_invalidated(monkeypatch) -> None:
    from types import SimpleNamespace
    from nca import ladder as ladder_module

    kernel = getattr(ladder_module._NATIVE, "calibration_subset", None)
    if kernel is None:
        pytest.skip("native calibration subset kernel is not built")
    calls = []
    def measured(*args):
        calls.append(True)
        return kernel(*args)
    monkeypatch.setattr(ladder_module, "_NATIVE", SimpleNamespace(calibration_subset=measured))
    rung = Rung(constant("missing-cache", (0.5, 0.3, 0.2), 1.0))
    rung.calibrate([0, 0], torch.tensor([0, 0]))
    decision = ((1,), (2,))
    for _ in range(3):
        with pytest.raises(ladder_module.MissingCalibrationError):
            rung.temperature(decision)
    assert len(calls) == 1
    with pytest.raises(ValueError):
        rung.calibrate([0], torch.tensor([3]))
    with pytest.raises(ladder_module.MissingCalibrationError):
        rung.temperature(decision)
    assert len(calls) == 1
    rung.calibrate([0, 0], torch.tensor([1, 2]))
    assert rung.temperature(decision) > 0
    assert len(calls) == 2
    rung.held_out = (torch.zeros((1, 3), dtype=torch.float64), torch.tensor([0]))
    rung.temperatures = {None: 1.0}
    with pytest.raises(ladder_module.MissingCalibrationError):
        rung.temperature(decision)
    assert len(calls) == 3


def test_single_entry_default_temperature_is_cached_and_invalidated() -> None:
    rung = Rung(constant("single-default-cache", (0.5, 0.5), 1.0))
    decision = ((1,),)
    rung.calibrate([0, 0], torch.tensor([0, 0]))
    assert rung.temperature(decision) == 1.0
    assert decision in rung._missing_temperatures
    rung.held_out = (torch.zeros((1, 2), dtype=torch.float64), torch.tensor([1]))
    assert rung.temperature(decision) == pytest.approx(0.1)
    rung.calibrate([0, 0], torch.tensor([1, 1]))
    assert decision not in rung._missing_temperatures
    assert rung.temperature(decision) == pytest.approx(0.1)


def test_missing_calibration_cache_has_bounded_entries() -> None:
    from nca.ladder import MissingCalibrationError

    rung = Rung(None)
    rung.held_out = (torch.zeros((1, 262), dtype=torch.float64), torch.tensor([0]))
    for i in range(1, 131):
        with pytest.raises(MissingCalibrationError):
            rung.temperature(((i,), (i + 1,)))
    assert len(rung._missing_temperatures) == 128


def test_missing_calibration_cache_does_not_retain_old_labels() -> None:
    import gc
    import weakref
    from nca.ladder import MissingCalibrationError

    rung = Rung(None)
    labels = torch.tensor([0])
    old_labels = weakref.ref(labels)
    rung.held_out = (torch.zeros((1, 3), dtype=torch.float64), labels)
    with pytest.raises(MissingCalibrationError):
        rung.temperature(((1,), (2,)))
    rung.held_out = None
    del labels
    gc.collect()
    assert old_labels() is None


def test_missing_calibration_cache_does_not_break_serialization() -> None:
    import pickle
    from nca.ladder import MissingCalibrationError

    rung = Rung(None)
    rung.held_out = (torch.zeros((1, 3), dtype=torch.float64), torch.tensor([0]))
    with pytest.raises(MissingCalibrationError):
        rung.temperature(((1,), (2,)))
    restored = pickle.loads(pickle.dumps(rung))
    assert not restored._missing_temperatures
    with pytest.raises(MissingCalibrationError):
        restored.temperature(((1,), (2,)))


def test_pre_cache_serialized_rung_state_restores_missing_calibration() -> None:
    from nca.ladder import MissingCalibrationError

    legacy_state = {
        "module": None,
        "temperatures": {},
        "held_out": (torch.zeros((1, 3), dtype=torch.float64), torch.tensor([0])),
    }
    restored = Rung.__new__(Rung)
    restored.__setstate__(legacy_state)
    for _ in range(2):
        with pytest.raises(MissingCalibrationError):
            restored.temperature(((1,), (2,)))
    assert len(restored._missing_temperatures) == 1


@pytest.mark.parametrize("native", [False, True])
def test_restricted_calibration_gathers_only_requested_columns(native, monkeypatch) -> None:
    from nca import ladder as ladder_module

    if native and getattr(ladder_module._NATIVE, "calibration_subset", None) is None:
        pytest.skip("native calibration subset kernel is not built")
    if not native:
        monkeypatch.setattr(ladder_module, "_NATIVE", None)

    class CaptureRung(Rung):
        def _fit(self, log, labels, entries=None):
            self.captured = (log, labels, entries)
            return 1.0

    width = 100_000
    logits = torch.arange(4 * width, dtype=torch.float64).reshape(4, width).requires_grad_()
    labels = torch.tensor([width - 1, 7, 2, 17], dtype=torch.int64)
    rung = CaptureRung(None)
    rung.held_out = (logits, labels)
    assert rung.temperature(((2, 17), (width - 1,))) == 1.0
    selected, targets, entries = rung.captured
    assert selected.shape == (3, 3)
    assert targets.tolist() == [1, 0, 0]
    assert entries == [[0, 1], [2]]
    expected = torch.stack([logits[i, [2, 17, width - 1]] for i in (0, 2, 3)])
    assert torch.equal(selected, expected)
    selected.sum().backward()
    assert logits.grad is not None and logits.grad.sum().item() == 9.0


@pytest.mark.parametrize("device", ["mps", "cuda"])
def test_accelerator_restricted_calibration_gather(device) -> None:
    available = (torch.backends.mps.is_available() if device == "mps" else torch.cuda.is_available())
    if not available:
        pytest.skip(f"{device} is unavailable")

    class CaptureRung(Rung):
        def _fit(self, log, labels, entries=None):
            self.captured = (log, labels)
            return 1.0

    logits = torch.arange(24, dtype=torch.float32, device=device).reshape(4, 6)
    labels = torch.tensor([5, 1, 2, 3], dtype=torch.int64, device=device)
    rung = CaptureRung(None)
    rung.held_out = (logits, labels)
    assert rung.temperature(((2, 3), (5,))) == 1.0
    selected, targets = rung.captured
    assert targets.tolist() == [1, 0, 0]
    assert selected.cpu().tolist() == [[2.0, 3.0, 5.0], [14.0, 15.0, 17.0], [20.0, 21.0, 23.0]]


@pytest.mark.parametrize("grouped", [False, True])
def test_native_temperature_fit_matches_reference(grouped, monkeypatch) -> None:
    from nca import ladder as ladder_module

    if getattr(ladder_module._NATIVE, "calibration_loss_grid", None) is None:
        pytest.skip("native calibration kernel is not built")
    rng = np.random.default_rng(522)
    entries = ((0, 2), (1, 3, 4), (5, 6, 7)) if grouped else None
    cases = []
    for _ in range(8):
        logits = torch.tensor(rng.normal(0, 3, size=(37, 8)), dtype=torch.float64)
        labels = torch.tensor(rng.integers(0, 3 if grouped else 8, size=37), dtype=torch.int64)
        cases.append((logits, labels))
    for temperature in (0.4, 1.0, 2.5):
        raw = rng.normal(0, 2, size=(200, 8))
        scaled = raw / temperature
        probabilities = np.exp(scaled - scaled.max(axis=1, keepdims=True))
        probabilities /= probabilities.sum(axis=1, keepdims=True)
        if grouped:
            probabilities = np.stack([probabilities[:, list(entry)].sum(axis=1)
                                      for entry in entries], axis=1)
        draws = rng.random((200, 1))
        targets = (draws > probabilities.cumsum(axis=1)).sum(axis=1)
        cases.append((torch.tensor(raw, dtype=torch.float64),
                      torch.tensor(targets, dtype=torch.int64)))
    native = [Rung._fit(logits, labels, entries) for logits, labels in cases]
    monkeypatch.setattr(ladder_module, "_NATIVE", None)
    assert native == [Rung._fit(logits, labels, entries) for logits, labels in cases]


@pytest.mark.parametrize("grouped", [False, True])
def test_native_calibration_grid_matches_reference_losses(grouped) -> None:
    from nca import ladder as ladder_module

    native = getattr(ladder_module._NATIVE, "calibration_loss_grid", None)
    if native is None:
        pytest.skip("native calibration kernel is not built")
    rng = np.random.default_rng(71)
    logits = torch.tensor(rng.normal(0, 7, size=(29, 8)), dtype=torch.float64)
    groups = np.array([0, 1, 0, 1, 1, 2, 2, 2] if grouped else range(8), dtype=np.int64)
    labels = torch.tensor(rng.integers(0, 3 if grouped else 8, size=29), dtype=torch.int64)
    temperatures = np.geomspace(0.1, 8.0, 120)
    actual = native(logits.numpy().reshape(-1), labels.numpy(), groups,
                    3 if grouped else 8, temperatures)
    expected = []
    for temperature in temperatures:
        scaled = torch.log_softmax(logits / temperature, dim=-1)
        if grouped:
            scaled = torch.stack([scaled[:, groups == group].logsumexp(dim=-1)
                                  for group in range(3)], dim=-1)
        expected.append(nn.functional.nll_loss(scaled, labels).item())
    assert np.allclose(actual, expected, rtol=1e-13, atol=1e-13)


@pytest.mark.parametrize("grouped,small_rows,large_rows", [(False, 100, 300), (True, 100, 2100)])
def test_temperature_fit_routes_large_cpu_batches_to_reference(grouped, small_rows, large_rows, monkeypatch) -> None:
    from types import SimpleNamespace
    from nca import ladder as ladder_module

    kernel = getattr(ladder_module._NATIVE, "calibration_loss_grid", None)
    if kernel is None:
        pytest.skip("native calibration kernel is not built")
    calls = []
    def measured(*args):
        calls.append(True)
        return kernel(*args)
    monkeypatch.setattr(ladder_module, "_NATIVE", SimpleNamespace(calibration_loss_grid=measured))
    entries = ((0, 1), (2, 3, 4, 5, 6, 7)) if grouped else None
    for rows in (small_rows, large_rows):
        Rung._fit(torch.zeros((rows, 8), dtype=torch.float64),
                  torch.zeros(rows, dtype=torch.int64), entries)
    assert calls == [True]


def test_observation_preserves_small_positive_probabilities() -> None:
    for probability in (1e-18, 1e-100, 1e-300):
        rung = Rung(constant("small", (1.0, probability), 1.0))
        observed = rung.observe(None)
        assert observed.dtype == torch.float64
        assert rung.risk(observed) == pytest.approx(probability, rel=1e-12, abs=0)
    zero = Rung(constant("zero", (1.0, 0.0), 1.0))
    assert zero.risk(zero.observe(None)) == math.nextafter(0.0, 1.0)


@pytest.mark.parametrize("native", [False, True])
def test_ranked_observation_retains_original_restricted_order(native, monkeypatch) -> None:
    from nca import ladder as ladder_module

    if native and getattr(ladder_module._NATIVE, "observation_logs", None) is None:
        pytest.skip("native observation preparation is not built")
    if not native:
        monkeypatch.setattr(ladder_module, "_NATIVE", None)

    class Expert:
        manifest = Manifest("ranked", "1", Contract(("x",), "dist"))
        calls = 0
        def invoke(self, value):
            self.calls += 1
            return (1.0, 1e-300, math.nextafter(1e-300, math.inf))

    expert = Expert()
    observed = Rung(expert).observe_ranked(None)
    assert expert.calls == 1
    assert observed.top() == 0
    assert observed.top([1, 2]) == 2
    assert observed.top([2, 1]) == 2
    assert observed.weights[1] < observed.weights[2]
    forced_tie = ladder_module.RankedObservation(torch.tensor([0.0, -1.0, -1.0]), observed.weights)
    assert forced_tie.top([1, 2]) == 2
    equal = ladder_module.RankedObservation(torch.tensor([0.0, 0.0]), (0.5, 0.5))
    assert equal.top([1, 0]) == 1
    values = [0.2, 0.8]
    snapshot = Rung(constant("mutable-output", values, 1.0)).observe_ranked(None)
    values[0] = 1.0
    assert snapshot.top() == 1
    for invalid in ([], [-1], [3], [True]):
        with pytest.raises(ValueError, match="class indices"):
            observed.top(invalid)


@pytest.mark.parametrize("native", [False, True])
@pytest.mark.parametrize("bad", [math.nan, math.inf, -math.inf, -0.1])
def test_ranked_selection_rejects_invalid_weights(native, bad, monkeypatch) -> None:
    from nca import ladder as ladder_module

    if native and getattr(ladder_module._NATIVE, "ranked_argmax_checked", None) is None:
        pytest.skip("native ranked selection kernel is not built")
    if not native:
        monkeypatch.setattr(ladder_module, "_NATIVE", None)
    logits = torch.tensor([0.0, 0.0, 0.0], dtype=torch.float64)
    observation = ladder_module.RankedObservation(logits, (0.5, bad, 0.0))
    reading = ladder_module.RankedReading((0.5, 0.3, 0.2), observation.weights)
    for ranked in (observation, reading):
        with pytest.raises(ValueError, match="finite and nonnegative"):
            ranked.top()
        assert ranked.top([2, 0]) == 0
    with pytest.raises(ValueError, match="finite.*nonnegative"):
        Rung(None).risk(observation)


@pytest.mark.parametrize("native", [False, True])
def test_ranked_selection_preserves_zero_weight_ties(native, monkeypatch) -> None:
    from nca import ladder as ladder_module

    if native and getattr(ladder_module._NATIVE, "ranked_argmax_checked", None) is None:
        pytest.skip("native ranked selection kernel is not built")
    if not native:
        monkeypatch.setattr(ladder_module, "_NATIVE", None)
    observation = ladder_module.RankedObservation(torch.zeros(3), (1.0, 0.0, 0.0))
    assert observation.top([2, 1]) == 2
    assert Rung(None).risk(observation, ((2,), (1,))) == pytest.approx(0.5)


def test_ranked_selection_validates_with_legacy_kernel(monkeypatch) -> None:
    from types import SimpleNamespace
    from nca import ladder as ladder_module

    monkeypatch.setattr(ladder_module, "_NATIVE", SimpleNamespace(row_argmax=lambda *args: [0]))
    observation = ladder_module.RankedObservation(torch.zeros(2), (0.5, math.nan))
    with pytest.raises(ValueError, match="finite and nonnegative"):
        observation.top()


@pytest.mark.parametrize("native", [False, True])
def test_large_restricted_ranked_selection_preserves_contract(native, monkeypatch) -> None:
    from nca import ladder as ladder_module

    if native and getattr(ladder_module._NATIVE, "ranked_argmax_indices_checked", None) is None:
        pytest.skip("native indexed ranked selection kernel is not built")
    if not native:
        monkeypatch.setattr(ladder_module, "_NATIVE", None)
    weights = [0.1] * 32
    weights[4] = weights[19] = 0.8
    observation = ladder_module.RankedObservation(torch.zeros(32), tuple(weights))
    indices = tuple(reversed(range(32)))
    assert observation.top(indices) == 19
    assert observation.top(indices + (19,)) == 19
    for bad in (-1, 32, True, 1.5, 2**100):
        with pytest.raises(ValueError, match="class indices"):
            observation.top(indices[:-1] + (bad,))
    weights[7] = math.nan
    invalid = ladder_module.RankedObservation(torch.zeros(32), tuple(weights))
    with pytest.raises(ValueError, match="finite and nonnegative"):
        invalid.top(indices)
    assert invalid.top(tuple(i for i in indices if i != 7)) == 19


def test_native_restricted_ranked_selection_matches_reference(monkeypatch) -> None:
    from nca import ladder as ladder_module

    if getattr(ladder_module._NATIVE, "ranked_argmax_indices_checked", None) is None:
        pytest.skip("native indexed ranked selection kernel is not built")
    rng = np.random.default_rng(197)
    cases = []
    for _ in range(50):
        weights = tuple(float(x) for x in rng.integers(0, 8, size=64))
        indices = tuple(int(i) for i in rng.integers(0, 64, size=40))
        cases.append((weights, indices))
    actual = [ladder_module._ranked_top(weights, indices) for weights, indices in cases]
    monkeypatch.setattr(ladder_module, "_NATIVE", None)
    assert actual == [ladder_module._ranked_top(weights, indices) for weights, indices in cases]


@pytest.mark.parametrize("native", [False, True])
@pytest.mark.parametrize("outside", [10**400, "not-a-weight"])
def test_restricted_ranked_selection_ignores_unconvertible_outside_weights(native, outside, monkeypatch) -> None:
    from nca import ladder as ladder_module

    if native and getattr(ladder_module._NATIVE, "ranked_argmax_indices_checked", None) is None:
        pytest.skip("native indexed ranked selection kernel is not built")
    if not native:
        monkeypatch.setattr(ladder_module, "_NATIVE", None)
    weights = tuple([0.5] * 31 + [outside])
    observation = ladder_module.RankedObservation(torch.zeros(32), weights)
    assert observation.top(tuple(range(16))) == 0


def test_ranked_index_cache_respects_identity_and_mutable_lists() -> None:
    from nca import ladder as ladder_module

    if getattr(ladder_module._NATIVE, "ranked_argmax_indices_checked", None) is None:
        pytest.skip("native indexed ranked selection kernel is not built")
    weights = tuple(float(i) for i in range(32))
    observation = ladder_module.RankedObservation(torch.zeros(32), weights)
    indices = tuple(range(32))
    assert observation.top(indices) == 31
    native_indices = ladder_module._immutable_ranked_indices(id(indices), indices)
    assert native_indices is not None and not native_indices.flags.writeable
    assert ladder_module._immutable_ranked_indices(id(indices), indices) is native_indices
    bool_indices = (False, True) + indices[2:]
    assert bool_indices == indices
    with pytest.raises(ValueError, match="class indices"):
        observation.top(bool_indices)
    mutable = list(indices)
    assert observation.top(mutable) == 31
    mutable[-1] = 0
    assert observation.top(mutable) == 30


@pytest.mark.parametrize("native", [False, True])
def test_ranked_risk_uses_original_winner_group(native, monkeypatch) -> None:
    from nca import ladder as ladder_module

    if native and getattr(ladder_module._NATIVE, "calibrated_risk_at", None) is None:
        pytest.skip("native ranked risk is not built")
    if not native:
        monkeypatch.setattr(ladder_module, "_NATIVE", None)
    low = 1e-300
    high = math.nextafter(low, math.inf)
    rung = Rung(constant("ranked-risk", (1.0, low, high, 1e-301), 1.0))
    observed = rung.observe_ranked(None)
    groups = ((1, 3), (2,))
    assert observed.top([1, 3, 2]) == 2
    assert rung.risk(observed, groups) == pytest.approx(11 / 21, abs=1e-14)
    assert rung.risk(observed.logits, groups) == pytest.approx(10 / 21, abs=1e-14)
    assert torch.equal(rung.reading(observed), rung.reading(observed.logits))
    assert torch.equal(rung.distribution(observed, groups),
                       rung.distribution(observed.logits, groups))
    # Consumers can select with the same retained ordering.
    assert observed.top([1, 2]) == 2
    arbitrary = ladder_module.RankedObservation(torch.tensor([1000.0, -1000.0]), (0.1, 0.9))
    assert rung.risk(arbitrary, ((0,), (1,))) == 1.0
    for temperature in (0.0, -1.0, math.inf, math.nan):
        rung.temperatures[None] = temperature
        with pytest.raises(ValueError, match="positive finite temperature"):
            rung.risk(observed)
    rng = np.random.default_rng(416)
    for values in rng.dirichlet(np.ones(4), size=12):
        ordinary = Rung(constant("unambiguous", tuple(values), 1.0))
        ranked = ordinary.observe_ranked(None)
        for decision in (None, ((0, 2), (1, 3)), ((0,), (1,), (2, 3))):
            assert ordinary.risk(ranked, decision) == pytest.approx(
                ordinary.risk(ranked.logits, decision), abs=1e-14)


@pytest.mark.parametrize("native", [False, True])
@pytest.mark.parametrize("weights", [(), (0.0, 0.0), (-0.1, 1.0),
                                      (float("nan"), 1.0), (float("inf"), 1.0),
                                      (float("-inf"), 1.0), ((0.1, 0.9),), 1.0])
def test_observation_rejects_invalid_weights(weights, native, monkeypatch) -> None:
    from nca import ladder as ladder_module

    if native and getattr(ladder_module._NATIVE, "observation_logs", None) is None:
        pytest.skip("native observation validation is not built")
    if not native:
        monkeypatch.setattr(ladder_module, "_NATIVE", None)
    with pytest.raises(ValueError, match="expert output"):
        Rung(constant("invalid", weights, 1.0)).observe(None)


@pytest.mark.parametrize("native", [False, True])
def test_observation_accepts_unnormalized_positive_weights(native, monkeypatch) -> None:
    from nca import ladder as ladder_module

    if native and getattr(ladder_module._NATIVE, "observation_logs", None) is None:
        pytest.skip("native observation validation is not built")
    if not native:
        monkeypatch.setattr(ladder_module, "_NATIVE", None)
    rung = Rung(constant("weights", (2.0, 1.0), 1.0))
    assert rung.reading(rung.observe(None)).tolist() == pytest.approx([2 / 3, 1 / 3])
    large = Rung(constant("large-weights", (1e308, 1e308), 1.0))
    assert large.reading(large.observe(None)).tolist() == pytest.approx([0.5, 0.5])


def test_native_observation_logs_match_fallback(monkeypatch) -> None:
    from nca import ladder as ladder_module

    if getattr(ladder_module._NATIVE, "observation_logs", None) is None:
        pytest.skip("native observation preparation is not built")
    rng = np.random.default_rng(413)
    values = np.concatenate(([0.0, np.nextafter(0.0, 1.0), np.nextafter(1.0, 0.0), 1.0],
                             rng.random(1000), np.exp(rng.uniform(-740, 709, 1000))))
    rung = Rung(constant("weights", tuple(values), 1.0))
    actual = rung.observe(None).numpy()
    noncontiguous = values[::2]
    assert not noncontiguous.flags.c_contiguous
    strided = Rung(constant("strided", noncontiguous, 1.0)).observe(None).numpy()
    monkeypatch.setattr(ladder_module, "_NATIVE", None)
    expected = rung.observe(None).numpy()
    np.testing.assert_array_equal(actual, expected)
    fallback = Rung(constant("strided", noncontiguous, 1.0)).observe(None).numpy()
    np.testing.assert_array_equal(strided, fallback)


def test_observation_decisions_match_across_cpu_paths(monkeypatch) -> None:
    from nca import ladder as ladder_module

    if getattr(ladder_module._NATIVE, "observation_logs", None) is None:
        pytest.skip("native observation preparation is not built")
    weights = (0.30888158696060686, 0.3088815869606069)
    rung = Rung(constant("adjacent", weights, 1.0))
    native = rung.observe(None)
    monkeypatch.setattr(ladder_module, "_NATIVE", None)
    fallback = rung.observe(None)
    assert torch.equal(native, fallback)
    assert int(native.argmax()) == int(fallback.argmax())


@pytest.mark.parametrize("native", [False, True])
def test_observation_accepts_tensor_containing_sequence(native, monkeypatch) -> None:
    import warnings
    from nca import ladder as ladder_module

    if native and getattr(ladder_module._NATIVE, "observation_logs", None) is None:
        pytest.skip("native observation preparation is not built")
    if not native:
        monkeypatch.setattr(ladder_module, "_NATIVE", None)
    values = (torch.tensor(0.4, requires_grad=True), torch.tensor(0.6))
    with warnings.catch_warnings():
        warnings.simplefilter("ignore", UserWarning)
        rung = Rung(constant("tensor-values", values, 1.0))
        reading = rung.reading(rung.observe(None))
    assert reading.tolist() == pytest.approx([0.4, 0.6])


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


def test_solve_session_is_shared_by_generic_consumer_hooks() -> None:
    from nca.selective import solve_many

    events = []
    class Consumer:
        manifest = Manifest("session-consumer", "1.0.0", Contract(("seq[dist]",), "out"))
        def solve_session(self) -> Any:
            token = sum(event[0] == "session" for event in events) + 1
            events.append(("session", token))
            class Session:
                def demand(self, index: int, demand: Demand) -> Demand:
                    events.append(("demand", token))
                    return None
                def certificate(self, readings: Any, risk: Any, distribution: Any) -> dict[int, float]:
                    events.append(("certificate", token))
                    return {i: 0.2 for i in range(len(readings))}
                def floor(self, readings: Any, risk: Any, fixed: Any) -> float:
                    events.append(("floor", token))
                    return 0.0
                def invoke(self, readings: Any) -> int:
                    events.append(("invoke", token))
                    return token
            return Session()

    reader = constant("session-reader", (0.1, 0.9), 1.0, Contract(("ch",), "dist"))
    route = plan_stable([Splitter(), reader, Consumer()], ("text",), "out")
    assert route is not None
    ladders = {"dist": [Rung(reader)]}
    assert solve(route, ladders, "a", 0.1, floors=True).value == 1
    assert {name for name, token in events if token == 1} == {
        "session", "demand", "certificate", "floor", "invoke"}
    answers = solve_many(route, ladders, "a", [0.1, 1.0])
    assert [answer.value for answer in answers] == [2, 2]
    assert len([event for event in events if event[0] == "session"]) == 2


def test_missing_certificate_cannot_meet_infinite_target() -> None:
    from nca.selective import solve_many

    low = Rung(constant("uncertain", (0.4, 0.6), 1.0))
    high = Rung(constant("certain", (0.01, 0.99), 2.0))
    seen = []
    def certificate(readings: Any, risk: Any, distribution: Any) -> dict[int, float] | None:
        return {0: 0.01} if readings[0][1] > 0.9 else None
    result = refine([0], [[low, high]], float("inf"), certificate=certificate,
                    observe=seen.append)
    assert [state.available for state in seen] == [False, True]
    assert seen[0].abstained and not result.abstained and result.cost == 3.0
    missing = refine([0], [[low]], float("inf"), certificate=lambda *_: None)
    assert missing.abstained and not missing.available

    class Consumer:
        manifest = Manifest("no-certificate", "1.0.0", Contract(("seq[dist]",), "out"))
        def certificate(self, readings: Any, risk: Any, distribution: Any) -> None:
            return None
        def invoke(self, readings: Any) -> str:
            return "unverified"
    reader = constant("reader-no-certificate", (0.1, 0.9), 1.0, Contract(("ch",), "dist"))
    route = plan_stable([Splitter(), reader, Consumer()], ("text",), "out")
    assert route is not None
    ladders = {"dist": [Rung(reader)]}
    assert solve(route, ladders, "a", float("inf")).abstained
    assert all(answer.abstained for answer in solve_many(route, ladders, "a", [1.0, float("inf")]))


@pytest.mark.parametrize("account", [
    {0: float("nan")}, {0: float("inf")}, {0: -0.1}, {-1: 0.1},
    {2: 0.1}, {True: 0.1}, {0: 1e308, 1: 1e308},
])
def test_refinement_rejects_invalid_certificate_charges(account: dict[int, float]) -> None:
    rung = Rung(constant("invalid-account-reader", (0.1, 0.9), 1.0))
    with pytest.raises(ValueError, match="certificate charges"):
        refine([0, 0], [[rung], [rung]], 1.0, certificate=lambda *_: account)


def test_refinement_accepts_non_builtin_integral_indices() -> None:
    rung = Rung(constant("numpy-index-reader", (0.1, 0.9), 1.0))
    result = refine([0], [[rung]], 0.5, certificate=lambda *_: {np.int64(0): 0.1})
    assert not result.abstained and result.bound == 0.1


def test_refinement_preserves_small_charges_in_total() -> None:
    rung = Rung(constant("small-charges-reader", (0.1, 0.9), 1.0))
    charges = {0: 1.1186891848835543e-179, 1: 0.15944700478182372,
               2: 0.4537584643973063}
    target = math.nextafter(math.fsum(charges.values()), -math.inf)
    result = refine([0] * 3, [[rung]] * 3, target, certificate=lambda *_: charges)
    assert result.bound >= math.fsum(charges.values())
    assert result.bound > target and result.abstained


@pytest.mark.parametrize("charge, exact", [
    (Fraction(1, 3), Fraction(1, 3)),
    (Decimal("1e-400"), Fraction(1, 10 ** 400)),
    (2 ** 53 + 1, Fraction(2 ** 53 + 1)),
])
def test_refinement_rounds_non_binary64_charge_up(charge: Any, exact: Fraction) -> None:
    rung = Rung(constant("precise-charge-reader", (0.1, 0.9), 1.0))
    result = refine([0], [[rung]], float("inf"), certificate=lambda *_: {0: charge})
    assert Fraction.from_float(result.bound) >= exact


@pytest.mark.parametrize("reference", [False, True])
@pytest.mark.parametrize("direction", ["upper", "lower"])
def test_directed_sum_bounds_exact_binary64_sum(reference: bool, direction: str,
                                               monkeypatch: pytest.MonkeyPatch) -> None:
    import nca.ladder as ladder_module

    if reference:
        monkeypatch.setattr(ladder_module, "_NATIVE", None)
    rng = random.Random(321)
    samples = [[0.0, 0.0], [1.0, 1e-300], [float.fromhex("0x0.0000000000001p-1022")]]
    samples.extend([[math.ldexp(rng.random(), rng.randint(-1070, 200))
                     for _ in range(rng.randrange(30))] for _ in range(300)])
    for values in samples:
        actual = getattr(ladder_module, f"_{direction}_sum")(values)
        exact = sum(map(Fraction.from_float, values), Fraction())
        assert math.isfinite(actual)
        assert (Fraction.from_float(actual) >= exact if direction == "upper"
                else Fraction.from_float(actual) <= exact)


def test_lower_sum_handles_overflow_conservatively() -> None:
    import nca.ladder as ladder_module

    largest = float.fromhex("0x1.fffffffffffffp+1023")
    assert ladder_module._lower_sum([largest, largest]) == largest


@pytest.mark.parametrize("target", [float("nan"), -1.0])
def test_refinement_and_single_solve_reject_invalid_targets(target: float) -> None:
    rung = Rung(constant("invalid-target-reader", (0.1, 0.9), 1.0))
    with pytest.raises(ValueError, match="target"):
        refine([0], [[rung]], target)
    reader = constant("invalid-target-route", (0.1, 0.9), 1.0, Contract(("ch",), "dist"))
    route = plan_stable([Splitter(), reader, Argmax(), Joiner()], ("text",), "out")
    assert route is not None
    with pytest.raises(ValueError, match="target"):
        solve(route, {"dist": [Rung(reader)]}, "a", target)


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


@pytest.mark.parametrize("reference", [False, True])
def test_risk_preserves_tiny_alternative_mass(reference: bool,
                                               monkeypatch: pytest.MonkeyPatch) -> None:
    from nca import ladder as ladder_module

    if reference:
        monkeypatch.setattr(ladder_module, "_NATIVE", None)
    probabilities = torch.tensor([1.0, 1e-18, 2e-18], dtype=torch.float64)
    rung = Rung(constant("tiny-risk", (1.0, 1e-18, 2e-18), 1.0))
    logits = probabilities.log()
    for classes, expected in ((None, 3e-18), (((0,), (1, 2)), 3e-18),
                              (((0, 1), (2,)), 2e-18)):
        assert ladder_module.risk(probabilities, classes) == pytest.approx(expected, rel=1e-14, abs=0)
        assert rung.risk(logits, classes) == pytest.approx(expected, rel=1e-13, abs=0)


@pytest.mark.parametrize("decision", [((0, 1), (1, 2)), ((0, 0), (1,)),
                                      ((), (0,)), (), ((-1,), (0,)), ((True,), (0,))])
def test_grouped_decision_rejects_invalid_partitions(decision) -> None:
    from nca.ladder import risk

    reading = torch.tensor([0.6, 0.4, 0.0], dtype=torch.float64)
    rung = Rung(constant("partition-validation", (0.6, 0.4, 0.0), 1.0))
    for action in (lambda: risk(reading, decision),
                   lambda: rung.risk(rung.observe(None), decision),
                   lambda: rung.risk(rung.observe_ranked(None), decision),
                   lambda: rung.distribution(rung.observe(None), decision)):
        with pytest.raises(ValueError, match="nonempty partition"):
            action()


def test_grouped_decision_rejects_boolean_indices_after_cached_integer_partition() -> None:
    from nca.ladder import risk

    reading = torch.tensor([0.6, 0.4])
    risk(reading, ((1,), (0,)))
    for decision in (((True,), (0,)), ([True], [0])):
        with pytest.raises(ValueError, match="nonempty partition"):
            risk(reading, decision)


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


def test_predictive_stopping_handles_zero_and_extreme_targets() -> None:
    from nca.ladder import State, stopping_rule

    state = State(0.1, 0.1, 1.0)
    traces = [([state], False, 2.0)]
    for target in (0.0, 5e-324, float("inf")):
        stop = stopping_rule(traces, target, 0.1)
        assert stop(state)
    # The quotient overflows, but distinct finite logarithmic bins remain distinct.
    near = State(1e-10, 0.1, 1.0)
    far = State(1e308, 0.1, 1.0)
    stop = stopping_rule([([far], False, 2.0)], 5e-324, 0.1)
    assert stop(far) and not stop(near)
    tiny = State(1e-200, 1e-200, 1.0)
    small = State(1e-100, 1e-100, 1.0)
    stop = stopping_rule([([small], False, 2.0)], 5e-324, 0.1)
    assert stop(small) and not stop(tiny)
    # A tie with stopping now continues; positive net reward does too.
    assert not stopping_rule([([state], True, 2.0)], 0.1, 1.0)(state)
    assert not stopping_rule([([state], True, 2.0)], 0.1, 0.5)(state)


def test_predictive_stopping_can_split_by_open_charge() -> None:
    from nca.ladder import State, stopping_rule

    fixed = State(1.0, 0.0, 1.0)
    open_ = State(1.0, 1.0, 1.0)
    unseen = State(1.0, 0.5, 1.0)
    runs = [([fixed], False, 2.0), ([open_], True, 2.0)]
    pooled = stopping_rule(runs, 0.1, 0.4)
    split = stopping_rule(runs, 0.1, 0.4, open_charge=True)
    assert not pooled(fixed) and not pooled(open_)
    assert split(fixed) and not split(open_) and not split(unseen)
    unbounded = State(float("inf"), 1.0, 1.0)
    assert stopping_rule([([unbounded], False, 2.0)], 0.0, 0.4,
                         open_charge=True)(unbounded)
    low = State(float("inf"), 0.1, 1.0)
    high = State(float("inf"), 10.0, 1.0)
    split = stopping_rule([([low], False, 2.0), ([high], True, 2.0)],
                         0.1, 0.4, open_charge=True)
    assert split(low) and not split(high)
    zero = State(float("inf"), 0.0, 1.0)
    tiny = State(float("inf"), 1e-200, 1.0)
    split = stopping_rule([([zero], False, 2.0)], 0.1, 0.4, open_charge=True)
    assert split(zero) and not split(tiny)
    # Distinct subnormal priorities can round to the same quotient.
    subnormal = 1e-320
    adjacent = math.nextafter(subnormal, math.inf)
    low = State(float("inf"), subnormal, 1.0)
    high = State(float("inf"), adjacent, 1.0)
    split = stopping_rule([([low], False, 2.0)], 3.0, 0.4, 1e-5, open_charge=True)
    assert split(low) and not split(high)


@pytest.mark.parametrize("target, weight, width", [(-1, 0.1, 0.25),
                                                    (float("nan"), 0.1, 0.25),
                                                    (0.1, -1, 0.25),
                                                    (0.1, float("inf"), 0.25),
                                                    (0.1, 0.1, 0),
                                                    (0.1, 0.1, float("nan"))])
def test_predictive_stopping_rejects_invalid_parameters(target, weight, width) -> None:
    from nca.ladder import stopping_rule

    with pytest.raises(ValueError):
        stopping_rule([], target, weight, width)


@pytest.mark.parametrize("priorities", [[0.0, 0.0], [0.0, 3.0, 1.0],
                                       [1e308, 1e308], [1e-320, 2e-320]])
def test_risk_allocation_uses_current_bound(priorities: list[float]) -> None:
    # Reuse the same priorities while the current posterior risk changes.
    for bound in (0.0, 0.001, 0.4, 1.0):
        charges = allocate_risk(bound, priorities)
        assert all(c >= 0 for c in charges)
        assert sum(charges) == pytest.approx(bound)
        assert len(charges) == len(priorities)


@pytest.mark.parametrize("native", [False, True])
def test_risk_allocation_accepts_numpy_vectors(native, monkeypatch) -> None:
    from nca import ladder as ladder_module

    if native and getattr(ladder_module._NATIVE, "risk_shares_covering", None) is None:
        pytest.skip("native risk allocation kernel is not built")
    if not native:
        monkeypatch.setattr(ladder_module, "_NATIVE", None)
    priorities = np.array([1.0, 2.0, 3.0], dtype=np.float32)
    assert allocate_risk(0.3, priorities) == pytest.approx([0.05, 0.10, 0.15])
    assert allocate_risk(0.3, np.zeros(2)) == pytest.approx([0.15, 0.15])
    with pytest.raises(ValueError, match="at least one item"):
        allocate_risk(0.3, np.array([], dtype=np.float64))


@pytest.mark.parametrize("bound, priorities", [(float("nan"), [1.0]),
                                               (-0.1, [1.0]), (0.1, []),
                                               (0.1, [-1.0]), (0.1, [float("inf")])])
def test_risk_allocation_rejects_invalid_inputs(bound: float, priorities: list[float]) -> None:
    with pytest.raises(ValueError):
        allocate_risk(bound, priorities)


@pytest.mark.parametrize("reference", [False, True])
def test_risk_allocation_covers_bound_as_exact_binary64_sum(reference, monkeypatch) -> None:
    from nca import ladder as ladder_module

    if reference:
        monkeypatch.setattr(ladder_module, "_NATIVE", None)
    rng = np.random.default_rng(829)
    cases = [(0.1, [1.0, 1.0, 1.0]),
             (math.nextafter(0.0, 1.0), [1.0, 2.0, 1.0]),
             (np.finfo(float).max, [1.0, 1.0, 1.0])]
    cases.extend((float(rng.random()), rng.random(int(rng.integers(1, 40))).tolist())
                 for _ in range(300))
    for bound, priorities in cases:
        shares = allocate_risk(bound, priorities)
        assert all(math.isfinite(share) and share >= 0 for share in shares)
        assert sum(map(Fraction.from_float, shares)) >= Fraction.from_float(bound)


@pytest.mark.parametrize("reference", [False, True])
def test_risk_allocation_rejects_priorities_lost_by_binary64_conversion(reference, monkeypatch) -> None:
    from nca import ladder as ladder_module

    if reference:
        monkeypatch.setattr(ladder_module, "_NATIVE", None)
    with pytest.raises(ValueError, match="finite and nonnegative"):
        allocate_risk(0.1, [Decimal("-1e-1000")])
    with pytest.raises(ValueError, match="finite and nonnegative"):
        allocate_risk(0.1, [1.0, float("nan")])


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


@pytest.mark.parametrize("temperature", [0.1, 1.0, 8.0])
def test_native_calibrated_groups_match_torch(temperature: float,
                                             monkeypatch: pytest.MonkeyPatch) -> None:
    from nca import ladder as ladder_module

    if getattr(ladder_module._NATIVE, "calibrated_groups", None) is None:
        pytest.skip("native calibration groups are not built")
    classes = ((0, 2), (1,), (3, 4))
    rung = Rung(constant("groups", (0.2,) * 5, 1.0))
    rung.temperatures[ladder_module.decision_key(classes)] = temperature
    logits = [torch.tensor([0.0, -1000.0, -2.0, -3.0, -10.0]),
              torch.zeros(5), torch.tensor([1000.0, 999.0, -1000.0, 998.0, -999.0])]
    actual = [rung.distribution(row, classes) for row in logits]
    monkeypatch.setattr(ladder_module, "_NATIVE", None)
    for row, probabilities in zip(logits, actual):
        assert torch.allclose(probabilities, rung.distribution(row, classes), atol=2e-6)
        assert float(probabilities.sum()) == pytest.approx(1.0, abs=1e-7)


def test_grouped_distribution_preserves_gradients() -> None:
    rung = Rung(constant("gradient", (0.2,) * 5, 1.0))
    row = torch.tensor([-1.0, -2.0, -3.0, -4.0, -5.0], requires_grad=True)
    result = rung.distribution(row, ((0, 2), (1,), (3, 4)))
    result[0].backward()
    assert row.grad is not None and torch.isfinite(row.grad).all()
    assert torch.count_nonzero(row.grad) > 0


@pytest.mark.parametrize("classes", [None, ((0,), (1, 2)), ((0, 2), (1,))])
def test_native_calibrated_risk_uses_top_class_group(classes: Any,
                                                   monkeypatch: pytest.MonkeyPatch) -> None:
    from nca import ladder as ladder_module

    if getattr(ladder_module._NATIVE, "calibrated_risk", None) is None:
        pytest.skip("native calibrated risk is not built")
    rung = Rung(constant("risk", (0.4, 0.3, 0.3), 1.0))
    rows = [torch.tensor([0.4, 0.3, 0.3]).log(), torch.zeros(3),
            torch.tensor([0.0, -1000.0, -2.0])]
    actual = [rung.risk(row, classes) for row in rows]
    monkeypatch.setattr(ladder_module, "_NATIVE", None)
    assert actual == pytest.approx([rung.risk(row, classes) for row in rows], abs=1e-7)
    if classes == ((0,), (1, 2)):
        assert actual[0] == pytest.approx(0.6, abs=1e-7)


@pytest.mark.parametrize("native", [False, True])
def test_calibrated_risk_preserves_tiny_finite_alternatives(
        native: bool, monkeypatch: pytest.MonkeyPatch) -> None:
    from nca import ladder as ladder_module

    if native and getattr(ladder_module._NATIVE, "calibrated_risk", None) is None:
        pytest.skip("native calibrated risk is not built")
    if not native:
        monkeypatch.setattr(ladder_module, "_NATIVE", None)
    rung = Rung(constant("tiny", (0.5, 0.5), 1.0))
    assert rung.risk(torch.tensor([0.0, -200.0])) == pytest.approx(math.exp(-200), rel=1e-12, abs=0)
    assert rung.risk(torch.tensor([0.0, -1000.0])) == math.nextafter(0.0, 1.0)
    assert rung.risk(torch.tensor([0.0, -math.inf])) == 0.0
    assert rung.risk(torch.tensor([0.0, -1000.0]), ((0, 1),)) == 0.0
    assert rung.risk(torch.tensor([0.0, -2.0, -math.inf]), ((0, 1), (2,))) == 0.0
    many = torch.tensor([0.0] + [-746.0] * 10, dtype=torch.float64)
    assert rung.risk(many) > math.nextafter(0.0, 1.0)
    rung.temperatures[None] = 0.01
    assert rung.risk(torch.tensor([0.0, -1e308], dtype=torch.float64)) == math.nextafter(0.0, 1.0)


def test_element_certificate_keeps_independent_reading_snapshots() -> None:
    from nca.ladder import Distribution
    from nca.selective import element_certificate

    snapshots: list[list[Any]] = []
    sources: list[object | None] = []
    risk_sources: list[object | None] = []

    class Consumer:
        def certificate(self, readings: list[Any], risk: Any, distribution: Any) -> dict[int, float]:
            snapshots.append(readings)
            sources.append(getattr(distribution, "source", None))
            risk_sources.append(getattr(risk, "source", None))
            return {0: 0.1}

    version = [0]
    callback = element_certificate(Consumer(), [(0, 0)], 1)
    assert callback is not None
    distribution = Distribution(lambda i, d: torch.tensor([0.5, 0.5]), version.__getitem__)
    callback([torch.tensor([0.4, 0.6])], lambda i, d: 0.1, distribution)
    version[0] += 1
    callback([torch.tensor([0.7, 0.3])], lambda i, d: 0.1, distribution)
    assert snapshots[0][0] == pytest.approx((0.4, 0.6))
    assert snapshots[1][0] == pytest.approx((0.7, 0.3))
    assert sources[0] is sources[1] is distribution.source
    # Ordinary callbacks may change values without carrying a revision.
    def plain(i: int, d: Any) -> torch.Tensor:
        return torch.tensor([0.5, 0.5])
    callback([torch.tensor([0.2, 0.8])], lambda i, d: 0.1, plain)
    callback([torch.tensor([0.7, 0.3])], lambda i, d: 0.1, distribution)
    assert snapshots[-1][0] == pytest.approx((0.7, 0.3))
    replacement = Distribution(lambda i, d: torch.tensor([0.5, 0.5]), lambda i: version[0])
    callback([torch.tensor([0.9, 0.1])], lambda i, d: 0.1, replacement)
    assert snapshots[-1][0] == pytest.approx((0.9, 0.1))
    assert sources[-1] is replacement.source
    def risk(i: int, decision: Any) -> float:
        return 0.1
    callback([torch.tensor([0.9, 0.1])], risk, replacement)
    callback([torch.tensor([0.9, 0.1])], risk, replacement)
    assert risk_sources[-1] is risk_sources[-2] is risk


def test_element_floor_maps_current_readings_and_fixed_items() -> None:
    from nca.selective import element_floor

    observed: list[Any] = []

    class Consumer:
        def floor(self, readings: list[Any], risk: Any, fixed: frozenset[int]) -> float:
            observed.append((readings, fixed))
            return sum(risk(i, None) for i in fixed)

    floor = element_floor(Consumer(), [(1, 0), (3, 0)], 4)
    assert floor is not None
    readings = [torch.tensor([0.4, 0.6]), torch.tensor([0.7, 0.3])]
    result = floor(readings, lambda i, d: (i + 1) * 0.1, frozenset({1}))
    assert result == pytest.approx(0.2)
    assert observed[0][1] == frozenset({3})
    assert observed[0][0][0] is None
    assert observed[0][0][1] == pytest.approx((0.4, 0.6))
    assert observed[0][0][3] == pytest.approx((0.7, 0.3))
    readings[1] = torch.tensor([0.2, 0.8])
    floor(readings, lambda i, d: 0.1, frozenset({1}))
    assert observed[-1][0][3] == pytest.approx((0.2, 0.8))
    assert observed[0][0][3] == pytest.approx((0.7, 0.3))


def test_certification_budget_obstruction() -> None:
    from nca.ladder import certification_possible, certify

    assert not certification_possible(44, 0.05, 0.1)
    assert certification_possible(45, 0.05, 0.1)
    assert not certification_possible(229, 0.01, 0.1)
    assert certification_possible(230, 0.01, 0.1)
    assert not certification_possible(0, 0.05, 0.1)
    for answered in range(21):
        for wrong in range(answered + 1):
            assert certify([(answered, wrong)], 0.05, 0.1) == []


def test_impossible_audit_skips_candidate_evaluations(monkeypatch: pytest.MonkeyPatch) -> None:
    from types import SimpleNamespace
    from nca import logic

    calls: list[int] = []

    def outcomes(route: Any, ladders: Any, samples: Any, delta: float,
                 **kwargs: Any) -> tuple[int, int]:
        calls.append(len(samples))
        assert len(samples) == 3  # Only the unchanged uncontrolled evaluation remains.
        return 3, 0

    monkeypatch.setattr(logic, "outcomes", outcomes)
    args = SimpleNamespace(depths=[2], samples=3, shift=0.2, seed=0, xor=0.0,
                           draws=1, audit=20, targets=[0.05, 0.01], alpha=0.1)
    logic.shifted(None, {}, args)
    assert calls == [3, 3]


def test_audit_stops_checking_at_first_failed_candidate(monkeypatch: pytest.MonkeyPatch,
                                                       capsys: pytest.CaptureFixture[str]) -> None:
    from types import SimpleNamespace
    from nca import logic

    calls: list[tuple[int, float]] = []

    def outcomes(route: Any, ladders: Any, samples: Any, delta: float,
                 **kwargs: Any) -> tuple[int, int]:
        calls.append((len(samples), delta))
        if len(calls) == 1:  # First checking candidate.
            assert len(samples) == 60
            assert kwargs["shared"] is None  # The fit coverage cannot certify.
            return 60, 0
        if len(calls) == 2:
            assert len(samples) == 60
            assert kwargs["shared"] is not None  # A passed check enables sharing.
            return 60, 20
        assert len(samples) == 3
        return 3, 0

    fit_calls: list[int] = []

    def fit_outcomes(route: Any, ladders: Any, samples: Any,
                     targets: Any) -> list[tuple[int, int]]:
        fit_calls.append(len(samples))
        counts = [(60, 0) for _ in targets]
        counts[2] = (0, 0)
        return counts

    monkeypatch.setattr(logic, "outcomes_many", fit_outcomes)
    monkeypatch.setattr(logic, "outcomes", outcomes)
    monkeypatch.setattr(logic, "certification_order", lambda candidates, alpha: [2, 0, 1, 3, 4, 5, 6])
    args = SimpleNamespace(depths=[2], samples=3, shift=0.2, seed=0, xor=0.0,
                           draws=1, audit=60, targets=[0.05], alpha=0.1)
    logic.shifted(None, {}, args)
    assert fit_calls == [60]
    assert len(calls) == 4
    assert calls[0][1] == pytest.approx(0.05 / logic.INFLATIONS[2])
    assert calls[1][1] == pytest.approx(0.05 / logic.INFLATIONS[0])
    assert calls[-1][1] == pytest.approx(0.05 / logic.INFLATIONS[2])
    assert "risk   1.5" in capsys.readouterr().out


def test_low_fit_coverage_checks_first_candidate_without_speculative_paths(
        monkeypatch: pytest.MonkeyPatch) -> None:
    from types import SimpleNamespace
    from nca import logic
    from nca.selective import Answer

    calls: list[str] = []

    def solve(route: Any, ladders: Any, text: str, target: float) -> Answer:
        calls.append(text)
        return Answer(None, 1.0, 1.0, True)

    def unexpected(*args: Any, **kwargs: Any) -> Any:
        pytest.fail("first failed check should not compute shared paths")

    monkeypatch.setattr(logic, "solve", solve)
    monkeypatch.setattr(logic, "solve_many", unexpected)
    monkeypatch.setattr(logic, "outcomes_many", lambda r, l, s, t: [(0, 0) for _ in t])
    monkeypatch.setattr(logic, "certification_order", lambda counts, alpha: [0, 1])
    args = SimpleNamespace(depths=[2], samples=3, shift=0.2, seed=0, xor=0.0,
                           draws=1, audit=60, targets=[0.05], alpha=0.1)
    logic.shifted(None, {}, args)
    assert len(calls) == 63  # Full first check plus uncontrolled evaluation.


@pytest.mark.parametrize("wrong_first", [False, True])
def test_checking_rejects_early_but_never_accepts_early(wrong_first: bool,
                                                       monkeypatch: pytest.MonkeyPatch) -> None:
    from types import SimpleNamespace
    from nca import logic
    from nca.ladder import certify
    from nca.selective import Answer

    samples = [SimpleNamespace(text=str(i), value=True) for i in range(60)]
    calls: list[str] = []

    def solve(route: Any, ladders: Any, text: str, delta: float) -> Answer:
        calls.append(text)
        return Answer(not (wrong_first and text == "0"), 1.0, 0.01, False)

    monkeypatch.setattr(logic, "solve", solve)
    counts = logic.outcomes(None, {}, samples, 0.05, reject_above=0.05, alpha=0.1)
    if wrong_first:
        assert len(calls) == 1 and counts == (1, 1)
        assert certify([counts], 0.05, 0.1) == []
    else:
        assert len(calls) == 60 and counts == (60, 0)
        assert certify([counts], 0.05, 0.1) == [0]


def test_shared_checking_paths_preserve_counts_and_early_rejection(
        monkeypatch: pytest.MonkeyPatch) -> None:
    from types import SimpleNamespace
    from nca import logic
    from nca.selective import Answer

    samples = [SimpleNamespace(text=str(i), value=True) for i in range(60)]
    targets = [0.1, 0.2, 0.3]
    individual: list[tuple[str, float]] = []
    batched: list[str] = []

    def answer(text: str, target: float) -> Answer:
        i = int(text)
        return Answer(not (target == 0.2 and i == 7), 1.0, 0.01,
                      target == 0.3 and i % 3 == 0)

    def solve(route: Any, ladders: Any, text: str, target: float) -> Answer:
        individual.append((text, target))
        return answer(text, target)

    def solve_many(route: Any, ladders: Any, text: str, targets: Any) -> list[Answer]:
        batched.append(text)
        return [answer(text, target) for target in targets]

    monkeypatch.setattr(logic, "solve", solve)
    monkeypatch.setattr(logic, "solve_many", solve_many)
    separate = [logic.outcomes(None, {}, samples, target, reject_above=0.05)
                for target in targets]
    shared = logic._AuditPaths(None, {}, samples, targets)
    combined = [logic.outcomes(None, {}, samples, target, reject_above=0.05,
                               shared=shared, target_index=i)
                for i, target in enumerate(targets)]
    assert combined == separate
    assert separate[1] == (8, 1)  # An irreversible failure stops at the same sample.
    assert len(batched) == len(samples) and len(individual) > len(batched)


def test_shared_refinement_trace_matches_independent_thresholds() -> None:
    rungs = [Rung(constant(str(i), output, float(i + 1))) for i, output in
             enumerate(((0.4, 0.6), (0.1, 0.9), (0.001, 0.999)))]
    states: list[Any] = []
    strict = refine([0, 0], [rungs, rungs], 0.001, observe=states.append)
    assert strict.abstained  # Include exhaustion, not only a successful strict run.
    for target in (0.001, 0.01, 0.2, 0.6, 0.9):
        shared = next((state for state in states if state.bound <= target), states[-1])
        independent = refine([0, 0], [rungs, rungs], target)
        assert shared.bound == independent.bound
        assert shared.cost == independent.cost
        assert all(torch.equal(a, b) for a, b in zip(shared.readings, independent.readings))
    assert states[0].cost == 2.0
    assert torch.allclose(states[0].readings[0], torch.tensor([0.4, 0.6], dtype=torch.float64))
    assert states[0].readings is not states[-1].readings


def test_solve_many_matches_independent_answers_and_costs() -> None:
    from nca.ladder import charge_per_cost
    from nca.selective import solve_many

    cheap = constant("cheap", (0.4, 0.6), 1.0, Contract(("ch",), "dist"))
    strong = constant("strong", (0.001, 0.999), 3.0, Contract(("ch",), "dist"))
    route = plan_stable([Splitter(), Joiner(), Argmax(), cheap, strong], ("text",), "out")
    assert route is not None
    ladders = {"dist": [Rung(cheap), Rung(strong)]}
    targets = [0.9, 0.01, 0.0001, 0.2, 0.9]
    shared = solve_many(route, ladders, "abcd", targets)
    assert shared == [solve(route, ladders, "abcd", delta) for delta in targets]
    assert solve_many(route, ladders, "abcd", targets, priority=charge_per_cost) == [
        solve(route, ladders, "abcd", delta, priority=charge_per_cost) for delta in targets]
    assert shared[0].cost < shared[1].cost
    assert shared[2].abstained
    assert solve_many(route, ladders, "abcd", []) == []
    assert solve_many(route, ladders, "", targets) == [
        solve(route, ladders, "", delta) for delta in targets]
    with pytest.raises(ValueError):
        solve_many(route, ladders, "abcd", [float("nan")])


@pytest.mark.parametrize("floors", [False, True])
def test_solve_stops_matches_independent_policies(floors: bool) -> None:
    from nca.ladder import charge_per_cost
    from nca.selective import solve_stops

    cheap = constant("cheap", (0.4, 0.6), 1.0, Contract(("ch",), "dist"))
    strong = constant("strong", (0.001, 0.999), 3.0, Contract(("ch",), "dist"))
    route = plan_stable([Splitter(), Joiner(), Argmax(), cheap, strong], ("text",), "out")
    assert route is not None
    ladders = {"dist": [Rung(cheap), Rung(strong)]}
    policies = [None, lambda state: state.cost >= 4, lambda state: state.cost >= 7,
                lambda state: False, lambda state: True]
    for text in ("abcd", ""):
        shared = solve_stops(route, ladders, text, 0.01, policies, floors=floors)
        assert shared == [solve(route, ladders, text, 0.01, floors=floors, stop=policy)
                          for policy in policies]
        assert solve_stops(route, ladders, text, 0.01, policies, floors=floors,
                           priority=charge_per_cost) == [
            solve(route, ladders, text, 0.01, floors=floors, stop=policy,
                  priority=charge_per_cost) for policy in policies]
        stopped = policies[1:3]
        assert solve_stops(route, ladders, text, 0.01, stopped, floors=floors) == [
            solve(route, ladders, text, 0.01, floors=floors, stop=policy) for policy in stopped]
    assert solve_stops(route, ladders, "abcd", 0.01, []) == []


def test_solve_stops_preserves_certificate_and_floor_endpoints() -> None:
    from nca.selective import solve_stops

    class Consumer:
        manifest = Manifest("certified", "1.0.0", Contract(("seq[dist]",), "out"))

        def certificate(self, readings, risk, distribution):
            return {i: risk(i, None) for i in range(len(readings))}

        def floor(self, readings, risk, fixed):
            return sum(risk(i, None) for i in fixed)

        def invoke(self, readings):
            return tuple(int(np.argmax(row)) for row in readings)

    cheap = constant("cheap-cert", (0.4, 0.6), 1.0, Contract(("ch",), "dist"))
    strong = constant("strong-cert", (0.1, 0.9), 3.0, Contract(("ch",), "dist"))
    route = plan_stable([Splitter(), Consumer(), cheap, strong], ("text",), "out")
    assert route is not None
    ladders = {"dist": [Rung(cheap), Rung(strong)]}
    policies = [None, lambda state: state.cost >= 4, lambda state: state.cost >= 7]
    for target in (0.01, 0.4, 1.0):
        shared = solve_stops(route, ladders, "abcd", target, policies, floors=True)
        assert shared == [solve(route, ladders, "abcd", target, floors=True, stop=policy)
                          for policy in policies]


def test_structural_shift_reaches_both_audit_halves_and_evaluation(
        monkeypatch: pytest.MonkeyPatch) -> None:
    from types import SimpleNamespace
    from nca import logic

    checked: list[int] = []

    def counts(route: Any, ladders: Any, samples: Any, delta: float,
               **kwargs: Any) -> tuple[int, int]:
        assert all(len(sample.words) <= 2 for sample in samples)
        checked.append(len(samples))
        return len(samples), 0

    def fit(route: Any, ladders: Any, samples: Any, targets: Any) -> list[tuple[int, int]]:
        assert all(len(sample.words) <= 2 for sample in samples)
        checked.append(-len(samples))
        return [(len(samples), 0) for _ in targets]

    monkeypatch.setattr(logic, "outcomes", counts)
    monkeypatch.setattr(logic, "outcomes_many", fit)
    args = SimpleNamespace(depths=[3], samples=3, shift=0.2, seed=0, xor=0.0,
                           draws=1, audit=60, targets=[0.05], alpha=0.1, early_leaf=1.0)
    logic.shifted(None, {}, args)
    assert checked[0] == -60
    assert checked.count(60) == len(logic.INFLATIONS)
    assert checked[-2:] == [3, 3]


def test_family_budget_reaches_all_audit_decision_paths(
        monkeypatch: pytest.MonkeyPatch, capsys: pytest.CaptureFixture[str]) -> None:
    from types import SimpleNamespace
    from nca import logic
    from nca.stats import family_audit_alpha

    level = family_audit_alpha(0.1, 8)
    seen = {"order": 0, "check": 0, "certify": 0}
    original = logic.certify

    def order(counts: Any, alpha: float) -> list[int]:
        assert alpha == level
        seen["order"] += 1
        return [0]

    def outcomes(route: Any, ladders: Any, samples: Any, delta: float,
                 **kwargs: Any) -> tuple[int, int]:
        if "reject_above" in kwargs:
            assert kwargs["alpha"] == level
            seen["check"] += 1
        return len(samples), 0

    def certify(counts: Any, delta: float, alpha: float) -> Any:
        assert alpha == level
        seen["certify"] += 1
        return original(counts, delta, alpha)

    monkeypatch.setattr(logic, "certification_order", order)
    monkeypatch.setattr(logic, "certify", certify)
    monkeypatch.setattr(logic, "outcomes", outcomes)
    monkeypatch.setattr(logic, "outcomes_many", lambda route, ladders, samples, targets: [
        (len(samples), 0) for _ in targets])
    args = SimpleNamespace(depths=[0, 1], draws=2, targets=[0.05, 0.1], samples=1,
                           audit=400, shift=0.2, seed=0, xor=0.0, alpha=0.1, family_alpha=0.1)
    logic.shifted(None, {}, args)
    assert seen == {"order": 8, "check": 8, "certify": 8}
    assert "audit family: 8 tests" in capsys.readouterr().out


def test_ranked_consumer_uses_same_order_for_answer_and_certificate() -> None:
    from nca.selective import solve_many

    class Consumer:
        manifest = Manifest("ranked-consumer", "1", Contract(("seq[dist]",), "out"))
        ranked_readings = True

        def certificate(self, readings, risk, distribution):
            assert readings[0].top([1, 2, 3]) == 2
            return {0: risk(0, ((1, 3), (2,)))}

        def invoke(self, readings):
            return readings[0].top([1, 2, 3])

    low = 1e-300
    reader = constant("ranked-reader", (1.0, low, math.nextafter(low, math.inf), 1e-301),
                      1.0, Contract(("ch",), "dist"))
    route = plan_stable([Splitter(), reader, Consumer()], ("text",), "out")
    assert route is not None
    answers = solve_many(route, {"dist": [Rung(reader)]}, "a", [0.5, 0.53])
    assert [answer.value for answer in answers] == [2, 2]
    assert [answer.abstained for answer in answers] == [True, False]
    assert answers[1].bound == pytest.approx(11 / 21, abs=1e-14)


def test_ranked_shared_paths_keep_each_observation_snapshot() -> None:
    from nca.selective import solve_many, solve_stops

    class Consumer:
        manifest = Manifest("ranked-snapshot-consumer", "1", Contract(("seq[dist]",), "out"))
        ranked_readings = True

        def certificate(self, readings, risk, distribution):
            return {0: risk(0, ((1, 3), (2,)))}

        def invoke(self, readings):
            return readings[0].top([1, 2, 3])

    low = 1e-300
    high = math.nextafter(low, math.inf)
    contract = Contract(("ch",), "dist")
    first = constant("ranked-first", (1.0, high, low, 1e-301), 1.0, contract)
    second = constant("ranked-second", (1.0, low, high, 1e-301), 2.0, contract)
    route = plan_stable([Splitter(), first, second, Consumer()], ("text",), "out")
    assert route is not None
    ladders = {"dist": [Rung(first), Rung(second)]}
    shared = solve_many(route, ladders, "a", [0.5, 0.45])
    assert [answer.value for answer in shared] == [1, 2]
    assert [answer.cost for answer in shared] == [1.0, 3.0]
    assert [answer.abstained for answer in shared] == [False, True]
    assert shared == [solve(route, ladders, "a", target) for target in (0.5, 0.45)]
    stops = [lambda state: True, None]
    shared_stops = solve_stops(route, ladders, "a", 0.45, stops)
    assert [answer.value for answer in shared_stops] == [1, 2]
    assert shared_stops == [solve(route, ladders, "a", 0.45, stop=stop) for stop in stops]


def test_ranked_fuser_and_legacy_fuser_match_their_risk_decisions() -> None:
    class Fuser:
        manifest = Manifest("ranked-fuser", "1", Contract(("dist",), "read"))
        ranked_readings = True

        def decision_classes(self, index, demand):
            return ((1, 3), (2,))

        def invoke(self, reading):
            return reading.top([1, 3, 2])

    class LegacyFuser(Fuser):
        ranked_readings = False

        def invoke(self, reading):
            return max((1, 3, 2), key=reading.__getitem__)

    low = 1e-300
    reader = constant("fused-ranked-reader", (1.0, low, math.nextafter(low, math.inf), 1e-301),
                      1.0, Contract(("ch",), "dist"))
    ladders = {"dist": [Rung(reader)]}
    ranked = plan_stable([Splitter(), reader, Fuser(), Joiner()], ("text",), "out")
    legacy = plan_stable([Splitter(), reader, LegacyFuser(), Joiner()], ("text",), "out")
    assert ranked is not None and legacy is not None
    selected = solve(ranked, ladders, "a", 0.5)
    old = solve(legacy, ladders, "a", 0.5)
    assert selected.value == (2,) and selected.abstained
    assert selected.bound == pytest.approx(11 / 21, abs=1e-14)
    assert old.value == (1,) and not old.abstained
    assert old.bound == pytest.approx(10 / 21, abs=1e-14)


def test_symbol_fuser_hands_ranked_order_to_parser() -> None:
    from nca.modules.digit_recognizer import DIGIT_DISTRIBUTION
    from nca.modules.operator_recognizer import OPERATOR_DISTRIBUTION
    from nca.modules.symbols import EXPRESSION, ExpressionParser, SymbolFuser

    low = 1e-300
    high = math.nextafter(low, math.inf)
    digit_weights = (0.0, low, high) + (0.0,) * 7
    operator_weights = (low, high, 0.0, 0.0)
    digit = constant("ranked-digit", digit_weights, 1, Contract(("ch",), DIGIT_DISTRIBUTION))
    operator = constant("ranked-operator", operator_weights, 1,
                        Contract(("ch",), OPERATOR_DISTRIBUTION))
    fuser, parser = SymbolFuser(), ExpressionParser()
    route = plan_stable([Splitter(), digit, operator, fuser, parser], ("text",), EXPRESSION)
    assert route is not None
    ladders = {DIGIT_DISTRIBUTION: [Rung(digit)], OPERATOR_DISTRIBUTION: [Rung(operator)]}
    answer = solve(route, ladders, "aaa", 2.0)
    assert answer.value == ("2", fuser.vocabulary.operators[1], "2")
    assert not answer.abstained

    class LegacyParser(ExpressionParser):
        ranked_symbol_readings = False

    assert not fuser.ranked_readings_for(LegacyParser())
    assert fuser.ranked_readings_for(parser)


@pytest.mark.parametrize("native", [False, True])
def test_extreme_temperature_preserves_tied_calibrated_readings(native, monkeypatch) -> None:
    from nca import ladder as ladder_module

    if native and getattr(ladder_module._NATIVE, "calibrated_groups", None) is None:
        pytest.skip("native calibration kernels are not built")
    if not native:
        monkeypatch.setattr(ladder_module, "_NATIVE", None)
    rung = Rung(constant("cold-equal", (0.5, 0.5), 1.0))
    decision = ((0,), (1,))
    rung.temperatures[None] = math.ulp(0.0)
    rung.temperatures[ladder_module.decision_key(decision)] = math.ulp(0.0)
    observation = rung.observe_ranked(None)
    for value in (observation, observation.logits, observation.logits.float()):
        assert rung.reading(value).tolist() == [0.5, 0.5]
        assert rung.distribution(value, decision).tolist() == [0.5, 0.5]
        assert rung.risk(value, decision) == 0.5


@pytest.mark.parametrize("decision", [None, ((0,), (1,))])
@pytest.mark.parametrize("temperature", [0.0, -1.0, math.inf, math.nan])
def test_ranked_distribution_rejects_invalid_temperature(decision, temperature) -> None:
    from nca.ladder import decision_key

    rung = Rung(constant("bad-distribution-temperature", (0.4, 0.6), 1.0))
    observation = rung.observe_ranked(None)
    rung.temperatures[decision_key(decision)] = temperature
    with pytest.raises(ValueError, match="ranked distribution requires a positive finite temperature"):
        rung.distribution(observation, decision)


@pytest.mark.parametrize("native", [False, True])
@pytest.mark.parametrize("temperature", [0.0, -1.0, math.inf, math.nan])
def test_calibration_paths_reject_invalid_temperature(native, temperature, monkeypatch) -> None:
    from nca import ladder as ladder_module

    if native and ladder_module._NATIVE is None:
        pytest.skip("native calibration kernels are not built")
    if not native:
        monkeypatch.setattr(ladder_module, "_NATIVE", None)
    rung = Rung(constant("invalid-temperature", (0.4, 0.6), 1.0))
    ranked = rung.observe_ranked(None)
    decision = ((0,), (1,))
    rung.temperatures[None] = temperature
    rung.temperatures[ladder_module.decision_key(decision)] = temperature
    for observation in (ranked, ranked.logits):
        for call in (lambda: rung.reading(observation),
                     lambda: rung.risk(observation),
                     lambda: rung.risk(observation, decision, reading=torch.tensor([0.4, 0.6])),
                     lambda: rung.distribution(observation),
                     lambda: rung.distribution(observation, decision),
                     lambda: rung.log_distribution(observation),
                     lambda: rung.log_distribution(observation, decision)):
            with pytest.raises(ValueError, match="positive finite temperature"):
                call()


@pytest.mark.parametrize("native", [False, True])
@pytest.mark.parametrize("case", ["empty_full", "empty_restricted", "nan", "positive_inf"])
def test_calibration_rejects_undefined_decision_mass(native, case, monkeypatch) -> None:
    from nca import ladder as ladder_module

    if native and ladder_module._NATIVE is None:
        pytest.skip("native calibration kernels are not built")
    if not native:
        monkeypatch.setattr(ladder_module, "_NATIVE", None)
    rung = Rung(constant("undefined-decision", (0.3, 0.3, 0.4), 1.0))
    decision = None if case == "empty_full" else ((1,), (2,))
    values = {
        "empty_full": [-math.inf, -math.inf, -math.inf],
        "empty_restricted": [0.0, -math.inf, -math.inf],
        "nan": [0.0, math.nan, -1.0],
        "positive_inf": [0.0, math.inf, -1.0],
    }[case]
    logits = torch.tensor(values, dtype=torch.float64)
    ranked = ladder_module.RankedObservation(logits, (1.0, 0.5, 0.25))
    for observation in (logits, ranked):
        for call in (lambda: rung.risk(observation, decision),
                     lambda: rung.distribution(observation, decision),
                     lambda: rung.log_distribution(observation, decision)):
            with pytest.raises(ValueError, match="positive mass"):
                call()
        if decision is None:
            with pytest.raises(ValueError, match="positive mass"):
                rung.reading(observation)


@pytest.mark.parametrize("native", [False, True])
def test_calibration_allows_zero_mass_entries_when_decision_has_mass(native, monkeypatch) -> None:
    from nca import ladder as ladder_module

    if native and ladder_module._NATIVE is None:
        pytest.skip("native calibration kernels are not built")
    if not native:
        monkeypatch.setattr(ladder_module, "_NATIVE", None)
    rung = Rung(constant("partly-empty-decision", (0.3, 0.3, 0.4), 1.0))
    logits = torch.tensor([0.0, -math.inf, -2.0], dtype=torch.float64)
    decision = ((1,), (2,))
    assert rung.risk(logits, decision) == 0.0
    assert rung.distribution(logits, decision).tolist() == [0.0, 1.0]
    assert rung.log_distribution(logits, decision).tolist() == [-math.inf, 0.0]


@pytest.mark.parametrize("native", [False, True])
@pytest.mark.parametrize("dtype,scale", [(torch.float32, 3e38), (torch.float64, 1e308)])
def test_calibration_rescales_before_overflow(native, dtype, scale, monkeypatch) -> None:
    from nca import ladder as ladder_module

    if native and ladder_module._NATIVE is None:
        pytest.skip("native calibration kernels are not built")
    if not native:
        monkeypatch.setattr(ladder_module, "_NATIVE", None)
    rung = Rung(constant("extreme-scale", (0.5, 0.5), 1.0))
    rung.temperatures[None] = scale
    decision = ((0,), (1,))
    rung.temperatures[decision] = scale
    logits = torch.tensor([scale, -scale], dtype=dtype)
    expected = torch.softmax(torch.tensor([1.0, -1.0], dtype=torch.float64), dim=0)
    assert torch.allclose(rung.reading(logits).double(), expected, atol=1e-7)
    assert torch.allclose(rung.distribution(logits, decision).double(), expected, atol=1e-7)
    assert torch.allclose(rung.log_distribution(logits, decision), expected.log(), atol=1e-7)
    assert rung.risk(logits, decision) == pytest.approx(expected[1].item(), abs=1e-7)


def test_calibration_overflow_rescaling_preserves_gradients() -> None:
    rung = Rung(constant("extreme-gradient", (0.5, 0.5), 1.0))
    rung.temperatures[None] = 1e308
    logits = torch.tensor([1e308, -1e308], dtype=torch.float64, requires_grad=True)
    probability = rung.reading(logits)[0]
    probability.backward()
    expected = probability.item() * (1 - probability.item()) / 1e308
    assert logits.grad is not None
    assert logits.grad[0].item() == pytest.approx(expected, rel=1e-12, abs=0)
    assert logits.grad[1].item() == pytest.approx(-expected, rel=1e-12, abs=0)


@pytest.mark.parametrize("native", [False, True])
@pytest.mark.parametrize("dtype,scale,temperature", [
    (torch.float16, 60000.0, 200000.0),
    (torch.float32, 3e38, 1e39),
])
def test_calibration_temperature_above_dtype_range(native, dtype, scale, temperature, monkeypatch) -> None:
    from nca import ladder as ladder_module

    if native and ladder_module._NATIVE is None:
        pytest.skip("native calibration kernels are not built")
    if not native:
        monkeypatch.setattr(ladder_module, "_NATIVE", None)
    rung = Rung(constant("large-temperature", (0.5, 0.5), 1.0))
    decision = ((0,), (1,))
    rung.temperatures[None] = temperature
    rung.temperatures[decision] = temperature
    logits = torch.tensor([scale, -scale], dtype=dtype)
    expected = torch.softmax(logits.double() / temperature, dim=0)
    tolerance = 5e-4 if dtype == torch.float16 else 1e-7
    assert torch.allclose(rung.reading(logits).double(), expected, atol=tolerance)
    assert torch.allclose(rung.distribution(logits, decision).double(), expected, atol=tolerance)
    assert torch.allclose(rung.log_distribution(logits, decision), expected.log(), atol=1e-7)
    assert rung.risk(logits, decision) == pytest.approx(expected[1].item(), abs=tolerance)


def test_calibration_large_temperature_keeps_float32_gradients() -> None:
    rung = Rung(constant("large-temperature-gradient", (0.5, 0.5), 1.0))
    rung.temperatures[None] = 1e39
    logits = torch.tensor([3e38, -3e38], dtype=torch.float32, requires_grad=True)
    rung.reading(logits)[0].backward()
    expected = torch.softmax(logits.detach().double() / 1e39, dim=0)
    expected_gradient = (expected[0] * expected[1] / 1e39).item()
    assert logits.grad is not None
    assert logits.grad[0].item() == pytest.approx(expected_gradient, rel=1e-5, abs=0)
    assert logits.grad[1].item() == pytest.approx(-expected_gradient, rel=1e-5, abs=0)


def test_calibration_rejects_nonfinite_legacy_kernel_results(monkeypatch) -> None:
    from types import SimpleNamespace
    from nca import ladder as ladder_module

    legacy = SimpleNamespace(
        calibrated_groups=lambda *args: [math.nan, math.nan],
        calibrated_log_groups=lambda *args: [-math.inf, math.nan],
    )
    monkeypatch.setattr(ladder_module, "_NATIVE", legacy)
    rung = Rung(constant("legacy-invalid", (0.5, 0.5), 1.0))
    logits = torch.tensor([0.0, -1.0], dtype=torch.float64)
    for call in (rung.distribution, rung.log_distribution):
        with pytest.raises(ValueError, match="positive mass"):
            call(logits, ((0,), (1,)))


@pytest.mark.parametrize("native", [False, True])
def test_legacy_risk_follows_numerical_reading_when_temperature_merges_order(native, monkeypatch) -> None:
    from nca import ladder as ladder_module

    if native and getattr(ladder_module._NATIVE, "calibrated_risk_at", None) is None:
        pytest.skip("native selected-risk kernel is not built")
    if not native:
        monkeypatch.setattr(ladder_module, "_NATIVE", None)
    rung = Rung(constant("warm-tie", (1.0, 2.0, 1.0), 1.0))
    rung.temperatures[None] = 1e308
    observed = rung.observe(None)
    reading = rung.reading(observed)
    assert reading.tolist() == [1 / 3] * 3
    groups = ((0,), (1, 2))
    assert rung.risk(observed, groups) == pytest.approx(0.75)
    assert rung.risk(observed, groups, reading=reading) == pytest.approx(0.75)


def test_legacy_consumer_does_not_understate_risk_after_reading_tie() -> None:
    class Consumer:
        manifest = Manifest("warm-consumer", "1", Contract(("seq[dist]",), "out"))

        def certificate(self, readings, risk, distribution):
            return {0: risk(0, ((0,), (1, 2)))}

        def invoke(self, readings):
            return max(range(3), key=readings[0].__getitem__)

    reader = constant("warm-reader", (1.0, 2.0, 1.0), 1.0, Contract(("ch",), "dist"))
    rung = Rung(reader)
    rung.temperatures[None] = 1e308
    route = plan_stable([Splitter(), reader, Consumer()], ("text",), "out")
    assert route is not None
    answer = solve(route, {"dist": [rung]}, "a", 0.5)
    assert answer.value == 0
    assert answer.bound == pytest.approx(0.75)
    assert answer.abstained


def test_native_risk_from_reading_matches_fallback_for_restricted_ties(monkeypatch) -> None:
    from nca import ladder as ladder_module

    if getattr(ladder_module._NATIVE, "calibrated_risk_for_reading", None) is None:
        pytest.skip("native reading-risk kernel is not built")
    rng = np.random.default_rng(481)
    cases = [(tuple(rng.uniform(0.01, 1.0, size=5)), temperature)
             for temperature in (0.01, 1.0, 1e308) for _ in range(12)]
    decisions = (None, ((4, 2), (0,), (3, 1)), ((0,), (1, 2, 3, 4)))

    def calculate():
        results = []
        for weights, temperature in cases:
            rung = Rung(constant("reading-risk", weights, 1.0))
            rung.temperatures[None] = temperature
            ordinary = rung.observe(None)
            ranked = rung.observe_ranked(None)
            for decision in decisions:
                results.append((rung.risk(ordinary, decision), rung.risk(ranked, decision)))
        return np.asarray(results)

    native = calculate()
    monkeypatch.setattr(ladder_module, "_NATIVE", None)
    assert np.allclose(native, calculate(), rtol=1e-13, atol=1e-15)


def test_native_unrestricted_risk_accepts_noncontiguous_readings(monkeypatch) -> None:
    from nca import ladder as ladder_module

    if getattr(ladder_module._NATIVE, "calibrated_risk_for_reading", None) is None:
        pytest.skip("native reading-risk kernel is not built")
    rung = Rung(constant("noncontiguous-risk", (0.2, 0.8), 1.0))
    logits = torch.tensor([-3.0, 9.0, -1.0, 9.0], dtype=torch.float64)[::2]
    reading = torch.tensor([0.4, 9.0, 0.6, 9.0], dtype=torch.float64)[::2]
    assert not logits.is_contiguous() and not reading.is_contiguous()
    native = rung.risk(logits, reading=reading)
    monkeypatch.setattr(ladder_module, "_NATIVE", None)
    assert native == pytest.approx(rung.risk(logits, reading=reading))


@pytest.mark.parametrize("native", [False, True])
@pytest.mark.parametrize("bad", [float('nan'), float('inf'), float('-inf'), -0.1])
def test_reused_risk_reading_rejects_invalid_values(native, bad, monkeypatch) -> None:
    from nca import ladder as ladder_module

    if native and getattr(ladder_module._NATIVE, "calibrated_risk_for_reading", None) is None:
        pytest.skip("native reading-risk kernel is not built")
    if not native:
        monkeypatch.setattr(ladder_module, "_NATIVE", None)
    rung = Rung(constant("invalid-cached-reading", (0.3, 0.7), 1.0))
    logits = torch.tensor([0.0, 1.0], dtype=torch.float64)
    for reading in (torch.tensor([0.5, bad]), torch.tensor([bad, 0.5])):
        with pytest.raises(ValueError, match="finite.*nonnegative"):
            rung.risk(logits, reading=reading)
    with pytest.raises(ValueError, match="shape"):
        rung.risk(logits, reading=torch.tensor([1.0]))
    with pytest.raises(ValueError, match="finite.*nonnegative"):
        rung.risk(logits, reading=torch.tensor([0.5 + 1j, 0.5]))


@pytest.mark.parametrize("native", [False, True])
def test_reused_risk_reading_allows_zero_mass_restricted_ties(native, monkeypatch) -> None:
    from nca import ladder as ladder_module

    if native and getattr(ladder_module._NATIVE, "calibrated_risk_for_reading", None) is None:
        pytest.skip("native reading-risk kernel is not built")
    if not native:
        monkeypatch.setattr(ladder_module, "_NATIVE", None)
    rung = Rung(constant("zero-cached-reading", (0.3, 0.3, 0.4), 1.0))
    logits = torch.tensor([0.0, -1000.0, -1001.0], dtype=torch.float64)
    reading = torch.tensor([1.0, 0.0, 0.0], dtype=torch.float64)
    assert rung.risk(logits, ((1,), (2,)), reading=reading) == pytest.approx(1 / (1 + math.e))


def test_reused_risk_reading_is_checked_with_legacy_kernel(monkeypatch) -> None:
    from types import SimpleNamespace
    from nca import ladder as ladder_module

    monkeypatch.setattr(ladder_module, "_NATIVE", SimpleNamespace(
        calibrated_risk_for_reading=lambda *args: 0.0))
    rung = Rung(constant("legacy-reading", (0.3, 0.7), 1.0))
    logits = torch.tensor([0.0, 1.0], dtype=torch.float64)
    with pytest.raises(ValueError, match="finite.*nonnegative"):
        rung.risk(logits, reading=torch.tensor([0.5, math.nan]))


@pytest.mark.parametrize("native", [False, True])
@pytest.mark.parametrize("scale", [1e-320, 1.0, 1e308])
def test_decision_risk_is_invariant_to_weight_scale(native, scale, monkeypatch) -> None:
    from nca import ladder as ladder_module

    if native and getattr(ladder_module._NATIVE, "weighted_decision_risk", None) is None:
        pytest.skip("native weighted-risk kernel is not built")
    if not native:
        monkeypatch.setattr(ladder_module, "_NATIVE", None)
    weights = torch.tensor([scale, scale, 0.0], dtype=torch.float64)
    assert ladder_module.risk(weights) == pytest.approx(0.5)
    assert ladder_module.risk(weights, ((0, 2), (1,))) == pytest.approx(0.5)
    assert ladder_module.risk(weights, ((0,), (1,)), _top=1) == pytest.approx(0.5)


@pytest.mark.parametrize("native", [False, True])
def test_decision_risk_retains_small_summed_tail_when_total_overflows(native, monkeypatch) -> None:
    from nca import ladder as ladder_module

    if native and getattr(ladder_module._NATIVE, "weighted_decision_risk", None) is None:
        pytest.skip("native weighted-risk kernel is not built")
    if not native:
        monkeypatch.setattr(ladder_module, "_NATIVE", None)
    weights = torch.tensor([1e308, 1e308] + [1e-16] * 100, dtype=torch.float64)
    decision = ((0, 1), tuple(range(2, 102)))
    value = ladder_module.risk(weights, decision)
    assert value > 0.0
    assert value == pytest.approx(5e-323, abs=1e-323)


@pytest.mark.parametrize("native", [False, True])
def test_decision_risk_preserves_positive_alternatives(native, monkeypatch) -> None:
    from nca import ladder as ladder_module

    if native and getattr(ladder_module._NATIVE, "weighted_decision_risk", None) is None:
        pytest.skip("native weighted-risk kernel is not built")
    if not native:
        monkeypatch.setattr(ladder_module, "_NATIVE", None)
    half = torch.tensor([60000.0, 0.001], dtype=torch.float16)
    expected = half[1].item() / (half[0].item() + half[1].item())
    assert ladder_module.risk(half) == pytest.approx(expected, rel=1e-12)
    extreme = torch.tensor([1e308, math.nextafter(0.0, 1.0)], dtype=torch.float64)
    assert ladder_module.risk(extreme) == math.nextafter(0.0, 1.0)
    assert ladder_module.risk(torch.tensor([1.0, 0.0], dtype=torch.float64)) == 0.0


@pytest.mark.parametrize("device", ["mps", "cuda"])
def test_accelerator_decision_risk_preserves_half_precision_tail(device) -> None:
    from nca.ladder import risk

    available = (torch.backends.mps.is_available() if device == "mps" else torch.cuda.is_available())
    if not available:
        pytest.skip(f"{device} is unavailable")
    weights = torch.tensor([60000.0, 0.001], dtype=torch.float16, device=device)
    expected = weights[1].item() / (weights[0].item() + weights[1].item())
    assert risk(weights) == pytest.approx(expected, rel=1e-6)


@pytest.mark.parametrize("native", [False, True])
@pytest.mark.parametrize("weights", [[0.0, 0.0], [-1.0, 2.0], [float('nan'), 1.0], [float('inf'), 1.0]])
def test_decision_risk_rejects_invalid_weights(native, weights, monkeypatch) -> None:
    from nca import ladder as ladder_module

    if native and getattr(ladder_module._NATIVE, "weighted_decision_risk", None) is None:
        pytest.skip("native weighted-risk kernel is not built")
    if not native:
        monkeypatch.setattr(ladder_module, "_NATIVE", None)
    with pytest.raises(ValueError, match="positive mass"):
        ladder_module.risk(torch.tensor(weights, dtype=torch.float64))


def test_decision_accepts_nonbuiltin_integral_indices_without_cache_aliasing() -> None:
    from nca.ladder import decision_key, risk

    reading = torch.tensor([0.6, 0.3, 0.1], dtype=torch.float64)
    decision = (np.int64(0), (np.int32(1), np.int64(2)))
    assert decision_key(decision) == (0, (1, 2))
    assert risk(reading, decision) == pytest.approx(0.4)
    for invalid in ((np.bool_(True),), ((np.float64(1),),)):
        with pytest.raises(ValueError, match="nonempty partition"):
            decision_key(invalid)


def test_partition_layout_positions_follow_class_order() -> None:
    from nca.ladder import _layout

    union, positions = _layout(((8, 2, 5), 7, (0, 4)))
    assert union == [8, 2, 5, 7, 0, 4]
    assert positions == [[0, 1, 2], [3], [4, 5]]


def test_native_restricted_risk_tracks_mutated_decisions() -> None:
    from nca import ladder as ladder_module

    if getattr(ladder_module._NATIVE, "calibrated_risk_for_reading", None) is None:
        pytest.skip("native reading-risk kernel is not built")
    rung = Rung(constant("changing-decision", (0.6, 0.3, 0.1), 1.0))
    observation = rung.observe_ranked(None)
    decision = [[0], [1]]
    first = rung.risk(observation, decision)
    decision[1].append(2)
    second = rung.risk(observation, decision)
    assert first == pytest.approx(1 / 3)
    assert second == pytest.approx(0.4)
    key = ladder_module.decision_key(decision)
    indices = ladder_module._native_indices(key)
    assert indices.tolist() == [0, 1, 2]
    assert not indices.flags.writeable


def test_decision_metadata_cache_eviction_preserves_results() -> None:
    from nca.ladder import _group_ids, _layout, _native_indices

    caches = (_layout, _group_ids, _native_indices)
    for cache in caches:
        cache.cache_clear()
    first = (0, (1, 2))
    expected_layout = _layout(first)
    expected_groups = _group_ids(first).copy()
    expected_indices = _native_indices(first).copy()
    capacity = _layout.cache_info().maxsize
    assert capacity is not None
    for i in range(capacity + 1):
        key = (i + 3, (i + 4, i + 5))
        for cache in caches:
            cache(key)
    for cache in caches:
        assert cache.cache_info().currsize <= cache.cache_info().maxsize
    assert _layout(first) == expected_layout
    assert np.array_equal(_group_ids(first), expected_groups)
    assert np.array_equal(_native_indices(first), expected_indices)


def test_native_partition_group_ids_match_reference(monkeypatch) -> None:
    from nca import ladder as ladder_module

    native = getattr(ladder_module._NATIVE, "partition_group_ids", None)
    if native is None:
        pytest.skip("native partition kernel is not built")
    assert native(np.array([2, 1, 3], dtype=np.int64), 6) == [0, 0, 1, 2, 2, 2]
    assert native(np.array([2, 0], dtype=np.int64), 2) == []
    assert native(np.array([2, 2], dtype=np.int64), 3) == []
    assert native(np.array([1], dtype=np.int64), 10**12) == []
    assert native(np.array([1, -1], dtype=np.int64), 2) == []
    rng = np.random.default_rng(738)
    for count in range(1, 32):
        lengths = rng.integers(1, 12, size=count, dtype=np.int64)
        expected = np.repeat(np.arange(count, dtype=np.int64), lengths).tolist()
        assert native(lengths, int(lengths.sum())) == expected
    key = ((7, 3), 2, (9, 5, 1))
    actual = ladder_module._group_ids.__wrapped__(key)
    monkeypatch.setattr(ladder_module, "_NATIVE", None)
    expected = ladder_module._group_ids.__wrapped__(key)
    assert np.array_equal(actual, expected)
    assert not actual.flags.writeable


def test_refinement_reuses_current_rung_account_and_refreshes_after_climb() -> None:
    class CountingRung(Rung):
        risk_calls = 0
        distribution_calls = 0

        def risk(self, log, classes=None, *, reading=None):
            self.risk_calls += 1
            return super().risk(log, classes, reading=reading)

        def distribution(self, log, classes=None):
            self.distribution_calls += 1
            return super().distribution(log, classes)

    low = CountingRung(constant("cache-low", (0.5, 0.5), 1.0))
    high = CountingRung(constant("cache-high", (0.99, 0.01), 2.0))
    seen = []

    def certificate(readings, risk, distribution):
        first = risk(0, None)
        assert risk(0, None) == first
        assert distribution(0, None) is distribution(0, None)
        for decision in ((0,), (1,)):
            assert risk(0, decision) == risk(0, decision)
            assert distribution(0, decision) is distribution(0, decision)
        assert risk(0, None) == first
        seen.append(first)
        return {0: first}

    result = refine([0], [[low, high]], 0.1, certificate=certificate)
    assert seen == pytest.approx([0.5, 0.01])
    assert not result.abstained and result.cost == 3.0
    assert [(r.risk_calls, r.distribution_calls) for r in (low, high)] == [(3, 3), (3, 3)]


def test_decision_tuple_with_mutable_groups_is_not_stale() -> None:
    from nca.ladder import decision_key

    group = [0]
    decision = (group, [1])
    assert decision_key(decision) == ((0,), (1,))
    group.append(2)
    assert decision_key(decision) == ((0, 2), (1,))
    group.append(True)
    with pytest.raises(ValueError, match="nonempty partition"):
        decision_key(decision)


@pytest.mark.parametrize("ranked", [False, True])
@pytest.mark.parametrize("with_floor", [False, True])
@pytest.mark.parametrize("with_stop", [False, True])
def test_incremental_default_account_matches_explicit_decisions(ranked, with_floor, with_stop) -> None:
    from nca.ladder import charge_per_cost

    low = Rung(constant("incremental-low", (0.55, 0.45), 1.0))
    high = Rung(constant("incremental-high", (0.98, 0.02), 2.0))
    ladders = [[low, high]] * 5
    floor = (lambda readings, risk, fixed: sum(risk(i, None) for i in fixed)) if with_floor else None
    stop = (lambda state: state.cost >= 9.0) if with_stop else None

    def run(classes):
        snapshots, trace = [], []
        result = refine([0] * 5, ladders, 0.01, classes=classes, floor=floor,
                        stop=stop, trace=trace, observe=snapshots.append,
                        priority=charge_per_cost, ranked=ranked)
        states = [(s.cost, s.bound, s.abstained, s.available,
                   [reading.tolist() for reading in s.readings]) for s in snapshots]
        return result.cost, result.bound, result.abstained, states, trace

    assert run(None) == run([[0, 1] for _ in range(5)])


@pytest.mark.parametrize("classes,ladders", [([None], 2), ([None] * 3, 2), (None, 1), (None, 3)])
def test_refinement_rejects_mismatched_inputs_before_invocation(classes, ladders) -> None:
    class CountingExpert:
        manifest = Manifest("length-validation", "1", Contract(("x",), "dist"))
        calls = 0

        def invoke(self, value):
            self.calls += 1
            return (0.5, 0.5)

    expert = CountingExpert()
    rung = Rung(expert)
    with pytest.raises(ValueError, match="one decision per value|one nonempty ladder per value"):
        refine([0, 0], [[rung]] * ladders, 0.5, classes=classes)
    assert expert.calls == 0


def test_refinement_rejects_empty_ladder_before_invocation() -> None:
    rung = Rung(constant("present", (0.5, 0.5), 1.0))
    with pytest.raises(ValueError, match="one nonempty ladder per value"):
        refine([0, 0], [[rung], []], 0.5)


@pytest.mark.parametrize("decision", [(0, 1), range(2), ((0,), (1,))])
def test_incremental_fixed_decisions_match_mutable_reference(decision) -> None:
    low = Rung(constant("fixed-low", (0.55, 0.45), 1.0))
    high = Rung(constant("fixed-high", (0.9, 0.1), 2.0))
    ladders = [[low, high]] * 4

    def run(decisions):
        trace = []
        result = refine([0] * 4, ladders, 0.01, classes=decisions, trace=trace)
        return result.cost, result.bound, result.abstained, trace

    assert run([decision] * 4) == run([list(decision) for _ in range(4)])


def test_refinement_rechecks_mutable_decision_after_observer_change() -> None:
    low = Rung(constant("mutable-low", (0.5, 0.5), 1.0))
    high = Rung(constant("mutable-high", (0.9, 0.1), 2.0))
    mutable = [0]
    bounds = []

    def observe(state):
        bounds.append(state.bound)
        if len(bounds) == 1:
            mutable.append(1)

    refine([0, 0], [[low, high], [low, high]], 0.2,
           classes=[mutable, None], observe=observe)
    assert bounds[:2] == pytest.approx([0.5, 0.6])


def test_restricted_temperature_requires_matching_held_out_labels() -> None:
    rung = Rung(constant("no-matching-labels", (0.5, 0.49, 0.01), 1.0))
    rung.calibrate([0, 0], torch.tensor([0, 0]))
    for action in (lambda: rung.temperature((1, 2)),
                   lambda: rung.risk(rung.observe_ranked(None), (1, 2)),
                   lambda: rung.distribution(rung.observe(None), (1, 2))):
        with pytest.raises(ValueError, match="without matching held-out labels"):
            action()
    assert (1, 2) not in rung.temperatures
    assert rung.risk(rung.observe_ranked(None), ((1, 2),)) == 0.0
    assert rung.distribution(rung.observe(None), ((1, 2),)).tolist() == [1.0]


def test_failed_recalibration_preserves_state_and_snapshots_labels(monkeypatch) -> None:
    rung = Rung(constant("calibration-state", (0.6, 0.4), 1.0))
    labels = torch.tensor([0, 1], dtype=torch.int32)
    rung.calibrate([0, 1], labels)
    previous = rung.held_out
    previous_temperatures = dict(rung.temperatures)
    labels[:] = 0
    assert previous is not None and previous[1].tolist() == [0, 1]
    for values, invalid in (([0, 1], torch.tensor([0, 2])),
                            ([0], torch.tensor([0, 1])),
                            ([0], torch.tensor([0.0])),
                            ([], torch.tensor([], dtype=torch.long))):
        with pytest.raises(ValueError, match="calibration"):
            rung.calibrate(values, invalid)
        assert rung.held_out is previous
        assert rung.temperatures == previous_temperatures

    def fail_fit(*args):
        raise RuntimeError("fit failed")

    monkeypatch.setattr(rung, "_fit", fail_fit)
    with pytest.raises(RuntimeError, match="fit failed"):
        rung.calibrate([0, 1], torch.tensor([0, 1]))
    assert rung.held_out is previous
    assert rung.temperatures == previous_temperatures


def test_calibration_snapshots_labels_before_invoking_expert() -> None:
    labels = torch.tensor([0, 1])

    class MutatingExpert:
        manifest = Manifest("label-mutator", "1", Contract(("x",), "dist"))

        def invoke(self, value):
            labels[1] = 0
            return (0.6, 0.4)

    rung = Rung(MutatingExpert())
    rung.calibrate([0, 1], labels)
    assert labels.tolist() == [0, 0]
    assert rung.held_out is not None
    assert rung.held_out[1].tolist() == [0, 1]


def test_calibration_snapshots_value_sequence_before_invoking_expert() -> None:
    values = [0, 1]

    class MutatingExpert:
        manifest = Manifest("value-list-mutator", "1", Contract(("x",), "dist"))

        def invoke(self, value):
            values[1] = 0
            return (0.9, 0.1) if value == 0 else (0.1, 0.9)

    rung = Rung(MutatingExpert())
    rung.calibrate(values, torch.tensor([0, 1]))
    assert values == [0, 0]
    assert rung.held_out is not None
    assert rung.held_out[0].exp().tolist()[1] == pytest.approx([0.1, 0.9])


@pytest.mark.parametrize("device", ["mps", "cuda"])
def test_accelerator_expert_can_fit_restricted_temperature(device) -> None:
    available = (torch.backends.mps.is_available() if device == "mps" else torch.cuda.is_available())
    if not available:
        pytest.skip(f"{device} is unavailable")

    class AcceleratorExpert:
        manifest = Manifest("accelerator-calibration", "1", Contract(("x",), "dist"))

        def invoke(self, value):
            return torch.tensor([0.6, 0.3, 0.1], device=device)

    rung = Rung(AcceleratorExpert())
    rung.calibrate([0, 1, 2, 3], torch.tensor([0, 1, 0, 1]))
    assert rung.held_out is not None
    if device == "mps":
        assert rung.held_out[0].device.type == "cpu"
    observed = rung.observe_ranked(None)
    assert observed.top() == 0
    assert rung.temperature((0, 1)) > 0
    assert rung.risk(observed, (0, 1)) == pytest.approx(0.5, abs=0.03)


@pytest.mark.parametrize("output", [
    (1 + 2j, 1 + 0j),
    [np.complex128(1 + 2j), 1.0],
    np.array([1 + 2j, 1 + 0j]),
    np.array([np.complex128(1 + 2j), 1.0], dtype=object),
    np.array([torch.tensor(1 + 2j), 1.0], dtype=object),
    [torch.tensor(1 + 2j), torch.tensor(1 + 0j)],
    torch.tensor([1 + 2j, 1 + 0j]),
])
def test_observation_rejects_complex_weights(output) -> None:
    rung = Rung(constant("complex-weights", output, 1.0))
    with pytest.raises(ValueError, match="real-valued"):
        rung.observe(None)
    with pytest.raises(ValueError, match="real-valued"):
        rung.observe_ranked(None)


@pytest.mark.parametrize("output", [
    ("0.9", "0.1"),
    np.array(["0.9", "0.1"]),
    np.array(["0.9", 0.1], dtype=object),
    np.array([b"0.9", 0.1], dtype=object),
])
def test_observation_rejects_text_weights(output) -> None:
    rung = Rung(constant("text-weights", output, 1.0))
    for observe in (rung.observe, rung.observe_ranked):
        with pytest.raises(ValueError, match="real-valued"):
            observe(None)


def test_observation_accepts_numeric_object_weights() -> None:
    values = np.array([Decimal("0.6"), Fraction(2, 5)], dtype=object)
    observation = Rung(constant("numeric-object-weights", values, 1.0)).observe_ranked(None)
    assert observation.weights == pytest.approx((0.6, 0.4))


@pytest.mark.parametrize("native", [False, True])
def test_observation_rejects_masked_weights(native, monkeypatch) -> None:
    from nca import ladder as ladder_module

    if native and getattr(ladder_module._NATIVE, "observation_logs", None) is None:
        pytest.skip("native observation kernel is not built")
    if not native:
        monkeypatch.setattr(ladder_module, "_NATIVE", None)
    masked = np.ma.array([0.99, 0.01], mask=[True, False])
    rung = Rung(constant("masked-weights", masked, 1.0))
    with pytest.raises(ValueError, match="masked weights"):
        rung.observe_ranked(None)
    unmasked = np.ma.array([0.99, 0.01], mask=[False, False])
    assert Rung(constant("unmasked-weights", unmasked, 1.0)).observe_ranked(None).top() == 0


@pytest.mark.parametrize("mode", ["default", "risk-certificate", "distribution-certificate"])
@pytest.mark.parametrize("ranked", [False, True])
def test_refinement_climbs_past_missing_restricted_calibration(mode, ranked) -> None:
    low = Rung(constant("missing-calibration", (0.8, 0.15, 0.05), 1.0))
    high = Rung(constant("usable-calibration", (0.05, 0.9, 0.05), 2.0))
    low.calibrate([0, 1], torch.tensor([0, 0]))
    high.calibrate(list(range(10)), torch.tensor([1] * 9 + [2]))
    decision = (1, 2)

    def certificate(readings, risk, distribution):
        if mode == "distribution-certificate":
            distribution(0, decision)
        return {0: risk(0, decision)}

    callback = None if mode == "default" else certificate
    snapshots = []
    result = refine([0], [[low, high]], 0.2, classes=[decision],
                    certificate=callback, observe=snapshots.append, ranked=ranked)
    assert [s.available for s in snapshots] == [False, True]
    assert snapshots[0].abstained and math.isinf(snapshots[0].bound)
    assert not result.abstained and result.bound == pytest.approx(0.1, abs=0.02)
    assert result.cost == 3.0

    missing = refine([0], [[low]], float("inf"), classes=[decision], certificate=callback, ranked=ranked)
    assert missing.abstained and not missing.available and math.isinf(missing.bound)


def test_solve_many_preserves_unavailable_calibration_until_usable_rung() -> None:
    from nca.selective import solve_many

    class Consumer:
        manifest = Manifest("calibration-consumer", "1", Contract(("seq[dist]",), "out"))

        def certificate(self, readings, risk, distribution):
            distribution(0, (1, 2))
            return {0: risk(0, (1, 2))}

        def invoke(self, readings):
            return max((1, 2), key=readings[0].__getitem__)

    low = constant("missing-rung", (0.8, 0.15, 0.05), 1.0, Contract(("ch",), "dist"))
    high = constant("usable-rung", (0.05, 0.9, 0.05), 2.0, Contract(("ch",), "dist"))
    a, b = Rung(low), Rung(high)
    a.calibrate([0, 1], torch.tensor([0, 0]))
    b.calibrate(list(range(10)), torch.tensor([1] * 9 + [2]))
    route = plan_stable([Splitter(), low, high, Consumer()], ("text",), "out")
    assert route is not None
    answers = solve_many(route, {"dist": [a, b]}, "a", [float("inf"), 0.2])
    assert all(not answer.abstained and answer.cost == 3.0 for answer in answers)
    assert [answer.value for answer in answers] == [1, 1]


def test_unavailable_floor_does_not_stop_usable_account() -> None:
    low = Rung(constant("floor-missing", (0.8, 0.15, 0.05), 1.0))
    high = Rung(constant("floor-usable", (0.99, 0.009, 0.001), 2.0))
    low.calibrate([0, 1], torch.tensor([0, 0]))
    low.temperatures[None] = 1.0
    high.temperatures[None] = 1.0

    def floor(readings, risk, fixed):
        return risk(0, (1, 2))

    result = refine([0], [[low, high]], 0.02, floor=floor)
    assert not result.abstained and result.cost == 3.0
    assert result.bound == pytest.approx(0.01)


@pytest.mark.parametrize("ranked", [False, True])
def test_unavailable_fixed_item_can_become_irrelevant_after_another_climb(ranked) -> None:
    unavailable = Rung(constant("fixed-unavailable", (0.8, 0.15, 0.05), 1.0))
    unavailable.calibrate([0, 1], torch.tensor([0, 0]))
    low = Rung(constant("switch-low", (0.5, 0.5), 1.0))
    high = Rung(constant("switch-high", (0.99, 0.01), 2.0))

    def certificate(readings, risk, distribution):
        if readings[1][0] < 0.9:
            return {0: risk(0, (1, 2)), 1: risk(1, None)}
        return {1: risk(1, None)}

    snapshots = []
    result = refine([0, 0], [[unavailable], [low, high]], 0.05,
                    certificate=certificate, observe=snapshots.append, ranked=ranked)
    assert [state.available for state in snapshots] == [False, True]
    assert snapshots[0].abstained and math.isinf(snapshots[0].bound)
    assert not result.abstained and result.bound == pytest.approx(0.01)
    assert result.cost == 4.0


@pytest.mark.parametrize("operation", ["risk", "distribution"])
def test_missing_calibration_is_reused_until_item_changes(operation) -> None:
    class CountingRung(Rung):
        missing_checks = 0

        def temperature(self, classes=None):
            if classes == (1, 2):
                self.missing_checks += 1
            return super().temperature(classes)

    missing = CountingRung(constant("missing-count", (0.8, 0.15, 0.05), 1.0))
    missing.calibrate([0, 1], torch.tensor([0, 0]))
    low = Rung(constant("many-low", (0.5, 0.5), 1.0))
    high = Rung(constant("many-high", (0.99, 0.01), 1.0))

    def certificate(readings, risk, distribution):
        if readings[1][0] < 0.9:
            if operation == "distribution":
                distribution(0, (1, 2))
            else:
                risk(0, (1, 2))
            raise AssertionError("missing calibration must make the account unavailable")
        return {1: risk(1, None)}

    result = refine([0, 0], [[missing], [low] * 8 + [high]], 0.05, certificate=certificate)
    assert not result.abstained and result.cost == 10.0
    assert missing.missing_checks == 1


@pytest.mark.parametrize("missing_operation", ["risk", "distribution"])
def test_missing_calibration_cache_is_scoped_to_query_type(missing_operation) -> None:
    from nca.ladder import MissingCalibrationError

    class PartialRung(Rung):
        def risk(self, log, classes=None, *, reading=None):
            if classes == (0, 1) and missing_operation == "risk":
                raise MissingCalibrationError("risk unavailable")
            return super().risk(log, classes, reading=reading)

        def distribution(self, log, classes=None):
            if classes == (0, 1) and missing_operation == "distribution":
                raise MissingCalibrationError("distribution unavailable")
            return super().distribution(log, classes)

    partial = PartialRung(constant("partial-calibration", (0.7, 0.3), 1.0))
    low = Rung(constant("query-low", (0.5, 0.5), 1.0))
    high = Rung(constant("query-high", (0.99, 0.01), 1.0))

    def certificate(readings, risk, distribution):
        if readings[1][0] < 0.9:
            (risk if missing_operation == "risk" else distribution)(0, (0, 1))
        else:
            (distribution if missing_operation == "risk" else risk)(0, (0, 1))
        return {1: risk(1, None)}

    result = refine([0, 0], [[partial], [low, high]], 0.05, certificate=certificate)
    assert not result.abstained and result.bound == pytest.approx(0.01)
    assert result.cost == 3.0


@pytest.mark.parametrize("native", [False, True])
def test_log_distribution_retains_underflowed_group_mass(native, monkeypatch) -> None:
    from nca import ladder as ladder_module

    if native and getattr(ladder_module._NATIVE, "calibrated_log_groups", None) is None:
        pytest.skip("native calibrated log groups are not built")
    if not native:
        monkeypatch.setattr(ladder_module, "_NATIVE", None)
    rung = Rung(constant("log-groups", (1.0, 1.0, 1.0), 1.0))
    logits = torch.tensor([0.0, -1000.0, -1001.0], dtype=torch.float64)
    decision = ((0,), (1, 2))
    assert rung.distribution(logits, decision).tolist() == [1.0, 0.0]
    logs = rung.log_distribution(logits, decision)
    assert logs[0].item() == pytest.approx(0.0)
    assert logs[1].item() == pytest.approx(float(np.logaddexp(-1000.0, -1001.0)))


def test_log_distribution_keeps_gradients() -> None:
    rung = Rung(constant("log-gradient", (0.2, 0.3, 0.5), 1.0))
    logits = torch.tensor([-1.0, -3.0, -5.0], requires_grad=True)
    result = rung.log_distribution(logits, ((0, 1), (2,)))
    result[1].backward()
    assert logits.grad is not None
    assert torch.isfinite(logits.grad).all()
    assert torch.count_nonzero(logits.grad) == 3


def test_log_distribution_respects_custom_probability_override() -> None:
    class CustomRung(Rung):
        def distribution(self, log, classes=None):
            return torch.tensor([0.8, 0.2], dtype=torch.float64)

    rung = CustomRung(constant("custom-probabilities", (0.1, 0.9), 1.0))
    captured = []

    def certificate(readings, risk, distribution):
        captured.append((distribution(0, None), distribution.log(0, None)))
        return {0: 0.0}

    result = refine([0], [[rung]], 0.0, certificate=certificate)
    assert not result.abstained
    assert torch.allclose(captured[0][0], captured[0][1].exp())
    assert captured[0][0].tolist() == pytest.approx([0.8, 0.2])


@pytest.mark.parametrize("native", [False, True])
def test_risk_allocation_preserves_smallest_positive_bound(native, monkeypatch) -> None:
    from nca import ladder as ladder_module

    if native and getattr(ladder_module._NATIVE, "risk_shares", None) is None:
        pytest.skip("native risk allocation is not built")
    if not native:
        monkeypatch.setattr(ladder_module, "_NATIVE", None)
    smallest = math.nextafter(0.0, 1.0)
    shares = allocate_risk(smallest, [1.0, 2.0, 1.0])
    assert shares == [0.0, smallest, 0.0]


def test_risk_allocation_preserves_positive_bound_with_older_native_kernel(monkeypatch) -> None:
    from types import SimpleNamespace
    from nca import ladder as ladder_module

    monkeypatch.setattr(ladder_module, "_NATIVE", SimpleNamespace(risk_shares=lambda bound, p: [0.0] * len(p)))
    smallest = math.nextafter(0.0, 1.0)
    assert allocate_risk(smallest, [1.0, 2.0, 1.0]) == [0.0, smallest, 0.0]


def test_native_log_groups_match_reference_across_extreme_rows(monkeypatch) -> None:
    from nca import ladder as ladder_module

    if getattr(ladder_module._NATIVE, "calibrated_log_groups", None) is None:
        pytest.skip("native calibrated log groups are not built")
    rng = np.random.default_rng(938)
    rung = Rung(constant("extreme-log-groups", (1.0,) * 8, 1.0))
    decision = ((7, 3), (0,), (4, 1, 6), (5, 2))
    rows = [torch.tensor(rng.uniform(-1500.0, 10.0, size=8), dtype=torch.float64)
            for _ in range(20)]
    rows.append(torch.tensor([0.0, -math.inf, -1000.0, -math.inf,
                              -2000.0, -1.0, -3.0, -math.inf], dtype=torch.float64))
    actual = [rung.log_distribution(row, decision).numpy() for row in rows]
    monkeypatch.setattr(ladder_module, "_NATIVE", None)
    for row, expected in zip(rows, actual):
        np.testing.assert_allclose(rung.log_distribution(row, decision).numpy(), expected,
                                   rtol=1e-12, atol=1e-12)
