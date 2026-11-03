"""Calibration attestations and calibrated expert adapters."""

from __future__ import annotations

from collections.abc import Sequence
from typing import Any
import torch
from nca.abi import Module
from nca.objects import Attestation, Ref, canonical
from nca import ladder as _ladder


def recalibrated(rungs: Sequence[_ladder.Rung], values: Sequence[Any], labels: torch.Tensor,
                 ) -> list[_ladder.Rung]:
    """Copies of ``rungs`` calibrated on other held-out data, such as a
    teacher-labeled audit from the deployment distribution."""
    copies = [_ladder.Rung(r.module) for r in rungs]
    for rung in copies:
        rung.calibrate(values, labels)
    return copies


class Calibrated:
    """An expert read through its rung (§33.1): it outputs the calibrated
    distribution and reports ``1 - max p``, the risk of deciding by it,
    which bounds the risk of every restricted decision (Theorem 16.4)."""

    def __init__(self, rung: _ladder.Rung) -> None:
        self.rung = rung
        self.manifest = rung.module.manifest

    def invoke(self, value: Any) -> tuple[float, ...]:
        return tuple(self.rung.reading(self.rung.observe(value)).tolist())

    def risk(self, output: Sequence[float], *inputs: Any) -> float:
        return _ladder.risk(torch.tensor(output, dtype=torch.float64))


def calibration(rung: _ladder.Rung, subject: Ref, decisions: Sequence[_ladder.Decision] = (),
                issuer: str = "") -> Attestation:
    """The rung's temperatures, after fitting those of ``decisions``, as an
    attestation about ``subject``, its expert's reference (§28.4). The
    held-out data stay with the issuer."""
    for decision in decisions:
        rung.temperature(decision)
    entries = [[None if key is None else [list(e) if isinstance(e, tuple) else e for e in key],
                temperature] for key, temperature in rung.temperatures.items()]
    entries.sort(key=lambda entry: canonical(entry[0]))
    return Attestation(subject, _ladder.CALIBRATION, {"temperatures": entries}, issuer)


def attested(module: Module, attestation: Attestation) -> _ladder.Rung:
    """A rung for ``module`` reading the temperatures a calibration
    attestation states; a decision it does not state has temperature 1."""
    if attestation.kind != _ladder.CALIBRATION:
        raise ValueError(f"not a calibration attestation: {attestation.kind}")
    identity = getattr(module, "identity", None)
    if identity is not None and identity != attestation.subject:
        raise ValueError("the attestation is about another expert")
    temperatures = {
        None if key is None else tuple(tuple(e) if isinstance(e, list) else e for e in key):
        float(temperature) for key, temperature in attestation.claim["temperatures"]}
    return _ladder.Rung(module, temperatures)
