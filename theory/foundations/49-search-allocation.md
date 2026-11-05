# 49. Allocating search across goals

Chapters 44 and 45 treat one goal. This chapter treats a population: how to divide a total budget among goals when
it is unknown which can be solved, and what information or sharing can lower the cost further.

## 49.1 Model

There are `N` goals. Goal `i` needs `t i` work, possibly infinite, and search on a goal can be paused and resumed. A cap
`c` gives each goal up to `c` work, and costs

`W(c) = ∑ min (t i, c)`, solving `K(c) = #{i : t i ≤ c}` goals.

A policy that visits unsolved goals in turn, giving each the same work, passes through every point `(W(c), K(c))`.
This is round robin, and it needs no cap: it stops wherever the budget stops, holding what that budget can buy.

## 49.2 A cap is a stopping point, not a parameter

**Theorem 49.1 (monotone cost).** If `c ≤ d` then `W(c) ≤ W(d)`.

Let `c*` be the largest solved cost. Then `W(c*)` solves all a limit `L ≥ c*` solves, and the limit overspends by
`W(L) - W(c*) = U * (L - c*)` when `U` goals are never solved and no solved cost exceeds `c*`.

**Theorem 49.2 (no allocation beats a uniform cap without information).** An allocation solving every goal of
cost at most `c`, for every possible choice of which goals those are, gives each goal at least `c`, so it spends at
least `N * c`.

Uniform allocation is therefore minimax optimal. Any saving beyond it must come from knowing something about the goals
(49.5) or from sharing work between them (49.6). This is the sense in which further tuning of a cap is pointless.

**Theorem 49.3 (doubling).** Rounds at caps `1, 2, ..., 2 ^ k` cost less than `2 ^ (k + 1)` per goal. With
`c ≤ 2 ^ k < 2 * c`, doubling with restarts costs less than `4 * N * c`, against `N * c` for a resumed search.

Resumption is thus worth a factor of up to four, and neither needs `c` in advance. Round robin of this kind has a known
competitive ratio of two for mean completion time (Motwani, Phillips and Torng, 1994).

## 49.3 When to continue

The solve rate of a cap is `K(c) / W(c)`.

**Theorem 49.4 (marginal value).** For positive `W` and `w`, `K / W ≤ (K + k) / (W + w)` if and only if `K / W ≤ k / w`.

Raising a cap raises the overall rate exactly when the next stretch's rate exceeds the rate so far. This is the
marginal value theorem of foraging (Charnov, 1976), and on continuous costs the optimal cap has hazard equal to the
overall rate. The achievable points are those under the concave envelope of `(W(c), K(c))`, and its slopes are the prices
in work per solve at which each further solve is worth buying.

The rate need not be unimodal. Costs may cluster, with long stretches yielding nothing followed by many solves, so a
rule that stops at the first low rate can lose those. A budget stop has no such failure, and the price is a value
judgement that the budget expresses. Solving a goal may also lower the cost of later goals (44.4), which this count omits.

## 49.4 Dividing work between strategies

Let strategies `A` and `B` have costs `a i` and `b i` on goal `i`, with separate caps. Run in sequence, a goal unsolved by
the first pays its whole cap before the second starts. Run together, a goal pays at most `2 * min (a i, b i)`.

**Theorem 49.5 (parallel strategies).** `2 * min (a, b) ≤ a + b` and `min (a, b) ≤ a`.

So equal shares cost at most the sum and at most twice the best. Equal shares are not required: each strategy has its own
cost curve, and the caps need not agree (49.6). Combining strategies keeps success (44.16).

## 49.5 What a failure predictor is worth

Suppose a test costing `e` is run on each of `N` goals, and it abandons a share `β` of the `U` unsolved goals and a share `α`
of the `S` solvable ones. With cap `c`, it saves `β * U * c`, costs `N * e`, and loses `α * S` solves.

**Theorem 49.6 (predictor saving).** The predictor lowers work if `N * e ≤ β * U * c`.

For `U / N` near two thirds, a test that costs `e` pays if it finds at least a share `1.5 * e / c` of unsolved goals, so at high
caps a weak predictor pays. Abandoned goals must keep a reserve share, or solves lost to the predictor are never observed (44.14, 45.5).

## 49.6 Sharing enumeration across goals

Enumerating hypotheses by size depends on the library and a goal's types, not its labels. Observational pruning
depends only on the inputs the hypotheses are run on. If goals with the same contract use one pool of inputs, one enumeration
gives each hypothesis one output vector, and that vector can be looked up against every goal's labels.

**Theorem 49.7 (shared enumeration).** Let `k` contracts cover `N` goals, each enumerated to `c` at unit cost, with lookup
cost `l` per goal. If `k * c + N * l ≤ N * c` then sharing costs no more than separate search, and the saving tends to
`N / k` as `N` grows with lookups negligible.

**Theorem 49.8 (a shared search dominates).** Each goal's solution at cost at most `c` is found by the shared search at `c`.

The cost grows with the number of contracts rather than goals, so it no longer scales with how many goals fail. Three
assumptions carry this result. Goals must admit the same inputs, so labels are queried or drawn from a pool rather than sampled
per goal. Lookup requires exact equality of outputs, or an index supporting the task's agreement relation. And pruning on
pool inputs may merge hypotheses a goal's own inputs would separate, or the reverse, so measured costs carry over only
approximately. Fresh certification is unaffected, since it evaluates a candidate on its own cases (20.22).

## 49.7 Labels

Theorem 44.17 ties checks to reach: with `h` hypotheses examined and each wrong one passing a case with probability `q`,
about `log h / log (1 / q)` cases leave no expected false pass. Cases can then be requested as hypotheses survive, rather than
fixed in advance.

**Theorem 49.9 (labels grow with the logarithm of reach).** If `h ≤ (1 / q) ^ s` for `0 < q ≤ 1`, then `h * q ^ s ≤ 1`.

A lower cap thus reduces labels as well as work, and a goal abandoned early spends few. This count is for search only, as the
gate draws its own cases.

## 49.8 Consequences to test

1. Round robin passes every point a fixed cap reaches, at no higher cost (49.1), if search can resume.
2. Most cheap solves arrive at a tiny fraction of the work, when costs are heavy-tailed.
3. A saving past uniform allocation requires information or sharing (49.2).
4. Sharing makes the cost of failed goals nearly vanish for goals that have a pooled contract (49.7).
5. Goals only a guided strategy solves keep costing per goal, since guided search uses labels and is not shared.
