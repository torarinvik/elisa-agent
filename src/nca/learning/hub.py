"""Learning hub connectors without hub labels (§29.5).

A hub's values need not be observed directly. A new contributor type pairs its
values with those of any member already attached to the hub; mapping the
member's side through its encoder gives hub values, from which a supplied
fitter learns the new type's encoder and decoder. The hub therefore grows from
its first member by attachment. A type's hub error is at most its own fitting
error plus its partner's hub error (``NCA.attached_risk``), so errors add up
along attachment paths, and attaching to shallow members keeps them bounded
(``NCA.attachment_depth_risk``).
"""

from __future__ import annotations

from collections.abc import Callable, Hashable, Sequence

from nca.abi import Contract, Module, TypeId

Fitter = Callable[[Contract, Sequence[Hashable], Sequence[Hashable]], Module]
"""Fits a unary expert of a contract from aligned keys and labels."""


def attach(new: TypeId, hub: TypeId, partner_encoder: Module,
           pairs: Sequence[tuple[Hashable, Hashable]], fit: Fitter) -> tuple[Module, Module]:
    """An encoder ``new → hub`` and a decoder ``hub → new`` from pairs of a new
    type's values with a partner member's values."""
    contract = partner_encoder.manifest.contract
    if contract.output != hub or len(contract.inputs) != 1 or contract.slots:
        raise ValueError("the partner encoder must map one member type into the hub")
    if not pairs:
        raise ValueError("attachment needs paired observations")
    values = [value for value, _ in pairs]
    codes = [partner_encoder.invoke(partner) for _, partner in pairs]
    return (fit(Contract((new,), hub), values, codes),
            fit(Contract((hub,), new), codes, values))
