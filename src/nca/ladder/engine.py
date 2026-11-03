"""Budgeted refinement execution over calibrated expert ladders."""

from __future__ import annotations

from collections import Counter
from collections.abc import Callable, Sequence
from dataclasses import dataclass
import math
from numbers import Integral
from typing import Any
import torch
from nca import ladder as _ladder


@dataclass
class Refinement:
    readings: list[torch.Tensor | _ladder.RankedReading]
    cost: float
    bound: float
    abstained: bool
    available: bool = True


def refine(values: Sequence[Any], ladders: Sequence[Sequence[_ladder.Rung]], delta: float,
           start: int = 0, classes: Sequence[_ladder.Decision] | None = None,
           certificate: _ladder.Certificate | None = None, floor: _ladder.Floor | None = None,
           additive_floor: bool = False, stop: _ladder.Stop | None = None,
           trace: list[_ladder.State] | None = None,
           observe: Callable[[Refinement], None] | None = None, *,
           priority: _ladder.ClimbPriority | None = None, ranked: bool = False) -> Refinement:
    """Read ``values[i]`` with ``ladders[i]``, refining until the bound meets ``delta``.

    Each value requires one nonempty ladder and, when supplied, one decision.
    Every item starts at rung ``min(start, top)``, reading each rung below it.
    The bound sums the charges of ``certificate``'s account; by default every
    item ``i`` is charged the risk of decision ``classes[i]``. While it exceeds
    ``delta`` the open item with the largest charge climbs a rung; if the
    readings determine no answer, the riskiest item. A supplied ``priority``
    instead ranks open items using their index, charge and next invocation
    cost; it must not mutate the refinement state. ``observe`` receives each
    state, including the initial and terminal states, with an independent
    outer reading list. Observers must not mutate the reading tensors. Experts,
    ladders and calibration parameters must remain fixed during a run. When
    ``ranked`` is enabled, readings preserve the original weight ordering;
    the certificate and downstream consumer must use that ordering to choose.
    Missing restricted calibration makes the account unavailable; refinement
    may climb another rung and abstains if no usable account is found.
    """
    if math.isnan(delta) or delta < 0:
        raise ValueError("target must be nonnegative and not NaN")
    decisions = list(classes) if classes is not None else [None] * len(values)
    if len(decisions) != len(values):
        raise ValueError("classes must contain exactly one decision per value")
    if len(ladders) != len(values) or any(not ladder for ladder in ladders):
        raise ValueError("ladders must contain one nonempty ladder per value")
    levels = [0] * len(values)
    logs: list[torch.Tensor | _ladder.RankedObservation] = [torch.empty(0)] * len(values)
    readings: list[_ladder.Reading] = [torch.empty(0)] * len(values)
    risks: list[tuple[_ladder.DecisionKey, float | _ladder._MissingCalibration] |
                dict[_ladder.DecisionKey, float | _ladder._MissingCalibration] | None] = [None] * len(values)
    distributions: list[tuple[_ladder.DecisionKey, torch.Tensor | _ladder._MissingCalibration] |
                        dict[_ladder.DecisionKey, torch.Tensor | _ladder._MissingCalibration] | None] = [None] * len(values)
    log_distributions: list[dict[_ladder.DecisionKey, torch.Tensor | _ladder._MissingCalibration] | None] = [None] * len(values)
    cost = 0.0

    def climb(i: int) -> None:
        nonlocal cost
        rung = ladders[i][levels[i]]
        risks[i] = None
        distributions[i] = None
        log_distributions[i] = None
        observation = rung.observe_ranked(values[i]) if ranked else rung.observe(values[i])
        logs[i] = observation
        numeric = rung.reading(observation)
        readings[i] = (_ladder.RankedReading(tuple(numeric.tolist()), observation.weights)
                       if isinstance(observation, _ladder.RankedObservation) else numeric)
        cost += rung.cost

    def item_risk(i: int, decision: _ladder.Decision) -> float:
        key = _ladder.decision_key(decision)
        cache = risks[i]
        if isinstance(cache, tuple) and cache[0] == key:
            result = cache[1]
        elif isinstance(cache, dict) and key in cache:
            result = cache[key]
        else:
            try:
                result = ladders[i][levels[i]].risk(
                    logs[i], decision, reading=readings[i] if isinstance(readings[i], torch.Tensor) else None)
            except _ladder.MissingCalibrationError:
                result = _ladder._MISSING_CALIBRATION
            if cache is None:
                risks[i] = (key, result)
            elif isinstance(cache, tuple):
                risks[i] = {cache[0]: cache[1], key: result}
            else:
                cache[key] = result
        if result is _ladder._MISSING_CALIBRATION:
            raise _ladder._UnavailableCalibration(i)
        return result

    def item_distribution(i: int, decision: _ladder.Decision) -> torch.Tensor:
        key = _ladder.decision_key(decision)
        cache = distributions[i]
        if isinstance(cache, tuple) and cache[0] == key:
            result = cache[1]
        elif isinstance(cache, dict) and key in cache:
            result = cache[key]
        else:
            try:
                result = ladders[i][levels[i]].distribution(logs[i], decision)
            except _ladder.MissingCalibrationError:
                result = _ladder._MISSING_CALIBRATION
            if cache is None:
                distributions[i] = (key, result)
            elif isinstance(cache, tuple):
                distributions[i] = {cache[0]: cache[1], key: result}
            else:
                cache[key] = result
        if result is _ladder._MISSING_CALIBRATION:
            raise _ladder._UnavailableCalibration(i)
        return result

    def item_log_distribution(i: int, decision: _ladder.Decision) -> torch.Tensor:
        key = _ladder.decision_key(decision)
        cache = log_distributions[i]
        if cache is None:
            cache = log_distributions[i] = {}
        if key not in cache:
            rung = ladders[i][levels[i]]
            log_method = getattr(rung, "log_distribution", None)
            base_log = getattr(log_method, "__func__", None) is _ladder.Rung.log_distribution
            base_distribution = getattr(rung.distribution, "__func__", None) is _ladder.Rung.distribution
            try:
                if log_method is None or (base_log and not base_distribution):
                    cache[key] = item_distribution(i, decision).double().log()
                else:
                    cache[key] = log_method(logs[i], decision)
            except _ladder.MissingCalibrationError:
                cache[key] = _ladder._MISSING_CALIBRATION
        result = cache[key]
        if result is _ladder._MISSING_CALIBRATION:
            raise _ladder._UnavailableCalibration(i)
        return result

    current_distribution = _ladder.Distribution(item_distribution, levels.__getitem__,
                                        log_lookup=item_log_distribution)

    for i in range(len(values)):
        climb(i)
        while levels[i] < min(start, len(ladders[i]) - 1):
            levels[i] += 1
            climb(i)
    fixed_account = certificate is None and all(map(_ladder._fixed_decision, decisions))
    # Seed the default account in native batches when this preserves the exact
    # per-item kernel and does not bypass lazy calibration or custom rungs.
    if (fixed_account and len(values) >= 16
            and getattr(_ladder._NATIVE, "calibrated_risk_rows_into", None) is not None
            and getattr(_ladder._NATIVE, "calibrated_risk_for_reading_checked", None) is not None):
        # A batch cannot span rungs, so skip detailed checks for rungs that
        # cannot possibly fill one. This matters for heterogeneous ladders.
        rung_counts = Counter(id(ladders[i][levels[i]]) for i in range(len(values)))
        batches: dict[tuple[int, _ladder.DecisionKey, int], list[int]] = {}
        for i, decision in enumerate(decisions):
            rung = ladders[i][levels[i]]
            if rung_counts[id(rung)] < 16:
                continue
            observation = logs[i]
            if ranked != isinstance(observation, _ladder.RankedObservation):
                continue
            log = observation.logits if isinstance(observation, _ladder.RankedObservation) else observation
            if (type(rung) is not _ladder.Rung or type(rung.temperatures) is not dict
                    or getattr(rung.risk, "__func__", None) is not _ladder.Rung.risk
                    or getattr(rung.risk_batch, "__func__", None) is not _ladder.Rung.risk_batch
                    or getattr(rung.temperature, "__func__", None) is not _ladder.Rung.temperature
                    or log.ndim != 1 or log.device.type != "cpu"
                    or log.dtype != torch.float64 or log.requires_grad):
                continue
            if not ranked:
                reading = readings[i]
                if (not isinstance(reading, torch.Tensor) or reading.shape != log.shape
                        or reading.device.type != "cpu" or reading.dtype != torch.float64
                        or reading.requires_grad):
                    continue
            elif len(observation.weights) != log.numel():
                continue
            key = _ladder.decision_key(decision)
            if key not in rung.temperatures and key is not None and rung.held_out is not None:
                continue
            try:
                union = None if key is None else _ladder._layout(key)[0]
                if log.numel() == 0 or (union is not None and max(union) >= log.numel()):
                    continue
            except ValueError:
                continue
            batches.setdefault((id(rung), key, log.numel()), []).append(i)
        for (_, key, width), indices in batches.items():
            selected_width = width if key is None else len(_ladder._layout(key)[0])
            chunk_size = 65536 // selected_width
            if chunk_size < 16:
                continue
            for offset in range(0, len(indices), chunk_size):
                chunk = indices[offset:offset + chunk_size]
                if len(chunk) < 16:
                    continue
                rung = ladders[chunk[0]][levels[chunk[0]]]
                try:
                    if ranked:
                        observations = [logs[i] for i in chunk]
                        batch = torch.stack([o.logits for o in observations])
                        ordering = torch.tensor([o.weights for o in observations], dtype=torch.float64)
                        result = rung.risk_batch(batch, key, ordering=ordering)
                    else:
                        batch = torch.stack([logs[i] for i in chunk])
                        reading = torch.stack([readings[i] for i in chunk])
                        result = rung.risk_batch(batch, key, reading=reading)
                except (ValueError, IndexError):
                    # Preserve the ordinary path's error and calibration order.
                    continue
                for i, value in zip(chunk, result.tolist()):
                    risks[i] = (key, value)
    default_account: dict[int, float] | None = None
    while True:
        unavailable: set[int] = set()
        try:
            if certificate is not None:
                account = certificate(readings, item_risk, current_distribution)
            elif default_account is not None:
                account = default_account
            else:
                account = {i: item_risk(i, d) for i, d in enumerate(decisions)}
                if fixed_account:
                    default_account = account
        except _ladder._UnavailableCalibration as exc:
            unavailable.add(exc.index)
            account = None
        if account is None:
            charges = {}
            for i, decision in enumerate(decisions):
                try:
                    charges[i] = item_risk(i, decision)
                except _ladder._UnavailableCalibration:
                    unavailable.add(i)
                    charges[i] = 1.0
            for i in unavailable:
                charges[i] = 1.0
        else:
            charges = account
        binary_charges = []
        for i, charge in charges.items():
            if (isinstance(i, bool) or (not isinstance(i, int) and not isinstance(i, Integral))
                    or not 0 <= i < len(values) or not math.isfinite(charge) or charge < 0):
                raise ValueError("certificate charges must have valid item indices and finite nonnegative values")
            rounded = float(charge)
            if charge > rounded:
                rounded = math.nextafter(rounded, math.inf)
            binary_charges.append(rounded)
        bound = math.inf if account is None else _ladder._upper_sum(binary_charges)
        if account is not None and not math.isfinite(bound):
            raise ValueError("certificate charges must have a finite total")
        available = account is not None
        if observe is not None:
            observe(Refinement(list(readings), cost, bound,
                               not available or bound > delta, available))
        if available and bound <= delta:
            break
        if not unavailable and (floor is not None or (certificate is None and additive_floor)):
            fixed = frozenset(i for i in range(len(values)) if levels[i] + 1 >= len(ladders[i]))
            if floor is not None:
                try:
                    if floor(readings, item_risk, fixed) > delta:
                        break
                except _ladder._UnavailableCalibration:
                    pass  # An unavailable floor cannot justify early abstention.
            elif _ladder._lower_sum([charges[i] for i in fixed]) > delta:
                break
        open_ = [i for i in charges if levels[i] + 1 < len(ladders[i])]
        if not open_:
            break
        if trace is not None or stop is not None:
            state = _ladder.State(bound, sum(charges[i] for i in open_), cost)
            if trace is not None:
                trace.append(state)
            if stop is not None and stop(state):
                break
        if priority is None:
            i = max(open_, key=charges.__getitem__)
        elif priority is _ladder.charge_per_cost:
            i = _ladder._cost_aware_choice(open_, charges, ladders, levels)
        else:
            def score(i: int) -> float:
                value = priority(i, float(charges[i]), float(ladders[i][levels[i] + 1].cost))
                if math.isnan(value):
                    raise ValueError("climb priority must not be NaN")
                return value
            i = max(open_, key=score)
        levels[i] += 1
        climb(i)
        if default_account is not None:
            try:
                default_account[i] = item_risk(i, decisions[i])
            except _ladder._UnavailableCalibration:
                default_account = None
    return Refinement(readings, cost, bound, not available or bound > delta, available)
