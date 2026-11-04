# 31. Composing uncertainty

## 31.1 Risk is an expected count

Section 4 bounds a composition's error by the sum of its invocations'
failure probabilities. Routes, however, invoke experts a varying number of
times: a map runs its body once per element, a higher-order expert calls a
slot as often as it needs, and a package hides a route of its own. This
section makes the bound compositional by counting.

Fix a finite weighted sample space (`p ω ≥ 0`), as in §26: the data
distribution or an audit's empirical distribution. On input `ω` the route
invokes expert `e` `I_e(ω)` times, of which `F_e(ω)` fail. The
**propagation hypothesis** of §4 reads: if no invocation fails, the answer
is correct. Say that an invocation *fails* when its inputs are correct and
its output is not. Then the hypothesis holds for every route whose experts
compute functions of their inputs: by induction over the route, if no
invocation fails, every value it computes is correct. Let `F = Σ_e F_e`.

**Theorem 31.1 (risk is an expected count).** Under the propagation
hypothesis, `P(wrong) ≤ E[F]`.

*Proof.* A wrong answer has `F ≥ 1`, so `1_wrong ≤ F` pointwise; take
expectations. ∎

The expectation splits by expert. Define the *in-situ rate* of `e` as
`ε_e = E[F_e] / E[I_e]`, the fraction of its invocations, on this route and
this distribution, that fail (and `0` if it is never invoked).

**Theorem 31.2 (risk decomposes).** `E[F] = Σ_e E[I_e] · ε_e`. If `I_e ≤ ν_e`
on every input, then `E[F] ≤ Σ_e ν_e · ε_e`.

No independence is assumed. What is assumed is that the rate `ε_e` is the
in-situ one: measured on the inputs `e` receives inside this route, as §4
already requires.

## 31.2 Composition

Theorem 31.2 has the form of a cost: each invocation of `e` is charged
`ε_e`, and a route's risk is the total charge. It therefore composes
exactly as cost does (§20.4): a map charges its body once per element, a
slot is charged its filling's risk times the number of calls, and a
package's export is charged its route's risk, with its requirements charged
through the slots that fill them (§28.3). With worst-case call bounds and
an upper bound on every sequence's length, the total is an upper bound on
`E[F]`; with call counts affine in the length (§28.3), expected lengths give
`E[F]` itself for the counted invocations.

**Theorem 31.3 (risk is monotone).** Lowering the rate of any expert, or
replacing any argument or filling by one of lower risk, never raises a
route's risk.

*Proof.* The total charge is a sum of nonnegative terms, each monotone in
the rates and counts it involves, as for cost (Theorem 20.4). ∎

So the planning machinery that minimizes cost minimizes risk, or any
nonnegative combination of risk and cost, unchanged.

## 31.3 Rates from evidence

Rates are not known; evaluations (§30.1) give upper confidence bounds.
If the rate bound of each of `m` experts holds with probability at least
`1 − βₑ`, then all hold together with probability at least `1 − Σₑ βₑ`
(the union bound of Theorem 30.1), and on that event Theorems 31.1–31.2
bound the route's error by the total charge computed from the bounds.

Two cautions. The evaluations must be in situ: a reader's rate on a clean
benchmark is not its rate on the glyphs a segmenter hands it. And the
bound is only as tight as the propagation hypothesis is loose: an expert
whose input is wrong may still answer correctly, and every such case is
counted as a failure here. Demand (§14) and certificates (§18) tighten the
bound by not counting invocations that cannot change the answer.

## 31.4 Planning by risk

The error objective of the Pareto planner (§13) is the total charge of
§31.2, so its exactness theorems apply to risk unchanged: every option it
returns is a well-typed plan with its reported cost and charge, every
searchable plan is dominated by one of them, and the cheapest plan whose
charge is at most a target `δ` is found exactly. By Theorems 31.1–31.2,
with in-situ rate bounds that hold together, that plan's error probability
is at most `δ`.

A rate must be known to be charged. Treating an expert without evidence
as exact would make every bound through it meaningless, so such an expert
is left out, and the frontier is exact over the experts with rates. An
export's rate per invocation is the charge of its own route, its
requirements excluded since the slots that fill them are charged where
the export is applied.

## 31.5 Spending the confidence budget

A route's bound combines `m` rate bounds, each holding with probability at
least `1 − βₑ`. Any allocation with `Σₑ βₑ ≤ β` that is fixed before the
audits are seen makes all of them hold together with probability at least
`1 − β` (Theorem 30.1's union bound); one chosen after looking at the
outcomes need not.

**Theorem 31.4 (allocation).** For every allocation fixed in advance with
`Σₑ βₑ ≤ β`, with probability at least `1 − β` the route's error is at most
`Σₑ νₑ · uₑ(βₑ)`, where `uₑ(βₑ)` is the upper confidence bound on `εₑ` at
level `βₑ` and `νₑ` bounds its invocations.

The route's structure is known before the audits, so the allocation may
depend on it. An expert invoked `νₑ` times enters the bound `νₑ` times, so
an even split spends as much confidence on an expert invoked once as on
one invoked once per element. Splitting in proportion to `νₑ` gives the
frequently invoked experts the larger share; it is a rule of thumb, not an
optimum.

An expert whose exactness is established otherwise, by a proof or by
construction, and attested by a trusted issuer, is charged rate `0` and
needs no share: its premise is the attestation, as purity's is (§32.3),
not an audit.

## 31.6 Charging only relevant invocations

The propagation hypothesis of §31.1 counts every failed invocation, also
those whose output nothing downstream decides on. Demand (§14) says what a
consumer reads of each input, and a decision demand what of it can change
the consumer's decision. Call an invocation *relevant* if the demand on its
output, propagated from the answer, is not empty, and let `Rₑ ≤ Iₑ` count
the relevant invocations of `e`.

If the declared demands are sound (Theorems 14.10–14.13), a value that
agrees with the correct one under its demand gives the correct answer, and
the empty demand is met by every value. So a run whose relevant
invocations do not fail answers correctly: the propagation hypothesis holds
with relevant failures in place of all failures.

**Theorem 31.5 (relevant failures).** Under sound demands,
`P(wrong) ≤ Σₑ E[Rₑ] · εₑ`, where `εₑ` is the in-situ rate among relevant
invocations, and the bound with per-input limits on `Rₑ` follows as in
Theorem 31.2.

*Proof.* Theorems 31.1 and 31.2 hold for any counts satisfying the
propagation hypothesis; apply them to `Rₑ`. ∎

Demand on a sequence is per element, so a map's body is charged at each
element's own demand: an expression parser that reads digits only at even
positions charges a digit reader for half the glyphs and an operator reader
for the other half, where §31.2 charged both for every glyph. The bound is
as sound as the declared demands, which are claims of the experts' authors.

## 31.7 Majority over redundant routes

A route's risk adds over its experts (Theorem 31.1), so it grows linearly with
depth. Suitable joint-failure bounds can make redundancy reduce that risk.
Let `k` routes to the same goal share no
expert, let `Fᵢ` be the event that route `i` fails, and let
`t = ⌈k/2⌉`. The *vote* answers the value produced by more than half of
the routes and abstains otherwise.

**Theorem 31.6 (majority).**

1. If fewer than `t` routes fail, the correct value has more than half the
   votes, so the vote answers it.
2. If every set `S` of `t` routes fails jointly with probability at most
   `∏_{i∈S} pᵢ` (independent failures), then the vote is wrong or abstains
   with probability at most `e_t(p) = Σ_{|S|=t} ∏_{i∈S} pᵢ`.

*Proof.* (1) At least `k − t + 1 > k/2` routes are correct and agree. (2) If
`t` or more fail, some `t`-subset fails jointly; take the union bound over
the `t`-subsets. ∎

For equal risks `p`, `e_t(p) = C(k, t) pᵗ`, which falls exponentially in `k`
whenever `p < 1/4`, while a single route's risk grows with depth. Independence
is an assumption about joint failures on the distribution of use; disjoint
experts or separate training data alone do not establish it. Abstention is safe (§17): a vote
without a majority answers nothing rather than something wrong.

## 31.8 Majority with dependent failures

Let `p_i` be upper bounds on the marginal failure probabilities, with no
independence assumption. For any omitted set `O` of `r < t` route indices,
write `S` for the remaining routes.

**Theorem 31.7 (dependence-safe vote risk).** The probability of a wrong or
abstaining vote is at most
`min(1, (Σ_{i∈S} p_i)/(t−r))`. Taking the minimum over all such omitted sets
preserves the bound. For each fixed `r`, omitting the `r` largest marginal
bounds minimizes this expression.

*Proof.* A failing vote requires at least `t` route failures; removing `r`
indices leaves at least `t−r`. The remaining failure count has expectation
at most `Σ_{i∈S} p_i`, without independence. Markov's inequality gives the
quotient. Probabilities are also at most one; every member of the finite
family is a valid bound, hence so is its minimum. With a fixed denominator,
removing the largest summands minimizes the remaining sum. ∎

For equal marginal risks `p`, the bound is `min(1,kp/t)`. This does not
promise reliability amplification: if all routes fail on the same event of
probability `p`, their vote also fails with probability `p`, however many
routes are added. Observed frequencies qualify as marginal bounds only for
the distribution they exactly describe, or with an additional statistical
coverage guarantee. Neither separate implementations nor independent fitting
datasets establishes independent errors for fixed fitted routes.

## 31.9 Acquire toward a jointly certified error target

Declare increasing route counts `k₁ < … < k_R` and an error target `ε`.
Acquire routes up to each declared count, freeze the resulting vote, then
test it on fresh labeled cases. Disagreement and abstention both count as
failure. Stop at the first vote passing every case; if none passes or
resources are unavailable, return no certified vote. Routes may share experts
and have dependent failures: the test measures the whole vote's error.

**Theorem 31.8 (jointly certified ensemble search).** On search `j`, give
each declared size level `α_j/R`, where `α_j = δ/((j+1)(j+2))`, and test at
least `m` cases with `ε m ≥ log(R/α_j)`. Under the fresh conditional IID
sampling hypothesis and fixed candidate/scoring semantics, the probability
of ever returning a vote whose error exceeds `ε` is at most `δ`.

*Proof.* Conditional on the history before a test, its entire vote is fixed.
If its error is `ℓ > ε`, the probability of zero errors in `m` fresh cases
is `(1−ℓ)^m ≤ exp(−εm) ≤ α_j/R`. A union bound over tested sizes gives
`α_j`; summing over searches gives `δ`, as in Theorem 20.18. This argument
uses no independence among routes. Durable non-reused spending indices may
skip levels without weakening the bound (Theorem 20.17). ∎

This guarantees admission quality, not that any vote will be admitted.
Correlated failure can persist at every size, and even a vote below the target
may fail a finite zero-error test. At most `k_R` route requests and `R`
candidate tests are made. Label and execution cost depend on the target,
spending level and stopping stage. The acquisition procedure may learn from
past observations, but certification cases must remain fresh for each new
candidate. A refusal is not a proof that no better ensemble can be acquired.
