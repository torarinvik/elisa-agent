# 28. Packages as experts

## 28.1 Objects and references

A system built from many independently contributed experts needs a unit of
distribution larger than one expert, and an identity for each unit that does
not depend on who holds it. Every unit here is an immutable *object*, and its
identity is a cryptographic digest of its canonical encoding, its
*reference*. There are three kinds of object:

- a **primitive**: one expert, given by its manifest (contract, cost,
  declared slot calls and effects) and how to load its implementation,
  including the digest of its weights;
- a **composite**: an ordered list of member references, the slots it
  requires and the contracts it exports;
- an **attestation**: a claim about another object (§28.4).

A composite names its members by reference, so composites form a directed
graph whose nodes may be shared by many parents. Since a reference is
computed from contents that include the members' references, a composite
cannot contain itself, directly or through others, unless the digest has a
collision. Under the usual assumption that collisions are infeasible to
find, the graph is acyclic, and equal references mean equal objects.

## 28.2 Composites and their order

A package is an expert or an ordered list of packages. Its *flattening* lists
the contracts of its experts in member order:

> `flatten(expert c) = [c]`, `flatten(composite ps) = flatten(p₁) ++ … ++ flatten(pₙ)`.

**Theorem 28.1 (flattening respects order).** Flattening a concatenation of
member lists concatenates their flattenings.

Installation order is the stable planner's priority (§3): a task's route is
planned in the shortest library prefix that solves it. A *transparent*
composite exports every member, and installing it appends its flattening.

**Theorem 28.2 (installing a package keeps every route).** If a library
solves a task, appending the flattening of any package does not change the
task's route.

*Proof.* Theorem 3.3 applied to the flattening. ∎

An implementation may drop later repetitions of an expert already present;
the planner reads the first occurrence first, so the order of first
occurrences is what it sees. That removal is not part of the formal model.

## 28.3 Exports: packages are experts

An *exporting* composite offers contracts `c₁, …, cₖ` and hides its members.
Each exported contract `c` has an implementation: a plan for `c.output` from
`c.inputs` over the composite's members and the experts its surroundings
supply. The composite *requires* those as slots `σ₁, …, σₘ`, and seen from
outside, export `c` is the higher-order contract `c` with slots `σ₁, …, σₘ`
(§20). The surrounding planner fills the requirements exactly as it fills any
slot, and nothing else about the composite is visible.

*Inlining* replaces each application of `c` in a plan by its implementation
with the implementation's inputs instantiated by the application's
arguments. An input of type `t` is read as the first argument of type `t`, as
everywhere else in the type-keyed model; map bodies read only their element
and are left unchanged.

**Theorem 28.3 (packages are experts).** Let `c` be implemented by a plan
well-typed over `inner ++ lib` from `c.inputs` to `c.output`. Every plan
well-typed over `c :: lib` inlines to a plan of the same type over
`inner ++ lib`.

So a library may hold a composite in place of its members without changing
which tasks it can serve: every route through an export is a route through
the members. The converse fails by design. The members' intermediate types
are private, so a plan that needs one of them is not available outside, and
a composite whose authors want its members visible makes itself
transparent.

**Scoped planning.** Since exports hide their members, the outer planner's
index holds one entry per export rather than one per member. Each export's
route is planned once, in its own scope, by the stable planner, so
Theorem 28.2 also holds inside every composite. Requests made inside are
resolved by a kernel over the composite's own library (§14). Planning cost in
the outer scope depends on the number of exports, not the number of experts
behind them.

**Declared cost.** An export's cost is its route's cost: each invocation's
declared cost, a map body once per element, and an internal slot filling by
its declared calls, at an assumed sequence length. The number of calls to a
requirement is declared exactly when it is affine in the length, that is,
when no requirement is called inside nested maps.

An export's identity is the pair of its composite's content reference and its
zero-based position in the export list. Reinstalling the same object preserves
that pair, including across store save/reload. Different positions remain
different exports even if they have equal contracts. This is a statement about
object identity; it does not prove that executable code loaded from an entry
point implements the declared object faithfully.

## 28.4 Attestations

Calibration temperatures, audit results, measured costs and failure rates,
and signatures are *claims about* an expert, not part of it. An attestation
is an object naming its subject's reference, the kind of claim and the
claim. The subject stays immutable while evidence about it accumulates, any
party may publish evidence, and selecting among experts, as in route
upgrades (§8) or calibrated ladders (§16), reads attestations. An
attestation is evidence under its stated assumptions; its presence does not
make a claim true.

## 28.5 Effects and caching

A manifest may declare an expert's *effects*: what an invocation may do
besides computing its output from its inputs, such as drawing randomness or
reading the outside world. The empty declaration states that the expert is
*pure*: a function of its inputs. An undeclared expert promises nothing. A
composite must declare at least the effects of its members, so a pure
composite contains only pure experts.

A pure expert identified by reference `e` defines a function, and the pair
of `e` and the digest of an input determines the output. A *result cache*
maps such pairs to outputs.

**Theorem 28.4 (caching is invisible).** If every entry of a cache is the
function's value, reading through the cache and computing on a miss returns
the function's value, and storing a computed value or evicting entries
keeps every entry the function's value.

Caches can therefore be shared between machines and runs without changing
any answer, provided the declarations are true. A false purity declaration,
or a digest collision, breaks the premise, not the theorem; attestations
(§28.4) are where evidence of either is recorded.

## 28.6 Names and discovery

References identify contents; *names* are a separate, mutable map from
human-readable strings to references, so a name can move to a new version
while every reference stays valid. Contributions are found by name: each
installed distribution may offer packages under names of its choosing, and
discovery puts every offered package into the store and binds its name.

Discovered packages are installed after the library already present, in
name order, as the members of one transparent composite. By Theorem 28.2,
discovery never changes a route the library already had, whatever is
discovered. Among the discovered packages, name order is the planner's
priority: deterministic, so every installation of the same contributions
yields the same library, but a policy and not a measure of quality.
Selecting by evidence instead reads attestations (§28.4). A name offered
twice is ambiguous and is refused rather than resolved by an arbitrary
rule.

## 28.7 Explicit expert dependencies

A primitive may name an ordered list of dependency object references in
addition to its implementation arguments. These are executable scopes passed
to its factory, not extra experts exposed in the outer planning scope. A
factory receives the installed exports of each dependency in reference order;
it may retain those lazy experts for later invocation. It must not invoke
them during loading, since loading cannot re-enter the same residency store.
Dependencies share the installation's ordinary primitive wrappers and budgets.

Dependency references contribute to the primitive's content identity. Admission
requires every dependency to be present, rejects attestations as executable
dependencies, and requires the primitive's declared effects to cover theirs.
Changing a dependency therefore changes the enclosing object's reference,
under the existing digest collision assumption. Empty dependency lists keep
the prior canonical encoding, preserving existing objects' references.

**Proposition 28.4 (ranked dependencies are acyclic).** If every dependency
edge strictly decreases a natural-number admission rank, no nonempty dependency
path returns to its start. Strict decrease is transitive along a path and a
rank cannot be strictly below itself. This is conditional on the rank invariant;
its correspondence with store admission and executable factory behavior is
not proved in Lean. Content references alone still do not establish that an
entry point or external weights implement the declared object faithfully.

Preparing a lazy route includes the conservative closure of its declared
primitive dependencies when checking and pinning resident bytes. This closure
can exceed what one invocation actually uses. Byte accounting depends on
accurate size declarations; it is not a measurement of process-wide memory.

## 28.8 Canonical snapshots and retained identity

Let a store be a finite map from references to immutable byte sequences. Let
`E` encode a value, `D` decode bytes, and `H` compute a reference. These functions
are pure, but no injectivity or codec round-trip axiom is assumed. A checked
decode of `b` succeeds only when `D(b) = v` and `E(v) = b`.

Admission encodes its input once to `b`, computes `k = H(b)`, and checks the
decoded snapshot. A failed check leaves the store unchanged. Under serialized
admission, an existing `k` accepts identical bytes idempotently and refuses
different bytes. An absent `k` is inserted only if a supplied policy accepts
the current store and decoded snapshot. The policy may depend on the entire
preceding state and may change on every admission.

A read captures the stored bytes, checks their reference and performs checked
decoding. Decoded values are views rather than storage: a caller-side edit does
not alter the stored byte sequence. Resubmitting an edited view is a new
admission. The serialized identity of a returned view is guaranteed at the read
boundary, not after a caller deliberately edits that view.

**Theorem 28.5 (admitted bytes retain their identity).** After successful fresh
admission of `b` at `k = H(b)`, every finite interleaving of admissions, reads and
caller-side operations retains `b` at `k`. Reading `k` returns a checked view
whose encoding is exactly `b`. This holds for every codec, digest and sequence
of admission policies, including digests with collisions.

*Proof.* Induct on the interleaving. Reads and caller-side operations do not
change the map. Admission at an existing key never replaces its bytes, including
when the proposed bytes collide with a retained reference. Insertion at another
key preserves lookup at `k`. The successful checked decode established on
admission therefore remains available; its re-encoding equals `b`, and its
reference remains `H(b) = k`. ∎

This is an in-memory result under immutable-byte and serialized-transition
semantics. It does not establish atomic filesystem publication, correctness of
an external codec implementation, or behavior of loaded executable experts.
Global agreement between independent stores still requires the cryptographic
assumptions of §28.1.

## 28.9 Loader identifiers

A primitive's entry is part of its reference (§28.1), so it must name its
factory by something that does not change when code is reorganized. Let `N` be
identifiers and `L` code locations. A *registry* is a finite list of
registrations `(n, l) ∈ N × L`, contributed by installed distributions in no
particular order. Write `locs(R, n)` for the set of locations registered for
`n` in `R`. Resolution is

    resolve(R, n) = l     if locs(R, n) = {l},
    resolve(R, n) = ⊥     otherwise,

so an identifier with no registration, or with registrations that disagree,
does not resolve. A primitive stores an identifier; its location is looked up
only at load time.

**Theorem 28.6 (loader resolution).** For registries `R`, `R'` and identifier `n`:

1. if `R'` is a permutation of `R`, then `resolve(R', n) = resolve(R, n)`;
2. if no registration in `E` names `n`, then `resolve(R ++ E, n) = resolve(R, n)`;
3. if `(n, a), (n, b) ∈ R` with `a ≠ b`, then `resolve(R, n) = ⊥`;
4. for an injective relocation `μ : L → L`, relabelling every location of `R`
   by `μ` gives `resolve(μR, n) = μ(resolve(R, n))`.

*Proof.* `locs` depends only on the multiset of registrations naming `n`, which
permutation preserves and which `E` does not change, giving 1 and 2. Under 3,
`locs(R, n)` contains `a` and `b`, so it is not a singleton. For 4, `locs(μR, n)`
is the image of `locs(R, n)` under `μ`, and an injective image of a set is a
singleton exactly when the set is, with image `{μ(l)}`. ∎

Part 4 is the guarantee that matters: moving code changes locations, never
stored identifiers, so a registry updated with the move resolves every stored
primitive to its moved factory and every reference is unchanged. Part 2 bounds
what a contributed distribution can affect: it can make only identifiers it
registers ambiguous, and it cannot redirect an identifier another distribution
registers without making that identifier refuse to load. Earlier references
whose entries were import paths stay valid by registering those paths as
identifiers. The result assumes each location's factory behaves as its
identifier promises; versioned identifiers (`…@1`) change when a factory's
arguments or behavior change.


## 28.10 Dependency traversal without a call-stack limit

Let a finite acyclic graph have ordered adjacency lists. Start with one visit
of its root on a work stack. On the first visit to v, mark v seen and replace
that visit by visits of its children in supplied order, then an emission of v.
Skip later visits to seen vertices. An emission returns the vertex. For V
reachable vertices and E reachable edges, count repeated adjacency positions
in E, even when they name the same child.

**Theorem 28.7 (finite dependency-first traversal).** This procedure terminates,
emits each reachable vertex exactly once with every dependency before its
parent, and performs exactly 1+V+E work-stack pops. It preserves the recursive
depth-first postorder. Each vertex's adjacency list need be read only once.

*Proof.* A finite DAG admits positive integer weights satisfying
w(v) > 1 + Σ w(c), summed over v's child positions. Give a visit weight w(v)
and an emission weight 1. Expanding an unseen visit strictly decreases the
sum of pending work weights; skipping a seen visit or consuming an emission
also strictly decreases it. Thus traversal terminates. Every reachable vertex
is eventually visited, expanded once and emitted once. A dependency already
seen while processing v is either finished or an active ancestor; the latter
would imply a cycle. Unseen dependencies are scheduled before v's emission.
This gives dependency-first order and the same depth-first continuation as
recursive traversal. Initially one task is pending. Each of the V expansions
schedules one emission and its outgoing edge visits. Each scheduled task is
popped exactly once, giving 1+V+E. ∎

For transparent flattening, follow only composite-member edges and stop at
primitive leaves. Keeping only emitted primitive leaves gives their first
member-occurrence order. Skipping an already expanded composite changes no
first occurrence: its primitive descendants were already visited in the first
expansion. Shared subgraphs therefore need not be expanded once per path.

The work stack and visited set require O(V+E) reference storage, independent
of host call-stack depth. This is not a byte quota: decoded metadata and input
size still matter. Admission must supply an immutable acyclic graph, and
adjacency callbacks must remain faithful. The theorem does not remove recursive
limits from other interpreters, package installation or expert execution.


## 28.11 Scope continuations and repeated occurrences

Installation may interpret a shared reference several times. Primitive wrappers
can be shared by identity, while separate occurrences of a composite export may
need distinct wrappers. A global visited set over every scope would change that
allocation behavior. Instead, suspend each parent scope while its next child
scope is interpreted, then resume it with that child's ordered result, including
an empty result. Completion is distinct from a request for another child.

**Theorem 28.8 (finite occurrence expansion).** Suppose every interpreted scope
has a finite ordered list of lower-ranked child requests, and creation of a
scope's own wrappers terminates. Replacing recursive calls by an explicit stack
of suspended scope continuations terminates and preserves child-before-parent
completion, request order and per-occurrence allocation. No host call-stack
bound on scope depth is required.

*Proof.* Unfold shared references into occurrences. The finite acyclic request
graph admits weights w(v) > 1+Σ w(c). A pending child request has weight w(v),
and its parent's completion has weight 1. Expanding any occurrence into child
requests and completion decreases total pending weight, even without a visited
set; popping a completion also decreases it. Thus no infinite occurrence
expansion exists. Suspension resumes the same parent at the same next operation
with the same child result as recursive return. Induction over these finite
completions gives the same ordered results and allocation occurrences. ∎

Memoized primitive requests may skip work; they do not add child requests.
This theorem assumes faithful continuation creation/resumption and terminating
wrapper construction; it does not prove a foreign factory's behavior. The
unfolding can still have exponentially many occurrences in the size of a shared
graph. Transitive dependency declarations, decoded bytes and wrapper residency
also have costs. Removing host recursion does not supply a global memory quota,
prove invocation termination, or snapshot mutable expert state.

## 28.12 Complete-file publication

Separate private preparation from public publication. A writer prepares a full
immutable byte string privately. Before preparation completes, failure has no
public effect. Publication atomically installs the complete string only if its
name is absent. An existing name is never overwritten; a caller may accept an
identical existing string or report a conflict.

**Theorem 28.9 (complete non-overwriting publication).** Under those transition
semantics, after any finite interleaving of writers and abandoned preparations:
(i) every initially present name retains exactly its original bytes;
(ii) every publicly present name contains either its initial bytes or exactly
the complete bytes of one publication proposal. No proper prefix introduced
only by an incomplete preparation can become public.

*Proof.* A failed preparation changes no public entry. Publication at an occupied
name also changes nothing; at an absent name it inserts exactly its complete
proposal. These facts establish both claims for one step. Induction on the
interleaving establishes them for every finite run. ∎

This model assumes linearizable create-if-absent publication, complete private
writes and immutable published contents. It does not prove a filesystem's
primitives, defend against unrelated destructive writers, establish persistence
after power loss, or make publication of several files one atomic transaction.
An interrupted multi-object save can expose a completed prefix of objects.
Dependency-before-parent publication is needed separately for a reopenable
prefix; existing malformed or externally modified files remain errors.
