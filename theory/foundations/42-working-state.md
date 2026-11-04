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

## 42.4 Declared effects and mediated authority

Let G be the host-granted effect identifiers and D the expert's declared set.
Admission under an explicit policy requires a known D ⊆ G. While running the
expert, the effective grant is G ∩ D. Nested scopes intersect their requested
grant with the current one, so no nested scope widens the original authority.
A gateway operation e succeeds only if e belongs to both the active declaration
and grant. In particular, e ∉ G or e ∉ D implies refusal before the gateway's
operation, provided the gateway checks before acting.

Declarations apply to expert callbacks, including demand, relevance and risk,
not just the main invocation. Suspended continuations resume with the same
declaration. Delegation and nested execution retain the caller's restriction;
a requested sub-route cannot acquire effects absent from its caller. A supplied
higher-order expert must therefore declare authority covering effects it
intentionally delegates. Compiled per-row and batch callbacks use the same
rule. Pure cache hits still undergo declaration admission.

This is a conditional containment result for mediated operations only. An expert
can bypass a cooperative gateway with ordinary Python or native system access;
these mechanisms do not isolate hostile code, validate declarations or undo
completed effects. Unknown declarations are refused under explicit restricted
policies. Outside such policies, legacy execution is preserved. No permission
identifier or resource implementation is built into the frame. Grant lookup and
membership are independent of catalog size; grant-set intersection also depends
on the sizes of the requested and inherited footprints.


## 42.5 Stable message identities and suffix rollback

Model a workspace as an ordered log L and an index I from message identifiers
to opaque message objects. Payload equality is not assumed available. Each
identifier denotes exactly one admitted object. Reposting that object is a
no-op; a different object under the same identifier is refused. A fresh post
requires every parent identifier to be present before it extends L and I.
A checkpoint is a valid retained-log position, rather than a durable capability.

**Theorem 42.1 (workspace prefix preservation).** Suppose calls are serialized,
message objects and their payloads are immutable or treated as immutable, and
log/index container operations are faithful. A finite suffix of fresh posts
preserves every prior index binding. Erasing those suffix identifiers in reverse
admission order and truncating the log to its checkpoint restores exactly the
prior index and log. Idempotent reposts and rejected collisions change neither.

*Proof.* A fresh write at identifier k changes no previously present identifier.
Writing k and then erasing k restores the previous index, since k was absent.
Induct over suffix writes: undo the tail, then erase the fresh head write.
The log is L followed by the admitted suffix; taking its first |L| elements
returns L. Reposts add no suffix element, and collisions are refused before
mutation, so both can be removed from the trace without changing the result. ∎

Freshness is essential. If a suffix overwrites a prefix identifier, erasing that
identifier loses the old binding even though the prefix log still names it.
Input admission must enforce the same rule as ordinary posts: merely finding
an identifier present does not establish that a supplied object is its message.
A malformed checkpoint must be rejected before state changes. A bare numeric
position can become stale after another rollback; it is not an isolated or
concurrent transaction handle. This result covers workspace message bindings,
not arbitrary payload mutation, external memory/effects, ledger charges, or
already incurred costs.

## 42.6 Component declarations inside learned compositions

A composite advertises the union D∪S of a selected component's declared effects
D and its siblings' declarations S. This union states the whole composition's
resource footprint; it does not grant every component every sibling's effects.
Invoke each immediate component callback under its own declaration D.

**Theorem 42.2 (siblings supply no component authority).** Under explicit finite
host grants G, the selected component's effective allowance is
(G∩(D∪S))∩D = G∩D. An effect absent from D is denied even if it belongs to S.

*Proof.* Membership on the left means membership in G, in D∪S, and in D.
Membership in D already implies membership in D∪S, leaving exactly G∩D.
The gateway requires membership in that allowance, so an effect outside D is
unavailable. ∎

The component's callback must actually be invoked within its declaration
scope, and the gateway must check before the protected operation. The same
rule applies when a training or evaluation procedure calls an expert to obtain
observations; the procedure's own authority is not the expert's declaration.
Callbacks and metadata must remain faithful and scopes must restore after
return or exception. Immediate callback scoping alone does not attach origin
authority to returned requests, generators, callbacks or other deferred objects;
their later use requires explicit runtime mediation. This result establishes
neither arbitrary-code isolation nor rollback of operations already performed.

## 42.7 Evaluation authority follows callback ownership

Under an explicit finite host policy G, let D₁,…,Dₙ be the known finite
declared footprints of the active callback path. Its allowance is G∩D₁∩…∩Dₙ. An evaluator may have a larger
footprint than a candidate or reference expert; entering that expert's callback
must intersect the evaluator's current grant with the expert's own declaration.
A per-use implementation delegated by an expert retains that expert's declaration
when it has no independent ownership interface. If it also declares an independent
footprint, both declarations constrain its callback.

**Theorem 42.3 (callback path ownership).** Every operation admitted by the
checked gateway at the end of a finite callback path belongs to G and to every
Dᵢ on the path. In particular, an evaluator-only operation absent from the
candidate's declaration is unavailable during candidate evaluation, at any
finite nesting depth.

*Proof.* Each intersection is a subset of its preceding allowance and of the
new declaration. Induction over the path gives the subset of G and of each
path member. Gateway membership transfers through those subset inclusions. ∎

Returning or raising from the callback restores the evaluator's scope. This
lets trusted sampling, fitting and agreement procedures retain their own
permissions while candidate callbacks use theirs. Scopes must faithfully track
actual ownership; parameter or factory metadata does not prove an arbitrary
implementation honest. The result applies to immediate callback execution,
including owned per-use implementation calls. Returned active objects and
other deferred callbacks need origin authority when later activated. It does
not isolate hostile code or roll back work, labels or effects already incurred.
