"""Plan execution under an explicit invocation budget."""

from __future__ import annotations

from typing import Mapping

from nca.abi import Message, TypeId
from nca.planner import Apply, Given, Plan
from nca.workspace import Workspace


class BudgetExceeded(RuntimeError):
    pass


def execute(
    plan: Plan,
    inputs: Mapping[TypeId, Message],
    workspace: Workspace,
    budget: int,
) -> Message:
    """Run ``plan``; each module invocation costs one budget unit.

    On failure the workspace is rolled back to its state before execution.
    """
    snapshot = workspace.snapshot()
    remaining = budget

    def run(node: Plan) -> Message:
        nonlocal remaining
        if isinstance(node, Given):
            return inputs[node.type_id]
        args = [run(arg) for arg in node.args]
        if remaining == 0:
            raise BudgetExceeded(f"budget of {budget} invocations exhausted")
        remaining -= 1
        manifest = node.module.manifest
        result = Message(
            type_id=manifest.contract.output,
            payload=node.module.invoke(*(a.payload for a in args)),
            producer=manifest.ref,
            parents=tuple(a.message_id for a in args),
        )
        workspace.post(result)
        return result

    try:
        for message in inputs.values():
            if message.message_id not in workspace:
                workspace.post(message)
        return run(plan)
    except Exception:
        workspace.rollback(snapshot)
        raise
