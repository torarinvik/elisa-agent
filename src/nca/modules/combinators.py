"""Higher-order experts (§20): combinators whose sub-computations are slots.

* ``MapExpert``: ``map`` as a library expert at one pair of element types,
  with slot ``[a] ⇒ e``, input ``seq a`` and output ``seq e``. It costs
  nothing itself and calls its slot once per element (``NCA.embed_wellTyped``:
  every plan using the kernel's built-in ``map`` is expressed this way at the
  same cost). Demand on its output passes through to each call.
  ``embed_maps`` rewrites a plan accordingly.
* ``Fallback``: the confidence cascade of §14 with both recognizers as slots
  ``[x] ⇒ y``. It answers with the first slot's distribution when its most
  probable class has probability at least ``threshold``, and calls the second
  slot otherwise. Its error is a property of the pair of fillings
  (``NCA.cascade_error_eq``), not a sum over them, so it declares
  ``assess``: on audit inputs, the cost and error of the cascade for given
  fillings, which the Pareto planner uses in place of the additive formula.
"""

from __future__ import annotations

from collections.abc import Callable, Sequence
from typing import Any

import torch

from nca.abi import Calls, Contract, Manifest, Message, SequenceDemand, TypeId, seq_type
from nca.optimize import Option
from nca.planner import Apply, Given, Plan, output_type
from nca.runtime import execute
from nca.workspace import Workspace


class MapExpert:
    def __init__(self, element: TypeId, result: TypeId) -> None:
        self.manifest = Manifest(
            f"nca.map.{element}.{result}", "1.0.0",
            Contract((seq_type(element),), seq_type(result), (((element,), result),)),
            cost=0.0, calls=(Calls(per_element=1.0),))

    def __eq__(self, other: object) -> bool:
        return isinstance(other, MapExpert) and other.manifest == self.manifest

    def __hash__(self) -> int:
        return hash(self.manifest)

    def invoke(self, body: Callable[..., Any], values: Sequence[Any]) -> list[Any]:
        outer = getattr(body, "outer", None)
        n = len(values)
        return [body(v, demand=outer.element(i, n) if isinstance(outer, SequenceDemand) else outer)
                for i, v in enumerate(values)]


def embed_maps(plan: Plan) -> Plan:
    """``plan`` with every built-in ``map`` replaced by a ``MapExpert``
    application (``NCA.embed_wellTyped``)."""
    if isinstance(plan, Given):
        return plan
    if isinstance(plan, Apply):
        return Apply(plan.module, tuple(embed_maps(a) for a in plan.args),
                     tuple(embed_maps(f) for f in plan.slots))
    body = embed_maps(plan.body)
    return Apply(MapExpert(plan.element, output_type(body)), (embed_maps(plan.source),), (body,))


class Fallback:
    def __init__(self, element: TypeId, result: TypeId, threshold: float,
                 audit: Sequence[Any], labels: Sequence[int], cost: float = 0.0) -> None:
        self.element, self.threshold = element, threshold
        self.audit, self.labels = list(audit), torch.tensor(list(labels))
        slot = ((element,), result)
        self.manifest = Manifest(f"nca.fallback.{element}.{result}.{threshold:g}", "1.0.0",
                                 Contract((element,), result, (slot, slot)), cost=cost,
                                 calls=(Calls(1.0), Calls(1.0)))
        self._readings: dict[Plan, tuple[torch.Tensor, torch.Tensor]] = {}

    def invoke(self, first: Callable[..., Any], second: Callable[..., Any],
               value: Any) -> tuple[float, ...]:
        own = first(value)
        return own if max(own) >= self.threshold else second(value)

    def readings(self, plan: Plan) -> tuple[torch.Tensor, torch.Tensor]:
        """The plan's distribution and cost on each audit input, computed once."""
        if plan not in self._readings:
            rows, costs = [], []
            for value in self.audit:
                workspace = Workspace()
                rows.append(execute(plan, {self.element: Message(self.element, value, "audit")},
                                    workspace, 10_000).payload)
                costs.append(workspace.spent)
            self._readings[plan] = (torch.tensor(rows), torch.tensor(costs, dtype=torch.float64))
        return self._readings[plan]

    def assess(self, fillings: Sequence[Option]) -> tuple[float, float]:
        """Audit cost and error of the cascade with these fillings
        (``NCA.cascade_error_eq``). The second filling is charged its cost on
        the inputs where it is called: its expected cost times ``P(unsure)``
        (``NCA.cascade_expected_cost``) would assume its cost does not depend
        on whether it is called, which fails when it shares the first's doubt."""
        (p1, c1), (p2, c2) = (self.readings(f.plan) for f in fillings)
        confident = p1.max(dim=1).values >= self.threshold
        answer = torch.where(confident[:, None], p1, p2).argmax(dim=1)
        cost = float((c1 + torch.where(confident, 0.0, c2)).mean())
        return cost, int((answer != self.labels).sum()) / len(self.labels)
