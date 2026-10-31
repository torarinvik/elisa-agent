"""Plan execution under an explicit invocation budget, with kernel-mediated requests.

A module may return a ``Request`` instead of its output. The runtime then asks
the resolver (the kernel) for a plan producing the requested type from the
request's inputs, with every module of the current request chain excluded,
executes it under the same budget, and uses its result as the requester's
output. Modules never invoke one another; every invocation is planned,
type-checked, budgeted, and recorded by the kernel (``lean/NCA/Request.lean``).
"""

from __future__ import annotations

from typing import Mapping, Protocol

from nca.abi import Message, Request, TypeId
from nca.planner import Given, Map, Plan, output_type
from nca.workspace import Workspace


class BudgetExceeded(RuntimeError):
    pass


class UnresolvedRequest(RuntimeError):
    pass


class Resolver(Protocol):
    def resolve(self, request: Request, chain: tuple[str, ...]) -> Plan | None: ...


def execute(
    plan: Plan,
    inputs: Mapping[TypeId, Message],
    workspace: Workspace,
    budget: int,
    resolver: Resolver | None = None,
) -> Message:
    """Run ``plan``; each module invocation, including each element of a
    ``Map``, costs one budget unit.

    On failure the workspace is rolled back to its state before execution.
    """
    snapshot = workspace.snapshot()
    remaining = budget

    def run(node: Plan, env: Mapping[TypeId, Message], chain: tuple[str, ...]) -> Message:
        nonlocal remaining
        if isinstance(node, Given):
            return env[node.type_id]
        if isinstance(node, Map):
            source = run(node.source, env, chain)
            results = []
            for value in source.payload:
                element = Message(node.element, value, "map", (source.message_id,))
                workspace.post(element)
                results.append(run(node.body, {node.element: element}, chain))
            result = Message(
                type_id=output_type(node),
                payload=[r.payload for r in results],
                producer="map",
                parents=(source.message_id, *(r.message_id for r in results)),
            )
            workspace.post(result)
            return result
        args = [run(arg, env, chain) for arg in node.args]
        if remaining == 0:
            raise BudgetExceeded(f"budget of {budget} invocations exhausted")
        remaining -= 1
        manifest = node.module.manifest
        workspace.spent += manifest.cost
        payload = node.module.invoke(*(a.payload for a in args))
        parents = tuple(a.message_id for a in args)
        if isinstance(payload, Request):
            return delegate(payload, manifest.module_id, manifest.ref, manifest.contract.output,
                            parents, chain)
        result = Message(manifest.contract.output, payload, manifest.ref, parents)
        workspace.post(result)
        return result

    def delegate(request: Request, module_id: str, ref: str, output: TypeId,
                 parents: tuple[str, ...], chain: tuple[str, ...]) -> Message:
        if request.type_id != output:
            raise UnresolvedRequest(f"{ref} requested {request.type_id}, not its output {output}")
        chain = (*chain, module_id)
        sub_plan = None if resolver is None else resolver.resolve(request, chain)
        if sub_plan is None:
            raise UnresolvedRequest(f"no route for {request.type_id} requested by {ref}")
        record = Message("kernel.request", request, ref, parents)
        workspace.post(record)
        env = {}
        for type_id, value in request.inputs.items():
            env[type_id] = Message(type_id, value, ref, (record.message_id,))
            workspace.post(env[type_id])
        answer = run(sub_plan, env, chain)
        result = Message(output, answer.payload, f"{ref}+kernel", (answer.message_id,))
        workspace.post(result)
        return result

    try:
        for message in inputs.values():
            if message.message_id not in workspace:
                workspace.post(message)
        return run(plan, inputs, ())
    except Exception:
        workspace.rollback(snapshot)
        raise
