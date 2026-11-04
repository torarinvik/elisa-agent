# 43. Durable typed episodic records

## 43.1 Records and exact recall

An episodic record consists of a contributor-defined type identifier, opaque
immutable payload bytes, producer identity, observation time, optional reported
confidence, parent record references and an optional superseded record reference.
The frame assigns no payload meaning, codec, embedding dimension or memory kind.
Contributors can encode inputs, outputs, outcomes and context in their own types.
Confidence is a recorded assertion, not a calibration certificate.

A record's identity is the digest of its canonical encoding. Appending either
adds a new identity or returns the already identical record. Existing identities
never change. Therefore exact lookup after a fresh insertion returns its value,
and further insertions preserve every previous lookup. These algebraic results
assume collision-free identities and faithful storage; they do not prove a
particular database, hash implementation or crash recovery algorithm.

## 43.2 Provenance and permissions

All parent references must already exist in the same store. Supersession requires
a parent reference of the same type. It adds evidence without deleting the
superseded record or asserting which claim is correct. Producers and observation
times are supplied assertions; append order need not be observation-time order.
No automatic nearest-neighbour search, semantic interpretation or consolidation
strategy belongs in this primitive. Retrieval experts remain replaceable packages
and their wrong answers use ordinary runtime risk accounting.

Store reads and appends are cooperative resource gateways requiring separately
configured effect identifiers. The host provisions and closes the store; experts
receive access only through declared and granted effects. As in §42.4, this does
not contain code that bypasses the gateway and accesses database files directly.

## 43.3 Capacity and lookup scaling

Define a record's charged bytes as its canonical encoding length plus its
reference length. A transaction adds a fresh record only if current charged
bytes plus that charge do not exceed the store's persistent capacity. Duplicate
appends charge nothing. Capacity checks and insertion are one writer transaction,
including across independent handles. No automatic eviction exists: a full store
refuses new records, so it cannot silently remove gate evidence.

This quota bounds logical record bytes, not database pages, indices, journals,
resident memory or filesystem use. Physical capacity enforcement needs a separate
storage boundary. Indexed exact lookup takes logarithmic index work in record
count, plus reading and hashing the chosen record. Large payloads and provenance
lists increase that cost. Append work also depends on the number of parents.
No semantic retrieval or sublinear memory-growth claim follows. Durable typed
records are a prerequisite for the broader continual-learning pipeline, not its
completion.

A bounded append-order reference scan lets external strategies rebuild an index
without retaining all references outside the store. Each fresh append receives
a strictly increasing position in the same transaction; duplicate appends get
no new position. Continuing after the last returned position includes later
committed appends. Scans expose storage order, not observation-time order, and
perform no semantic selection or payload decoding.

## 43.4 Retained evaluations and replay admission

An existing expert evaluation may bind its ordered outcome vector to an ordered
nonempty sequence of distinct episodic record references. Its benchmark identity
is the digest of those references. The evaluator interprets their typed payloads;
the frame does not supply a task codec or correctness rule. Trusted outcome
assertions and record identity bind a reproducible finite evaluation, not a
statement that all possible observations have been retained.

Compatible evaluations for the same route are combined in first-seen order,
counting a record only once. Conflicting trusted outcomes for the same route and
record are errors. Different routes still have separate cases and loss budgets.

For each affected route r, freeze its references and baseline correctness bits
bᵣᵢ before evaluating a proposed replacement. Replay gives bits cᵣᵢ. Define
Lᵣ = |{i : bᵣᵢ = true and cᵣᵢ = false}|. Admit the replacement only when every
route has Lᵣ at most the caller's loss budget. Wins on another route never offset
these losses. For zero budget, every retained baseline success remains successful.
In general, retained failure count increases by at most Lᵣ, since new successes
can only reduce failures.

This guarantee assumes the caller includes every affected route, evaluates the
actual proposed version, supplies truthful trusted baselines and a sound scoring
rule, and commits only after the complete result accepts. Missing/corrupt records,
untrusted or malformed assertions and exceeded replay budgets are errors, never
acceptance. An empty affected-route set protects no routes and is vacuously
accepted; it is no evidence of new-task correctness. Invocation budgets, effects
and cost limits belong to the supplied evaluator, ordinarily using the runtime.

This is a deterministic finite-evidence gate. Repeated use can overfit the retained
cases. No population regression bound follows without fresh held-out samples or
an appropriate uniform/adaptive-valid argument. The gate does not mutate routes,
install replacements, infer dependency coverage, consolidate records or evict
anything. Those mechanisms must preserve its explicit assumptions.

## 43.5 Guarded multi-root route snapshots

A protected catalog maps retained-evidence anchors to current typed plans and
contributor-supplied case codecs/scorers. An anchor identifies the original
attested evaluation, not the content identity of every subsequent plan. Each
applied expert must obey version immutability; replacing a version constructs new
plan nodes and never edits an active expert or old route snapshot.

A simultaneous replacement maps old expert objects to contract-equal, distinctly
identified new versions. Its affected roots are precisely registered explicit
plans containing an old object in an argument, map source/body or slot filling.
Shared nodes are rewritten once per update. Opaque experts and resolver objects
are pinned boundaries: replacing something outside them cannot change their
hidden code. To update a hidden implementation, replace its outer expert version.
Mutation of an existing expert/resolver bypasses these assumptions and is not
contained by the host-language implementation.

Every affected root must have retained evidence. The prepared current/candidate
plans execute through the ordinary runtime on independently decoded copies of
each record, with invocation/cost budgets and fresh ledgers. The candidate must
pass both the trusted original baseline and a replay against actual current
correctness. The second comparison protects successes acquired since the original
attestation. With zero loss allowance, successful retained answers persist through
a sequence of accepted snapshots by induction, assuming deterministic evaluation
or a faithfully reset fixed replay environment. With stochastic components the
gate protects observed replay outcomes only. This remains finite-case protection,
not an adaptive population guarantee. Codecs must faithfully reconstruct the same
case and isolate mutable state; replay must not repeat irreversible live actions.

Publication returns a new catalog only after all required comparisons accept.
Refusal returns the identical old catalog; exceptions return no update. Old
snapshots and their expert references remain usable. The reverse index finds
explicit dependencies without guessing them from implementation names. Unchanged roots with unchanged declared manifests may reuse their established
type/dependency checks;
rewritten roots require validation. Snapshot copying, index rebuilding and metadata
parsing can still require linear total catalog work even with few affected roots. Dynamic resolver changes, arbitrary
manual router upgrades, evidence eviction and automatic artifact installation
are outside this managed publication API.

## 43.6 Protected dispatch, upgrades and rollback

A protected dispatch snapshot contains a catalog C and a binding map B from
(ordered available input types, goal type) to evidence anchors. A lookup uses one
snapshot and returns C(B(request)); absent bindings return no route, with no
fallback to an unregistered planner answer. Ambiguous signatures need an explicit
binding. This is a configured coverage boundary, not a fixed catalog of tasks.

Explicit replanning preserves a root's external input/output signature, codec and
scoring rule while permitting arbitrary new internal wiring. Only that root's
plan changes; opaque old experts and other roots retain their actual objects.
Normal upgrades and rollback both use the same retained/current replay admission
as expert replacement. Rollback is not automatically safe: an older version may
lose a success acquired since its attestation. Removing a protected root is not
an unchecked rollback operation.

Mutations are serialized; lookups keep using the published snapshot while replay
is running. Complete acceptance switches the catalog reference; refusal keeps the
old catalog and records the refused check as diagnostic metadata. Reentrant or
concurrent mutation is refused, not allowed to publish a stale prepared snapshot.
This relies on the host's snapshot-selection and synchronization semantics; the
functional no-fallback/refusal facts do not verify a language memory model.

Activating protection must preserve every existing explicit pin and detach legacy
mutable aliases. It cannot infer all tasks a previously unprotected planner might
have answered. Once protected, arbitrary legacy pin edits, route removal, missing
replay context and unregistered request signatures are refused. Initial task
coverage and trusted case codecs remain host-supplied. Unprotected research
routing still exists and makes no non-forgetting claim.

Replay permissions default to the configured memory-read effect; additional
resettable effects require an explicit replay allowlist and an existing host
grant. Scope intersection never creates authority. Unknown/effectful experts
without sufficient grants are refused before invocation. These are cooperative
gateway checks, not interception of arbitrary Python/native system access.

## 43.7 Sampled admission on fresh cases

The gate of §43.4 replays every retained case, so its cost grows with retained
history, and its guarantee covers only those cases. This section bounds
regression on a route's operating distribution instead, at a cost set by the
tolerance.

Fix a tolerance `ε ∈ (0, 1)` and a confidence budget `δ ∈ (0, 1)`. Each route `r`
has a pool of retained cases with baseline bits, and a cursor. Decisions are
numbered `k = 0, 1, …` in the order they draw cases. Decision `k` with affected
routes `Aₖ` uses level `αₖ = δ / ((k+1)(k+2)|Aₖ|)` and sample size `mₖ`, the
smallest `m` with `log(1/αₖ) ≤ εm`. If some affected route has fewer than `mₖ`
unused cases, the decision is refused, draws nothing and keeps its number.
Otherwise it takes the next `mₖ` cases of every affected pool, advancing the
cursors, and admits the proposal only if no drawn baseline success fails.
Drawn cases are retired whether the proposal is admitted, rejected or the
evaluation fails.

For a proposal `P` and route `r`, the *loss rate* `ℓ(P, r)` is the probability,
on `r`'s operating distribution `Dᵣ`, that the baseline succeeds and `P` fails.

**Sampling hypothesis.** Each pool lists independent draws from `Dᵣ`, in an
order fixed before any proposal is made (the implementation shuffles each batch
of added cases once, with a seed fixed at construction), and evaluation is
deterministic.

**Theorem 43.1 (sampled admission).** Under the sampling hypothesis, for any
rule choosing proposals and affected routes from everything observed so far,
the probability that some decision admits a proposal `P` with
`ℓ(P, r) > ε` on some affected route `r` is at most `δ`.

*Proof.* (i) Freshness: cursors only advance, so the case ranges drawn by
different decisions are disjoint. (ii) Hence the cases of decision `k` are
independent of everything that chose its proposal, and conditionally on that
history its `mₖ` losses on route `r` are independent Bernoulli(`ℓ`) variables.
Zero losses then has probability `(1-ℓ)^{mₖ}`. (iii) If `ℓ > ε` then
`(1-ℓ)^{mₖ} ≤ (1-ε)^{mₖ} ≤ e^{-εmₖ} ≤ αₖ`, by `1 - x ≤ e^{-x}` and the choice of
`mₖ`. (iv) Summing over the routes of decision `k` gives at most
`δ/((k+1)(k+2))`, and `Σₖ δ/((k+1)(k+2)) = δ(1 - 1/(n+1)) < δ` for any number
`n` of decisions. A union bound finishes. ∎

Steps (i), (iii) and (iv), and the union over decisions and routes, are proved
in Lean. Step (ii) is the sampling hypothesis applied to fresh cases; it is
assumed, not proved.

Each decision evaluates at most `mₖ = ⌈log((k+1)(k+2)|Aₖ|/δ)/ε⌉` cases per
affected route, growing only logarithmically in `k` and `|Aₖ|`, and independent
of pool size. Only drawn baseline successes need replay. The zero-loss rule is
conservative: a proposal with `0 < ℓ ≤ ε` is admitted with probability only
`(1-ℓ)^{mₖ}`. Pools are consumed, so sustained admission needs newly retained
cases, which `add` appends behind every cursor; refusal for missing evidence
is never acceptance. As in §43.4, the caller must name every affected route.

A route catalog (§43.5) using sampled admission counts a drawn case as lost when
the candidate fails where either the original baseline or the current route
succeeds, so successes acquired after the original attestation stay protected
as under exact replay. This is still a fixed per-case loss for each proposal,
so Theorem 43.1 applies with `ℓ` the probability of that combined loss. One
sampler is shared by every snapshot of a catalog, so decisions are numbered and
cases retired across versions, and a router passes it through its replay
context.

## 43.8 Self-regulating plasticity

The gate decides whether a change is admitted; plasticity decides where change
is attempted and how much acquisition effort each place receives. Let keys
`κ` name (piece, region) pairs chosen by the caller. Each observation window
supplies, per key, a *surprise* `s ∈ [0, 1]` (for example an excess failure
rate, refuted calibration or detected shift) and a *stability* `w ∈ [0, 1]`
(for example use-weighted dependents or attestation strength). With rate
`η ∈ (0, 1]`, the default regulator updates plasticity by

    p' = (1 - η)p + η · s(1 - w),

and a key opens when `p ≥ hi` and closes when `p ≤ lo`, with `0 ≤ lo < hi ≤ 1`.
An acquisition budget is divided among open keys in proportion to `p`. When
the gate admits a change for `κ`, the key *settles*: it closes and `p` resets to
an initial value `p₀ ≤ lo`.

**Theorem 43.2 (bounded, non-oscillating plasticity).** If `p, s, w ∈ [0, 1]`
then `p' ∈ [0, 1]` and `|p' - p| ≤ η`. Consequently, on any trajectory, an open
key cannot close and a closed key cannot reopen in fewer than `(hi - lo)/η`
observations, and the same bound holds for reopening after settling.

*Proof.* `s(1 - w) ∈ [0, 1]`, and `p'` is a convex combination of `p` and
`s(1 - w)`. Also `p' - p = η(s(1 - w) - p)` with `|s(1 - w) - p| ≤ 1`. By the
triangle inequality, `n` observations move `p` by at most `nη`. Closing an open
key needs `p` to fall from at least `hi` to at most `lo`, and reopening needs the
reverse; after settling `p = p₀ ≤ lo`. ∎

Plasticity never enters admission: Theorem 43.1 holds for any rule that chooses
proposals from the history, so any regulator, learned or contributed, keeps the
non-regression guarantee. Theorem 43.2 concerns only the default regulator;
another regulator must stay in `[0, 1]`, which the implementation checks, but
it gets no step or oscillation bound without its own proof. Signals are
computed by the frame from ledgers and audits, never reported by pieces.

## 43.9 Signals from ledgers, audits and dependents

The frame computes plasticity signals from its own records. For a window of
execution ledgers and a key function `κ` on charged invocations, let `I_κ` be
the invocations with key `κ` and `r_i ∈ [0, 1]` their reported risks. The
*surprise* of `κ` is

    s(κ) = 1                                  if an audit of κ refutes calibration at level α,
    s(κ) = (1/|I_κ|) Σ_{i ∈ I_κ} r_i          otherwise.

When the reports are calibrated (§33), the mean report estimates the key's
failure rate without labels. When they are not, an audit (§35, §38, §40)
refutes them and surprise saturates; reports alone cannot reveal failures they
do not announce. The *stability* of an expert with `d` dependent protected
routes is `d/(d + h)` for a half-saturation `h > 0`.

**Proposition 43.3.** Both signals lie in `[0, 1]`, and stability is
nondecreasing in `d`. Hence a field fed by them satisfies Theorem 43.2.

*Proof.* A mean of values in `[0, 1]` lies in `[0, 1]`, and so does the
indicator. For `h > 0`, `0 ≤ d/(d + h) < 1`, and `d ≤ e` gives
`d(e + h) ≤ e(d + h)`. ∎

## 43.10 Consolidation

Let a protected catalog use a piece `P` that has accumulated local corrections.
Consolidation chooses training records, runs each through a protected route
that uses `P`, records `P`'s inputs and outputs, and gives these examples to a
caller's distiller, which returns a compact piece `Q` with `P`'s contract. It
then proposes replacing `P` by `Q` through the gate on every protected route
that uses `P`. If admitted, `P` has no protected dependents and is reported as
retirable. Examples come from `P`'s own behavior, so no labels are spent.

**Proposition 43.4 (consolidation is gated and fresh).** (i) Whatever `Q` the
distiller returns, the catalog changes only if the gate admits `Q`, so
consolidation inherits Theorem 43.1 under the sampled gate and the finite
guarantee of §43.4 under exact replay. (ii) Under the sampled gate, if every
training record has already been drawn, no later decision draws it, so `Q` is
independent of the cases that judge it.

*Proof.* (i) Publication returns the old snapshot unless the gate accepts.
(ii) Drawn cases lie before their route's cursor, and every later allocation
starts at or after the cursor. ∎

Part (ii) is why training on undrawn cases is refused: a proposal fitted to
cases the gate may still draw would make those cases a biased test, and the
sampling hypothesis of Theorem 43.1 would no longer apply. The cost is
coverage: training is limited to drawn cases, so consolidation under a sampled
gate needs enough of them, or a distiller that generalizes. Retirement here
means only that no protected route uses `P`; removing stored artifacts or
episodes is eviction, which must preserve evidence that gates rely on.

## 43.11 Evidence-preserving eviction

Memory has fixed capacity, so records must be removed. Call a record
*protected* if a retained evaluation of a registered route names it (exact
replay scores every such record), if it is a case a sampled gate has not drawn,
or if the caller has stored it but not yet given it to a gate. A record named as
a parent by another record is never removed, so provenance never dangles.
Ordinary eviction removes only unprotected records, preferring cases sampled
gates have drawn (no decision uses them again) and then older records. A forced
removal, such as a deletion request, may remove protected records. It withdraws
them from every sampled pool and reports the routes whose unused evidence
shrank and the routes whose retained evaluations name removed records.

**Proposition 43.5 (eviction preserves gate evidence).** (i) Ordinary eviction
leaves every protected record in the store. (ii) After any withdrawal, forced
or not, a sampled gate's later draws take only cases that were unused before
the withdrawal and were never drawn, so freshness, and with it Theorem 43.1,
is unaffected; fewer remaining cases can only cause refusals for insufficient
evidence. (iii) Removing a record named by an exact gate's retained evaluation
makes that gate's replay fail, never accept.

*Proof.* (i) The removed set excludes protected records. (ii) Withdrawal filters
the drawn and unused parts of a pool separately; later draws are prefixes of
the filtered unused part, a sublist of the original unused part, which is
disjoint from the drawn part. (iii) Missing records are errors in §43.4. ∎

Forced removal can bias a pool if what is deleted depends on the loss being
estimated; the sampling hypothesis of Theorem 43.1 then needs deletions to be
independent of it. The reported shrinkage makes this visible rather than
silent.

## 43.12 Append cursors survive eviction

An append-ordered store has state `(h,L)`, where `h` is the greatest issued
position and every live position in `L` is at most `h`. A newly admitted
record receives `h+1` and raises `h` to that value. Removing a record filters
`L` and leaves `h` unchanged. Duplicate admissions and failed transactions
leave the state unchanged. Reopening restores both components exactly.

**Proposition 43.6 (no cursor reuse).** These transitions preserve the bound
on live positions. After any number of removals, the next admitted record has
position strictly greater than every saved cursor at most the preceding
high-water mark, even when all earlier records have been removed.

*Proof.* On append, old live positions are at most `h < h+1`, and the new
position equals the new mark. Removal only takes a subset of live positions
and does not change the mark. Induction gives the invariant over a sequence
of operations. A saved cursor `c ≤ h` satisfies `c < h+1`. ∎

The durable high-water mark and record admission must commit atomically, and
concurrent writers must serialize that transition. A store that retained only
live records cannot reconstruct an evicted maximum: identical empty stores
can have arbitrarily different histories. Upgrading such a store requires an
externally supplied upper bound on previously issued positions; the live
maximum alone is insufficient. The bound is an additional trusted hypothesis.
