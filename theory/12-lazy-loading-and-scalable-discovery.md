# 12. Lazy loading and scalable discovery

Planning reads only contracts (manifests), so manifests stay resident while
implementations load on first use into a memory-budgeted store with
least-recently-used eviction.

**Working set.** `Plan.contracts p` lists the contracts a plan invokes.

| Theorem | Statement |
|---|---|
| 12.1 | a well-typed plan invokes only installed contracts |
| 12.2 | installing modules leaves the working set of every routed task unchanged |
| 12.3 | a successful plan witnesses `Derivable` at the same depth |
| 12.4 | installing modules never makes a solvable goal unsolvable |
| 12.5 | success with the first `k` modules implies success with the first `k' ≥ k` |
| 12.6 | planning through an index of producers by output type computes exactly `plan` |

**Binary-search layered planning.** By
Theorem 12.5, success is monotone in the prefix length, so the smallest
successful prefix (the route `planStable` returns) is found with
`O(log |lib|)` planner calls instead of `|lib| + 1`.

**Memoized search.** For a fixed library prefix the planner is a pure function
of `(available, goal, fuel)`; memoizing it within one call returns exactly what
recomputation would and bounds the work by the number of distinct subgoals
rather than search paths.

**Reachability pruning.** Dormant producers of a
relevant type, whose inputs nothing can supply, are dead ends the planner would
otherwise explore. `planPruned` skips producers with an input rejected by a
reachability oracle `reach`. An oracle is *sound* if it accepts every derivable
type.

| Theorem | Statement |
|---|---|
| 12.7 | with a sound oracle, pruned planning returns exactly `plan` |
| 12.8 | every derivable type is a sequence type or in the forward closure `Closure lib avail` |
| 12.9 | any oracle accepting the closure (and all sequence types) is sound |

`Closure lib avail` is the least set containing `avail` and closed under
contracts whose non-sequence inputs it contains. It is computed by Horn-clause
propagation: each contract keeps a count of
unsatisfied inputs, and each newly reachable type decrements the counts of its
consumers. The work is proportional to the contracts consuming reachable
types, independent of dormant modules elsewhere in the library.

**Eviction.** The store holds a set `S` of experts
within a byte budget; serving a route with working set `R` moves it to some
`S' ⊇ R` at cost `bytes(S' \ S)`.

| Theorem | Statement |
|---|---|
| 12.10 | every transition serving `R` loads at least `bytes(R \ S)` |
| 12.11 | keeping `R ∪ K` with `K ⊆ S` loads exactly `bytes(R \ S)`, the minimum |
| 12.12 | alternating routes `A`, `B` costs `bytes(B \ A)` per switch: shared experts are never reloaded |
| 12.13 | serving a resident route loads nothing |
| 12.14 | if `bytes(R)` exceeds the budget, no resident set within budget can serve `R` |

By Theorem 12.13, a task sequence costs only at route changes, so the
remaining lever is the number of changes: independent tasks grouped by route
switch once per route. Least-recently-used eviction is not optimal in general:
when one route runs a shared expert first and the next route runs its own
expert first, recency marks the shared expert as the victim, and it is
reloaded at once.

[Theory index](../THEORY.md)
