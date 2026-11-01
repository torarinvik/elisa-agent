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

**Persistent search.** Installation appends to the library, and every result
for a prefix of length `k` depends only on the first `k` contracts.

| Theorem | Statement |
|---|---|
| 12.18 | for `k ≤ |lib|`, planning with the first `k` contracts of `lib ++ more` equals planning with the first `k` of `lib` |

So plans, closures and candidate sets computed for a prefix stay valid when
contracts are installed, and can be kept across planning calls instead of
being rebuilt. Only removing a contract shifts later positions and
invalidates them. Replacing an implementation under the same contract leaves
every type-level result valid and changes only the plans that name it.

**Reachability pruning.** Dormant producers of a
relevant type, whose inputs nothing can supply, are dead ends the planner would
otherwise explore. `planPruned` skips producers with an input rejected by a
reachability oracle `reach`. It also skips each `map` candidate element `a`
whose body goal `e` the oracle rejects from `[a]`, or whose source `seq a` it
rejects from the available types. Without this, a sequence goal tries every
element type produced anywhere in the library, and a failing one costs time
quadratic in the library. An oracle is *sound* if it accepts every derivable
type.

| Theorem | Statement |
|---|---|
| 12.7 | with a sound oracle, pruned planning returns exactly `plan` |
| 12.8 | every derivable type is a sequence type or in the forward closure `Closure lib avail` |
| 12.9 | any oracle accepting the closure (and all sequence types) is sound |

The closure treats every sequence type as reachable, so it cannot reject the
source `seq a` of a `map` candidate. A sharper oracle for sources follows
from how a sequence is made. Let `E` be the elements `a` of the sequence types
that are available or are the output of a contract whose non-sequence inputs
are all in `Closure lib avail`.

| Theorem | Statement |
|---|---|
| 12.17 | if `seq e` is derivable from `avail`, then `e` is a sequence type or in the closure of `E` |

A derivation of `seq e` ends in an available type, a contract, or a `map`
from some `seq a`. In the first two cases `e ∈ E`. In the third, `e` is in the
closure of `[a]`, and by induction `a` is in the closure of `E`, which contains
the closure of `[a]`. So `map` candidates whose element lies outside the closure
of `E` can be skipped, by the argument of Theorem 12.7.

**Closure through eliminators.** A polymorphic contract whose output is a
bare variable `v`, such as an eliminator (§20.7), has an instance for every
type, so counting all its instances as reachable would make the closure total
and prune nothing. Its instances that are actually derivable are fewer. Match
its non-sequence input patterns against the closure to obtain bindings `β`;
any derivable instance of the contract arises from one of them, because its
inputs are derivable and hence in the closure (Theorem 12.8). Then:

- if `v` is itself an input, the output is a derivable input, already in the
  closure;
- if `β` binds `v`, the output is `β(v)`;
- if `v` occurs only as the output of slots whose inputs `β` makes ground,
  the output is produced by a slot filling from those inputs, so it lies in
  their closure (Theorem 12.8 again, applied to the filling);
- otherwise, the output is unconstrained and the closure stays total.

| Theorem | Statement |
|---|---|
| 12.19 | the least set containing `avail`, closed under contracts as in `Closure` and under these contributions, contains every derivable type except sequence types |

So such a contract is a candidate for a goal only if the goal is a sequence
type or in this closure. The argument combines Theorem 12.8 with the matching
of §2.1; the closure is computed as a fixed point, since contributed types can
make more contracts fire. A slot whose inputs already lie in the set being
closed contributes nothing beyond it, because the least closed set containing
those inputs is contained in every closed set that contains them.

Theorem 12.17 carries over. Let `E` now be the elements of the sequence types
in the closure of Theorem 12.19, where a contract whose output is a
constructor application contributes its output even when it is a sequence
type, and the other rules contribute as stated.

| Theorem | Statement |
|---|---|
| 12.20 | if `seq e` is derivable from `avail`, then `e` is a sequence type or in the closure of `E` |

The cases of a derivation of `seq e` are as before, with three more. An
eliminator whose output is one of its inputs passes on an input that is
itself derivable, so induction applies to it. One whose output variable is
bound contributes `seq e` to the closure, so `e ∈ E`. One whose output is a
slot's makes `seq e` in a slot filling, whose own `E` lies inside this one,
since the closure of the slot's inputs is part of this closure. So a sequence
goal `seq e`, with `e` neither a sequence type nor in the closure of `E`, has
no plan and can be rejected before any candidate is tried, which removes
eliminators, candidates for every sequence goal, from such searches.

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
| 12.12 | switching from a state containing exactly `A` to route `B` costs at most `bytes(B \ A)`; shared experts are never reloaded |
| 12.13 | serving a resident route loads nothing |
| 12.14 | if `bytes(R)` exceeds the budget, no resident set within budget can serve `R` |
| 12.15 | for a demanded subset `D ⊆ R`, `bytes(D \\ S) ≤ bytes(R \\ S)` |
| 12.16 | if `P ⊆ R`, `e ∈ R`, and `bytes(R) ≤ budget`, then `bytes(P ∪ {e}) ≤ budget` |

By Theorem 12.13, repeating a resident route incurs no loading cost. Grouping
independent tasks by route reduces route changes, although the resulting byte
cost also depends on expert sizes and what remains resident. Least-recently-used eviction is not optimal in general:
when one route runs a shared expert first and the next route runs its own
expert first, recency marks the shared expert as the victim, and it is
reloaded at once.

The working set `R` above is the set required to be resident, not necessarily
the set actually invoked. Demand-driven execution can skip part of a route;
if its invoked experts form `D ⊆ R`, Theorem 12.15 bounds the missing bytes
for `D` by those for `R`. Eager preparation of `R` can therefore load experts
that execution never invokes. Dynamic requests can invoke experts outside the
original route, so their working set must be considered separately.
For deferred preparation, Theorem 12.16 ensures that the already-resident
route pins and any next route expert fit together. This assumes fixed sizes,
unchanged route pins, and that non-route residents can be evicted; a loader
can still fail for reasons unrelated to the declared memory budget.

[Theory index](../THEORY.md)
