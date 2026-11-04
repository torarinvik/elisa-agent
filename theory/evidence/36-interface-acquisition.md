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

## 36.67 Target-directed feature construction

Let S be seed types, R ordered positive-arity ground transformation rules, and
T requested output types. Starting from T, repeatedly include all antecedents
of every rule whose output is included. The resulting dependency cone A contains
T and is closed under those antecedents. Rules may contain repeated inputs,
cycles and multiple alternatives for the same output.

**Theorem 36.67 (target restriction).** For every x in A and every depth n,
x is derivable from S using R within n transformations along a branch if and
only if it is derivable from S ∩ A using only rules whose output is in A.
In particular, restriction preserves every bounded target derivation.

*Proof.* Induct on depth. A leaf of allowed type belongs to S precisely when
it belongs to S ∩ A. For a rule with allowed output, closure puts every child
type in A; apply the induction hypothesis to every ordered child. Conversely,
each retained seed and rule was in the original library. ∎

The same structural induction preserves individual trees, not merely reachable
types: no relevant rule occurrence or ordered branch is removed. Closure is
only a necessary-condition filter. It does not establish that all inputs are
producible or that any transformation is semantically useful. A candidate cap
still bounds every retained intermediate tree as well as target trees, and
can exclude a useful target. Target restriction can change capped prefixes;
no capped completeness is asserted. Dependency inspection costs metadata reads
and storage; when most of the library is relevant it need not save work.
Higher-order and polymorphic rules require a separate search model.

## 36.68 Exact empirical category scores

For a finite sequence of observation/label pairs P, let c(k,l) count occurrences
of (k,l). Over finite sets K and L covering all observed keys and labels, define
M(P) = Σ_{k∈K} max_{l∈L} c(k,l), taking an empty maximum as zero. This is the
number of successes of a best constant-label decoder within each observed key.
It is an empirical selection score, not a bound on unseen errors.

**Theorem 36.68 (count-preserving scoring).** Reordering the pairs leaves M
unchanged. Replacing key and label values by injective identifiers also leaves
M unchanged when the count table is transported along those identifiers.
Thus sorting exact identifier pairs and counting their equal runs computes the
same score as counting opaque pairs directly. Within a sorted key group the
largest label-run length is its contribution; summing those maxima gives M.

*Proof.* A permutation preserves every pair's multiplicity. Injective naming
preserves pair equality and transports the count table without merging cells.
The maxima in each row and their sum therefore remain unchanged. Sorting makes
equal pairs contiguous and equal-key runs adjacent, so run lengths are exactly
those multiplicities. Every constant-label decoder scores at most the row
maximum within each key; summing gives empirical optimality. ∎

Hash equality alone is insufficient for naming: collisions must still compare
actual keys and labels. Equality must be an equivalence relation, with equal
values having equal stable hashes. Encoding and sorting are implementation obligations;
compiler correctness does not follow from this count-table identity. O(N)
identifier storage and sorting work can exceed direct histogram costs on small
samples. Frozen observations, stable equality/hashing, training-only selection
and independent certification remain required. No particular category or task
semantics is part of the score.

## 36.69 Unary composition continuations

Represent a finite unary composition by a leaf operation and heads ordered from
outermost to innermost. Recursive interpretation first evaluates the leaf, then
applies the innermost head and proceeds outward. An explicit continuation stack
records those same heads while descending, then pops them after the leaf returns.

**Theorem 36.69 (unary continuation equivalence).** For arbitrary unary functions
h₁,…,hₙ on a carrier and a leaf result x, the recursive composition
h₁(h₂(…hₙ(x))) equals folding function application over the reversed head list
starting at x. Each head occurs once and in the same order, without a recursive
host call per composition node.

*Proof.* For an empty list both interpretations return x. Reversing a nonempty
list places its outermost head last. Apply the induction hypothesis to the tail,
then apply that last head. ∎

The carrier may contain arbitrary tagged intermediate values; no common domain
meaning is required. To preserve effects and failures as well as values, the
interpreter must enter each child scope before inspecting/evaluating that child,
restore that scope before invoking its parent's head, and restore every remaining
scope on failure. The value identity alone does not prove these runtime details.
Only recognized structural compositions may be unfolded; opaque implementations
and overrides retain normal invocation. Terminating finite wiring, faithful
metadata and context restoration are assumptions. Stack storage grows linearly;
leaf operations, other graph kinds and deferred computations can still recurse.

## 36.70 Saturated empirical search

Consider candidates in a fixed order with integer scores bounded above by N.
Rank by descending score, keeping original order within ties. If an observed
prefix contains k candidates scoring N, the first k such candidates are the
stable top k of the entire sequence, regardless of the remaining suffix.
If strict improvement over an incumbent scoring N is required, no candidate
can qualify.

**Theorem 36.70 (saturated prefix).** Under that upper bound, stopping after
k prefix maxima preserves the selected stable top k. Every selected score
dominates every suffix score, and the first k maxima in prefix plus suffix
are exactly the first k maxima of the prefix. For empirical category scores,
Σ max_l c(k,l) ≤ Σ Σ_l c(k,l) = N when the count table covers N observations.

*Proof.* Each cell is bounded by its row sum, so each row maximum is too.
Summing yields the score bound. A maximum-scoring prefix candidate outranks
every lower-scoring candidate; any equally scoring suffix candidate follows it
by stable tie order. Appending the suffix therefore cannot change the first k
maxima already present. If the incumbent is maximal, strict improvement is
impossible. ∎

Lazy observation of unused candidates can skip both their empirical scoring and
their training executions. Selection equivalence assumes frozen observations,
faithful scores and no state changes affecting later candidates; observable
side-effect traces need not be identical. This is an opt-in compute policy,
not a claim that training maxima generalize. Independent certification remains
necessary. Non-saturating searches may still visit the entire bounded family.


## 36.71 Structural output construction

Let a candidate construct an output pair from two expressions. If each
expression equals its corresponding target component at an input, the pair
equals the target there (`structural_pair_correct`). The statement extends
inductively to finite tuple trees. Training consistency alone does not establish
these component equalities on unseen inputs; independent certification is
needed, under its existing fresh-sampling and fixed-candidate assumptions.


## 36.72 Bounded candidate evaluation

If at most C candidate programs each inspect at most N training examples, the
number of candidate/example evaluations is at most C·N
(`bounded_candidate_evaluations`). A single evaluation may have variable cost,
so this is not a CPU or learning-rate bound. Rejection on a training mismatch
never removes a program that agrees with every training example; consistency
on training data does not certify generalization. A proposed program must be
frozen and tested on fresh cases under the existing admission assumptions.


## 36.73 Construction after selection

If a selector chooses an item and an output expression renders that item to
the target at the given input, their composition returns the target there
(`selected_output_correct`). This is pointwise: neither component hypothesis
follows from finite training consistency. Fresh admission remains necessary;
the statement does not establish selection accuracy or a learning rate.
