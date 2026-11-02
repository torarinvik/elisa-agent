# 26. Composing cascades

## 26.1 The failure

The planner's expected-cost objective is wrong for nested fallbacks. The
objective of §20.4 multiplies the second filling's *average* cost by
`P(unsure)`, which assumes that cost does not depend on whether the filling is
called. An inner cascade defers on the same hard glyphs as the outer one, so
on the glyphs where it is called it is far dearer than on average. This
section derives the exact quantities, states when the old formula errs and in
which direction, and says what a planner must know to compose cascades
exactly.

All statements are over a finite weighted sample space (`p ω ≥ 0`). That
covers both the data distribution and an audit's empirical distribution, which
is what the planner actually uses.

## 26.2 Exact cost of a fallback

Let `U` be the inputs on which the first slot is unsure, `κ₁` its cost, and
`c ω` the second slot's cost on input `ω`. The second slot may itself be a
cascade, so `c` varies with the input.

| Theorem | Statement |
|---|---|
| 26.1 | `E[cost] = κ₁ + Σ_{ω ∈ U} p ω · c ω` |
| 26.2 | for `P(U) > 0`, this is `κ₁ + P(U) · E[c \| U]` |
| 26.3 | `Σ_U p c − P(U) · E[c] = Cov(1_U, c)` |
| 26.4 | if `Cov(1_U, c) ≥ 0`, the exact cost is at least the independent formula |

So the independent formula `κ₁ + P(U) · E[c]` is exact precisely when the
deferral indicator is uncorrelated with the second slot's cost. It
underestimates exactly when the second slot is dearer on the deferred
inputs than on average. That is the normal case for nested cascades: an
inner fallback is unsure, and so calls its own expensive slot, mostly on the
inputs the outer one passes it.

**When nesting is cheaper.** Compare `Fallback(a, b)` with
`Fallback(a, Fallback(a', b))`. The second pays `κ_{a'}` on `U` and then
`κ_b` only on `U ∩ U'`, where `U'` is where `a'` is unsure. Nesting saves
`κ_b · P(U \ U') − κ_{a'} · P(U)`. It is cheaper exactly when
`P(U' | U) < 1 − κ_{a'} / κ_b`, that is, when the inner recognizer is
confident on a large enough share of what the outer one defers. Re-checking
with the same recognizer (`a' = a` at a lower threshold) gives
`P(U' | U)` close to 1 for hard glyphs, so such a re-check loses.

## 26.3 Error and cost of a chain

A chain of recognizers `0, …, k − 1` answers each input at one level:
`lev ω`, the first level that is confident, or the last level.

| Theorem | Statement |
|---|---|
| 26.5 | error `= Σᵢ P(lev = i ∩ Wᵢ)`, with `Wᵢ` level `i`'s errors |
| 26.6 | cost `= Σᵢ κᵢ · P(lev ≥ i)`: level `i` is paid wherever it is reached |
| 26.7 | splitting the level answering on `R` into a cascade that keeps `C ⊆ R` and passes `R \ C` on changes the error by `P((R \ C) ∩ W') − P((R \ C) ∩ W)` |

Theorem 26.5 generalizes Theorem 14.4 to any depth.
Theorem 26.7 says when depth helps: a new level lowers error exactly
when it errs less than the old level *on the inputs passed to it*, and it
adds cost `κ_new · P(R \ C)`. Both quantities are conditional on the
deferral set, not marginal.

## 26.4 What the planner needs

**Worst-case cost stays compositional.** With worst-case call bounds `ν`,
cost depends on a filling only through a number fixed in advance.
Theorem 20.4 applies, and the Bellman recursion of §20.5 is exact.

**Expected cost is not compositional under correlated deferral.** A
filling's contribution is `E[c | U]`, which depends on the context `U` it is
called in, not only on the filling. The cheapest filling of a slot is then
the one minimizing cost *on the inputs reaching it*. A filling that is
cheapest on average can lose in a context that concentrates hard inputs.
So the sub-goal "a recognizer for glyphs" no longer has a single cheapest
plan. Its cheapest plan depends on the input distribution conditioned on
deferral.

**Exact planning.** The planner evaluates each candidate chain on the audit
restricted to the inputs that reach it. Equivalently, the planning state gains
the conditioning context. The statistics needed per candidate are:

- `P(U)` for each level, on the audit's inputs reaching it;
- cost on the deferred inputs, `Σ_U p c`;
- errors on the answered inputs per level, `P(lev = i ∩ Wᵢ)`.

All three come from one pass of the chain over the audit. Context-dependence
multiplies the number of evaluations by the number of distinct deferral
contexts, which grows with depth. In practice that is one audit pass per
candidate chain, bounded by the planner's depth limit.

## 26.5 Choosing among many cascades on one audit

The planner picks the candidate with the best audit estimate. With `K`
candidates:

| Theorem | Statement |
|---|---|
| 26.8 | if every candidate's estimate is within `ε` of its true value, the chosen one is within `2ε` of the best |
| 26.9 | the probability that some estimate deviates is at most the sum over candidates |

The per-candidate deviation probability comes from a standard concentration
inequality for a binomial error rate, which is not formalized here. For an
error rate near `e` on `n` audit inputs, a Bernstein-type bound gives
deviation `ε ≈ √(2 e ln(2K/β) / n)` with probability at least `1 − β` for
all `K` candidates together.

Resolving a gain `Δ` therefore needs `n ≈ 8 e ln(2K/β) / Δ²` audit inputs.
Comparing two candidates on the same inputs (paired) replaces `e` by their
disagreement rate, typically a few times smaller.

[Theory index](../THEORY.md)
