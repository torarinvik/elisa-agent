"""Plan execution under an explicit invocation budget, with kernel-mediated requests.

A module may return a ``Request`` instead of its output. The runtime then asks
the resolver (the kernel) for a plan producing the requested type from the
request's inputs, with every module of the current request chain excluded,
executes it under the same budget, and uses its result as the requester's
output. Modules never invoke one another; every invocation is planned,
type-checked, budgeted, and recorded by the kernel (``lean/NCA/Request.lean``).

Requests are resolved lazily. A consumer module may declare
``relevant(index, provisional) -> bool``: given the provisional values of all
its inputs, whether input ``index`` can influence its result. A pending request
the consumer declares irrelevant is settled with the requester's provisional
answer instead of being resolved (``NCA.gated_error_le``,
``NCA.gated_error_eq_of_sound``). Requests whose value is consumed without a
relevance declaration, mapped, or returned are always resolved.

Evaluation is demand-driven. A consumer may declare ``demand(index, demand)``:
given the demand on its own output, what it reads of input ``index``. Inputs
(and map elements) with empty demand are not evaluated at all, so neither the
modules computing them nor requests raised there run. For demand-sound
declarations the answer is unchanged (``lean/NCA/Demand.lean``), which makes
skipping their requests a sound gate.

A module may also continue with a sub-result: ``invoke`` returns a generator
that yields ``Request`` objects of any type and receives each resolved value
before continuing, until it returns its output. Each such request is resolved
at once, with the requester in the chain (``lean/NCA/Continuation.lean``:
correct answers give correct results, and the number of requests is bounded by
the program's question depth).

A higher-order expert (§20) receives its slot fillings first, before its
inputs, each as a ``Filling``: calling it runs the slot's plan through the
kernel on the given values, bound by position, so inputs of equal type stay
apart, under the same budget, recorded in the
workspace. A call may pass the demand on its result; with empty demand the
plan is not run. ``Filling.outer`` is the demand on the expert's own output,
so an expert that knows how its output relates to its calls (``map``) can
pass demand through.

With ``cost_budget`` every invocation is also paid its declared cost before
it runs, and requests are served from what remains (``NCA.serve``): every
answer is fully paid for (``NCA.serve_spent``), and with a kernel that lets
an expert ask its own question again (``Kernel(recursive=True)``),
recursion terminates because the budget decreases. ``attempt`` reports a
refusal for lack of budget as no answer instead of an exception
(``NCA.serve_sound``: a refusal is never a wrong answer).

With a ``ResultCache``, an application of an expert that declares itself
pure, has a content identity and takes no slots is looked up by its identity
and the digests of its inputs before it runs (THEORY §28.5,
``NCA.cache_lookup_correct``). A hit is not an invocation and charges no
budget: the result was paid for when it was computed. A hit the cache
samples for a purity check is invoked and charged as usual, and its fresh
output is used (§32.3). Only results the expert returned directly are
stored; one that raised requests depends on how the kernel resolved them,
not only on the inputs.
"""

from __future__ import annotations

from collections.abc import Callable, Generator, Sequence
from dataclasses import dataclass
from typing import Any, Mapping, Protocol

from nca.abi import NOTHING, Demand, Message, Request, SequenceDemand, TypeId
from nca.cache import ResultCache, value_digest
from nca.planner import Given, Map, Plan, output_type
from nca.workspace import Workspace


class BudgetExceeded(RuntimeError):
    pass


class UnresolvedRequest(RuntimeError):
    pass


class Resolver(Protocol):
    def resolve(self, request: Request, chain: tuple[str, ...]) -> Plan | None: ...


@dataclass(frozen=True)
class Pending:
    """A request awaiting a decision: resolve it, or settle it provisionally."""

    request: Request
    module_id: str
    ref: str
    output: TypeId
    parents: tuple[str, ...]
    chain: tuple[str, ...]


class Filling:
    """A slot's plan as a function of the slot's inputs, run by the kernel."""

    def __init__(self, call: Callable[[tuple[Any, ...], Demand], Any], outer: Demand) -> None:
        self._call = call
        self.outer = outer
        """The demand on the output of the expert receiving this filling."""

    def __call__(self, *values: Any, demand: Demand = None) -> Any:
        return self._call(values, demand)


def execute(
    plan: Plan,
    inputs: Mapping[TypeId, Message] | Sequence[Message],
    workspace: Workspace,
    budget: int,
    resolver: Resolver | None = None,
    cost_budget: float | None = None,
    cache: ResultCache | None = None,
) -> Message:
    """Run ``plan``; each module invocation, including each element of a
    ``Map``, costs one budget unit, and with ``cost_budget`` also its
    declared cost. ``inputs`` are the available messages, in order (a mapping
    is read in its order), so several may share a type.

    On failure the workspace is rolled back to its state before execution.
    """
    snapshot = workspace.snapshot()
    remaining = budget
    funds = cost_budget

    def unread(node: Plan) -> Message:
        message = Message(output_type(node), None, "kernel.unread")
        workspace.post(message)
        return message

    def filling(node: Plan, inputs: tuple[TypeId, ...], ref: str, chain: tuple[str, ...],
                outer: Demand) -> Filling:
        def call(values: tuple[Any, ...], demand: Demand) -> Any:
            if demand == NOTHING:
                return unread(node).payload
            env = [Message(type_id, value, ref) for type_id, value in zip(inputs, values,
                                                                          strict=True)]
            for message in env:
                workspace.post(message)
            return force(run(node, env, chain, demand)).payload

        return Filling(call, outer)

    def run(node: Plan, env: Sequence[Message], chain: tuple[str, ...],
            demand: Demand = None) -> Message:
        nonlocal remaining, funds
        if isinstance(node, Given):
            if (node.position is not None and node.position < len(env)
                    and env[node.position].type_id == node.type_id):
                return env[node.position]
            return next(m for m in env if m.type_id == node.type_id)
        if isinstance(node, Map):
            source = run(node.source, env, chain)
            results = []
            length = len(source.payload)
            for i, value in enumerate(source.payload):
                element = Message(node.element, value, "map", (source.message_id,))
                workspace.post(element)
                element_demand = (demand.element(i, length)
                                  if isinstance(demand, SequenceDemand) else demand)
                if element_demand == NOTHING:
                    results.append(unread(node.body))
                else:
                    results.append(force(run(node.body, (element,), chain, element_demand)))
            result = Message(
                type_id=output_type(node),
                payload=[r.payload for r in results],
                producer="map",
                parents=(source.message_id, *(r.message_id for r in results)),
            )
            workspace.post(result)
            return result
        declare = getattr(node.module, "demand", None)
        args = []
        for i, arg in enumerate(node.args):
            arg_demand = declare(i, demand) if declare is not None else None
            args.append(unread(arg) if arg_demand == NOTHING else run(arg, env, chain, arg_demand))
        relevant = getattr(node.module, "relevant", None)
        provisional = [a.payload.request.provisional if isinstance(a.payload, Pending)
                       else a.payload for a in args]
        for index, arg in enumerate(args):
            if not isinstance(arg.payload, Pending):
                continue
            if (relevant is not None and arg.payload.request.provisional is not None
                    and not relevant(index, provisional)):
                args[index] = settle(arg.payload)
            else:
                args[index] = force(arg)
        manifest = node.module.manifest
        contract = node.contract
        parents = tuple(a.message_id for a in args)
        key = cache_key(node, args)
        checking = False
        if key is not None:
            hit, stored = cache.lookup(key)
            if hit and not cache.sample():
                result = Message(contract.output, stored, f"{manifest.ref}+cache", parents)
                workspace.post(result)
                return result
            checking = hit
        if remaining == 0:
            raise BudgetExceeded(f"budget of {budget} invocations exhausted")
        if funds is not None:
            if manifest.cost > funds:
                raise BudgetExceeded(f"cost budget of {cost_budget} exhausted")
            funds -= manifest.cost
        remaining -= 1
        workspace.spent += manifest.cost
        fillings = [filling(sub, inputs, manifest.ref, chain, demand)
                    for sub, (inputs, _) in zip(node.slots, contract.slots, strict=True)]
        payload = node.module.invoke(*fillings, *(a.payload for a in args))
        if key is not None and not isinstance(payload, (Generator, Request)):
            if checking:
                cache.check(key, stored, payload)
            else:
                cache.store(key, payload)
        if isinstance(payload, Generator):
            payload = resume(payload, manifest.module_id, manifest.ref, parents, chain)
        if isinstance(payload, Request):
            output = contract.output
            if payload.type_id != output:
                raise UnresolvedRequest(
                    f"{manifest.ref} requested {payload.type_id}, not its output {output}")
            pending = Pending(payload, manifest.module_id, manifest.ref, output, parents, chain)
            return Message(output, pending, manifest.ref, parents)
        result = Message(contract.output, payload, manifest.ref, parents)
        workspace.post(result)
        return result

    def cache_key(node: Plan, args: Sequence[Message]) -> tuple[Any, ...] | None:
        identity = getattr(node.module, "identity", None)
        if (cache is None or identity is None or node.slots
                or node.module.manifest.effects != frozenset()):
            return None
        digests = tuple(value_digest(a.payload) for a in args)
        return None if None in digests else (identity, digests)

    def resume(program: Generator[Request, object, object], module_id: str, ref: str,
               parents: tuple[str, ...], chain: tuple[str, ...]) -> object:
        answer = None
        try:
            while True:
                request = program.send(answer)
                answer = delegate(request, module_id, ref, request.type_id, parents,
                                  chain).payload
        except StopIteration as done:
            return done.value

    def settle(pending: Pending) -> Message:
        record = Message("kernel.skipped", pending.request, pending.ref, pending.parents)
        workspace.post(record)
        result = Message(pending.output, pending.request.provisional, pending.ref,
                         (record.message_id,))
        workspace.post(result)
        return result

    def force(message: Message) -> Message:
        if not isinstance(message.payload, Pending):
            return message
        pending = message.payload
        return delegate(pending.request, pending.module_id, pending.ref, pending.output,
                        pending.parents, pending.chain)

    def delegate(request: Request, module_id: str, ref: str, output: TypeId,
                 parents: tuple[str, ...], chain: tuple[str, ...]) -> Message:
        chain = (*chain, module_id)
        sub_plan = None if resolver is None else resolver.resolve(request, chain)
        if sub_plan is None:
            raise UnresolvedRequest(f"no route for {request.type_id} requested by {ref}")
        record = Message("kernel.request", request, ref, parents)
        workspace.post(record)
        env = [Message(type_id, value, ref, (record.message_id,))
               for type_id, value in request.inputs]
        for message in env:
            workspace.post(message)
        answer = force(run(sub_plan, env, chain))
        result = Message(output, answer.payload, f"{ref}+kernel", (answer.message_id,))
        workspace.post(result)
        return result

    given = tuple(inputs.values()) if isinstance(inputs, Mapping) else tuple(inputs)
    try:
        for message in given:
            if message.message_id not in workspace:
                workspace.post(message)
        return force(run(plan, given, ()))
    except Exception:
        workspace.rollback(snapshot)
        raise


def attempt(
    plan: Plan,
    inputs: Mapping[TypeId, Message] | Sequence[Message],
    workspace: Workspace,
    budget: int,
    resolver: Resolver | None = None,
    cost_budget: float | None = None,
    cache: ResultCache | None = None,
) -> Message | None:
    """``execute``, with a refusal for lack of budget reported as no answer."""
    try:
        return execute(plan, inputs, workspace, budget, resolver, cost_budget, cache)
    except BudgetExceeded:
        return None
