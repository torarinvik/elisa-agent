# 44. What failed search establishes

A bounded search can fail because no route exists, because a route lies beyond the budget, or because
the search order never turns towards it. These causes call for different remedies. This chapter
separates them and states what budget, reuse, decomposition and sharing can each buy.

## 44.1 Reach

Let `H` be the hypothesis space and `ok` consistency with a goal. Let `reach b ⊆ H` be the hypotheses a
search examines at budget `b`, assumed to grow with `b`. The search succeeds at `b` when
`reach b` contains a consistent hypothesis.

**Theorem 44.1 (monotone success).** Success at `a ≤ b` implies success at `b`.

Monotonicity is an assumption about `reach`. A scheduler that changes order with budget need not satisfy
it, and memoization limits or per-round caps must be checked against it.

## 44.2 Three kinds of failure

A goal failing at `b` is exactly one of:

- **inexpressible:** no hypothesis in `H` is consistent;
- **unreached:** a consistent hypothesis exists, and some larger budget examines it;
- **unguided:** a consistent hypothesis exists, and no budget examines it, because `⋃ b, reach b ≠ H`.

**Theorem 44.2 (inexpressibility).** If no hypothesis is consistent, the search fails at every budget.

**Theorem 44.3 (exhaustive failure).** If `reach b` contains every hypothesis of size at most `n` and the
search fails at `b`, then every consistent hypothesis has size greater than `n`.

**Theorem 44.4 (silence).** If the search fails at `b` and `h ∉ reach b`, the search also fails at `b`
for the goal that additionally accepts `h`.

Together, 44.3 and 44.4 say that only an exhaustive stage is evidence about the space. A failure that
stops on a budget is consistent with a solution in any unexamined place. Consistency here concerns
the examples; a consistent hypothesis may still be wrong elsewhere, which the fresh-case gate of Chapter
36 addresses.

## 44.3 What budget buys

Take the model in which examining all hypotheses of size `n` costs `m ^ n`, where `m` is the effective
branching factor.

**Theorem 44.5 (budget buys logarithmically).** For `m > 0`, `m ^ (n + d) ≤ k * m ^ n` if and only if
`m ^ d ≤ k`.

A factor `k` thus buys `⌊log_m k⌋` further sizes, regardless of `n`. In particular, when `m > k`, it buys
none. A null result from raising a budget by `k` is therefore weak evidence against an unreached
solution unless `m` has been measured: it excludes only solutions within `log_m k` sizes of the frontier.

**Theorem 44.6 (deepening overhead).** For `m ≥ 2`, `∑_{i ≤ n} m ^ i ≤ 2 * m ^ n`.

Restarting at each size costs at most a factor of two in this model, so deepening is not where budget goes.

## 44.4 What reuse buys

Add one entry to a library, and suppose a route of size `n` becomes one of size `n'`.

**Theorem 44.7 (unused entries cost).** For `n ≠ 0`, `m ^ n < (m + 1) ^ n`.

**Theorem 44.8 (reuse pays).** For `m ≥ 2` and `2 * n' < n`, `(m + 1) ^ n' < m ^ n`.

Reuse shifts the exponent, where budget acts only on the logarithm. It also taxes every goal that does
not use the entry, so an unselective library slows search. 44.8 is a sufficient condition that is
coarse for large `m`; the exact comparison is `(m + 1) ^ n'` against `m ^ n`.

## 44.5 What decomposition buys

**Theorem 44.9 (subgoals add).** For `m ≥ 2` and nonzero `a`, `b`, `m ^ a + m ^ b ≤ m ^ (a + b)`.

Let a witness offer `w` alternative binary decompositions per level, and let `L` be the leaf cost.

**Theorem 44.10 (guided cost).** Over `d` levels, `T(0) = L` and `T(d + 1) = w * (2 * T(d))` give
`T(d) = (2 * w) ^ d * L`.

Guided search therefore pays in decomposition depth and witness ambiguity, not in route size. Halving a
size `n` route `d` times gives leaves of size about `n / 2 ^ d`. These bounds hold only when the alternatives
contain a correct split and subgoals are independent. A witness search lacking an alternative is unguided
in the sense of 44.2, whatever its budget, so it must be combined with a complete strategy.

## 44.6 What sharing buys

**Theorem 44.11 (share suffices).** A strategy with share `p / q` of `T` steps receives `t` steps whenever
`t * q ≤ p * T`.

So a strategy needing `t` steps alone succeeds within about `t * q / p` total steps, the classical
dovetailing bound.

**Theorem 44.12 (sharing redistributes).** With monotone reach, what a strategy finds with a share of `T`
it also finds with all of `T`.

Sharing bounds regret across strategies. It adds no capability beyond the union of strategies at the
full budget, and helps only if some strategy is starved by another.

## 44.7 Consequences for diagnosis

The remedy follows from the kind of failure:

| Failure | Budget | Reuse | Decomposition | Sharing | Remedy |
|---|---|---|---|---|---|
| Inexpressible | none | none | none | none | new primitives |
| Unreached, small gap | yes, if `log_m k` covers it | yes | yes | if starved | any |
| Unreached, large gap | negligible | yes | yes | little | reuse or decomposition |
| Unguided | none | if the entry enters reach | if a witness exists | if a complete strategy is starved | new witness or complete strategy |

For a goal with a known reference solution, a diagnosis needs only measurable quantities: whether the
reference translates to a route over the library, its size `n` and witness depth, the measured `m`, and
the frontier size. Without a reference, only exhaustive stages give evidence (44.3).

The results use a uniform cost model and independent subgoals. Observational pruning, types and memoization
lower the effective `m`, which must be measured, and correlated subgoals can weaken 44.9 and 44.10 in
practice. The theorems state consequences of the model, not measurements of a particular search.
