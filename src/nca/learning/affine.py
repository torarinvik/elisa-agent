"""Scalar least-squares interface fitting with explicit numeric limits (§36.18)."""

import math
from collections.abc import Sequence
from typing import Any

from nca.abi import Contract, Manifest
from nca.learning.numeric import _observation
from nca.objects import Primitive, contract_data, contract_from, digest


class AffineAdapter:
    def __init__(self, contract: Contract, slope: float, offset: float, cost: float) -> None:
        if len(contract.inputs) != 1 or contract.slots:
            raise ValueError("affine adapters require a unary slot-free contract")
        self.slope, self.offset = _observation(slope), _observation(offset)
        if not math.isfinite(cost) or cost < 0:
            raise ValueError("adapter cost must be finite and nonnegative")
        data = {"contract": contract_data(contract), "slope": slope, "offset": offset, "cost": cost}
        self.manifest = Manifest(f"learned-affine/{digest(data)}", "1", contract,
                                 cost=cost, effects=frozenset())

    def invoke(self, value: float) -> float:
        return _observation(self.slope * _observation(value) + self.offset)


def fit_affine(contract: Contract, keys: Sequence[Any], labels: Sequence[Any], *,
               cost: float) -> AffineAdapter:
    """Fit scalar finite-float pairs; reject unrepresentable statistics explicitly.

    Constant inputs produce the mean target. Nonconstant inputs whose centered
    variance underflows are rejected instead of silently treated as constant.
    Real-valued least-squares optimality does not prove floating-point accuracy
    or generalization. Select the resulting route on independent observations.
    """
    if not keys or len(keys) != len(labels):
        raise ValueError("affine fitting needs aligned nonempty observations")
    xs, ys = tuple(map(_observation, keys)), tuple(map(_observation, labels))
    try:
        n = len(xs)
        xm, ym = math.fsum(x / n for x in xs), math.fsum(y / n for y in ys)
        if all(x == xs[0] for x in xs):
            slope, offset = 0.0, ym
        else:
            xx = math.fsum((x - xm) ** 2 for x in xs)
            xy = math.fsum((x - xm) * (y - ym) for x, y in zip(xs, ys, strict=True))
            if not math.isfinite(xx) or not math.isfinite(xy) or xx == 0:
                raise ValueError("unrepresentable centered variance or covariance")
            slope = xy / xx
            offset = ym - slope * xm
        return AffineAdapter(contract, slope, offset, cost)
    except (OverflowError, ValueError) as error:
        raise ValueError(f"affine fit failed within floating-point range: {error}") from error


def load_affine(contract: dict[str, Any], slope: float, offset: float, cost: float) -> AffineAdapter:
    return AffineAdapter(contract_from(contract), slope, offset, cost)


def affine_object(adapter: AffineAdapter, *, size: int) -> Primitive:
    """Snapshot the generic fitted model; no task implementation or teacher is retained."""
    return Primitive(adapter.manifest, "nca/affine@1",
                     {"contract": contract_data(adapter.manifest.contract),
                      "slope": adapter.slope, "offset": adapter.offset, "cost": adapter.manifest.cost},
                     size=size)
