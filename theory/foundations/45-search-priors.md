# 45. Priors over a growing library

Chapter 44 shows that an unselective library defeats its own reuse. This chapter treats selection as a
prior: search gives each hypothesis or strategy a share of effort, and the question is which
shares minimize cost over a population of goals, and what happens when the population is misjudged.

## 45.1 Cost of a prior

Let `p` be a subprobability on hypotheses, with search examining them in decreasing weight or dovetailing them
in proportion to weight.

**Theorem 45.1 (heavy hypotheses).** At most `1 / c` hypotheses have weight at least `c`.

So at most `1 / p(h)` hypotheses precede `h` in weight order, ties included. Cost depends on the
hypothesis's weight and not on library size, and retrieval, types and code lengths are ways of setting that
weight. This assumes unit cost per hypothesis; uneven evaluation costs need the shares of 44.11.

## 45.2 The best prior is not the frequency

Goals needing strategy `i` occur with frequency `f i = a i ^ 2`, and a strategy with share `p i` costs
`1 / p i`, so expected cost is `∑ f i / p i`.

**Theorem 45.2 (lower bound).** For positive `p` summing to one, `(∑ a i) ^ 2 ≤ ∑ a i ^ 2 / p i`.

**Theorem 45.3 (attainment).** For positive `a`, the prior `p i = a i / ∑ a j` attains this bound.

The optimal prior is proportional to `√f`, not `f`. Rare needs receive more effort than their frequency,
because cost is inverse in share. Proportional shares give cost `n` over `n` strategies; optimal shares
give `(∑ √f) ^ 2`, which equals `n` only for uniform `f` and approaches `1` as `f` concentrates. Learning a
prior by raw counts is therefore suboptimal in this model, whereas a square-root transform is a single
change. The model applies to dovetailed strategies with fixed unit costs and a single strategy per goal.

## 45.3 Misjudging the population

**Theorem 45.4 (mismatch).** If `g i ≤ ρ * f i` for all `i`, a prior has expected cost under `g` at most
`ρ` times its cost under `f`.

The ratio is unbounded where `f` is zero, so a learned prior alone offers no guarantee for new kinds
of goals, the case that matters most for generality.

**Theorem 45.5 (mixture bounds any goal).** For `0 < λ ≤ 1`, `p ≥ 0` and `u > 0`,
`1 / ((1 - λ) * p + λ * u) ≤ 1 / (λ * u)`.

**Theorem 45.6 (mixture keeps the prior).** For `0 ≤ λ < 1`, `p > 0` and `u ≥ 0`, the same mixture costs at
most `1 / (1 - λ)` times `1 / p`.

Reserving `λ` for a reference prior such as uniform-over-size caps the cost of any goal, known or new,
while costing known goals only a constant factor; `λ = 1 / 2` gives factor two against both. A system
that learns from experience should therefore never drive this reserve to zero.

## 45.4 Curricula

**Theorem 45.7 (stages add).** For `c ≥ 2` and `k ≥ 2`, `k * c ≤ c ^ k`.

If a size `k * s` route splits into `k` stages each solvable at cost `c` given earlier stages' results as library
entries, learning in order costs `k * c`, whereas joint search costs on the order of `c ^ k`. This requires
that each stage is separately checkable: it has its own examples, or a goal that identifies its result.
Intermediate goals are thus an input the system must obtain, whether from a curriculum, from
decomposition (44.5) or from requests. Absent such signals, the additive bound does not apply. Combined with
44.14, `c` includes the tax of earlier stages' entries, so the guarantee still depends on selection.

## 45.5 Predictions

1. Replacing frequency shares by square-root shares lowers expected cost on a skewed goal population,
   by the ratio of `n` to `(∑ √f) ^ 2`, and has no effect on a uniform one.
2. Removing the reference reserve speeds known goals by at most `1 / (1 - λ)` and loses goals of new kinds.
3. Providing intermediate goals turns goals beyond the frontier into ones solved at the sum of stage costs,
   while providing the same subroutines unranked gains less, by 44.14.

## 45.6 Ranked candidates at one gate

A gate that receives one candidate turns a selection mistake into a refusal, even when another fitted
candidate would pass. Let training data alone fix an ordered list of `c` candidates, before any fresh case.
Test them in order on new cases, each at level `α / c`, and admit the first that passes.

**Theorem 45.8 (ranked acquisition).** If, conditional on each training outcome with `c` candidates, every
one of its `c` tests wrongly admits with probability at most `α / c`, then a wrong admission has probability at
most `α`.

The count `c` may depend on training data, because it is fixed before any test case is drawn. A learner
with no training support therefore costs later candidates nothing. Each test needs a frozen candidate and cases
independent of the history before it. Requests and stages compose by Theorems 20.14 and 20.18.

The split has a price. A sole candidate keeps level `α`; with `c` candidates each faces `α / c`, which needs
more cases at zero error, or permits fewer errors at a fixed size. Wrong early candidates also consume labels up
to their first decisive failures. Ranking need not be correct for soundness, only for cost: a mistake delays a
true candidate and tightens its test. Selection scores remain proposals and are not evidence of correctness.
Unequal shares are possible by the same union bound, and how to set them is the question of 45.2.
