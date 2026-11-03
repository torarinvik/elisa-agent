# 42. Working state and bounded streams

## 42.1 State-threaded routes

Let a contributor supply a state type S and event input signature E. A
transition is an ordinary well-typed route T : (S, E) → S, including its
existing expert identities, costs, requests, slots and risk reports. The frame
assigns no meaning or representation to S or E. Working state is the last
successfully returned state message, not mutable expert-owned hidden storage.

For initial state s₀ and events e₀,…,eₙ₋₁, define
sᵢ₊₁ = T(sᵢ,eᵢ). A failed transition leaves the state cursor at sᵢ. Earlier
successful transitions remain committed. This statement assumes payloads are
immutable or treated as immutable; an invocation can otherwise mutate its
input before failing. Workspace rollback does not reverse external effects,
failed invocation costs, or ledger charges. There is no containment claim.

## 42.2 Invariants across time

Suppose a state predicate P holds initially and every successful transition
preserves P. Induction on the event list gives P for the final state of every
finite successful prefix. No assumption about the number of future events is
needed. This is conditional transition-invariant preservation, not verification
of an arbitrary expert, its type declarations or its Python implementation.

Each transition has its own invocation and optional cost budget. Nested work
uses the ordinary runtime's budget and ledger. Stream consumption is lazy and
limited by a caller-supplied step count: stopping consumption starts no further
transitions. No infinite-stream termination or total wall-clock bound follows.
If per-transition reported risk is rᵢ, the existing ledger accumulates those
charges across time. There is no depth-independent or time-independent error
bound; uncertainty does not disappear because the state persists.

## 42.3 Resources and remaining scope

For a fixed transition route and fixed-size state/event values, n events require
n transition executions. The cursor retains one state message, but an unpruned
workspace retains the provenance of all transitions and therefore generally
grows linearly. This mechanism is working state only. Durable episodic storage,
effect capabilities, state migration, eviction and continual-learning gates
require additional mechanisms. Payload size, route complexity and effects can
change transition cost; no constant-cost claim covers those changes.
