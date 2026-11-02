# 8. Explicit route upgrades

A router holds **pins**, per-goal routes that override layered planning:
`route pins lib avail n t = pins t`, or `planStable lib avail n t` when `t` is
unpinned. `upgrade pins t p` pins `p` for `t` if `infer lib avail p = some t`
and fails otherwise.

| Theorem | Statement |
|---|---|
| 8.1 | if all pins are well-typed, every route is well-typed |
| 8.2 | upgrading preserves well-typedness of all pins |
| 8.3 | after upgrading `t` to `p`, `t` is routed through `p` |
| 8.4 | every goal `t' ≠ t` keeps its route |
| 8.5 | restoring the previous pin of `t` restores the router exactly |
| 8.6 | installing modules never changes an existing route, pinned or not |
| 8.7 | pins remain well-typed after installing modules |

The theorems make upgrades safe to *apply*; whether to apply one is an
empirical question. **Decision rule**: evaluate the
current and candidate routes on the same validation samples. Let `w` be the
samples only the candidate answers correctly and `l` those only the current
route answers correctly. Under the null hypothesis that neither route is
better, `w ~ Binomial(w + l, 1/2)` conditional on `w + l`; the candidate is
pinned iff `P(X ≥ w) < α` (default `α = 0.05`). The test is exact and uses
only discordant samples, so shared successes and failures carry no weight.

[Theory index](../THEORY.md)
