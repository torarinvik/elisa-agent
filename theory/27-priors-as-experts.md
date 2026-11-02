# 27. Priors as experts

## 27.1 The idea

§24 showed that a corrected answer's risk is only as good as the prior over
arity sequences. The format-only prior of (P) has more support than the
generator, so the decoder can land outside the generator's support, where
its risk claim fails completely (§24.3). The remedy suggested there: let an
expert supply the prior. The evaluator stays generic, decoding under
whatever prior it is given. The prior is a typed value produced by an
expert, which the kernel plans and selects like any other.

## 27.2 Weighted automata and the product

A **prior automaton** has states `τ`, a start state, transitions `ε`, a
weight `v(t, a) ≥ 0` for reading arity `a` in state `t`, and a final weight
`f(t) ≥ 0`. A sequence's prior weight is the product of the weights along
its run, times the final weight (`prior`).
The automaton recurrence is independent of the arity values: its alphabet may
contain any distinct nonnegative integer arities. A prefix-format restriction,
when needed, remains a separate property of the automaton's support.
For a finite alphabet, replacing each arity label by its distinct column
index preserves the transition and weight of every sequence, provided labels
are mapped back after decoding. This permits a bounded native symbol type
without imposing that bound on the prior's original labels.
**Theorem 27.15 (empty sequence).** For the empty sequence there are no
transition weights, so its weight is the start state's final weight. It is
accepted exactly when that weight is positive. For an accepted empty
observation, the posterior and base normalizers coincide, so its relative
log evidence is zero.

**Theorem 27.16 (risk from alternative mass).** Let `w` be the selected
sequence's weight and `a` the sum of all other sequence weights. When
`w + a > 0`, the selected sequence's posterior risk is
`1 − w / (w + a) = a / (w + a)`. Computing `a` separately can avoid losing a
small risk when the rounded total is indistinguishable from `w`. This is a
real-number identity; it does not itself bound floating-point error. The
implementation sums selected and alternative paths separately in log space
for prior-backed risk, then computes their normalized ratio.

**Theorem 27.17 (combining path partitions).** Suppose two independent
segments have selected masses `p`, `q` and alternative masses `a`, `b`.
Their concatenation has selected mass `pq` and alternative mass
`a(q + b) + pb`. The first term covers all alternatives in the left segment;
the second covers a selected left segment and an alternative right segment.
This composition is associative, with identity `(1, 0)`. Automaton segments
must also retain their boundary states; the scalar identity alone does not
prove a stateful incremental implementation or a floating-point error bound.

**Theorem 27.18 (matching boundary states).** For a left segment ending at
state `j` and a right segment starting at `j`, compose their selected/other
mass pairs by Theorem 27.17 and sum over `j`. The two resulting components
sum to the usual boundary-state product of total segment masses, and remain
nonnegative when the input masses are nonnegative. This avoids counting pairs
of segments whose boundary states do not match. Boundary-state composition is
associative over the reals; an empty segment maps each state to itself with
selected mass one and alternative mass zero, and is an identity on both sides.
This does not establish the numerical accuracy of a particular cached implementation.
The current incremental implementation retains prefix summaries, rather than
using a general boundary-composition tree; its state invariants are tested but
not formally proved by these scalar and boundary identities.

**Theorem 27.19 (prefix reuse).** For any deterministic state update over a
sequence of inputs, if the old and new sequences have the same first `k`
inputs, folding the new sequence equals folding its suffix from the old
prefix's state. Here an input must include both the reading and the selected
symbol. This generic result justifies the dependency boundary; it does not
prove that the Elisa state implements the mathematical partition recurrence.

Decoding under the format automaton (§21.3) and a prior automaton together
runs the dynamic program on their product. A product state pairs a format
state `s` with a prior state `t`. Reading `a` moves to `(δ s a, ε t a)` with
weight `qₖ(a) · v(t, a)`. A run is accepted when the format accepts, with
final weight `f(t)`.

| Theorem | Statement |
|---|---|
| 27.1 | the product sum-product recursion equals the sum over all sequences of score × prior |
| 27.2 | with nonnegative weights, no sequence's score × prior exceeds the product max-product recursion |
| 27.3 | unless the maximum is 0, some sequence attains it; backtracking decodes it |
| 27.4 | with the one-state prior of weight 1, the product program is the format-only program `dpSum` |

So everything in §21 carries over unchanged under any prior automaton:

- the decoded sequence `â` (`pdpMax`);
- the normalizer `Z` (`pdpSum`);
- the risk `R = 1 − score(â) · prior(â) / Z`;
- the marginals, by forward–backward over product states;
- the charges and the pairing argument of §21.6.

The pairing argument holds whenever the prior's support lies in `L_m`.

**Cost.** Per position, the work is the number of live product states
times the arities allowed from each. In general that is at most
`|σ_live| · |τ|`.

If the prior's support lies inside `L_m` (every sequence it weights
parses), the prior state determines the format state. The awaited count is
then a function of the prior state. The product then has no more live
states than the prior automaton alone, and the format component can be
dropped.

**Theorem 27.6 (prefix support pruning).** At a split position, let `F(s)`
be a state's prefix weight and `B(s)` its continuation weight. Then
`Σ_s F(s) B(s) = Σ_{s : F(s) ≠ 0} F(s) B(s)`: removed terms are zero.
The same restriction applies to a marginal's split sum. With nonnegative
transition weights, a zero-weight prefix contributes nothing to any later
state, so its forward transitions may also be omitted. Backward values need
only be computed on the forward support when used for these split sums;
values outside that support are not unrestricted continuation probabilities.

For a forward step `F′(t) = Σ_s F(s) W(s,t)`, suppose `F` vanishes
outside `A`, and `W(s,t) = 0` whenever `s ∈ A` and `t ∉ A′`.
Then `F′` vanishes outside `A′`: each summand has a zero factor. Thus an
enclosing interval of reachable states suffices; it need not equal the
exact support. With two reusable rows, clear only the previous interval
of the destination row before accumulating its new values. All other cells
remain zero. Scan source states and symbols in their original order to
preserve the accumulation order. Including initialization and the final sum,
this requires O(S + H_m + Σ_{k<m} (C_k + w H_k)) work, where C_k is the
cleared interval width, H_k is the source interval width, and w is the
alphabet size, with O(S) storage.

The same envelope restriction applies to max-product: omitted unreachable
candidates have weight zero, the identity for a maximum seeded at zero.
Filtering those candidates preserves the maximum, even when their envelope
has gaps. In log space, unreachable weight is negative infinity. For
traceback, ascending state/symbol traversal and strict improvements retain
the original predecessor on ties. Rolling-row clearing uses the same
outside-envelope invariant. A dense predecessor table still costs O(mS)
initialization and storage; interval scans reduce the subsequent transition
work without removing that cost.
Full decoding can retain one envelope per position alongside its dense
forward rows, then reuse those envelopes during the reverse pass and marginal
sums. Holes inside an envelope remain zero and are checked individually.

## 27.3 The contract

A prior expert has the contract

> `length → arity.prior.v1`,

producing, for a formula of `m` words, a prior automaton over arities
`{0, 1, 2}`. The evaluator consumes it alongside the word distributions. It
decodes under the product, and the format-only prior is the default
(Theorem 27.4).

Nothing about a generator is written into the evaluator. A generator's
structure enters as a separately installed, separately chosen expert, as
readers do.

A prior is a second, cheap input to the evaluator that depends only on the
length, so it is naturally the filling of a slot `[length] ⇒ arity.prior.v1`
(§20).

## 27.4 Prior experts

| prior | states | support | `Λ` for complete alternating trees (§24) |
|---|---|---|---|
| format only | 1 | `L_m` | unbounded |
| `n`-gram over arities | `3^{n−1}` (times format states) | `L_m` | unbounded |
| height at most `D` | at most `(D + 1) · 2^D` | trees of height `≤ D` | unbounded if `D` exceeds the generator's height, else as below |
| complete alternating trees of depth `d` | about `2^{d+1}` | `S_m` | 1 |

**Format only.** The prior of §21: one state, weight 1.

**`n`-gram.** The state is the last `n − 1` arities. Weights are conditional
frequencies counted on training formulas. Support is all of `L_m`. It
lowers the chance of decoding outside `S_m`, but cannot exclude it, so `Λ`
stays unbounded in the worst case (§24.3).

**Height at most `D`.** In preorder, keep a stack of the height budgets of
subtrees still awaited, and the current node's budget `h`.

- A node of arity 2 at budget `h ≥ 1` pushes `h − 1` for its right child and
  continues into its left child with budget `h − 1`.
- A node of arity 1 continues with `h − 1`.
- A leaf pops the next budget.
- No node of positive arity is allowed at budget 0.

Every pushed budget is smaller than the one below it, so the stack is a
strictly decreasing sequence from `{0, …, D − 1}`, that is, a subset. With
the current budget, there are at most `(D + 1) · 2^D` states. The language
is regular, and the stack's size plus one is the format's awaited count, so
the format component is redundant (§27.2).

**Theorem 27.7 (height-bounded support).** A unary/binary tree of height
at most `D` has `m + 1 ≤ 2^{D+1}`. Constants satisfy the bound; a unary
node adds one word, and a binary node joins two smaller-budget trees and
adds one word. Induction gives the bound. Every complete depth-`d` binary
skeleton with optional negated leaves has height at most `d + 1`, so the
height-`d + 1` prior contains the complete prior's support. The inclusion
does not require internal nodes to alternate connective identity.

**Complete alternating trees of depth `d`.** This is the generator's own
support `S_m`. The same stack automaton applies, with two restrictions:
nodes at budget `h ≥ 1` must be connectives (arity 2), and at budget 0 a
leaf is either a constant (arity 0) or `not` followed by a constant (arity
1, then 0). The states are the pending budgets, a subset of
`{0, …, d − 1}`, with one extra flag for "after a `not`": about `2^{d+1}`
states, with at most two transitions each.

**Theorem 27.5 (complete-shape length).** A complete binary skeleton of
depth `d`, with each leaf optionally negated once, has
`2^{d+1} ≤ m + 1 ≤ 3 · 2^d`. At depth zero the lengths are 1 and 2.
A branch joins two depth-`d` shapes and adds one connective, so both
bounds follow by induction.

Length determines depth. A depth-`d` formula has
`m ∈ [2^{d+1} − 1, 3 · 2^d − 1]` words, and these ranges are disjoint for
different `d`. So `length → arity.prior.v1` is a function.

**Why the complete-tree prior is exact.** On `S_m` the generator's prior and
(P)'s prior are proportional (§24.3). With the complete-tree prior's
weights all 1, the effective prior is (P)'s restricted to `S_m`, which is
proportional to the generator's. The prior ratio `ρ` is constant on the
whole support, and `â` always lies in it. So `Λ = 1` in both directions
(Theorem 24.4 and its exchange): under per-word calibration and
independent readings, `R* = R` exactly. Decodings outside `S_m`, which §24.3
showed are certainly wrong, cannot occur.

**Height-bounded priors** sit between the two. With `D` equal to the
generator's height (`d + 1`, since `not` adds a level), the support is a
superset of `S_m`, much smaller than `L_m`. The two-case analysis of §24.3
applies with this smaller support in place of `L_m`.

**Cost at depth 8** (`m = 575`, `d = 8`). Every `(position, state)` pair is
bounded by `m · 2^{d+1} ≈ 294k`, with at most two transitions each, about
0.6M multiply-adds per pass. The format-only program does about 0.25M per
pass (`2.25 m²` over three passes, §21.4). The exact prior costs at most a
few times the format-only one and still well under one top-rung word pass
per formula. Most stack states are unreachable at a given position, so the
live count is smaller than this bound. The banding of §23 applies to the
product unchanged.

## 27.5 Choosing a prior without labels

Which prior expert to use is a choice the kernel can make from **unlabeled**
readings. Let every candidate use the same independent base prior `πₖ` and
observation likelihoods `Lₖ(aₖ) = p(xₖ | aₖ)`. Write
`qₖ(aₖ) = πₖ(aₖ) Lₖ(aₖ) / cₖ`, with `cₖ = p(xₖ) > 0`.
An expert supplies nonnegative tilt weights `v_e(a)`, inducing the normalized
sequence prior `P_e(a) = v_e(a) Πₖ πₖ(aₖ) / Z_e(π)`, where `Z_e(π) > 0`.

**Theorem 27.8 (normalized prior evidence).** Its observation evidence is

> `p_e(x) = Σ_a P_e(a) Πₖ Lₖ(aₖ) = (Πₖ cₖ) Z_e(q) / Z_e(π)`.

Here `Z_e(q) = Σ_a v_e(a) Πₖ qₖ(aₖ)` is the calibrated-reading normalizer,
and `Z_e(π)` is the same program evaluated at the shared base probabilities.
Substitute Bayes' rule into the sum: `Πₖ πₖ(aₖ) Lₖ(aₖ) = (Πₖ cₖ) Πₖ qₖ(aₖ)`.
Thus the shared observation-marginal factor cancels when comparing experts.
There is no extra sequence-dependent divisor outside this sum.
Common edge and final factors cancel from this evidence ratio at a fixed
length. When their combined log magnitude reaches `2²⁴`, the implementation
removes them using checked shifts before computing both normalizers, so a
large shared prior weight need not be subtracted from another nearly equal
large weight. If the shifts cannot be represented with the local precision
checks, the calculation reports an error. Smaller common offsets use the
original prior. Forbidden edges do not determine the common edge shift. If
either finite normalizer still has magnitude at least `2²⁴`, subtraction is
rejected unless the two input readings are identical, in which case the
evidence is exactly zero. Neither path bounds all floating-point error in a
normalizer.

The evidence interpretation requires a common observation model, normalized
rows and posterior support contained in base support. Normalized calibrated
scores alone do not establish the shared likelihood assumptions. A candidate
with zero base normalizer is undefined; zero posterior normalizer gives
zero evidence. Neither case justifies substituting a finite epsilon.
Numerical implementations must reject a computed NaN or positive infinity:
overflow or invalid arithmetic does not establish positive finite mass. A
computed negative infinity is treated as zero mass. The normalizer detects
overflow in additions of reachable finite edge, reading, and final weights;
this is conservative because an overflowing reachable prefix may not lead to
an accepted sequence. It does not constitute a general floating-point error
bound. Native maximum and full decoding also reject detected non-finite
intermediate sums; this can conservatively reject cases whose final result
would be representable after cancellation.
Full decoding also checks marginal rows for finite, nonnegative entries and
approximate unit sum. This detects some loss of precision but is not a
floating-point error bound and cannot validate every normalized result.
The weighted decoder also checks local log-weight additions and log-sum
corrections before using them. A conservative magnitude envelope permits
ordinary arithmetic when all relevant values are small enough that an
individual binary64 rounding error is below the local tolerance. This is
not a bound on accumulated error or a certificate of the final marginals.
On a detected marginal failure, a weighted prior can retry decoding after
checked common row, edge and final shifts and restore the normalizer to its
original scale.
That binary64 normalizer may still lose small corrections at large magnitudes;
the selected-sequence risk is computed separately.
Partition calculations likewise reject a log-sum correction distorted by at
least `1.01 × 10⁻⁸`; other numerical errors can remain undetected. Incremental
partition updates invalidate their cached suffix after this arithmetic failure
before a later retry.
Finite log-weight additions use the same local TwoSum residual check as the
format partition; it detects a materially rounded individual addition, not
the accumulated error of an entire partition. The Lean identity establishes
the corresponding exact-real algebra; it is not a proof of binary64 rounding.
The individual prior-path log-weight calculation applies the same local
check. A forbidden transition or zero edge/final mass still makes the path
weight zero, even if an earlier intermediate sum could not be represented.
Subtracting one common log weight per reading row, one from every supported
edge, and one from every supported final state scales every fixed-length path
by the same factor. Its selected-to-alternative risk is unchanged by Theorem
27.16 and `prior_common_factors`. On a detected partition arithmetic failure,
sequence-risk calculation retries when the individual shifts are finite and
their rounding residuals are small. The common offset need not be representable
because it cancels from risk. Other operations may require its finite absolute
value. Evidence ratios likewise cancel the common prior scale without
requiring its absolute log offset to be representable. These checks do not
certify the subsequent calculation. Absolute partitions and incremental
cursor outputs retain their original scale and still report the arithmetic
failure.

Evidence accumulation retains TwoSum residuals in a separate correction, so
small contributions can accumulate until they are representable in the score.
A final addition or correction update that loses at least `1.01 × 10⁻⁸` is
reported; smaller errors can still accumulate, so this is not an overall
selection-accuracy bound.

Both terms are instances of Theorem 27.1. The kernel selects the prior with
the largest summed log-evidence over held-out formulas, a label-free audit.

**Evidence-only evaluation.** Each normalizer is a sum-product computation;
maximum backtracking and posterior marginals are unnecessary. Retaining only
the previous and next forward rows uses O(number of states) working space,
independent of sequence length, with the same transition work per pass.

For a shared position-independent base and a fixed length-indexed provider,
`Z_e(π)` depends on the candidate and length, not the observed reading.
Across N observations at L distinct lengths, its reuse reduces normalizer
passes from 2KN to KN + KL for K candidates. This is exact reuse, not a
probability approximation; it requires the base and models to stay fixed
throughout the selection batch.

**Answer-only maximization.** The posterior normalizer is common to every
accepted sequence. Selecting an answer therefore needs only max-product
and traceback (Theorems 27.2–27.3), not forward sums or marginals. Rolling
maximum rows suffice during the forward pass, while predecessor choices
must remain available for backtracking. The same rolling maximum rows apply
when full decoding also retains forward sums for marginal calculation.
The native maximum pass detects material loss in individual log-weight
additions; when it fails despite nonzero mass, checked common shifts can be
used to retry. This local check is not a proof of exact ordering in every
floating-point case.
During the reverse pass, each position's marginals use the stored forward row
and the next backward row; after emitting them, the older backward row can be
reused. This leaves traceback choices and forward sums as the retained tables.
The backward recurrence and marginal contributions use the same supported
transitions, so they can be accumulated in one traversal, retaining ascending
state order within each marginal sum.

**Risk-only refinement.** Once an answer is selected, its posterior risk
needs its own weighted score and the current normalizer, not a new maximum
or marginal table. Allocation priorities may be older nonnegative weights:
Theorem 23.11 still makes their normalized charges sum to the current
sequence risk. Periodic marginal refreshes can guide refinement without
being part of the risk certificate. Different priorities can change the
refinement path, so deployment certification applies to the resulting
policy rather than transferring automatically from another refresh rule.

**What evidence rewards.** `−log Z_e(π)` rewards small support: an Occam
term. `log Z_e(q)` penalizes supports that exclude sequences the readings
favor. A prior that excludes the truth loses evidence on every formula
whose readings are confident about it. Asymptotically, evidence selects the
candidate closest to the generator in Kullback–Leibler divergence. This is
the standard consistency of Bayesian model selection over a finite family,
used here as a heuristic, not proved.

**The risk of a wrong but confident prior.** Selection can still pick a
prior that excludes some true sequences, when the readings rarely make the
exclusion visible. For formulas whose truth lies outside the prior's
support, §24.4 applies with the roles reversed: `R* = 1` whatever `R` says.

**Theorem 27.9 (priority selection under uniform score error).** Suppose
each candidate's reported total log score differs from its target score by
at most `ε`. Let `M` be the largest reported score. Choose the first
candidate in a declared priority order whose reported score is at least
`M − 2ε`. Its target score is within `4ε` of the largest target score.
For any competitor, its target score is at most its report plus `ε`, at
most `M + ε`, at most the chosen report plus `3ε`, and hence at most
the chosen target score plus `4ε`.

The bound must hold simultaneously over the candidate set and be expressed
in total-score units for the selection batch. This is a conditional
deterministic guarantee, not an estimator of sampling uncertainty or a
proof that finite scores obey the common-likelihood assumptions. Declaring
broader supports first implements the support preference below when such
an error bound is available. A zero supplied bound gives empirical
maximization, without a population guarantee unless its premise holds.

**Theorem 27.10 (bounded evidence scores).** Fix the reader, shared base,
candidate providers, sample size `n > 0`, clipping level `B > 0` and
`0 < α < 1` before drawing IID formula observations. Assume each candidate
has a valid positive base normalizer almost surely. Define
`g_e(x) = max(−B, min(B, log Z_e(q(x)) − log Z_e(π)))`, mapping zero
posterior mass to `−B`. Let `μ_e = E[g_e(X)]` and `S_e = Σ_i g_e(X_i)`.
For `K` candidates, with probability at least `1 − α`, simultaneously

> `|S_e − n μ_e| ≤ ε_n = B sqrt(2 n log(2K/α))`.

Each score lies in `[−B,B]`. Hoeffding gives failure probability at most
`2 exp(−ε_n²/(2 n B²))` for each total; a union bound over K gives α.
Combining this event with Theorem 27.9 bounds the selected expected clipped
score's regret by `4 ε_n / n`. The event holds for fixed n, not optional
stopping or arbitrary repeated selection.

Clipping changes the objective: this does not bound raw-evidence regret,
model misspecification or answer errors. The concentration statement does
not require that the scores be true likelihoods, but that interpretation
still requires Theorem 27.8's assumptions. Calibration data may fix the
reader and base before this sample; selecting B, K or models using the same
sample is outside this guarantee.

**Theorem 27.11 (independent selection before risk audit).** Let p_e be the
probability of selecting prior e before an audit. If, conditional on each
selected prior and all upstream fitting information, the probability of
certifying a policy whose population answered-error rate exceeds δ is at
most α_audit, then the unconditional failure probability is also at most
α_audit: sum_e p_e failure_e ≤ sum_e p_e α_audit = α_audit.

Independent checking data and a valid fixed-policy audit justify the
conditional premise. It is not justified by inspecting several prior-specific
checking results and selecting the most favorable one. The prior-selection
regret confidence α_prior concerns a different event; it need not be added
to α_audit for the answer-risk statement alone. A joint claim of both
regret and audit soundness has failure probability at most
α_prior + α_audit by a union bound. Neither result says that each finite
evaluation sample's observed error rate must lie below δ.

**Theorem 27.12 (bounded scores for partial prior providers).** A provider
may explicitly declare itself unavailable at some lengths. Define its
per-observation reward to be `−B` there, and the clipped log-evidence score
elsewhere. This is a fixed total function in `[−B,B]` when provided models
have valid base normalizers. The same Hoeffding and selection bounds of
Theorems 27.10 and 27.9 apply to its expected bounded reward, without
conditioning on observed availability or removing the candidate catalog.

The penalty must be fixed before the selection sample. It is not a
likelihood assigned to an undefined conditional model. Invalid base
normalizers in a provided model remain errors. If every model is unavailable,
all rewards tie at the floor; the score rule supplies no coverage guarantee.
A provider selected this way can still abstain on later inputs, and its
answering policy still needs an independent risk audit.

Finite-precision tilt construction checks each finite edge addition for
overflow and for a local TwoSum residual of at least `1.01 × 10⁻⁸`. A
finite mathematical tilt can otherwise be rounded away at large weights;
zero-weight edges remain zero. This local check does not bound accumulated
error in later inference.

**Theorem 27.13 (support-preserving symbol tilts).** Given an automaton's
edge weights v(s,a), final weights f(s) and positive symbol factors r(a),
replace each edge weight by v(s,a) r(a). The weight of a sequence becomes
`v_r(a₁…a_m) = v(a₁…a_m) Π_k r(a_k)`. Induction along the run proves
this factorization. Its nonzero support is unchanged because every factor
is positive. In log space, add log r(a) to that symbol's edge weights.
This changes relative preferences within a structural model without adding
hard exclusions. Finite arithmetic must reject edge overflow that would
turn a previously finite log weight into an infinity.

For example, r(1)=η with r(0)=r(2)=1 multiplies a sequence's weight by
η to the number of unary nodes. η<1 discourages unary nodes and η>1
encourages them. This is a residual tilt of the existing model; η is not
in general a unary-node probability. A fixed catalog of such weighted
experts can use the same evidence and bounded selection rules as structural
experts. Models/factors and the clipping level must be fixed independently
of the selection sample for Theorem 27.10. Support preservation does not
make posterior risks calibrated, and the selected answering policy still
requires an independent risk audit.

A feature constant over every accepted sequence of a fixed length is
unidentifiable from conditional decoding: its common multiplicative factor
cancels from posterior probabilities and from normalized evidence. In the
complete-skeleton model, length identifies depth and the numbers of binary
nodes and leaves; remaining nodes are unary negations. A unary-only tilt
therefore changes no conditional model there. It can change format-only
and height-bounded models, whose unary counts vary at fixed length. This
limits what parameter learning can express even with perfect observations.


**Theorem 27.14 (leaf and binary tilt equivalence).** For a finite rooted
prefix tree whose nodes have arities 0, 1, or 2, let L and B be the numbers
of leaves and binary nodes. Counting edges gives `L + U + B - 1 = U + 2B`,
so `L = B + 1`. Multiplying every leaf weight by a positive factor r and
multiplying every binary-node weight by r therefore produce unnormalized
sequence weights that differ by the same factor r for every valid tree.
Consequently their normalized sequence distributions, position marginals,
and normalized evidence against the same base agree whenever the relevant
normalizers are positive and finite. This equivalence applies only to priors
whose support consists entirely of complete single-root trees; partial forests
or other alphabets need not satisfy the count identity. Floating-point
implementations can differ by rounding.

Two safeguards:

1. Prefer the largest support among priors whose evidence is statistically
   indistinguishable from the best. Of priors that fit equally, keep the one
   least likely to exclude the truth.
2. Keep risk control (§24.5) on the deployed policy. It certifies the error
   rate among answered formulas whatever the prior.

The prior changes which formulas are answered; the audit decides whether
the guarantee holds.

For an alphabet `(0, ..., A − 1)`, a selected symbol is its own transition
column. Once this ordering is checked, a length-`m` prior path needs `O(A + m)`
work for column lookup instead of `O(mA)`; other alphabet orderings use the
general search. This does not change the automaton or its path weights.

[Theory index](../THEORY.md)
