# 36. Interface alignment acquisition

Continuation of [Acquiring experts](36-acquisition.md); section numbers remain stable.

## 36.56 Searching compatible adapter/consumer families

Freeze supplied source, teacher and consumer families. For each compatible triple,
fit a bridge from source observations to paired teacher observations, then compose
with a unary slot-free consumer whose input is the teacher's interface and whose
output is the external task type. External source/teacher signatures must match
the task inputs, slots and relevance. Skip incompatible metadata; bound fitted
triples explicitly. Retain source/teacher type declarations, but no teacher
implementation in the completed inference graph. Types remain distinct.

If a bridge agrees pointwise with its teacher, every consumer in a finite family
agrees after composition; Lean proves the resulting ordered map equality. This
is conditional, not a guarantee from training pairs. Consumers can still be
wrong for the task, so freeze complete candidates before independent end-to-end
selection under §36.3. The fit limit does not bound library scanning or fitter
computation. Stable models/data, faithful factories and useful teacher coverage
remain assumptions. No consumer implementation or task catalog enters the core.


## 36.57 Reusable shared interface alignment

Fit a source-to-teacher bridge independently of any final consumer, retaining
only source and learned adapter. Optionally fit it once per source/teacher pair
and share that same model across compatible consumer candidates. Candidate
budgets still count completed routes; no bridge is fitted for a pair with no
compatible consumer. Independent fitting remains the default, since sharing
changes the candidate family for stochastic fitters. Expose the bridge as an
explicit retained root when later consumers should install it independently.

For n > 0 consumers and r paired rows, one alignment requires r external paired
observations instead of n*r. Lean proves this count inequality, not runtime or
memory savings. Inference values are not cached; each route still invokes the
source. Existing conditional family agreement applies, with stable functional
models, faithful factories and independent end-to-end selection as assumptions.
The teacher adds no separate inference dependency.


## 36.58 Acquiring a family of alignment hypotheses

An explicit ordered family of fitters can propose different bridges for each
compatible source/teacher pair. Enumerate source, teacher, fitter, consumer in
that order, bounded by completed-route count. Shared alignment applies within a
fitter entry, not between independently fitted hypotheses. An empty fitter
family proposes nothing. Providers must accept the observed value shapes;
failures are reported rather than silently reclassified as inapplicability.

If an adapter belongs to a fitted family, its consumer composition belongs to
the mapped completed-route family; Lean proves this membership statement.
A bounded prefix may never reach that adapter. Even a reached hypothesis may
fail on independent data. Therefore freeze completed routes before selection
under §36.3, without using held-out outcomes to choose or train fitters. Neither
type identity nor teacher training agreement establishes which fitting family
is useful. Stable models/data and faithful providers remain assumptions.

## 36.59 Constructing candidate representations from typed parts

Let S be a finite seed family with a common external signature, and let E
relate representations joined by an applicable unary transformation. Define
C₀=S and Cₙ₊₁=S ∪ ⋃{E(x) : x∈Cₙ}. A transformation preserves the external
signature while replacing the representation output. Type compatibility alone
does not assert semantic usefulness or equality of implementations.

**Theorem 36.59 (bounded feature closure).** Cₙ contains exactly the endpoints
reachable from a seed by at most n transformations. The same construction over
paths, retaining distinct implementations, enumerates every compatible chain
through that depth. Cycles and repeated output types do not invalidate this.

*Proof.* At depth zero the endpoints are exactly S. At the next depth a path
is either a seed or a bounded shorter path followed by one applicable edge.
Induction gives both inclusion directions. ∎

Breadth-first path enumeration permits a deterministic candidate prefix cap;
truncation preserves soundness but can lose completeness. Its resource bounds
are search parameters, not universal bounds on possible representations.
No theorem here establishes that the supplied primitive family contains a
useful feature. Selecting or fitting a head uses training observations only;
reliability still requires independent end-to-end evaluation of frozen models.

## 36.60 Multi-input feature construction

Let a transformation rule be an ordered nonempty list of input types and one
output type. A feature tree begins at a seed with the common external signature;
each internal node supplies one compatible subtree per input position. Repeated
types do not merge positions. Height counts the maximum transformations along
a seed-to-root branch. Let C₀ be seed output types, and let Cₙ₊₁ contain seeds
and outputs of rules whose every input type occurs in Cₙ.

**Theorem 36.60 (bounded feature-tree closure).** Cₙ contains exactly the root
types of compatible trees of height at most n. Enumerating ordered child tuples
of the preceding closure generates every such tree. Assigning each non-leaf
tree to its leftmost maximum-height child gives a unique generation pivot.

*Proof.* A non-seed root of height at most n+1 has a compatible child of height
at most n for every input position; conversely those children and their rule
form a compatible tree. Induction gives both directions. Every positive-arity
tree has a leftmost child attaining its maximum child height, uniquely. ∎

This is closure of a supplied rule family, not a claim of task sufficiency or
efficiency: candidate counts can grow combinatorially, and a bounded prefix
may omit a useful tree. Each branch is evaluated separately, with cost and slot
calls added, even when two branches refer to the same object. Reusing a value
would require additional purity and execution-sharing assumptions. Polymorphic
or higher-order transformations require a richer rule model and are outside
this search fragment. The surrounding architecture is not restricted to it.

## 36.61 Retaining ordered multi-input applications

For a common external input x∈X, let branch i return fᵢ(x)∈Yᵢ and let a
head h accept the ordered dependent product of these values. The application
returns h((fᵢ(x))ᵢ). Two positions may name the same branch, without sharing
execution or collapsing their positions.

**Theorem 36.61 (faithful application restoration).** If every restored branch
agrees pointwise with fᵢ and the restored head agrees on every ordered argument
vector with h, then the restored application agrees pointwise with the original.

*Proof.* Pointwise branch equality gives equality of the complete ordered
argument vector. Substitute that equality, then pointwise head equality. ∎

This assumes stable functional implementations and faithful component bindings;
it does not prove codecs, filesystem behavior, external effects or hidden-state
snapshots. Repeated bindings may share retained bytes and a loaded implementation,
but each argument position still invokes its branch. Sharing computed results
would require additional assumptions. No risk certificate follows from retaining
parameters; changed operating distributions still require separate validation.

## 36.62 Type-indexed feature enumeration

Expand an ordered list of rule positions for a pivot feature. A position whose
required type differs from the pivot produces no candidates. An index stores,
for each required type, the matching positions in their original order,
including repeated entries. Similarly index available branches by output type,
preserving their order and the preceding-height restriction of §36.60.

**Theorem 36.62 (ordered incompatible-rule removal).** If every incompatible
entry expands to the empty list, filtering those entries before concatenating
expansions produces exactly the original candidate list. Every capped prefix,
including tie order and multiplicity, is therefore unchanged.

*Proof.* Induct over the entry list. A compatible head remains; an incompatible
head contributes the empty list. Apply induction to the tail. ∎

Faithful construction of both indices transfers this result to each expansion.
Induction over search heights then preserves the feature-tree enumeration and
its capped prefixes. Indices cost a pass over rule input positions and available
branches, with additional storage; they do not remove the combinatorial number
of compatible trees, prove hash-map behavior, or predict semantic usefulness.

## 36.63 Demand-built rule buckets

For a fixed ordered library, cache a type's matching rule-position list only
after its complete scan. An absent bucket means unknown, not empty: recompute
the ordered filter when that type is queried. Inspected immutable contract
headers may be shared between scans without retaining buckets for every type.

**Theorem 36.63 (demand-index lookup).** If a completed cached bucket equals
the ordered filter for its queried type, then choosing that bucket when present
and recomputing the filter when absent returns exactly the same list.

*Proof.* Split on cache presence. In the present case use the faithful-bucket
hypothesis; in the absent case the lookup is the filter by definition. ∎

Combined with Theorem 36.62, this preserves ordered enumeration and capped
prefixes. Partially scanned buckets must not be reused as complete ones. Early
termination may discard such work without declaring unseen positions absent.
Demand construction retains headers for reached library positions and entries
only for queried types. Querying a new type requires another header scan; it
does not promise lower CPU for every library or fewer compatible candidates.

An explicit budget may additionally prefetch positions from a contiguous rule
prefix, stopping before a rule whose whole input-position list exceeds the
remaining budget. A query concatenates its prefetched prefix matches with the
ordered filter of the remaining suffix. The filter-of-append identity proves
that result equals filtering the full list. The budget bounds these prefetched
positions only, not contract headers, completed queried buckets or model memory.
Unbounded prefetch and zero prefetch are resource policies of the same lookup;
neither changes the candidate family or establishes a universal speed advantage.

## 36.64 Exact verification after coarse rule selection

Let P be an exact matching predicate on ordered records and H a cheaper
prefilter with P(x)⇒H(x). Filtering first by H and then by P can accelerate
selection without replacing exact equality by a fingerprint comparison.

**Theorem 36.64 (collision-safe selection).** For any record list L,
filter P (filter H L) = filter P L. Multiplicity and ordering are preserved.

*Proof.* Induct over L. Exact matches survive H by hypothesis. Every other
record is removed by P regardless of whether it survives H. ∎

Equality-compatible hashes satisfy the no-false-negative hypothesis when
equal identifiers have equal stable hashes. Collisions may add comparisons,
never alter exact selection. Packed-record bounds, stable hashing, faithful
compiled scanning and final equality checks are implementation obligations;
this theorem alone proves none of those boundaries. Compact packed storage
also has a preparation and memory cost, so native scanning need not improve
small searches or searches whose prefetched prefix already covers the library.

## 36.65 Supplied priorities for bounded feature construction

Assign a finite score to every eligible transformation and stably sort the
library by descending score before constructing trees. Tie order remains the
supplied order. Scores may depend on earlier training evidence; they must not
change model behavior or inspect future certification observations.

**Theorem 36.65 (priority preserves untruncated reachability).** Permuting a
fixed transformation library leaves the bounded feature-tree closure unchanged
when enumeration is not truncated. Every constructed tree remains well typed.

*Proof.* A permutation has the same rule membership. The closure recurrence
depends only on those rules and all their antecedents; induction on depth
therefore gives the same closure. Each constructed application still checks
the same input/output contracts. ∎

A candidate cap deliberately changes which prefix is reached. An inaccurate
score can exclude the useful tree; no universal efficiency or completeness
claim follows for capped search. Supplied scores are hypotheses, not semantic
certificates. Whole-task acceptance still requires independent evaluation of
the frozen selected model. Inspecting/scoring a whole library also costs work
that cannot be hidden as free acquisition or assumed to amortize on new tasks.

## 36.66 Retaining configured compositions

Let an interpreter R take execution settings c, an ordered list of semantic
member descriptors D, and an input x. Its result may include an answer or refusal,
resource consumption, and an effect trace. A descriptor must include everything
used in planning and execution, including contracts and request behavior.

**Theorem 36.66 (configured interpretation preservation).** If restoration
preserves c and every member descriptor at every ordered position, then the
restored interpreter has the same result for every x.

*Proof.* Pointwise descriptor equality gives equality of the mapped member list,
including multiplicities and order. Substitute this equality and the settings
equality into R. ∎

This is conditional on a faithful, deterministic interpreter and semantic
member restoration. Matching type signatures alone is insufficient. Omitting
settings can change which route is selected, whether execution has enough
resources, or which request is issued. No mutable state snapshot, filesystem
atomicity, or statistical certificate preservation follows from this theorem.
