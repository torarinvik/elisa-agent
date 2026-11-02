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
