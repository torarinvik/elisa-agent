# 17. Calibration under distribution shift

## 17.1 The problem

Theorem 16.1 promises that the error rate among answered inputs is at
most `δ`, under one premise: the bound is valid, `q(x) ≤ b(x)` for every
input `x`, where `q(x)` is the true probability that the answer to `x` is
wrong and `b(x)` the controller's bound. The bound is a sum of calibrated
per-item risks, and calibration is *fitted*. Temperatures minimize negative
log-likelihood on held-out data from a reference distribution `P`, which
makes risks right *on average over `P`*. It makes them neither pointwise
valid nor right on average over the distribution `Q` met in use.

Three facts organize the repair:

1. how far the guarantee degrades is governed by a single quantity, the
   answered mass of the bound's deficit (§17.2);
2. degradation cannot be prevented by any method that looks only at `P`:
   some information about `Q` is required (§17.3);
3. a small audit sample from `Q`, labeled by a teacher, suffices for a
   finite-sample, distribution-free guarantee, through a family of
   increasingly cautious policies tested in a fixed order (§17.4–17.6).

## 17.2 How much the guarantee degrades

Write `A = {x : b(x) ≤ δ}` for the answered inputs and `p` for the input
distribution. Splitting `q = b + (q − b) ≤ δ + (q − b)⁺` on `A` gives
(Theorem 17.1):

> `Σ_{x∈A} p(x) q(x) ≤ δ · Σ_{x∈A} p(x) + Σ_{x∈A} p(x) (q(x) − b(x))⁺`.

Dividing by `p(A)`, the error among answered inputs is at most `δ + D`, where
`D = E[(q − b)⁺ | A]` is the mean *deficit* of the bound among answered
inputs. Three remarks:

- **Deficit, not miscalibration.** Only underestimation inside `A` matters.
  An overestimating bound costs coverage, never validity, and errors on
  inputs the system declines are irrelevant.
- **Selection amplifies.** `A` is selected *by* `b`: inputs whose bound
  happens to be low are exactly the answered ones, so `D` can exceed the
  average deficit over all inputs. The controller sharpens this. It refines
  until the bound crosses `δ`, then stops, so answered inputs sit just below
  `δ` with whatever estimation error they carry. This is why violations
  appear at strict targets first.
- **Transfer under bounded shift.** If deployment weights are at most `W`
  times reference weights (`pQ ≤ W · pP`), every nonnegative weighted sum
  grows by at most `W` (Theorem 17.2). A deficit measured on `P` thus
  bounds the deficit on `Q` up to the factor `W`, which is unknown in
  practice and can be large.

## 17.3 Why reference data alone cannot suffice

Fix any procedure that maps reference data to a bound `b`. Take two
deployment distributions `Q₁` and `Q₂` with the same inputs as `P` but
different labels on a set `S` of inputs that `b` answers. On `S` the true
error probabilities differ, while `b` is the same for both, because it never
saw `Q`. The bound cannot be valid for both unless it declines `S`. Pushed to
the limit, this is Theorem 5.2 (§5): a module that never fails
offline can fail always in situ. A guarantee on `Q` therefore requires
observations from `Q`. The question is how few, and how to use them
without spending the guarantee on their noise.

## 17.4 The audit

An **audit** is a sample of inputs from `Q`, labeled by a teacher, used only
for calibration decisions. It is distinct from the practice queue (§16),
whose labels are chosen by risk to train better experts. Audit inputs must
be drawn so that their distribution is known: uniformly from the deployment
stream (the default), or with known inclusion probabilities `π(x) > 0`, in
which case every audit quantity is weighted by `1 / π(x)` and remains
unbiased for its population value (Theorem 17.3). The second option
lets practice labels drawn with probability proportional to risk be reused
for auditing. Their weights are inversely proportional to risk, so
low-risk inputs, rarely drawn, count heavily.

Two uses of the audit are complementary.

**Recalibration (estimation).** Refit each rung's temperatures on audit
items (glyphs read in deployment, with teacher labels) instead of on
reference data. This moves the risks toward calibration *on average over
`Q`* and reduces the deficit `D`. It gives no finite-sample guarantee: the
fitted temperatures carry estimation error, and average calibration is not
pointwise validity.

**Risk control (guarantee).** Treat the controller as a policy family and
certify a member of it with the audit, as follows.

## 17.5 Risk control by fixed-sequence testing

**Policy family.** For an inflation factor `λ ≥ 1`, policy `π_λ` runs the
controller with target `δ / λ` and answers when the final bound satisfies
`λ · b ≤ δ`. Larger `λ` means more refinement and more caution. For a fixed
bound function the answered sets are nested (Theorem 17.4), and
the family always contains a *trivially safe* member in the limit: never
answer. The true selective risk of a policy on `Q` is

> `R(λ) = P_Q(wrong | answered by π_λ)`,

and `π_λ` is *safe* when `R(λ) ≤ δ`. Nothing requires `R` to be monotone in
`λ`, and empirically it need not be.

**Test of one candidate.** Run `π_λ` on the `m` audit expressions. Among the
`n_λ` it answers, let `k_λ` be wrong. Conditional on `n_λ`, the wrong answers
are a binomial sample with parameter `R(λ)` (audit expressions are drawn
independently from `Q`, and the policy is fixed before seeing their labels).
The exact one-sided Clopper–Pearson upper bound

> `U(k, n; α) = the largest r with P(Binomial(n, r) ≤ k) ≥ α`

satisfies `P(R(λ) > U(k_λ, n_λ; α)) ≤ α`. Declare `λ` safe when
`U(k_λ, n_λ; α) ≤ δ`. When `λ` is unsafe (`R(λ) > δ`), declaring it safe
requires `U < R(λ)`, which has probability at most `α`: each test is valid
at level `α`.

**Fixed sequence.** Fix an order of the candidates, test them in that
order, and stop at the first one not declared safe. By Theorem 17.5:

> `P(some accepted candidate is unsafe) ≤ α`,

with no correction for the number of candidates and no monotonicity
assumption. Since the event covers *every* accepted candidate at once, any
accepted candidate may be deployed, and in particular the one answering the
most audit expressions. Checking-sample predictions need only be computed
for this tested prefix: candidates after the first failure cannot enter the
accepted set. Omitting their evaluations leaves both the selected policy and
the validity argument unchanged, provided the order was already fixed without
checking labels. If none is accepted, the system abstains on
everything.

**Choosing the order.** The guarantee requires only that the order not
depend on the data the tests are run on. The natural order, from most to
least cautious, is a poor one. Cautious candidates answer few audit
expressions, so their upper bounds are wide, they fail, and testing stops
before reaching anything useful. The audit is therefore split: one
part runs every candidate and orders them by their Clopper–Pearson bound
there, most certifiable first; the other part runs the tests. Candidates
with `λ < 1` (answering above the bound) are admissible too. The test, not
the bound, decides their safety, and they pay off where the bound is
conservative. The proof is two lines: any acceptance of an unsafe candidate
passes through the *first* unsafe candidate `k*` in the order (a fixed index,
since safety is a property of `Q`, not of the audit). Reaching past `k*`
requires its test to have wrongly declared it safe, an event of probability
at most `α`.

**The guarantee.** With probability at least `1 − α` over the audit, the
deployed policy's error rate among answered inputs on `Q` is at most `δ`.
It holds for any experts, any calibration (good or bad), and any shift
between `P` and `Q`. What it assumes:

- audit and deployment inputs are independent draws from the same `Q`;
- the policy family and the order are fixed before the audit is labeled;
- for a weighted audit, the inclusion probabilities are known.

Calibration quality no longer affects validity. It affects only *efficiency*:
better risks put the safe candidates further down the sequence, so a less
cautious, higher-coverage policy is certified.

**Theorem 17.8 (threshold selection from a shared trace).** Suppose the
next refinement state depends only on the current readings and fixed
calibration, not on the requested target. A run stopped at a strict target
is a prefix of the trajectory obtained by continuing the same transitions.
For a looser target, its first qualifying state lies in that prefix whenever
the strict run answers: the strict stopping state itself qualifies. Appending
more states cannot change that first selection. More generally the same
conclusion holds for any prefix already containing a qualifying state.

An exhausted trajectory supplies the final abstention state for targets
never reached. Reuse requires identical transitions, including tie rules,
calibration and certificate state. Target-dependent floors or predictive
stopping are excluded. Per-policy cost is the cost at its first qualifying
state, not the cost of computing the entire shared trajectory.

## 17.6 How many audit labels

When a candidate answers `n` audit expressions and errs on none, it is
declared safe exactly when `(1 − δ)^n ≤ α`, that is when
`n ≥ ln(1/α) / −ln(1 − δ) ≈ ln(1/α) / δ`:

| `δ` | `α = 0.1` | `α = 0.05` |
|---:|---:|---:|
| 0.2 | 11 | 14 |
| 0.05 | 45 | 59 |
| 0.01 | 230 | 299 |

**Theorem 17.6 (audit budget obstruction).** Let `0 ≤ 1 − δ ≤ 1`
and let at most `N` checking examples be available. If
`α < (1 − δ)^N`, then no number `n ≤ N` of zero-error answers can meet
`(1 − δ)^n ≤ α`: powers of a number in `[0,1]` decrease with the exponent.
Errors only increase the binomial upper bound. Thus an audit whose best
possible zero-error result fails the target cannot certify any candidate,
regardless of its predictions. This precheck uses only the declared sample
budget and target, not checking labels, so it introduces no data-dependent
policy selection.

**Theorem 17.7 (irreversible checking failure).** Suppose an upper-bound
function `U(k,n)` increases with errors `k` and decreases with answered
sample size `n`. After observing `k` errors, any completion has at least
`k` errors and at most the full budget `N` answers. Therefore its bound is
at least `U(k,N)`. If `U(k,N) > δ`, the candidate must fail regardless of
the unseen examples. Evaluation may stop and reject it immediately.
The binomial upper bound has these monotonicities. Acceptance still requires
the complete fixed checking sample; no early-acceptance rule follows.

These are *answered* audit expressions with no errors. With errors the
requirement grows, since `U(k, n; α) ≈ k/n + O(√(k log(1/α))/n)`. Two
consequences follow. Strict targets need audits in the hundreds. And because
only answered expressions count, low-coverage policies need proportionally
larger audits: coverage and certifiability are linked. Recalibration on the
same audit raises coverage, so the two uses reinforce each other. To keep
the guarantee, the audit is split: one part fits temperatures, the other
tests the sequence. Reusing the fitting part for testing would make the
policy depend on the labels it is tested on.

## 17.7 Confidence across an audit family

**Theorem 17.9 (finite audit-family budget).** Let F_j be the event that
condition j certifies a policy whose population answered-error rate exceeds
its requested target. If P(F_j) ≤ α_j and sum_j α_j ≤ A, then
P(union_j F_j) ≤ sum_j P(F_j) ≤ A. No independence between conditions is
required. The individual audits must still satisfy their checking-data and
fixed-sequence assumptions.

For a predeclared family of M depth/draw/target combinations, allocating
α_j=A/M gives one answer-risk confidence budget for the whole report.
Candidate inflation thresholds within one fixed-sequence audit do not add
another factor: Theorem 17.5 already controls that sequence at α_j.
Uncontrolled evaluation policies are not covered. Impossible audits may
remain in the declared count, conservatively leaving some budget unused.

This does not cover arbitrary later runs, adaptive enlargement of the
family, selection among previously inspected checking results, or a joint
prior-regret claim. Such scopes need their own predeclared budget or valid
sequential procedure. Evaluation confidence intervals remain descriptive;
they are not the audit-family guarantee.

[Theory index](../THEORY.md)
