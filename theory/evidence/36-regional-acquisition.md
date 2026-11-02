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
