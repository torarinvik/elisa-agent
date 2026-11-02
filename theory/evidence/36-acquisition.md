# 36. Acquiring experts

## 36.1 Where to acquire

Audits (§35) and ledgers (§33) say where a route falls short. Summed over
a batch, a ledger's entries give each expert's share of the charged risk;
an expert with a large share, or one an audit refuted and recalibration
left uninformative, is where a better expert lowers the route's risk
most, by Theorem 31.3. *Acquisition* builds a challenger for that
expert's contract and lets the evidence decide between them.

## 36.2 Honest promotion of a trained challenger

The labeled invocations an audit collects are split, before any training,
into a training part `T` and an evaluation part `E`. A trainer, supplied
by the domain and arbitrary otherwise, maps `T` to a challenger with the
incumbent's contract. Both experts are then evaluated on `E`, and the
challenger is promoted by the paired sign test of §30.

**Theorem 36.1 (split promotion).** If `T` and `E` are independent, and
the test rejects with probability at most `α` for every fixed challenger
no better than the incumbent, then the probability of promoting a trained
challenger no better than the incumbent is at most `α`.

*Proof.* The challenger is a function of `T` alone. Conditionally on
`T`, it is fixed and `E` keeps its distribution, so a false promotion has
conditional probability at most `α`; averaging over `T` keeps the bound. ∎

The theorem fails if the trainer sees `E`, for instance by selecting
among training runs by their score on it, which is the overfitting the
split exists to prevent.

A promoted challenger reports risk only once it is calibrated; it is
calibrated and audited on `E` as in §35.2, which the sign test, not
depending on reports, leaves valid. Its calibration and promotion hold on
the distribution the audit sampled, so acquisition answers a shift
exactly as far as the audit's inputs represent it.

## 36.3 Proposing decompositions and interfaces

A proposer uses only `T` to return a finite family of experts with the
incumbent's external contract. Each expert may introduce new intermediate
constructor objects and an arbitrary internal composition. These declarations
are hypotheses about useful representations, not proofs of their meaning.
Freeze the whole family before evaluating any proposal on `E`.

**Theorem 36.2 (finite proposal selection).** Conditional on `T`, suppose
there are `k > 0` proposals and every no-better proposal's paired test has
false acceptance probability at most `α/k`. Then the probability of selecting
any no-better proposal is at most `α`. Independence between proposals is
unnecessary: selection implies that at least one proposal passed, so the union
bound applies. Averaging over independent `T` gives the unconditional bound
as in Theorem 36.1. With no proposals, nothing is selected.

The proposer must not select, retrain, or add proposals after seeing `E`.
Repeated adaptive searches need their own budget accounting. Shallow sequence
snapshots do not isolate mutable sample objects. This mechanism evaluates
proposed interfaces; it does not itself invent representations or prove transfer.

A proposed decomposition may be a stored package rather than a live expert.
Its candidate family consists of all installed exports with the incumbent's
external contract, identified by source object reference and export identity.
The budget counts these exports, not packages: a package can contribute several
competing experts. Package references are frozen using `T` alone before any
export is evaluated on `E`. Unselected objects can remain in a candidate store
without being added to the active expert library.

**Proposition 36.3 (reloaded outcomes).** If reloading a selected export preserves
its function on every input, then its scored outcomes on a fixed labeled sample
are unchanged. This follows pointwise by substitution. Content references alone
do not establish the premise: entry points, external weights, runtime state and
scoring behavior must also be preserved. Selection evidence is neither a
calibration certificate nor a proof of representation semantics.

## 36.4 Learning decoders for candidate representations

Given training pairs `(x, y)` and a fixed feature expert `f`, let `n(z, y)`
count training pairs with `f(x) = z` and target `y`. Construct a decoder `d`
by choosing a label of maximal count at each observed key `z`. Break ties
by first occurrence; at unseen keys use the global training mode. This defines
a proposed decomposition `x → f(x) → d(f(x))`, with the decoder contract
derived from the feature's output and the required target type. Keys and labels
must have stable hash/equality semantics, and the feature must not change.

**Theorem 36.4 (empirical decoder optimality).** For any decoder `g` on the
same representation, the modal decoder has at least as many correct training
predictions: `Σ_z n(z, g(z)) ≤ Σ_z n(z, d(z))`. Each summand is bounded by its
chosen maximum; sum over the finitely many observed keys. This asserts nothing
about unseen keys or held-out accuracy. Freezing several such decompositions
on `T` and selecting on independent `E` uses Theorem 36.2.

This learns the decoder and its interface contract without hand-writing one
for each representation. The feature family and its type meanings are still
supplied; this construction does not invent a feature space or new type meaning.
An inadequate feature irreversibly loses information, while an overly specific
one can memorize training pairs and generalize poorly.

## 36.5 Searching joint representations

For feature experts `f : X → A` and `g : X → B`, their joint representation is
`h(x) = (f(x), g(x)) : A × B`. Its interface is a structural product of the
existing feature types, not a claim of semantic equivalence or a new primitive
meaning. Repeated pairing represents any finite nonempty subset of features.
Enumerate subsets in increasing size, freeze them using training data alone,
fit the decoders of §36.4, then select using §36.3. The subset size and total
candidate count are explicit search resource bounds; enumeration can be
exponential in the number of available features.

**Proposition 36.5 (joint representation can simulate a component).** For
any decoder `d : A → Y`, the decoder `d'(a,b) = d(a)` satisfies
`d'(h(x)) = d(f(x))` for every `x`. Thus the optimal empirical decoder for a
joint representation cannot have fewer training successes than a decoder
using its first component, by Theorem 36.4. This does not imply better
held-out performance: a joint table can have many more unseen keys.

Joint feature execution calls both components on the same inputs and slot
fillings, in order. Declared costs and known slot-call counts add; effects
are their union when both are declared, otherwise unknown. Stateful features
need extra care: this construction does not make calls commute or preserve
a feature's behavior across separate training and evaluation invocations.

## 36.6 Learning conditional decompositions

A finite decision tree may choose a different feature expert at each node.
On a node's training subset, group examples by each unused feature's key and
score a split by the sum of its child groups' modal-label counts. Choose the
highest score, breaking ties by lower immediate declared cost and then
supplied feature order. A pure node, a node
without a separating feature, or a node whose split exceeds the remaining
node budget becomes a modal-label leaf. Process nodes breadth first; a feature
is used at most once along a path. Zero-improvement splits remain eligible,
since two features can be informative jointly while neither is informative
alone. Unseen keys return the current node's modal label.

**Proposition 36.6 (modal refinement).** Splitting a node cannot reduce its
empirical modal successes: for every child, its modal count is at least the
count of the parent's chosen label in that child. Summing over children gives
the parent's correct count as a lower bound. Repeating this argument gives
nondecreasing training accuracy as nodes are refined. The finite sum comparison
is proved conditional on each child's maximal count; the implementation's
counting and node-budget behavior are tested separately. Greedy splitting is
not a globally optimal tree search and implies no held-out improvement.

This learns conditional execution structure from supplied features. It creates
no new primitive feature meanings. Features and key/label equality must remain
stable. A conservative runtime bound sums declared costs and known slot counts
of all features used anywhere in the tree: each appears at most once on a path.
The supplied tree overhead bound is added to cost; expected calls are not
estimated from the training frequencies. Node limits are explicit resource
bounds, not fixed limits on task complexity.

## 36.7 Bounded lookahead for conditional structure

At a candidate split, project the best training success count of its children
for a finite remaining horizon. A projected leaf is always available; among
projections with equal success count, prefer lower summed declared feature
cost over training examples. A split's projected effort is its feature cost
times the subset size, plus its children's projected effort. Features already
used on a path are excluded. At horizon zero, return the modal leaf's count
and zero effort. Ties that remain use supplied feature order.

**Proposition 36.7 (complete-search inclusion).** If one complete projection
search includes every policy of another, its best training success count
cannot be smaller. Their finite attainable-score sets are included, so their
maxima are ordered. This establishes neither held-out accuracy nor optimality
of the final tree. In particular, a bounded search can stop early, and a
projection does not allocate the final tree's global node budget optimally.

A projection-work budget limits expanded states. Once exhausted, further
projections return modal-leaf scores. This is deterministic but order-dependent;
search exhaustion invalidates a claim of complete horizon search. Predictions
and measured feature calls must distinguish this search heuristic from a
proof of globally minimal execution cost. Declared tree costs remain the
conservative bounds of §36.6, not projected training averages.

## 36.8 A learned empirical-state interface

A trained tree partitions invocations into terminal states: leaves and internal
nodes reached just before an unseen key. Retain each node's training label
counts and its modal tie choice. Deduplicate equal count/tie records and assign
codes by canonical record order. A newly generated constructor describes this
finite codebook and the target type. Its values are codes for these empirical
records; the codebook is learned from training data, not a fixed label catalog.
It records empirical counts, with no claim about true probabilities.

Factor the tree into an encoder returning the reached state's code and a head
returning that record's chosen label. Include every node, so fallback at an
unseen key is represented as well. Counts with different compositions remain
different states even if their chosen labels agree.

**Proposition 36.8 (prediction-preserving state factorization).** Let `v(x)`
be the node at which tree evaluation stops, `c(n)` its code, and `m(n)` its
chosen label. If the head satisfies `d(c(n)) = m(n)` for every node, then
`d(c(v(x))) = m(v(x))` for every invocation. This is substitution and includes
unseen-key fallbacks. It proves prediction preservation, not better accuracy,
calibration, transfer, or that the state is a sufficient statistic for other
tasks. Features and the fitted tree must remain fixed after factorization.

The codebook's canonical label encoding must preserve label values. The first
implementation supports JSON scalar labels explicitly; richer labels need a
faithful codec, rather than conversion through display strings. The type
object can be stored independently; persisting the executable encoder and
training evidence requires additional integration.

## 36.9 Persisting a learned decoder head

A finite decoder is determined by its typed contract, key/label table, unseen-key
fallback and declared cost. Storing these as canonical data and reconstructing
the same table preserves every prediction, including unseen keys. The first
codec accepts JSON scalar keys and labels only, rejecting unsupported values
rather than coercing them. Its entry point is a generic table interpreter,
not a task-specific implementation. Constructor objects named by the contract
must already be present in the object store.

The prediction-preservation argument is Proposition 36.8 with a fixed key as
the stopping state. It assumes faithful key/value encoding and unchanged
interpreter behavior; neither the digest nor the Lean theorem proves the
Python codec correct. Round-trip and value-type preservation are tested.

## 36.10 Persisting conditional structure

A finite feature tree can be represented by an ordered node table. Each node
records its chosen label, empirical counts, feature position and keyed child
positions. Child positions strictly exceed their parent position, so decoding
cannot introduce a cycle. Each feature is bound to an export position within
an explicit dependency scope, checked against its content identity and manifest.
Reconstruction preserves predictions if these feature implementations and all
node data are preserved, by Proposition 36.8. Digests do not prove executable
fidelity. The scalar codec rejects unsupported keys/labels explicitly.

The stored interpreter manifest receives a model-content-derived identifier,
so distinct fitted models do not share a residency key merely because their
external contracts agree. External feature code and weights remain separate
versioned dependencies. This persists conditional structure, not online state.

## 36.11 Structural keys for learned models

Learned joint features can produce nested tuples, so their persisted keys need
a structural codec. Keep JSON scalars unchanged and encode a tuple as a tagged
record containing the recursively encoded elements. Ordinary strings, including
tag-like strings, remain distinct from tuple records. Reject unknown records,
unsupported values and nonfinite numbers rather than coercing them.

For every supported finite value, decoding its encoding returns the same value
with the same tuple/scalar structure. The tuple case follows componentwise from
the scalar and smaller-tuple cases. This codec is representation machinery,
not a declaration of domain value types. Existing scalar model encodings stay
unchanged; richer key support does not establish generalization or transfer.

## 36.12 Residual correction proposals

For a fixed incumbent and candidate feature, group training invocations by the
feature key. In each group compare the incumbent's number of correct answers
with the count of its modal target. Install a constant-label correction only
when the latter is strictly larger; otherwise retain the incumbent. At unseen
keys retain the incumbent as well. This learns local replacements where errors
concentrate instead of replacing behavior everywhere. Features, incumbent and
key/label equality must remain fixed.

**Proposition 36.9 (empirical residual dominance).** The corrected expert has
at least the incumbent's training successes: each group's contribution is the
maximum of incumbent successes and modal-label count. Sum the pointwise
inequalities. This gives no held-out guarantee; freeze every candidate using
training data only, then apply the finite-family selection of §36.3. Declared
costs and slot counts conservatively include both feature and incumbent, even
though corrected invocations skip the incumbent.

## 36.13 Learning a numeric partition interface

Given a fixed scalar-valued feature and labeled training invocations, sort
observations by feature value. Consider each boundary equal to an observed
value strictly greater than the minimum. The encoder returns one code below
the boundary and another at or above it. Fit the modal target in each region
and choose the boundary with the greatest training successes, ties at the
smallest boundary. Generate a constructor describing the source type, boundary
and code convention; no domain vocabulary or manually chosen threshold enters
this definition. Values must be finite floating-point observations.

**Proposition 36.10 (finite boundary optimum).** Every nonempty two-region
threshold partition of the observed values is induced by one considered
boundary. Thus the selected candidate maximizes empirical successes among
these thresholds with modal decoders. This is an empirical hypothesis-class
result, not a generalization theorem. A finite maximum dominates every member;
Lean proves that selection step conditional on membership. Completeness of the
Python sweep and faithful float comparisons are regression-tested. Promotion
still requires independent held-out evidence (§36.3).

## 36.14 Learning several numeric regions

Start with one interval carrying its modal target. At each step, consider the
best two-region split (§36.13) in every impure interval and choose the greatest
increase in training successes. Ties prefer the leftmost interval and then the
smallest boundary. Stop when all intervals are pure or unsplittable, or an
explicit maximum-region budget is reached. Zero-gain splits remain eligible.
The resulting sorted boundaries define a learned finite interface, with one
code per interval and a modal decoder.

Each refinement has nonnegative empirical gain by Proposition 36.6: child
modes can retain the parent's label. `modal_refinement_le` proves that local
sum comparison. This is greedy refinement, not a globally optimal segmentation,
and implies no held-out improvement. The budget is a caller-selected resource
limit; the representation has no fixed architectural region count.

## 36.15 Acquiring features at unresolved training nodes

A conditional learner may ask a supplied trainer for new feature experts at
each impure node, using only that node's training invocations and targets.
New features must preserve the incumbent's inputs, slots and relevance; their
output types and learned transformations may differ. They are eligible in
that node's subtree, not unrelated branches. The node budget bounds training
requests. Projection lookahead considers already fitted features only.

This makes the fitted tree, including its newly acquired interfaces, a function
of the training split alone. Under independent evaluation, the split-promotion
argument of Theorem 36.1 therefore still applies. It does not require that the
feature family was fixed before training. It does require that trainers cannot
inspect held-out samples, that their returned families are finite, and that
fitted experts remain stable during evaluation. The existing conditional
split theorem supplies this probability step; correctness of the executable
subtree scoping and callback data isolation is regression-tested.

## 36.16 Retaining acquired numeric interfaces

A learned numeric encoder can be stored by its boundary parameters, encoding
cost, generated constructor and an explicit binding to its measurement expert.
Reconstructing the same encoder over the same faithful measurement preserves
its code for every finite observation. Content-derived interpreter identities
distinguish separately fitted transformations in the residency store.

To retain a tree with acquired encoders, store each generated constructor and
encoder, install those artifacts, and rebind the tree's feature positions to
their reconstructed modules before storing its node table. Costs, effects and
contracts remain unchanged; only interpreter identifiers change. This is valid
conditional on executable feature equivalence, using Proposition 36.8. It does
not infer equivalence from matching contracts alone. The existing learned-state
factorization theorem supplies the conditional composition argument; Python
parameter serialization and binding checks are regression-tested.

## 36.17 Acquiring bridges between contributed interfaces

Suppose a source expert maps external inputs to type `A`, a teacher maps the
same inputs to type `B`, and a consumer accepts `B`. Fit an `A → B` decoder
from paired source/teacher outputs on training inputs only. Compose source,
learned adapter and consumer as a challenger for the original external task.
Select it by independent end-to-end outcomes, not by claiming `A = B` or that
matching shapes establish semantic equivalence. The teacher need not be used
during evaluation or inference. Its quality is an assumption of the training
signal, not a guarantee inherited by the adapter.

**Proposition 36.11 (conditional adapter composition).** If an adapter maps
every source output to the corresponding teacher output, then following it
with the consumer agrees with following the teacher with that consumer.
Apply the consumer to the assumed equality. Lean proves this conditional
statement, not universal correctness of an empirically fitted decoder.

The initial learner uses modal categorical decoding, with an empirical mode
fallback for unseen keys. The consumer and adapter are unary and slot-free;
source/teacher may retain the incumbent's external slots and inputs. Costs
add and effects are conservatively combined. New persisted heads have
content-derived residency identifiers so different fitted bridges can coexist;
previous scalar-head artifacts remain readable through their default loader id.

## 36.18 Continuous interface fitters

Bridge acquisition may accept any supplied fitter returning exactly the
requested unary adapter contract. It receives only paired training values;
end-to-end held-out selection is unchanged. The categorical fitter remains
the default, not a fixed catalog of possible interface learners.

One continuous instance fits `a x + b` by centered scalar least squares.
Set `a = Sxy/Sxx` and `b = mean(y) - a mean(x)` when the centered input
sum of squares is positive. Constant input uses the mean target. Finite
observations whose intermediate statistics or predictions exceed floating-point
range are rejected, not clipped or silently treated as constant.

**Proposition 36.12 (centered slope optimum).** For `Sxx ≥ 0`, any slope
satisfying `Sxx a = Sxy` minimizes `Sxx c² - 2 Sxy c`: the difference from
its value is `Sxx (c-a)² ≥ 0`. Lean proves this real-valued normal-equation
statement; it does not verify floating-point statistics or global interface
alignment. Independent outcomes must justify retaining the fitted bridge.

## 36.19 Vector-valued interface fitting

For paired finite tuple vectors, fit an affine map by least squares on a design
matrix containing the source coordinates and an intercept column. Input and
output dimensions come from the paired observations, not a fixed architecture.
The backend's rank-deficient minimum-norm solution need not identify behavior
in unobserved directions. Reject inconsistent shapes and nonfinite data/results.
Type identity remains nominal; observed numerical alignment does not equate
source and target interface types.

Coordinatewise exact alignment implies agreement after any consumer, by
function extensionality and Proposition 36.11. Lean proves this conditional
composition statement, not floating-point solver correctness, unique recovery,
or global embedding equivalence. Independent task outcomes must support keeping
the adapter. Parameter artifacts retain the matrix and contract without a
teacher implementation. This is an affine vector family, not arbitrary
nonlinear representation alignment.

## 36.20 Learned oblique intermediate partitions

Given finite tuple-vector observations and opaque categorical targets, estimate
one centroid per observed target. For each target pair within an explicit search
budget, use their centroid difference as a projection direction, then fit the
best observed scalar threshold and modal decoder as in §36.13. The learned
projection parameters and threshold define new intermediate interfaces. Input
dimension and target vocabulary come entirely from training observations.

For prototypes a and b and d=b−a, the projected separation is
`〈d,b〉−〈d,a〉 = Σᵢ (bᵢ−aᵢ)²`. Lean proves this finite real identity. It does
not prove that class centroids separate their observations, floating-point
accuracy, or generalization. Coincident centroids yield no direction; nonlinear
or symmetric distinctions can be missed. Candidate order follows first target
occurrence, and a budget truncates search without a completeness claim.
Independent end-to-end selection must justify keeping any proposal. This is
supervised acquisition of one representation family, not unrestricted invention.

## 36.21 Bounded nonlinear representation proposals

A polynomial lift enumerates all nonconstant coordinate monomials through a
caller-selected positive degree. Dimensions are observed, and the lift is
rejected before enumeration if `binomial(dimension+degree,degree)−1` exceeds the
explicit term budget. Candidate degrees and centroid-pair budgets are supplied,
not domain rules. Applying §36.20 in the lifted space learns a polynomial
projection and threshold, with generated lift, projection and partition types.
The polynomial basis is a supplied search family; only degrees retained by
independent task evidence should be promoted. This is not unrestricted invention.

An honest expressivity witness is the symmetric four-point construction:
for positive a,b, the mean product coordinate for `(a,b),(-a,-b)` exceeds that
for `(a,-b),(-a,b)` by `2ab>0`, although original class centroids coincide.
Lean proves this real identity and strict inequality, not noisy recovery or
floating-point polynomial accuracy. Reject nonfinite monomial results. Growth
is combinatorial, and a budget rejection is not evidence of impossibility.

A zero-error empirical split does not locate a boundary inside an unobserved
gap. The current threshold convention uses the first observation of the upper
region (§36.13). Even an exact learned interaction can therefore misclassify
fresh points in that gap. Neither the expressivity witness nor training success
establishes that this edge is the true boundary; boundary placement needs its
own justified modeling choice or further observations.

## 36.22 Boundary placement within an observed gap

For adjacent distinct observations l<u, any threshold t with l<t≤u preserves
all observed comparisons: if x≤l or u≤x then `(t≤x) ↔ (u≤x)`. Lean proves
this gap-invariance statement over the reals. It does not identify the true
boundary inside the gap. Threshold fitting may accept a supplied placement
policy, checked to remain in that interval; the default remains the upper
observed edge. Only the fitted threshold, not the callback, is retained.

A midpoint policy chooses l/2+u/2 to avoid intermediate overflow, falling back
to u when rounding fails to produce an interior float. Lean proves the exact
real midpoint lies inside the gap, not floating-point midpoint accuracy.
Midpoint placement expresses a modeling preference, not universally better
extrapolation. Independent outcomes compare policies as distinct candidates;
no held-out labels enter policy fitting or threshold placement.

## 36.23 Reusing training observations

For a deterministic, stable measurement f and projection p, mapping p over
materialized training values `map f rows` equals `map (p∘f) rows`. Lean proves
this pure list identity. It does not prove external modules deterministic or
verify executable snapshots. Numeric tuple snapshots are immutable; their
storage is local to fitting, never part of the proposed inference route.

An opt-in reuse mode requires a known empty effect declaration and no slots,
and the caller additionally assumes deterministic measurements and stable rows.
These checks alone do not establish determinism. Unknown/effectful measurements
and slot-bearing measurements cannot use this optimization. The normal path
continues repeated invocation. In reuse mode each measurement is evaluated once
per training row per projection-search call, then all centroid directions and
threshold fits consume those values. Inference still invokes the original
measurement. Contracts, declared inference costs and effect metadata are unchanged.
The scalar threshold learner is shared between both paths, not reimplemented.

## 36.24 Native monomial evaluation

The polynomial lift has an ordered list of coordinate-index terms. Pack these
as flattened indices and cumulative term offsets; evaluate each term by a
left-to-right product starting at one. The native evaluator checks offset and
index ranges before accessing values. It changes no basis ordering, type,
parameter, contract, or inference metadata. A reference interpreter remains
available when native kernels are unavailable or disabled.

Lean proves that an ordered real multiplication fold equals the initial
accumulator times the list product. It does not verify the Elisa compiler,
packed-buffer FFI, IEEE rounding, or the Python/native correspondence. Regression
experiments must compare both implementations, including finite extremes,
underflow, overflow rejection and empty bases. Wrapper validation of finite
Python-float tuples and finite output monomials remains identical on both paths.
No reassociation or exponentiation substitution is allowed by this design.

## 36.25 Retaining acquired encoder chains

An acquired numeric representation is a finite chain of known fitted runtimes
ending in a content-identified external measurement. Retain each generated type
and parameter record separately, with an explicit dependency on the preceding
artifact/export. Factories reconstruct the fitted runtime from parameters and
lazy dependencies; no external expert implementation or training rows are copied.
A chain serializer verifies the original external binding before saving and
rebinds later stages to the corresponding reconstructed predecessor. Cycles are
rejected. Byte sizes remain caller declarations, not measured resident memory.

If each stage's restored function equals its trained function, then their
composition does too. Lean proves this conditional list-of-endomorphisms special
case by induction. Heterogeneous typed constructors, executable factory fidelity,
floating-point behavior and the store/FFI remain unproved implementation
obligations. Admission and content identity check wiring and metadata, not
semantic equivalence. Existing package composition can export a restored
encoder plus a separately retained decoder; saved artifacts assert no calibration.

Regional routing and composition continue in [§§36.26–36.48](36-regional-acquisition.md).
