"""Acquire typed bridges from paired expert observations (§36.17)."""

import math
from collections.abc import Sequence
from dataclasses import replace
from typing import Any, Protocol

from nca.abi import Contract, Module
from nca.discovery import Decoded, Proposal, fit_decoder


class AdapterFitter(Protocol):
    def __call__(self, contract: Contract, keys: Sequence[Any], labels: Sequence[Any], *,
                 cost: float) -> Module: ...


def propose_adapter(incumbent: Module, source: Module, teacher: Module, consumer: Module,
                    rows: Sequence[tuple[Any, ...]], *, decoder_cost: float,
                    fit: AdapterFitter = fit_decoder) -> Proposal:
    """Fit a supplied bridge family and propose the completed external route.

    Call only with training rows, e.g. within discover's proposer. Source and
    teacher see the same external inputs/fillings. Their output types need not
    agree. The teacher must output the consumer's input type. The consumer is
    unary and slot-free. The default fitter needs stable, hashable categories;
    alternative fitters receive only the paired training values.
    Teacher agreement is training evidence, not a semantic-equivalence proof;
    select on independent end-to-end outcomes. No risk certificate is implied.
    """
    if not math.isfinite(decoder_cost) or decoder_cost < 0:
        raise ValueError("decoder cost must be finite and nonnegative")
    contract = incumbent.manifest.contract
    for module in (source, teacher):
        if replace(module.manifest.contract, output=contract.output) != contract:
            raise ValueError("paired experts must preserve external inputs, slots and relevance")
    head = consumer.manifest.contract
    if (head.inputs != (teacher.manifest.contract.output,) or head.slots
            or head.output != contract.output):
        raise ValueError("consumer must accept the teacher interface and produce the task output")
    if not rows or any(len(row) != len(contract.slots) + len(contract.inputs) for row in rows):
        raise ValueError("training rows must supply slot fillings followed by inputs")
    pairs = [(source.invoke(*row), teacher.invoke(*row)) for row in rows]
    adapter_contract = Contract((source.manifest.contract.output,), head.inputs[0])
    adapter = fit(adapter_contract, tuple(a for a, _ in pairs), tuple(b for _, b in pairs),
                  cost=decoder_cost)
    if adapter.manifest.contract != adapter_contract:
        raise ValueError("fitted adapter must preserve the requested interface contract")
    bridge = Decoded(source, adapter, teacher.manifest.contract)
    return Proposal(Decoded(bridge, consumer, contract))
