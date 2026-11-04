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
