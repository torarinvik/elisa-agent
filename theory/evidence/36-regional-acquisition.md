# 36. Regional expert acquisition

Continuation of [Acquiring experts](36-acquisition.md); section numbers remain stable.

## 36.26 Failure-directed regional expert acquisition

Group training rows by a supplied routing feature's stable hashable keys. Rank
regions by incumbent error count, with first-observed order breaking ties, and
invoke a supplied expert proposer on at most the caller's region budget among
regions with errors. Give each proposer all training rows/targets in its region,
including successful controls. Its experts must preserve the external contract;
constructor declarations are carried into the resulting proposals.

A regional proposal evaluates the routing feature and invokes the acquired
expert only on its selected key; elsewhere it invokes the incumbent. For pure
stable mathematical functions the resulting output equals the incumbent outside
the selected region. Lean proves this conditional noninterference statement.
It does not prove effectful execution unchanged, proposer generalization, or
optimal budget allocation. Targets need not be categorical/hashable: the caller
supplies the correctness predicate and training family. Independent whole-task
outcomes, including the unaffected regions, select the frozen candidates.
Metadata conservatively includes both branches and the routing feature; no
inference call-count or effect declaration is invented. Proposals are currently
in-memory, without a new persistence or calibration claim.

## 36.27 Acquiring routing boundaries from training failures

From training rows and a caller-supplied correctness predicate, form incumbent
failure indicators. Fit a scalar measurement partition to those indicators
using the existing empirical threshold objective; its generated interface
becomes the routing feature for §36.26. Then train regional specialists using
the original task targets, never the auxiliary failure indicators. Targets
need not be categorical. Measurement and region budgets remain explicit.

Constant failure indicators supply no error contrast, so this proposal family
returns nothing; constant measurements also yield no split. This is a limited
scalar routing family, not evidence that no decomposition exists. If a learned
router perfectly matches failure indicators on the training list, it covers
every failed training row; Lean proves this conditional finite-data statement.
No held-out coverage, actual perfect alignment, arbitrary feature discovery or
optimal allocation is implied. A generated partition may be imperfect, so
whole-task independent selection remains essential. The routing type and the
specialist's new constructors travel together in each in-memory proposal.

## 36.28 Multi-interval failure routing and refinement ties

A routing-region budget allows the same greedy interval refinement as §36.14
to fit incumbent failure indicators, followed by §36.26 regional task training.
A narrow internal error region can require two cuts although no single cut
improves modal accuracy. Choosing the first tied boundary may waste the budget.
An optional label-agnostic secondary score can choose among equally accurate
cuts; weighted purity is `Σ labels left_count²/left_size + right_count²/right_size`.
This is a supplied modeling preference, not domain knowledge or a global optimum.

The primary score remains modal successes. For binary counts a,b in one child
and c,d in another, `max(a+c,b+d) ≤ max(a,b)+max(c,d)`; Lean proves this integer
refinement bound without a premise about chosen modal labels. It does not prove
that executable histograms are correct, that greedy ties find the best future
cuts, or that held-out errors decrease. Empty/pure intervals and explicit region
budgets retain their existing behavior. The original first-boundary tie rule
remains the default. Independent whole-task outcomes must compare routing policies.

## 36.29 Retaining regional wiring

A regional model stores its selected structural key, dispatch overhead, and
three explicit content references/export positions: incumbent, routing feature,
and specialist. Verify each original binding before snapshotting; reconstruct
the runtime from lazy dependency scopes, with metadata recomputed from those
components. Model identity includes the key and dependency references so distinct
regional wirings do not share an artifact identity. Key encoding uses the
existing finite scalar/tuple codec; unsupported keys fail explicitly.

If restored routing and both restored branches agree with their original
functions, the restored regional function agrees everywhere. Lean proves this
conditional branch-composition statement with an unchanged key. It does not
verify key codecs, Python factories, effectful execution, or content-addressed
code fidelity. No training rows, external implementations, calibration claims,
or independent-selection evidence are silently embedded in this parameter record.

## 36.30 Combining disjoint regional specialists

A regional policy maps stable routing keys to contract-preserving experts,
evaluates the feature once, and delegates missing keys to the incumbent.
An explicit combination budget enumerates a bounded prefix of the Cartesian
product of trained alternatives across trainable selected regions, alongside
single-region candidates; it does not search all region subsets. Whole-task
independent selection remains required. Costs/calls conservatively cover all
branches. Lean proves pure output preservation for missing keys, not gains,
optimal enumeration, or executable fidelity. Parameter artifacts retain the
ordered keys and verified dependencies; unsupported structural keys fail.

## 36.31 Training-ranked composition budgets

For each trainable region, score every frozen alternative on that region's
training rows and original targets. Sort by descending successes, ascending
declared cost, then original order. Since regions are disjoint and incumbent
behavior outside them is fixed, the composition's training successes are a
constant plus the sum of regional successes. Thus choosing each regional
maximum maximizes that sum; Lean proves this conditional finite-sum bound.
It does not prove the executable scorer, heap enumeration, or generalization.

A best-first Cartesian frontier starts at the regional maxima and advances one
choice index at a time. Monotone local ordering allows enumeration by total
successes, then total cost, then choice positions, without materializing the
whole product. Retain at most the explicit composition budget; each popped
state generates at most the number of trainable regions in neighbors, with
visited states deduplicated. Initial scoring still costs all alternatives on
their regional training rows. Only subsequent independent outcomes justify
promotion; training maxima and a limited frontier do not imply best held-out
performance or exhaustive subset/representation search.

## 36.32 Leaving regions with the incumbent

Add an explicit fallback choice to each selected regional family, scored by
the incumbent's observed successes in that region. Its incremental wiring cost
is zero because the incumbent is already the policy's default. Prefer fallback
when scores and costs tie. The single-alternative special case realizes
`max(incumbent_successes, offered_successes)`; Lean proves this natural-number
identity, not held-out improvement or executable scoring correctness.

A combined policy omits fallback keys, allowing partial region subsets within
the same bounded ranked product. Incumbent-only and one-specialist assignments
are already represented by the baseline and single candidates, so skip them
without spending joint-output slots. With mᵢ nonfallback alternatives per region,
there are exactly `1+Σmᵢ` such assignment states; bound frontier pops by this
count plus the requested joint-candidate budget. This does not bound trainer
costs or prove heap enumeration. Stable models/scoring and independent selection
remain necessary; refusing an expert on training data is not a generalization proof.

## 36.33 Bounded refinement inside unresolved regions

After fitting a region's direct alternatives, choose the training-best seed
among them and the incumbent (cost then stable order break ties). If that seed
still has training errors and a refinement-call budget remains, invoke a supplied
refiner with the seed, the complete regional training subset and original targets.
Append its contract-preserving proposals rather than overwriting direct ones;
carry the seed's constructor declarations into them. Perfect training seeds
consume no refinement call. Empty direct families may still refine the incumbent.
The budget counts outer refiner calls, not arbitrary computation inside callbacks;
measurement searches each have their own budget, and allocation is greedy.

A refiner may itself propose a regional decomposition, creating a hierarchy.
Nested pure gates with the same fallback act on the intersection of their
regions; Lean proves this special-case identity, not learned-boundary accuracy,
seed quality or held-out improvement. Existing regional artifacts can represent
such dependencies after child components are retained. Stable models/samples,
faithful callbacks and independent whole-task selection remain assumptions.

## 36.34 Retaining an acquired model graph

Visit a known learned-runtime graph in postorder, retaining children before
parents and memoizing original object identities. Shared children reuse their
bindings; cycles in the traversed graph fail explicitly. Known runtimes retain
fitted parameters and reconstruct wiring from installed children without mutating
the trained graph. Metadata must agree except for content-derived module names.
External or unrecognized runtime types remain opaque and require a binding that
matches their original content identity and full manifest. A subclass is not
silently treated as its base interpreter. This is not arbitrary Python serialization.

For composition nodes, equality of restored feature and head functions implies
equality of their composition; Lean proves this conditional statement. Existing
regional restoration lemmas cover the branch case. Neither proves factories,
FFI, traversal, mutable state equivalence or hidden expert implementations.
Per-node byte sizes are caller declarations, not measured process memory.
The iterative visitor introduces no extra recursion-depth limit, but existing
store/install/runtime resource constraints still apply. Stable functional models
and faithful factories/dependencies remain assumptions.


## 36.35 Auxiliary feedback for bootstrap routing

Binary correctness is constant when every incumbent prediction is wrong. Let
an optional supplied function assign a stable hashable auxiliary label to each
training triple (input row, incumbent prediction, original target). Fit routing
cuts to these labels, while regional experts still train on original targets.
Require at least one incumbent error and at least two distinct routing labels.
The feedback function is needed only during acquisition, not inference.

For two observations l < b ≤ u and arbitrary labels a, c, the threshold rule
returns a at l and c at u. Lean proves this ordered two-observation special case.
It does not prove arbitrary feedback separable, useful, calibrated, or learned.
Larger empirical fitting and independent whole-task selection retain their
previous assumptions. Stable callbacks and observations are required; a supplied
feedback function extends the search signal, not the available measurements or
expert families, and offers no universal bootstrap guarantee.


## 36.36 Exact ordering of promotion evidence

For w wins and l losses on paired correctness, let n = w + l and retain
p = (Σ from k=w to n of binomial(n,k)) / 2^n as a rational number.
For a frozen family of m candidates accept exactly when m p < α; choose the
smallest accepted rational p, retaining proposal order for genuine ties.
Conversion to a reported floating value must not control either decision.
For an all-win candidate p = 1/2^w, strictly decreasing with w. Lean proves
the positive-denominator reciprocal ordering special case, not executable
binomial summation, probability validity or generalization. This preserves the
finite-family assumptions of §36.3 and does not make p-value ranking equivalent
to maximizing accuracy. Exact integer arithmetic has sample-dependent cost.


## 36.37 Training-only router screening

Fit at most B routing candidates from a supplied ordered measurement family.
For a fitted router r and auxiliary labels z, define its empirical modal score
S(r) = Σ over regions g of max over labels a of count{i : r(x_i)=g, z_i=a}.
Rank by decreasing S, retaining supplied order for ties; spend specialist
training on only the first M fitted routers. B and M are explicit resource
budgets, not architectural limits. Without screening keep prefix allocation.

For two scores a,b, choosing b when a ≤ b and a otherwise yields a score at
least each input score. Lean proves this two-candidate comparison, not the
implementation's sorting or a relationship to task improvement. All screening
uses training data only; original targets train specialists and independently
held-out whole-task selection remains mandatory. Measurement stability and
meaningful supplied feedback are assumptions. Additional observations and
sorting cost are real; empirical signal purity may prefer an unhelpful router.


## 36.38 Feedback-fitted routing measurements

Given a vector measurement v and opaque auxiliary training categories z, group
observations by z and form each finite centroid μ. For a bounded ordered set
of category pairs, propose the scalar measurement r(x) = (μ_b − μ_a) · v(x)
when the centroid difference is nonzero. Each projection introduces its own
source/direction-derived interface. Fit routing cuts on these scalar measurements,
then train regional experts on original targets, which need not be categories.
Feedback categories are not declared to be values of the task's output type.

For d = μ_b − μ_a, the projection gap at the two centroids is d · d ≥ 0,
strictly positive if d ≠ 0, as in §36.20. Additionally, replacing opaque category
names while preserving group membership cannot change centroid inputs; Lean
proves the filter-membership special case. It does not prove executable fitting,
finite arithmetic accuracy, generalization or nonlinear separability. Ordered
pair budgets, stable measurements and independent whole-task selection remain
assumptions. Learned directions do not invent the underlying vector measurement.


## 36.39 Feedback-driven measurement acquisition

After constructing nonconstant training feedback with at least one incumbent
error, freeze a prefix of supplied measurements. For a total candidate budget B
and F fixed candidates, request at most B−F additional measurement proposals
from a supplied learner on training rows and feedback only. Retain at most this
prefix of its outputs. Each proposal must preserve the original external inputs,
slots and relevance, with an arbitrary scalar output interface and explicit
constructor declarations. Fit/screen routers, then acquire task specialists.
Propagate the learned measurement declarations before the router declarations.

Taking at most k elements of a returned list retains at most k elements; Lean
proves this bound, not callback termination, truthful declarations or runtime
cost. The callback owns its internal work budget. Empty/constant feedback and
zero remaining slots must not invoke it. No callback or training sample becomes
part of the inference route. Learned implementations still belong to a supplied
family; this orchestration does not invent arbitrary executable bodies. Stable
models, faithful learners and independent whole-task selection remain necessary.


## 36.40 Acquiring heads on candidate representations

For a candidate representation f : X → A and original target type Y, request
a bounded family of heads h : A → Y trained on pairs (f(x_i), y_i). Compose
each head with its representation and propagate both constructor declarations
in dependency order. Targets need not be hashable or categorical. External
slots and relevance belong to f; heads are unary and slot-free. Candidate
feature/head limits bound retained families, not callback computation.

A necessary condition for exact factorization is: if f(x)=f(x′) and the same
head realizes targets at both points, then y(x)=y(x′). Lean proves this fiber
consistency condition. It does not assert a supplied feature is sufficient or
a head family can fit it. Training observations and original targets are fixed
before fitting; stable models/payloads and faithful callbacks are assumptions.
Independent whole-task selection, not training fit, decides retention. This
learns head parameters and wiring within supplied families, not arbitrary bodies.


## 36.41 Continuous-feedback projection fitting

For finite vector observations v_i and real feedback z_i, center both and solve
min_w Σ_i (w · (v_i−v̄) − (z_i−z̄))². Use the minimum-norm solution when the
design is rank deficient. Propose x ↦ w · v(x), with a generated direction type;
leave any offset to a separately fitted head. Exactly zero directions emit no
proposal. Feedback is numerical training evidence, not a task output declaration.

For centered residual r orthogonal to a perturbation p, expanding squares gives
Σ(r_i+p_i)² = Σr_i² + Σp_i². Lean proves the scalar orthogonal special case
r*p=0; it does not verify the numerical solver or general vector optimality.
Floating-point centering, conditioning and finite range can affect results.
Stable observations and independent whole-task selection remain assumptions.
No unobserved direction is identified by a minimum-norm fit, and a supplied
vector measurement or regression family is not invented by this mechanism.


## 36.42 Error-driven polynomial representation growth

Starting at degree one, form the complete nonconstant monomial basis, fit a
continuous-feedback projection, and retain its generated interfaces. For fitted
projection q_i, estimate offset b = mean_i(z_i−q_i) and stop at the first degree
with max_i |z_i−q_i−b| ≤ ε, for a supplied finite nonnegative ε. Otherwise grow
the degree, bounded by explicit degree and term budgets. Stop before allocating
an over-budget complete basis; never silently truncate a basis. Zero directions
emit no feature. Fit actual heads and select whole-task candidates independently.

For nested exact hypothesis classes, if the larger class contains a predictor
with error E_small and its optimizer attains no larger error than any member,
then its error is at most E_small. Lean proves this comparison principle, not
monomial enumeration, least-squares implementation or a monotonic maximum-error
claim. Least squares minimizes squared error, while the stopping statistic here
is maximum absolute residual. Training stopping can miss better generalizing
higher degrees. Families, tolerance and vector source remain supplied; resource
budgets bound retained structures, not callback time or numerical conditioning.


## 36.43 Training snapshot reuse during representation growth

For a deterministic slot-free measurement with known empty effects, capture
v_i once during growth. For each degree compute the validated polynomial lift
once and reuse it for projection fitting and residual evaluation. If the
captured values equal repeated observations, the fitted design and stopping
residuals are identical. Lean proves pointwise equality implies equality of the
mapped observations. It does not prove determinism, FFI correctness, floating
solver reproducibility or a time bound. Purity metadata alone is insufficient:
the caller explicitly asserts determinism by opting in.

Snapshots are local to acquisition. Returned projections retain the original
measurement/lift graph, not training caches. Temporary memory increases with
sample count and basis size; existing degree/term budgets do not bound total
bytes. Independent head fitting and selection retain their original behavior.


## 36.44 Refining representations after head failures

Process a bounded queue of candidate representations. Fit bounded unary heads
on each and, when a supplied correctness predicate finds unresolved training
errors, pass the best training head and its feature to a supplied refiner.
Rank heads by training success, then declared cost and stable order. If no head
was returned, pass no seed head. Refined features enter the same queue and must
preserve the original external signature. The refiner supplies the constructors
of its actual dependencies; replacements need not depend on the seed feature.

Initial and newly admitted features share one total budget B; if U have been
admitted, retain at most B−U new proposals. Lean proves U+A ≤ B when
A ≤ B−U and U ≤ B. A separate bound limits refiner calls, not their internal
computation. Perfect training heads and exhausted budgets skip refinement.
Models, payloads and scoring must remain stable; independent whole-task
selection still decides retention. This does not invent the refiner family,
prove training seed quality or guarantee a useful representation exists.


## 36.45 Combining representations to resolve ambiguity

For a seed feature f, bound a supplied ordered companion family g. Compute the
empirical modal score of f and of each pair (f,g); retain only strict gains,
ranked by descending training score with stable ties and a bounded output count.
Keys and labels are opaque stable hashable values. Pairing refines seed groups:
equal joint keys imply equal seed keys. Lean proves this implication. The binary
modal split inequality of §36.28 supports the two-label/two-child special case;
no general executable score theorem or generalization guarantee is claimed.

Each retained feature is an ordinary structural product of the original experts,
carrying both sets of required constructor declarations. No training tables are
retained in the feature. A categorical head may exploit the finer partition;
other head families may not. Screening sees training data only, and independent
whole-task selection decides retention. Finite sample gains can reflect noise;
this learner combines supplied capabilities rather than inventing their bodies.


## 36.46 Retaining learned structural products

Retain both ordered child bindings and the explicit pairing overhead of a known
structural-product runtime. Reconstruct from those children without evaluating
or copying their implementations. Shared children reuse one binding, nested
products preserve association, and changed metadata other than derived names
fails retention. Unsupported runtime subclasses remain opaque. Conditional on
each child function being restored exactly, the ordered pair function is restored
exactly; Lean proves this pointwise statement, not codecs, factories or provenance.

The pairing overhead is stored directly rather than recovered by floating-point
subtraction from total cost. External implementations still require verified
bindings. Sizes are declarations and mutable-state snapshots are not provided.
This extends graph retention to the representations acquired in §36.45; it does
not grant a semantic or risk certificate to a paired feature.


## 36.47 Bounded lookahead across modal-score plateaus

A companion may not improve empirical modal score alone while a larger joint
representation does. Enumerate bounded companion subsets in increasing size,
then supplied index order, scoring each directly against the seed. Do not require
strict gain at intermediate pairings. Bound companion count, subset depth, scored
subset count and retained outputs separately; non-improving subsets consume the
scoring budget too. Retained products associate left in subset order.

For any fixed coarse label, the sum of its child-group counts is at most the
sum of child modal scores whenever each modal score dominates that child's count.
Lean proves this finite-sum comparison for arbitrary child groups, not executable
ranking, search completeness or held-out gains. Source snapshots are local to
training and assume stable observations. Search remains combinatorial; bounded
lookahead can miss deeper interactions, and observed gains can reflect noise.


## 36.48 Learned categorical quotient interfaces

Observe source keys and category targets on training data. Assign each key its
empirical modal category, then group keys sharing that category into an opaque
code. Code numbering follows canonical source-key order; modal ties retain
training occurrence order. Add a fallback code for the global modal category,
even if no observed key has that mode. A generated constructor identifies the
source type and digest of the key-to-code partition. Inference retains only
keys, codes and fallback, not category names or training samples.

For keys grouped under category a, each key's count for a dominates its count
for every category b; summing preserves that dominance. Lean proves this finite
sum statement. Thus a categorical head can preserve empirical modal accuracy
under grouping, but arbitrary head families and downstream tasks may lose useful
information. Bijective category renaming preserving modal choices leaves the
partition unchanged. Stable keys/categories, faithful value encoding and
independent whole-task selection remain assumptions. Smaller downstream tables
do not imply a smaller whole model: the encoder itself retains a key table.


## 36.49 Prototype-based vector interfaces

Group finite vector observations by opaque training category and fit each
centroid. Generate an interface assigning a vector to the nearest Euclidean
centroid, breaking ties by first category occurrence. Identical centroids share
a code. A supplied group budget rejects excess categories rather than truncating
the model. No category names or samples remain in the encoder, and the generated
type records source and centers. Unlike a key table, this rule applies to fresh
vectors, but centroid geometry may not separate their categories.

In one dimension, if a < b and x < (a+b)/2, then (x−a)² < (x−b)². Lean
proves this strict two-center special case, not finite-vector distance evaluation,
centroid quality or generalization. Finite range and consistent dimensions are
required; unrepresentable distances fail explicitly. Independent whole-task
selection and faithful serialization remain assumptions. Sources, categories
and the prototype family are supplied; useful geometry is not guaranteed.


## 36.50 Multiple prototypes within a category

A category may have several separated observation modes whose single mean is
unrepresentative. Optionally initialize multiple centers within each category:
start with its first observation, then repeatedly choose the first farthest
observation by distance to its nearest existing center, stopping at zero distance
or a supplied per-category bound. Perform a bounded number of nearest-center
assignments and mean updates within that category. Keep empty-cluster centers;
stop early if centers are unchanged. Reject total prototype-budget overflow.

For two scalar observations, their mean minimizes the sum of squared distances;
Lean proves this special case. It does not prove global clustering optimality,
floating-point descent or category separation. Initialization and stable ties
depend on observation order. The fitted runtime still stores only centers, so
existing type generation and artifact factories apply unchanged. Independent
whole-task selection remains necessary, and larger prototype families can overfit.


## 36.51 Interval-separated nearest-prototype acceleration

A packed numeric kernel may return a center only when its upper distance bound
is strictly below every other center's lower bound. Outward-rounded subtraction,
squaring, summation and square root construct conservative intervals; extra norm
padding accounts for reference rounding. Overflow, unsupported shapes or overlapping
intervals request the original reference path, preserving first-center ties.

If each reference score lies in its stated interval, strict interval separation
implies the selected score is strictly smallest. Lean proves this abstract
implication, not the numerical interval construction, FFI or compiler semantics.
The enclosure argument assumes ordinary IEEE binary64 rounding, faithful libm
nextafter/sqrt, and reference norm error within one ulp. These assumptions are
not formalized or established by testing. Near ties and nonrepresentable squared
distances deliberately use the robust reference. Models retain original centers;
packed buffers are derived parameter caches, not training observations.


## 36.52 Error-driven prototype family growth

Increase the per-category center allowance from one while empirical modal
errors exceed a supplied nonnegative integer budget. Retain every fitted
representation and stop after the first sufficiently explained training sample.
Before fitting each family, require category_count × allowance ≤ total_budget.
This conservative complete-allocation check can reject a family whose duplicate
centers would fit in fewer slots, but never drops categories to satisfy a budget.
Per-category/iteration bounds remain explicit resources, not architectural limits.

Zero failed observations imply every Boolean training outcome is true; Lean
proves this special case, not scoring implementation, monotonic improvement or
head-family sufficiency. Positive tolerances are caller choices. Modal ambiguity
need not fall with each local clustering run, and training stopping can miss
better generalizing candidates. Independent whole-task selection remains
mandatory. Only centers and generated type declarations enter inference artifacts.


## 36.53 Allocating prototype growth to remaining errors

Optionally reserve one center allowance per observed category, then fit and score
modal predictions. Increment only the eligible category with the most training
mistakes, ties by category occurrence order. Eligibility requires remaining
mistakes and allowance below the supplied per-category cap. Stop if no category
is eligible, the total reserved allowance exceeds budget, or error tolerance is
met. Uniform allocation remains the default. Reservation counts can exceed the
number of distinct fitted centers because duplicate modes share runtime codes.

Increasing one allowance by one increases its summed reservation by one; Lean
proves the finite-sum identity. It does not prove this greedy choice optimizes
accuracy, finds every useful allocation or generalizes. Growing an apparently
correct category might indirectly improve another, which this heuristic can miss.
Stable observations and independent whole-task selection remain assumptions.
Training category names and allocations are not retained by fitted runtimes.


## 36.54 Bounded alternative prototype allocations

Optionally explore alternative incremented allowance vectors, including growth
of currently correct categories. Fit each state once, retaining all candidate
representations. Prioritize queued states by their parent's modal error count,
then the grown category's error count, then insertion order. This is a heuristic
ordering of unfitted children, not their measured score. Bound total fitted
states separately from per-category and total-center reservations. Stop at a
satisfactory training fit, empty frontier or the supplied trial limit.

Incrementing a category changes its allowance vector; Lean proves this pointwise
special case. Deduplicating signatures avoids fitting states reached by different
paths more than once. Neither proves global optimality, search completeness or
generalization. Distinct allocations can produce identical models and still
consume trials. Frontier memory depends on category count and trial budget;
callbacks/measurements remain subject to stable-training assumptions. Independent
whole-task selection remains mandatory.
