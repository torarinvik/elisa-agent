"""Plan execution under an explicit invocation budget."""

from __future__ import annotations

from typing import Mapping

from nca.abi import Message, TypeId
from nca.planner import Given, Map, Plan, output_type
from nca.workspace import Workspace


class BudgetExceeded(RuntimeError):
    pass


def execute(
    plan: Plan,
    inputs: Mapping[TypeId, Message],
    workspace: Workspace,
    budget: int,
) -> Message:
    """Run ``plan``; each module invocation, including each element of a
    ``Map``, costs one budget unit.

    On failure the workspace is rolled back to its state before execution.
    """
    snapshot = workspace.snapshot()
    remaining = budget

    def run(node: Plan, env: Mapping[TypeId, Message]) -> Message:
        nonlocal remaining
        if isinstance(node, Given):
            return env[node.type_id]
        if isinstance(node, Map):
            source = run(node.source, env)
            results = []
            for value in source.payload:
                element = Message(node.element, value, "map", (source.message_id,))
                workspace.post(element)
                results.append(run(node.body, {node.element: element}))
            result = Message(
                type_id=output_type(node),
                payload=[r.payload for r in results],
                producer="map",
                parents=(source.message_id, *(r.message_id for r in results)),
            )
            workspace.post(result)
            return result
        args = [run(arg, env) for arg in node.args]
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
        return run(plan, inputs)
    except Exception:
        workspace.rollback(snapshot)
        raise
