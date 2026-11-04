# 33. Per-input risk on any route

## 33.1 Two accounts, one charge

Section 16 answers an input only when a bound on its error probability is
at most `δ`, computed from the readings of that input; selective
refinement (§22, §25) builds that bound for one route shape, a producer
mapped over a sequence and read by one consumer. Section 31 bounds any
route's error by charging each invocation a rate, averaged over inputs.
Both are the same charge, read at different times: before execution with
rates, or during execution with each invocation's own risk.

An expert *reports* its risk if, from its output on an input, it gives a
number `r` with `P(fail | everything observed) ≤ r`, where *fail* is a
failure in the sense of §31.1. A calibrated reader's `1 − max p` is such a
number when its probabilities are calibrated (§16); an exact expert, an
adapter or a requirement reports `0`.

## 33.2 Answering within δ

During execution, the *ledger* of an input sums the reported risks of the
invocations whose output the answer reads (§31.6), including those inside
packages, which run their own routes on the same ledger.

**Theorem 33.1 (per-input charge).** Under sound demands, if every relevant
invocation reports its risk, the probability that the answer is wrong,
given everything observed on the input, is at most the ledger's total.

*Proof.* Conditionally on the observations, a wrong answer has a relevant
failure (§31.6); the union bound over the relevant invocations gives at
most the sum of their failure probabilities, each at most its report. ∎

**Theorem 33.2 (selective answering on any route).** Answering exactly the
inputs whose ledger total is at most `δ` gives an error rate among the
answered inputs of at most `δ`.

*Proof.* Theorem 16.1 with the ledger total as the bound. ∎

An invocation that reports no risk leaves the input uncertified: a rate
averaged over inputs does not bound a conditional probability on this
input, so it cannot be mixed into the per-input sum. Such inputs are not
answered under a target.

The static bound of §31 remains the planner's estimate. The expected
ledger total over inputs is at least the expected number of relevant
failures, and when reports are exactly calibrated it equals the static
charge computed from the same experts' in-situ rates.

## 33.3 Refinement on any route

When an input's ledger total exceeds `δ`, abstaining is not the only
option. An *escalating* expert holds a ladder of substitutes (§16), cheap to
dear, and answers each distinct input at that input's current level. The
ledger records, for each charged invocation, the expert, its inputs and
its report. *Refinement* repeats: execute; if the total is at most `δ`,
answer; otherwise raise the level of the invocation with the largest
report among those whose expert can still climb, and execute again; if
none can, abstain.

**Theorem 33.3 (termination).** Refinement executes the route at most
`1 + Σ (hₑ − 1) · nₑ` times, where `hₑ` is the height of escalating expert
`e`'s ladder and `nₑ` the number of distinct inputs it is invoked on.

*Proof.* Every execution but the last raises one level of one pair
(expert, input), and levels only rise and are bounded by the ladder
heights. ∎

**Theorem 33.4 (selective refinement on any route).** If every report is
calibrated given everything observed, including the readings that led to
the climbs, the error rate among inputs refinement answers is at most `δ`.

*Proof.* An answer is given only when the final ledger total is at most
`δ`; apply Theorem 33.2 to the final execution. ∎

The premise is stronger than calibration of each rung on its own: the
choice to climb depends on the cheaper readings, so the dearer rung's
report must remain calibrated on the inputs that reach it, which is the
in-situ condition of §31 at the level of single inputs. Climbing the
largest report is the rule of §25 on any route, and as there it need
not minimize compute.

## 33.4 Preserving internal accounting through lazy boundaries

An expert that accounts for its own internal invocations must retain that
declaration when represented lazily. With a live ledger, its cached payload
alone cannot replace replay of those invocations unless their charge is
separately reconstructed. Let a cache gate be C=o∧¬(l∧a), where l denotes a
live ledger, a internal accounting, and o ordinary cache eligibility.

**Theorem 33.5 (inside-account replay).** If l=a=true then C=false regardless
of o. Conditional on faithful replay contributing the inner charge r and
suppressing a duplicate outer report, the call contributes exactly r even
when a cached payload exists. Erasing a can instead contribute zero on a
cache hit whose outer report is zero, understating every r>0.

*Proof.* Substitute l=a=true in the cache gate and replay rule. For an erased
declaration and cached payload, the ordinary branch uses the outer zero report;
strict understatement follows from r>0. ∎

The declaration must be bound to the stored model and checked against its
implementation before use. This is a cooperative protocol, not isolation:
a dishonest implementation can omit internal reports. The theorem does not
prove faithful execution, calibration, effect attribution or transaction
atomicity. Cached values may still be reused without a ledger; enabling a
ledger must bypass that value-only reuse for internally accounted experts.

## 33.5 Valid reports and conservative accumulation

Reports must be finite nonnegative real bounds. Missing reports are a separate
uncertified state; negative and non-real reports cannot cancel other charges.
For nonnegative reports r₁,…,rₙ and initial charge c₀≥0, use an operation A
with A(a,b)≥a+b for nonnegative operands, defining cᵢ₊₁=A(cᵢ,rᵢ₊₁).

**Theorem 33.6 (conservative ledger fold).** The resulting charge satisfies
cₙ≥c₀+Σrᵢ. Thus numeric accumulation cannot turn a report sum above a given
budget into an accumulated charge below that budget.

*Proof.* Each step bounds the preceding charge plus the next report. Induction
and nonnegativity preserve that bound through the fold. ∎

Floating-point implementations must earn the operation hypothesis. With strict
binary64 round-to-nearest arithmetic, gradual underflow and no reassociation,
FastTwoSum's residual detects downward rounding of a nonnegative finite sum.
Moving that result to its next representable value upward gives an upper sum;
already exact or upward-rounded sums need no padding. Overflow gives an infinite
upper bound. Converting supported input scalars must also round upward when
necessary. This argument assumes the IEEE operations and faithful lowering;
it is not a proof of a compiled kernel or report calibration.
