"""Finite tuple-vector affine interface learning (§36.19)."""

import math
from collections.abc import Sequence
from typing import Any

import numpy as np

from nca.abi import Contract, Manifest
from nca.learning.numeric import _observation
from nca.objects import Primitive, contract_data, contract_from, digest


def _vector(value: Any) -> tuple[float, ...]:
    if not isinstance(value, tuple):
        raise ValueError("vector observations must be tuples of finite floats")
    return tuple(_observation(x) for x in value)


class VectorAffineAdapter:
    def __init__(self, contract: Contract, weights: Sequence[Sequence[float]], cost: float) -> None:
        if len(contract.inputs) != 1 or contract.slots:
            raise ValueError("vector adapters require a unary slot-free contract")
        if not math.isfinite(cost) or cost < 0:
            raise ValueError("adapter cost must be finite and nonnegative")
        rows = [tuple(_observation(x) for x in row) for row in weights]
        if not rows or any(len(row) != len(rows[0]) for row in rows):
            raise ValueError("weights must be a nonempty rectangular matrix")
        self._weights = np.array(rows, dtype=float)
        self._weights.flags.writeable = False
        data = {"contract": contract_data(contract), "weights": rows, "cost": cost}
        self.manifest = Manifest(f"learned-vector-affine/{digest(data)}", "1", contract,
                                 cost=cost, effects=frozenset())

    def invoke(self, value: tuple[float, ...]) -> tuple[float, ...]:
        vector = _vector(value)
        if len(vector) != self._weights.shape[0] - 1:
            raise ValueError("input vector dimension differs from fitted interface")
        with np.errstate(over="ignore", invalid="ignore"):
            result = np.asarray(vector) @ self._weights[:-1] + self._weights[-1]
        return tuple(_observation(x) for x in result.tolist())


def fit_vector_affine(contract: Contract, keys: Sequence[Any], labels: Sequence[Any], *,
                      cost: float) -> VectorAffineAdapter:
    """Fit arbitrary consistent dimensions, including empty vectors.

    Rank-deficient observations use NumPy's minimum-norm least-squares solution;
    this does not identify unobserved directions or establish generalization.
    Reject nonfinite data, parameters and predictions. No type alias is created.
    """
    if not keys or len(keys) != len(labels):
        raise ValueError("vector fitting needs aligned nonempty observations")
    xs, ys = list(map(_vector, keys)), list(map(_vector, labels))
    if any(len(x) != len(xs[0]) for x in xs) or any(len(y) != len(ys[0]) for y in ys):
        raise ValueError("inconsistent vector dimensions")
    design = np.column_stack((np.asarray(xs), np.ones(len(xs))))
    try:
        weights = np.linalg.lstsq(design, np.asarray(ys), rcond=None)[0]
    except np.linalg.LinAlgError as error:
        raise ValueError("vector least-squares solver failed") from error
    return VectorAffineAdapter(contract, weights.tolist(), cost)


def load_vector_affine(contract: dict[str, Any], weights: list[list[float]],
                       cost: float) -> VectorAffineAdapter:
    return VectorAffineAdapter(contract_from(contract), weights, cost)


def vector_affine_object(adapter: VectorAffineAdapter, *, size: int) -> Primitive:
    """Snapshot parameters only; training teachers are not runtime dependencies."""
    return Primitive(adapter.manifest, "nca/vector-affine@1",
                     {"contract": contract_data(adapter.manifest.contract),
                      "weights": adapter._weights.tolist(), "cost": adapter.manifest.cost},
                     size=size)
