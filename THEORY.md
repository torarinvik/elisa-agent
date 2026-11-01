# Theory

Mathematical foundations of module composition. Every theorem stated here is
machine-checked in `lean/` (build with `cd lean && lake exe cache get && lake build`),
and every algorithm has a Python mirror in `src/nca/` that is tested against
the Lean model's behavior.

## 1. Types and contracts

Semantic types `Ty` are abstract, with decidable equality and a sequence
former: `seq : Ty → Ty`, recognized by a partial inverse `elem?` with
`elem? u = some t ↔ u = seq t` (`NCA.SeqTypes`). In Python, type ids are
strings and `seq[t]` is the sequence type (`nca.abi.seq_type`).

A **contract** is a list of input types and one output type. Modules are known
to the system only through their contracts; two values are compatible exactly
when their types are equal.

A **plan** is a composition graph:

| Plan | Meaning |
|---|---|
| `given t` | a task input of type `t` |
| `apply c ps` | contract `c` applied to the outputs of sub-plans `ps` |
| `map a body src` | `body` run on each element (of type `a`) of the sequence `src` produces; inside `body` the element is the only input |

**Well-typedness** `WellTyped lib avail p t` (`lean/NCA/Contract.lean`): `p` uses
only installed contracts `lib` and available inputs `avail`, and produces `t`.

| Rule | Premises | Conclusion |
|---|---|---|
| given | `t ∈ avail` | `given t : t` |
| apply | `c ∈ lib`, `ps : c.inputs` pointwise | `apply c ps : c.output` |
| map | `body : e` under inputs `[a]`, `src : seq a` | `map a body src : seq e` |

**Theorem (monotonicity, `WellTyped.mono`).** If `lib ⊆ lib'`, every plan
well-typed under `lib` is well-typed under `lib'`. Installing modules never
invalidates an existing valid composition.

## 2. Planning

`plan lib avail n t` (`lean/NCA/Planner.lean`, `nca.planner.plan`) searches
backward from the goal with depth bound `n`:

1. If `t ∈ avail`, return `given t`.
2. Otherwise try contracts in installation order; the first `c` with
   `c.output = t` whose inputs are all plannable at depth `n - 1` wins.
3. Otherwise, if `t = seq e`, try each candidate element type `a` (elements of
   sequence types that are available or produced by some contract, in that
   order); succeed when `e` is plannable from `[a]` and `seq a` from `avail`.

**Derivability** `Derivable lib avail n t` is the specification: a composition
of depth at most `n` exists (for `map`, with `a` a candidate element type).

**Theorem (soundness, `plan_sound`).** `plan lib avail n t = some p` implies
`WellTyped lib avail p t`.

**Theorem (completeness, `plan_complete`).** `Derivable lib avail n t` implies
`plan lib avail n t` succeeds.

**Type checking** (`lean/NCA/Check.lean`, `nca.router.infer`). `infer lib avail p`
computes the type a plan produces: `given t` needs `t ∈ avail`; `apply c ps`
needs `c ∈ lib` and the argument types to equal `c.inputs`; `map a body src`
needs `body` to type-check under `[a]` and `src` to produce `seq a`.

**Theorem (decidability, `infer_iff`).** `infer lib avail p = some t ↔
WellTyped lib avail p t`. Plans not produced by the planner, such as
hand-written pipelines and proposed upgrades, are admitted by checking.

## 3. Routing stability

The add-and-freeze protocol requires that installing a module does not
change how already solved tasks are solved.

**Theorem (instability, `plan_not_stable`).** The plain planner is not stable.
With `need1 : [x] → g`, `from2 : [y] → g`, input `y`, the planner routes `g`
through `from2`; installing `make1 : [y] → x` makes the higher-priority
`need1` applicable and the route changes, although the old route remains valid.

**Generation-layered planning** `planStable` (`lean/NCA/Routing.lean`,
`nca.planner.plan_stable`): plan with the first `k` installed contracts, for
the smallest `k = 0, 1, …, |lib|` that succeeds.

**Theorem (`planStable_sound`, `planStable_complete`).** Layered planning is
sound and complete in the same sense as `plan`.

**Theorem (stability, `planStable_append`).** If `planStable lib avail n t`
succeeds, then `planStable (lib ++ extra) avail n t = planStable lib avail n t`
for every `extra`.

Cost: at most `|lib| + 1` planner runs per goal; results can be cached per
installation generation.

## 4. Compositional reliability

Let an execution consist of finitely many invocations `i`, invocation `i`
failing on an event `fail i` with `μ(fail i) ≤ εᵢ`, and suppose the
**propagation hypothesis**: if no invocation fails, the result is correct
(`⋂ᵢ (fail i)ᶜ ⊆ correct`). Exact modules (parsers, arithmetic) have
`εᵢ = 0`. (`lean/NCA/Reliability.lean`.)

**Theorem (union bound, `composition_error_le_sum`).** For any measure,
`μ(correctᶜ) ≤ Σᵢ εᵢ`.

**Theorem (independent product bound, `composition_success_ge_prod`).** If μ
is a probability measure and the failure events are independent,
`μ(correct) ≥ Πᵢ (1 − εᵢ)`.

Use as falsifiable predictions:

- The union bound holds for every measure, including the empirical
  measure of a test set. Measured accuracy below `1 − Σ (in-situ failure rates)`
  therefore refutes the propagation hypothesis: some failure is not
  attributed to any module.
- Accuracy below the product bound indicates positively correlated failures.
- Failure rates must be measured **in situ**, on the inputs a module
  actually receives inside the composition. Rates measured on the module's
  own training distribution are not the `εᵢ` of the theorem when the
  upstream modules shift that distribution.

## 5. Reliability under distribution shift

A deterministic module with input space `X` fails on a set `B ⊆ X`. Its
failure rate depends on the input distribution: offline it is `ν₀(B)` for the
distribution it was evaluated on; inside a composition it is `(g_*μ)(B)`,
where `g : Ω → X` is the upstream computation feeding it.
(`lean/NCA/Shift.lean`.)

**Definition (`ShiftBound ν ν₀ δ`).** `ν(s) ≤ ν₀(s) + δ` for every measurable
`s`. For probability measures this is equivalent to total variation distance
at most `δ`.

**Theorem (shifted composition bound, `composition_error_le_shifted`).** If
invocation `i` receives `gᵢ(ω)`, fails on `Bᵢ`, has offline failure rate at
most `εᵢ`, and `ShiftBound (gᵢ)_*μ ν₀ᵢ δᵢ`, then under the propagation
hypothesis `μ(correctᶜ) ≤ Σᵢ (εᵢ + δᵢ)`.

**Theorem (`offline_rate_insufficient`).** There are probability measures and
a failure set with offline failure rate 0 and in-situ failure rate 1. Offline
rates alone bound nothing; the shift term cannot be dropped.

**Theorem (`shift_ge_gap`).** Every valid shift bound satisfies
`δ ≥ ν(B) − ν₀(B)`. The measured excess of in-situ over offline failure rate is
therefore a lower bound on the distribution shift the composition induces,
and is reported per recognizer by `nca.pipeline`.

Design consequence: an upstream module's output convention is part of the
downstream module's contract. A segmenter that centers crops differently from
the recognizer's training data is type-correct but induces a shift `δ` that
the composition pays for in full.

## 6. Algorithms of the handwritten-arithmetic pipeline

**Segmentation** (`nca.modules.segmenter`). Ink columns (intensity > 0.1) are
grouped into runs; runs separated by fewer than 4 blank columns merge (the
gap was chosen on the `validation` split, where 4 minimizes segmentation
failures for 2, 8 and 32 operands; results in sections before §15 were
measured with a gap of 2, which split broken strokes more often). Each
run is cropped and translated so that its center of ink mass is at the center
of a 28×28 canvas, the MNIST normalization convention.

**Symbol fusion** (`nca.modules.symbols.SymbolFuser`). With operator
distribution `q` over `{+, −, ×, none}` and digit distribution `p`:
`P(op) = q_op`, `P(d) = q_none · p_d`. The result is a probability
distribution over the 13 symbols whenever `p` and `q` are.

Fusion, parsing and the recognizers are parameterized by an operator
vocabulary: arithmetic (`+ − ×`, value type `int.v1`) and comparison
(`< > =`, value type `bool.v1`) use separate module ids and semantic types,
so installing one family cannot satisfy or alter the other's contracts.

**MAP parsing** (`ExpressionParser`). The grammar `digit (op digit)*` fixes the
class of each position. Under independent per-position distributions the
probability of a token string factorizes, so the most probable well-formed
expression is the per-position argmax restricted to the position's class.
Even-length sequences have no parse.

**Evaluation** (`Evaluator`). `×` binds tighter than `+` and `−`; terms are
accumulated left to right.

**Comparison chains** (`ComparisonEvaluator`). `a₀ r₁ a₁ … rₖ aₖ` is true iff
every adjacent relation `aᵢ₋₁ rᵢ aᵢ` holds.

## 7. Measuring accumulation

The add-and-freeze runner (`nca.accumulation`) checks the stability theorem
on real modules. For each task in a fixed suite, before and after installing
new modules, it records coverage (whether `planStable` finds a route),
whether the route is unchanged, accuracy, and the number of individual
answers that changed. Weight fingerprints (SHA-256 of each learned module's
parameters) verify that installation modified no existing module.

For deterministic modules, an unchanged route implies identical answers, so
`planStable_append` predicts **zero changed answers** on every previously
covered task. The changed-answer count is the stricter regression metric:
equal accuracy can hide offsetting changes; zero changed answers cannot.

The `conflict` scenario reproduces `plan_not_stable` with learned modules. A
symbol classifier consuming `glyph.embedding.v1` is installed before the symbol
fuser but is dormant: no module produces its input type. Installing a glyph
encoder activates it. `plan` then routes every glyph through the classifier,
because it precedes the fuser in installation order, and previously correct
answers change; `planStable` keeps the original route.

Stability is a guarantee about *unrequested* change. It also means a newly
installed module never improves an already covered task on its own: adopting
a better route must be an explicit, evaluated decision (for example,
reordering or replacing modules after comparing both routes on the suite),
not a side effect of installation.

## 8. Explicit route upgrades

A router holds **pins**, per-goal routes that override layered planning:
`route pins lib avail n t = pins t`, or `planStable lib avail n t` when `t` is
unpinned. `upgrade pins t p` pins `p` for `t` if `infer lib avail p = some t`
and fails otherwise. (`lean/NCA/Upgrade.lean`, `nca.router.Router`.)

| Theorem | Statement |
|---|---|
| `route_sound` | if all pins are well-typed, every route is well-typed |
| `upgrade_valid` | upgrading preserves well-typedness of all pins |
| `upgrade_target` | after upgrading `t` to `p`, `t` is routed through `p` |
| `upgrade_local` | every goal `t' ≠ t` keeps its route |
| `upgrade_rollback` | restoring the previous pin of `t` restores the router exactly |
| `route_append` | installing modules never changes an existing route, pinned or not |
| `PinsValid.append` | pins remain well-typed after installing modules |

The theorems make upgrades safe to *apply*; whether to apply one is an
empirical question. **Decision rule** (`nca.router.sign_test`): evaluate the
current and candidate routes on the same validation samples. Let `w` be the
samples only the candidate answers correctly and `l` those only the current
route answers correctly. Under the null hypothesis that neither route is
better, `w ~ Binomial(w + l, 1/2)` conditional on `w + l`; the candidate is
pinned iff `P(X ≥ w) < α` (default `α = 0.05`). The test is exact and uses
only discordant samples, so shared successes and failures carry no weight.

`nca.accumulation --scenario conflict` applies this rule to the route `plan`
proposes after the encoder is installed: it rejects a weaker symbol
classifier and accepts a stronger one, and only the arithmetic route changes.
Validation samples are drawn with a different seed from the reported test
samples.

## 9. Module substitution

Plans refer to modules only through contracts, so replacing a module by one
with an identical contract (`Registry.replace` enforces this) leaves every
plan's shape and type unchanged; `infer` confirms the substituted route still
type-checks. Behavior is what changes. (`lean/NCA/Substitution.lean`.)

Let `disagree i` be the event that invocation `i` of the substitute gives a
different decision than the original's, with in-situ probability at most `dᵢ`,
and suppose the answer can change only if some such invocation disagrees.

**Theorem (`substitution_change_le`).** `P(answer changes) ≤ Σᵢ dᵢ`.

**Theorem (`accuracy_transfer`).** If original-correct and unchanged imply
substitute-correct, then `P(correct) ≤ P(correct′) + P(answer changes)`.

**Theorem (`substitution_accuracy_ge`).** Hence
`P(correct′) ≥ P(correct) − Σᵢ dᵢ`.

The bound is only as tight as the choice of events. Every invocation of the
substitute is a valid event set, but `ExpressionParser` reads digit
distributions only at even positions and only through their argmax, so the
answer changes only if an even-position invocation's argmax disagrees.
Restricting `disagree` to those invocations keeps the hypothesis true and
removes the substitute's (irrelevant) disagreements on operator glyphs.
Choosing the smallest event set that still covers every way the output can
change is how a composition's structure tightens its guarantees.

`nca.substitution` swaps independently trained digit recognizers (different
architectures, disjoint halves of the training data) into the frozen system
and reports route shape, type check, accuracy, changed-answer rate, `Σ d`, and
accuracy drop relative to the reference.

## 10. Complementarity

The mixed task `a op b rel c` requires arithmetic and comparison together.
Systems are compared by the composition gain
`G = Q(A⊕B) − max(Q(A), Q(B), Q(A+B), Q(baselines))` on held-out inputs, where
`A⊕B` adds integration modules to the installed capabilities and the
baselines are the majority class and a monolithic model trained on the task.
(`nca.complementarity`.)

**Product-of-experts fusion** (`MixedSymbolFuser`). With operator distribution
`q`, relation distribution `r` (each including a "none of mine" outcome) and
digit distribution `p`: `P(op) ∝ q_op r_none`, `P(rel) ∝ r_rel q_none`,
`P(d) ∝ q_none r_none p_d`. This treats the two recognizers as independent
evidence; unlike the two-recognizer fuser it is an assumption, not an
identity.

**Constrained MAP parsing** (`RelationalParser`). Grammar
`digit ((op | rel) digit)*` with at least one relation. Under independent
per-position distributions the unconstrained MAP takes each position's best
symbol of its class. If it contains no relation, the constrained MAP differs
from it in exactly one odd position, switched to its best relation; choosing
the position maximizing `P(rel) / P(op)` minimizes the loss in probability,
so the result is the exact constrained MAP.

**Same goal type, different task.** Comparison and mixed both produce
`bool.v1` from the same image type, so after installing the integration
modules stable routing keeps the comparison route for `bool.v1` (it was
installed first). The integration route subsumes it: comparison chains are
relational expressions without operators. It is adopted through the upgrade
rule of §8, on a validation suite drawn from both boolean tasks. This shows
a limit of the type system: the task a goal stands for is not determined by
its type alone, and choosing between routes for one type is an empirical
decision.

## 11. Evaluation methodology

**Data separation** (`nca.expressions`). Training splits draw digit images
from the MNIST training set. The MNIST test set is divided: its first half
supplies the `validation` split, used for every decision taken from data
(such as accepting route upgrades); its second half supplies `test` and
`test_unseen`, used only for reporting. No digit image is shared between
what decisions are made on and what is reported. `test_unseen` additionally
holds out digit pairs never seen in training.

**Deliberate shift.** The `hard` style renders operators with three times the
usual geometric jitter and thickens or thins digit strokes (3×3 max or min
filter). Evaluating on it measures robustness to a shift that no module was
trained on; by §5 the accuracy loss is bounded by the induced shifts of the
affected modules.

**Accuracy intervals** (`nca.stats.wilson`). For `k` successes in `n` samples
the 95% Wilson score interval is
`(p̂ + z²/2n ± z·√(p̂(1−p̂)/n + z²/4n²)) / (1 + z²/n)` with `z ≈ 1.96`. It stays
inside `[0, 1]` and remains accurate near 0 and 1, where accuracies cluster.

**Paired differences** (`nca.stats.paired_difference`). Systems are compared
on the same samples, so their difference is estimated from per-sample
differences `dᵢ = 1[second correct] − 1[first correct]`: mean `d̄`, interval
`d̄ ± z·s_d/√n`. Shared successes and failures contribute zero, which makes the
interval far narrower than one derived from two independent accuracy
intervals. Composition gain is reported this way against the best competing
system on that split.

## 12. Lazy loading and scalable discovery

Planning reads only contracts (manifests), so manifests stay resident while
implementations load on first use into a memory-budgeted store with
least-recently-used eviction (`nca.loader`). (`lean/NCA/Loading.lean`.)

**Working set.** `Plan.contracts p` lists the contracts a plan invokes.

| Theorem | Statement |
|---|---|
| `WellTyped.contracts_subset` | a well-typed plan invokes only installed contracts |
| `route_contracts_append` | installing modules leaves the working set of every routed task unchanged |
| `plan_derivable` | a successful plan witnesses `Derivable` at the same depth |
| `Derivable.mono`, `plan_mono` | installing modules never makes a solvable goal unsolvable |
| `plan_prefix_mono` | success with the first `k` modules implies success with the first `k' ≥ k` |
| `planIdx_eq` | planning through an index of producers by output type computes exactly `plan` |

**Binary-search layered planning** (`nca.planner.plan_stable_indexed`). By
`plan_prefix_mono`, success is monotone in the prefix length, so the smallest
successful prefix (the route `planStable` returns) is found with
`O(log |lib|)` planner calls instead of `|lib| + 1`.

**Memoized search.** For a fixed library prefix the planner is a pure function
of `(available, goal, fuel)`; memoizing it within one call returns exactly what
recomputation would and bounds the work by the number of distinct subgoals
rather than search paths.

**Reachability pruning** (`lean/NCA/Pruning.lean`). Dormant producers of a
relevant type, whose inputs nothing can supply, are dead ends the planner would
otherwise explore. `planPruned` skips producers with an input rejected by a
reachability oracle `reach`. An oracle is *sound* if it accepts every derivable
type.

| Theorem | Statement |
|---|---|
| `planPruned_eq` | with a sound oracle, pruned planning returns exactly `plan` |
| `derivable_closure` | every derivable type is a sequence type or in the forward closure `Closure lib avail` |
| `closure_oracle_sound` | any oracle accepting the closure (and all sequence types) is sound |

`Closure lib avail` is the least set containing `avail` and closed under
contracts whose non-sequence inputs it contains. It is computed by Horn-clause
propagation (`ProducerIndex.reachable`): each contract keeps a count of
unsatisfied inputs, and each newly reachable type decrements the counts of its
consumers. The work is proportional to the contracts consuming reachable
types, independent of dormant modules elsewhere in the library.

**Measured cost structure** (`nca.scaling`). Among up to 100,000 unusable decoy
experts, the loaded set always equals the route's working set and every answer
is unchanged, as the theorems require. Without pruning, planning time grew with
the number of dormant producers of relevant types (1.6 s at 100,000 experts);
with pruning it is 6.8 ms. The remaining growth is one constant-time check per
dormant producer of the goal type, removable by indexing producers by
reachability.

**Eviction** (`lean/NCA/Eviction.lean`). The store holds a set `S` of experts
within a byte budget; serving a route with working set `R` moves it to some
`S' ⊇ R` at cost `bytes(S' \ S)`.

| Theorem | Statement |
|---|---|
| `load_lower_bound` | every transition serving `R` loads at least `bytes(R \ S)` |
| `routeAware_load`, `routeAware_optimal` | keeping `R ∪ K` with `K ⊆ S` loads exactly `bytes(R \ S)`, the minimum |
| `routeAware_switch` | alternating routes `A`, `B` costs `bytes(B \ A)` per switch: shared experts are never reloaded |
| `routeAware_repeat` | serving a resident route loads nothing |

`ExpertStore.prepare(route)` implements the route-aware transition: the kernel
calls it before executing a route; it evicts only experts outside the route
(least recently used first), loads the missing ones, and pins the route's
experts until the next `prepare`. Least-recently-used eviction is not optimal:
when one route runs a shared expert first and the next route runs its own
expert first, recency marks the shared expert as the victim, and it is
reloaded at once (in `tests/test_loader.py`, 16 loads against the optimal 11).

By `routeAware_repeat`, a task sequence costs only at route changes, so the
remaining lever is the number of changes: independent tasks grouped by route
switch once per route. Measured (`nca.scaling`, 200 arithmetic and 200
comparison tasks, budget equal to the larger route, so both routes do not fit
together):

| order | eviction | loads | MB loaded |
|---|---|---:|---:|
| alternating | least recently used | 1602 | 677.8 |
| alternating | route-aware | 1602 | 677.8 |
| grouped by route | route-aware | 10 | 5.1 |

Here least-recently-used eviction already meets the lower bound (each route
runs its shared experts first, so they stay recent): 400 switches times the
1.69 MB the routes do not share. The cost of alternation is unavoidable for
any eviction policy; only reordering removes it. Accuracy is unchanged
(0.985) in every configuration.

## 13. Efficiency

**Goal.** Cost proportional to a task's dependency structure, not to the size
of the library or to all pairs of inputs. For local, compositional tasks that
means linear in input length and constant in library size; quadratic cost
should appear only in modules whose contracts require all-pairs interaction,
and only there.

**Cost model** (`lean/NCA/Cost.lean`). Each contract costs `κ(c)` per
invocation (declared in `Manifest.cost`, counted in `Workspace.spent`). On
sequences of length `L`:
`cost(given t) = 0`, `cost(apply c ps) = κ(c) + Σ cost(pᵢ)`,
`cost(map a body src) = L · cost(body) + cost(src)`.
Cost is additive by definition: a composition has no interaction term between
its modules.

| Theorem | Statement |
|---|---|
| `Plan.cost_le_pow` | `cost_L(p) ≤ (L + 1)^nest(p) · cost_1(p)`: polynomial degree is the map nesting depth |
| `Plan.cost_linear` | plans without nested maps cost at most `(L + 1) · cost_1(p)`: linear in length |
| `route_cost_append` | installing modules never changes the cost of an existing route |

Together with `route_contracts_append` (§12), a task's cost and memory are
independent of library size.

**Minimum-cost planning** (`lean/NCA/MinCost.lean`, `nca.optimize.plan_min`).
`planMin` keeps, at every type and depth, the cheapest candidate: a Bellman
recursion over the AND/OR structure of plans (a type needs *one* producer; a
producer needs *all* its inputs). *Searchable* plans are the well-typed plans
whose map elements are candidate element types, the space the planner
enumerates.

| Theorem | Statement |
|---|---|
| `planMin_sound` | the returned plan is well-typed and its cost is the reported cost |
| `planMin_optimal` | it costs at most any searchable plan of smaller depth |

With memoization the recursion visits each `(available, type, depth)` once.
Minimizing total compute is polynomial; minimizing the number of *distinct*
experts (memory) is a set-cover problem and is handled as a constraint, not an
objective.

**Cost under an error target** (`nca.optimize.plan_pareto`). By the union bound
(§4) a route's error is at most the sum of its invocations' failure rates, so
error composes exactly like cost, with map bodies counted `L` times. The
planner keeps the Pareto frontier of non-dominated (cost, error) pairs at each
type; combining sub-goal frontiers and discarding dominated results yields the
exact frontier for two additive objectives, from which the cheapest route
within an error target is read off. Since error composes like cost, a plan's
error bound is `p.cost ε L` for per-invocation failure rates `ε`, and the
recursion is `planMin` with `best` replaced by dominance pruning
(`lean/NCA/Pareto.lean`):

| Theorem | Statement |
|---|---|
| `front_cover` | pruning dominated options loses nothing: every option is dominated by a survivor |
| `planPareto_sound` | every option is a well-typed plan with its reported cost and error bound |
| `planPareto_cover` | every searchable plan within the depth bound is dominated by a returned option |
| `planPareto_within` | if a searchable plan meets error target `τ`, a returned option meets it at no greater cost |

Both planners are also tested against exhaustive enumeration of all
searchable plans.

**Length–accuracy coupling.** Every route's cost and error bound grow linearly
in `L`, so the cheapest expert meeting a fixed target changes with length, and
beyond some length no route meets it. The planner reports infeasibility
rather than silently degrading. Keeping error constant as inputs grow
requires per-glyph failure rates falling as `1/L`, or redundancy and
refinement (sub-goal requests) spent where uncertainty is high.

**Comparison with attention.** A transformer over `T` tokens of width `d` with
`ℓ` layers costs about `ℓ(24Td² + 4T²d)` floating-point operations; the
quadratic term dominates once `T > 6d`. At glyph granularity and the lengths
measured here the linear term dominates and costs are comparable; at
image-patch granularity the quadratic term dominates and cost grows
superlinearly. The modular pipeline's cost is proved linear at every length.

## 14. Kernel-mediated requests and refinement

Modules never invoke one another. A module may return a `Request` instead of
its output, delegating that output to the kernel: "produce a value of this type
from these inputs, without me". The kernel plans the request over the
installed modules minus every module in the current request chain, executes it
under the same budget, records it in the workspace, and uses its result as the
requester's output (`nca.runtime`, `nca.kernel`). (`lean/NCA/Request.lean`.)

| Theorem | Statement |
|---|---|
| `resolve_sound` | a resolved request is a well-typed plan producing the requested type from the request's inputs |
| `resolve_avoids` | it never invokes a module in the request chain |
| `RequestChain.length_le` | every chain of nested requests is at most as long as the number of installed modules, whatever the budget |

Termination follows from freshness: each new requester is a module of a plan
resolved with the chain excluded, so the chain has no repeats and is bounded
by the library.

**Confidence-triggered refinement** (`lean/NCA/Cascade.lean`,
`nca.modules.refinement`). A cheap module answers when confident (event `C`)
and otherwise requests refinement, served by a fallback. With `W₁`, `W₂` the
cheap and fallback error events, the composite errs exactly on
`(C ∩ W₁) ∪ (Cᶜ ∩ W₂)`.

| Theorem | Statement |
|---|---|
| `cascade_error_eq` | `P(error) = P(C ∩ W₁) + P(Cᶜ ∩ W₂)` |
| `cascade_le_fallback` | if `P(C ∩ W₁) ≤ P(C ∩ W₂)` (confidence is selective), the composite is at least as accurate as the fallback alone |
| `cascade_expected_cost` | expected cost is `κ₁ + κ₂ · P(Cᶜ)` |

The fallback can itself be a refining module, so the two-stage results compose
into chains of any depth. Refinement spends expensive computation only on the
fraction of inputs where the cheap module is unsure: cost tracks the input's
difficulty, not its size alone.

**Relevance gating.** A request is worth resolving only if its result can
change the answer. Let `R` be the event that the requester's output influences
the final answer: off `R`, the answer is wrong after refinement exactly when it
is wrong without it (`E_r ∩ Rᶜ = E_u ∩ Rᶜ`). A gate `G` predicts relevance, and
gated refinement resolves requests only on `Cᶜ ∩ G`.

| Theorem | Statement |
|---|---|
| `gated_error_le` | `P(error, gated) ≤ P(error, ungated) + P(Cᶜ ∩ Gᶜ ∩ R)`: gating costs at most the relevant requests it skips |
| `gated_error_eq_of_sound` | if the gate is sound (`R ⊆ G`), gated and ungated refinement err exactly equally |
| `gated_expected_cost` | gated refinement costs `κ₁ + κ₂ · P(Cᶜ ∩ G)` |

Requests are therefore resolved lazily (`nca.runtime`): a pending request is
decided when its value is consumed. The *consumer* declares relevance, since
only the reader knows what it reads: a module may define
`relevant(index, provisional)`, judging from the provisional values of all its
inputs whether input `index` can affect its result. An irrelevant pending
request is settled with the requester's provisional answer and recorded as
skipped; requests consumed without a declaration, mapped, or returned are
always resolved. `SymbolFuser` declares the digit reading irrelevant on glyphs
the operator recognizer judges to be operators. That gate is not sound (a digit
misjudged as an operator is skipped), so its cost is the extra term of
`gated_error_le`, measured by the answers that differ between gated and
ungated refinement (`nca.cascade`).

**Demand-driven evaluation (a sound gate).** Soundness is easy to obtain when
the gate comes from what a consumer provably reads rather than from what a
value looks like. A *readable* type pairs values `V` with demands `D` and, for
each demand, an agreement relation `v ≈_d v'` ("`v` and `v'` look the same to a
reader with demand `d`"). A module `f : V → W` with demand map `δ : D_W → D_V`
is *demand-sound* when `v ≈_{δ d} v'` implies `f v ≈_d f v'`: whatever the
module's input differs in outside `δ d` cannot be seen in its output under `d`
(`lean/NCA/Demand.lean`).

| Theorem | Statement |
|---|---|
| `DemandSound.comp` | demand-sound modules compose: `g ∘ f` is sound with `δ_f ∘ δ_g` |
| `DemandSound.pair` | modules on a pair are sound when each component's demand is |
| `DemandSound.map` | `map f` is sound on lists with per-element demand `(i, n) ↦ δ (d i n)` |
| `DemandSound.exact` | at a top demand under which agreement is equality, agreeing inputs give equal answers |

So inputs whose demand is empty can be replaced by anything, in particular
never computed, and the answer is unchanged. In `nca.runtime` a consumer may
declare `demand(index, demand)`; arguments and `map` elements with empty demand
are not evaluated, so neither their modules nor the requests raised there run.
This makes skipping those requests a sound gate: by `gated_error_eq_of_sound`,
gated and ungated refinement err exactly equally. `ExpressionParser` reads
digit entries at even positions, operator entries at odd ones, and nothing of
an even-length sequence; `SymbolFuser` reads its digit input only when digit
entries are demanded. Hence the digit recognizer never runs on operator
positions. With the cheap/expensive pair at `τ = 0.9` (300 test expressions):

| glyphs | ungated cost | heuristic gate cost, changed | demand gate cost, changed |
|---:|---:|---:|---:|
| 3 | 31.4 | 27.4, 0 | 27.0, 0 |
| 15 | 150.1 | 126.7, 1 | 123.6, 0 |
| 63 | 519.4 | 434.8, 13 | 425.4, 0 |

Cost is MFLOPs per expression; error is identical to ungated refinement
(0.030, 0.147, 0.503) and the expensive recognizer (0.033, 0.143, 0.500). The
demand gate is both exact and cheaper than the heuristic one, because it skips
the cheap recognizer as well as the request on operator positions.

**Continuation requests.** Delegation replaces the requester's output; an
expert that needs a sub-result and then keeps computing is instead a program
over questions (`lean/NCA/Continuation.lean`):
`Prog := pure a | ask q (k : A q → Prog)`, composed by `bind`. The kernel is a
handler `h q : Option (A q)` (no route is `none`); `run h p` returns the result
and the number of requests made. Each question `q` has a specification
`R q a`, and `Safe R post p` holds when `p` meets `post` whatever correct
answers it receives.

| Theorem | Statement |
|---|---|
| `Safe.run` | a handler returning only correct answers gives results meeting `post` |
| `Safe.bind` | a sequence is safe when the first program establishes what the continuation needs |
| `Depth.run_le` | a program of question depth `n` makes at most `n` requests on any run |
| `Depth.bind` | depths add under `bind` |

In `nca.runtime` a module's `invoke` may return a generator: each yielded
`Request` (of any type) is resolved at once, with the requester added to the
chain, so `resolve_avoids` and `RequestChain.length_le` still apply, and the
resolved value is sent back into the generator until it returns its output.
Demand-driven evaluation is unaffected: a continuation is just a module.

`ConsultingRecognizer` uses this to combine opinions rather than defer: when
its confidence is below `τ` it asks for a second opinion on the glyph and
answers `(1 − w) · own + w · second`. Under the demand gate, at `τ = 0.9` with
the same 300 expressions and the same cost as demand-gated refinement:

| glyphs | refine (replace) | consult `w = 0.3` | `w = 0.5` | `w = 0.7` |
|---:|---:|---:|---:|---:|
| 3 | 0.030 | 0.047 | 0.033 | 0.033 |
| 15 | 0.147 | 0.193 | 0.150 | 0.143 |
| 63 | 0.503 | 0.577 | 0.510 | 0.503 |

Mixing does not beat replacement: below `τ` the cheap recognizer is the less
reliable opinion, so weight on it costs accuracy and `w → 1` recovers
delegation. Ensembles help only when the opinions' errors are complementary
on the deferred set; for these two recognizers they are not. Continuations
are needed when the sub-result has a different type from the output, which
delegation cannot express (for example, splitting a value and requesting each
part, as in `tests/test_kernel.py`).

## 15. Normalization against shift

**Theory** (`lean/NCA/Normalize.lean`). A normalizer `N : X → Y` is a module
placed before a recognizer, which is then trained and evaluated on normalized
inputs. A style shift is a map `T` applied to reference inputs, so the shifted
distribution is `T_*ν₀` and the recognizer sees `N_*T_*ν₀` instead of `N_*ν₀`.

| Theorem | Statement |
|---|---|
| `ShiftBound.map` | normalization never increases a shift (data processing) |
| `shift_le_of_invariant_on` | if `N ∘ T = N` on `G`, the normalized shift is at most `ν₀(Gᶜ)` |
| `shift_zero_of_invariant` | if `N ∘ T = N` everywhere, the shift is removed |

With §5 this gives the design rule: a normalizer pays off exactly to the
extent that it undoes the style, and no normalizer can help where the style
destroys the information that separates classes (then `N(T x) = N(T x')` for
`x`, `x'` of different classes, and any recognizer after `N` errs on one of
them).

**Normalizer** (`nca.modules.normalizer.GlyphNormalizer`, contract
`GLYPH → NORMALIZED_GLYPH`). It scales the ink bounding box to 20 pixels,
centers it, then thickens or thins strokes (3×3 max or min, at most three
steps) until the ink fraction is in `[0.10, 0.21]`. This undoes size changes
and most stroke-width changes; it does not undo rotation or endpoint noise.
Recognizers trained with `--normalized` consume `NORMALIZED_GLYPH`, so the
planner routes glyphs through the normalizer; they are trained on the normal
style only.

**Diagnosis of the hard style** (2000 expressions, failure rates per
expression; before the fixes):

| | segmentation | first digit | operator | second digit | accuracy |
|---|---:|---:|---:|---:|---:|
| test | 0.031 | 0.006 | 0.002 | 0.005 | 0.958 |
| test (hard) | 0.123 | 0.157 | 0.257 | 0.161 | 0.428 |

Segmentation failures on the hard style are almost all *extra* glyphs:
thinned strokes break into pieces separated by narrow blank gaps. Thinning
also erases 7% of digit glyphs completely, which nothing downstream can undo.
For operators, a recognizer trained directly on the hard style reaches only
80% among operators: rotation by up to ~20° with three times the endpoint
noise makes `+` and `×` overlap, a floor of about 20% that no normalizer can
remove.

**Results** (2000 expressions; segmentation gap 4):

| system | test | test_unseen | test (hard) | test_unseen (hard) |
|---|---:|---:|---:|---:|
| before (gap 2, raw recognizers) | 0.958 | 0.965 | 0.428 | 0.449 |
| gap 4, raw recognizers | 0.977 | 0.984 | 0.446 | 0.463 |
| gap 4, normalized digits | 0.968 | 0.963 | 0.501 | 0.509 |
| gap 4, normalized digits and operators | 0.967 | 0.962 | 0.478 | 0.495 |

With normalization the digit failure rate on the hard style falls from 0.19 to
0.15 per position and the digit shift lower bound from 0.14 to 0.10 (the
normalized operator recognizer is worse on hard operators, 0.305 vs 0.280,
since rescaling does not undo rotation). The cost is about 0.5% digit
error on the normal style. Remaining hard-style errors are dominated by the
operator floor and erased digits. Choosing between the raw and normalized
digit recognizer is a route decision (§8): on normal-style validation data the
raw one wins, so the normalized route is adopted only when the deployment
distribution is known to include such styles.

**Monolithic baseline under the same shift** (`nca.baseline`, one CNN trained
end to end on 60,000 normal-style expressions, 5 epochs; 2000 expressions per
split):

| system | test | test_unseen | test (hard) | test_unseen (hard) |
|---|---:|---:|---:|---:|
| monolithic | 0.948 | 0.105 | 0.304 | 0.064 |
| modular, raw recognizers | 0.977 | 0.984 | 0.446 | 0.463 |
| modular, normalized digits | 0.968 | 0.963 | 0.501 | 0.509 |

On seen digit pairs the shift costs the monolithic model 64 points and the
modular pipeline 53 (47 with normalization). On unseen pairs the shift
compounds with the monolithic model's failure to compose. The modular system's
loss is also diagnosable, since per-module failure rates and shift lower
bounds locate it, and it can be fixed by replacing a single module.

## 16. Knowing when to be unsure

**Problem.** A long expression is answered correctly only if every glyph is
read correctly, so with per-glyph error `ε` the answer error grows like
`1 − (1 − ε)^L`: about 50% at 63 glyphs even with the expensive recognizer.
Errors cannot be corrected without redundancy, but they can be *located*:
calibrated confidences say which glyphs are doubtful, compute can be spent
there, and the system can decline to answer when doubt remains.

**Theory** (`lean/NCA/Selective.lean`). Each input carries an error bound
`b`, the sum of its glyphs' calibrated error probabilities `1 − max p`
(union bound, §4). Refining glyph `i` costs `κ i` and lowers the bound by
`β i`.

| Theorem | Statement |
|---|---|
| `selective_risk_le` | if the true error probability is at most `b` and only inputs with `b ≤ δ` are answered, the error rate among answered inputs is at most `δ` |
| `threshold_optimal` | for a price `λ` per unit of compute, refining exactly `{i : λ κ i ≤ β i}` minimizes bound plus priced compute over all refinement sets |
| `bound_ge_floor`, `length_limit` | if every item's risk is at least `ρ`, a bound of at most `δ` needs `n · ρ ≤ δ`: holding `δ` as inputs grow needs floors shrinking like `1 / n` |

So the efficient policy is local: refine a glyph when its expected bound
reduction pays for its cost, and sweep `λ` (equivalently the target `δ`) to
trade compute for reliability.

**Implementation** (`nca.ladder`, `nca.selective`). The controller is
generic over experts. A *ladder* for a contract is every installed module
with that contract whose output is a distribution, ordered by declared cost,
and each rung has its own temperature fitted on held-out labeled data by
negative log-likelihood. `SecondLook` wraps any such expert into a costlier
one with the same contract that averages its readings of several views, and
joins ladders like any other expert. `refine` reads every item on the bottom
rung and, while the summed risk `1 − max p` exceeds `δ`, moves the riskiest
item up one rung, using its latest reading. If no rung remains, the system
abstains. (Keeping the least risky of an item's readings instead would bias
the bound downward: in a trial the mean bound fell below the observed error,
voiding `selective_risk_le`.)

`nca.selective` applies the controller to a planned route ending in
single-input consumers over a `map`. What it reads comes from module
declarations, not from the task:

- **Which elements:** the map consumer's `demand`.
- **Which inputs of each element:** the map body's `demand`.
- **Which experts:** the ladders for the body's input contracts.
- **Segmentation:** if the map's source offers `alternatives` (the segmenter
  offers its runs, then merges of adjacent runs, narrowest gap first), a
  candidate the consumer would read nothing of is skipped without being read.
  The parser declares that it reads nothing of an even-length sequence, so
  this repairs split glyphs. On the test split 11% of 63-glyph expressions
  had one extra glyph (broken strokes; the validation half has almost none).

The arithmetic library installs cheap, expensive and (optionally) stronger
digit recognizers, the operator recognizer, and second looks (four one-pixel
shifts) of all but the cheapest. The stronger recognizer (`--arch wide
--augment`: a wider network trained six epochs on randomly rotated, shifted
and rescaled digits) reaches 99.19% on MNIST at about 10× the expensive
recognizer's compute.

**Decision demand.** The body declares `decides(index, demand)`: what of an
input can change the consumer's *decision*, not only its value. Readings are
computed, and enter the bound, only where decision-demanded; unread inputs
are passed as `None`. Agreement on decisions is coarser than agreement on
values, so this is demand-soundness for a coarser reader
(`DemandSound.coarsen`, `DemandSound.shrink` in `lean/NCA/Demand.lean`).
The fuser's operator input only rescales digit entries by `q_none`, and a
positive rescaling leaves the digit argmax unchanged, so digit decisions
need the digit reading alone and operator decisions the operator reading
alone. (This holds while `q_none > 0`; a randomized test checks that the
parse is unchanged.)

**Decision-relative risk.** A decision may range over only some of a
reading's classes: at an operator position the parser chooses among
operators, never "not an operator". The body declares this with
`decision_classes(index, demand)`, and the item's risk becomes the error
probability of that restricted decision, `1 − max_C p / Σ_C p`. When the most
probable class lies in `C` this never exceeds `1 − max p`
(`restricted_risk_le`), so the bound only tightens. Renormalizing the full
output's calibrated probabilities is not enough. In a trial, error among
answered expressions exceeded the target (0.084 at `δ = 0.05`, interval
`[0.050, 0.138]`), because the restricted decision was over-confident. Each
rung therefore fits a separate temperature per restricted decision, on the
held-out inputs whose label is among its classes.

**Results** (300 test expressions per length; MFLOPs per expression; decision
demand and decision-relative risk):

| glyphs | ladder | system | coverage | error answered | error forced | MFLOPs |
|---:|---|---|---:|---:|---:|---:|
| 3 | base | bottom rungs | 1.000 | 0.037 | 0.037 | 9 |
| 3 | base | top rungs | 1.000 | 0.010 | 0.010 | 153 |
| 3 | base | δ = 0.05 | 0.950 | 0.004 | 0.007 | 18 |
| 15 | base | top rungs | 1.000 | 0.063 | 0.063 | 768 |
| 15 | base | δ = 0.2 | 0.933 | 0.064 | 0.080 | 114 |
| 15 | + strong | δ = 0.05 | 0.903 | 0.030 | 0.050 | 598 |
| 63 | base | bottom rungs | 1.000 | 0.523 | 0.523 | 278 |
| 63 | base | top rungs | 1.000 | 0.280 | 0.280 | 3221 |
| 63 | base | δ = 0.2 | 0.493 | 0.155 | 0.293 | 1785 |
| 63 | + strong | top rungs | 1.000 | 0.193 | 0.193 | 20661 |
| 63 | + strong | δ = 0.2 | 0.800 | 0.142 | 0.213 | 4498 |
| 63 | + strong | δ = 0.05 | 0.450 | 0.074 | 0.190 | 11701 |

*Error forced* is the error when the system must answer after refining as
far as the target asks.

- **Reliability.** Every interval for error among answered expressions
  contains its target, though at strict targets on long inputs the estimates
  lean above it (63 glyphs, strong ladder: 0.074 at `δ = 0.05`, interval
  `[0.041, 0.131]`). Calibration is fitted on the validation half of the
  MNIST test set, which is easier than the half used for testing, and this
  shift is the likely cause.
- **Efficiency.** Targeted refinement matches refining everything at a
  fraction of the compute: 8× cheaper at 3 glyphs (and more accurate), and
  7× cheaper at 15 glyphs for 1.7 points more error.
- **Long inputs.** Second looks and segmentation repair cut forced error at 63
  glyphs from 0.523 to 0.280, and a stronger rung lowers the floor
  (`length_limit`) to 0.193. At `δ = 0.2` the strong ladder answers 80% of
  63-glyph expressions with 0.142 error, at 22% of the compute of reading
  everything with it.
- **Cost of genericity.** Decision demand brought compute near a controller
  hand-written for this task (278 against 248 MFLOPs at 63 glyphs on the
  bottom rungs; the rest is the generic second look's re-read of the
  original view). Decision-relative risk then raised coverage past it
  (0.49 against 0.42 at 63 glyphs and `δ = 0.2`). The hand-written
  controller also restricted operator decisions, so the difference lies
  elsewhere, plausibly in per-rung temperatures for the averaged second
  looks; it was not isolated.
- **Limit.** Targets below about 0.15 at 63 glyphs remain infeasible for most
  expressions: per-glyph floors are still too high for `L · ρ ≤ δ`.

**Practice queue** (`lean/NCA/Practice.lean`, `nca.practice`). Abstentions
and doubtful glyphs show where the library is weakest. In use, glyphs with
calibrated risk `r ≥ θ` are queued for a teacher's label.

| Theorem | Statement |
|---|---|
| `queued_value` | each queued label is expected to correct at least `θ` errors |
| `unqueued_errors` | at most `θ` expected errors per unqueued glyph escape the queue |
| `queued_captures` | the queue holds all but `θ · n` of the expected errors among `n` glyphs |
| `proportional_value` | drawing glyphs with probability `∝ r` finds `Σ r² / Σ r ≥ Σ r / n` expected errors per label, never fewer than random labels |

Practice is offline. A copy of the recognizer is fine-tuned on the queued
glyphs mixed with 10,000 replayed MNIST training digits, so the normal style
is not forgotten. The new version is adopted only if it beats the current one
by a one-sided sign test on `validation` expressions of both styles (§8).
Training on the system's own unverified answers is excluded, since it
reinforces errors.

**Experiment.** The expensive recognizer (calibrated on the normal style)
reads 4000 `train`-split expressions in the unseen hard style: 7878 digit
glyphs, 27% misread. For a label budget `k` the queue takes the `k` riskiest
glyphs, compared with `k` random glyphs from the same stream. Results on
2000 test expressions per style (seed 0):

| practice | labels | misread among labeled | digit error hard | accuracy normal | accuracy hard | sign test |
|---|---:|---:|---:|---:|---:|---|
| none | 0 | — | 0.211 | 0.977 | 0.446 | — |
| queue | 100 | 91% | 0.173 | 0.981 | 0.485 | adopted, p = 2e-6 |
| random | 100 | 27% | 0.201 | 0.981 | 0.455 | adopted, p = 0.003 |
| proportional | 100 | 67% | 0.178 | 0.980 | 0.484 | adopted |
| queue | 300 | 89% | 0.157 | 0.979 | 0.503 | adopted |
| random | 300 | 27% | 0.152 | 0.980 | 0.514 | adopted |
| proportional | 300 | 62% | 0.140 | 0.979 | 0.525 | adopted |
| queue | 1000 | 82% | 0.130 | 0.974 | 0.536 | adopted |
| random | 1000 | 27% | 0.128 | 0.978 | 0.538 | adopted |
| proportional | 1000 | 63% | 0.099 | 0.976 | 0.569 | adopted |
| everything | 7878 | 27% | 0.074 | 0.975 | 0.594 | adopted |
| replay only (budget 0) | 0 | — | 0.234 | 0.978 | 0.418 | rejected, p = 0.16 |

- **Finding errors.** Risk ranks errors well: 91% of the 100 riskiest glyphs
  are misread against 27% of random ones, and the expected errors in the
  queue (82, 243, 778) track the observed ones (91, 267, 824). The small
  excess comes from calibrating on the normal style.
- **Learning from them.** Queued labels help most when labels are scarce:
  with 100 labels the queue gains 3.9 points of hard-style accuracy, random
  labels 0.9. From 300 labels on, queue and random are equal within noise.
  The riskiest glyphs are the most distorted, so their value as training
  examples saturates while random labels add diversity.
- **Risk with diversity.** Sampling with probability proportional to risk
  keeps most of the queue's error-finding (62–67% of labels misread) and the
  diversity of random labels. It ties the top-risk queue at 100 labels and
  beats both alternatives from 300 on. At 1000 labels it reaches 0.569
  hard-style accuracy, 83% of the gain from labeling all 7878 glyphs with 13%
  of the labels. On a second seed it is again best at 300 and 1000 labels
  (0.527 and 0.553, against at most 0.511 and 0.538).
- **Safety.** Every adopted version keeps normal-style accuracy within its
  interval. The one version that made things worse (replay without practice
  data) was rejected by the sign test, as the upgrade rule intends.

## 17. Calibration under distribution shift

### 17.1 The problem

`selective_risk_le` promises that the error rate among answered inputs is at
most `δ`, under one premise: the bound is valid, `q(x) ≤ b(x)` for every
input `x`, where `q(x)` is the true probability that the answer to `x` is
wrong and `b(x)` the controller's bound. The bound is a sum of calibrated
per-item risks, and calibration is *fitted*. Temperatures minimize negative
log-likelihood on held-out data from a reference distribution `P` (the
`validation` half of the MNIST test set), which makes risks right *on
average over `P`*. It makes them neither pointwise valid nor right on
average over the distribution `Q` met in use (the other half, written by
different people). §16 measured the consequence. At 63 glyphs with the strong
ladder, the error among answered expressions was 0.074 at `δ = 0.05`
(interval `[0.041, 0.131]`) and 0.053 at `δ = 0.01`: consistent with the
target only because the intervals are wide, and leaning above it.

Three facts organize the repair:

1. how far the guarantee degrades is governed by a single quantity, the
   answered mass of the bound's deficit (§17.2);
2. degradation cannot be prevented by any method that looks only at `P`:
   some information about `Q` is required (§17.3);
3. a small audit sample from `Q`, labeled by a teacher, suffices for a
   finite-sample, distribution-free guarantee, through a family of
   increasingly cautious policies tested in a fixed order (§17.4–17.6).

### 17.2 How much the guarantee degrades

Write `A = {x : b(x) ≤ δ}` for the answered inputs and `p` for the input
distribution. Splitting `q = b + (q − b) ≤ δ + (q − b)⁺` on `A` gives
(`selective_risk_le_excess`, `lean/NCA/Calibration.lean`):

> `Σ_{x∈A} p(x) q(x) ≤ δ · Σ_{x∈A} p(x) + Σ_{x∈A} p(x) (q(x) − b(x))⁺`.

Dividing by `p(A)`, the error among answered inputs is at most `δ + D`, where
`D = E[(q − b)⁺ | A]` is the mean *deficit* of the bound among answered
inputs. Three remarks:

- **Deficit, not miscalibration.** Only underestimation inside `A` matters.
  An overestimating bound costs coverage, never validity, and errors on
  inputs the system declines are irrelevant.
- **Selection amplifies.** `A` is selected *by* `b`: inputs whose bound
  happens to be low are exactly the answered ones, so `D` can exceed the
  average deficit over all inputs. The controller sharpens this. It refines
  until the bound crosses `δ`, then stops, so answered inputs sit just below
  `δ` with whatever estimation error they carry. This is why violations
  appear at strict targets first.
- **Transfer under bounded shift.** If deployment weights are at most `W`
  times reference weights (`pQ ≤ W · pP`), every nonnegative weighted sum
  grows by at most `W` (`shift_ratio_le`). A deficit measured on `P` thus
  bounds the deficit on `Q` up to the factor `W`, which is unknown in
  practice and can be large.

### 17.3 Why reference data alone cannot suffice

Fix any procedure that maps reference data to a bound `b`. Take two
deployment distributions `Q₁` and `Q₂` with the same inputs as `P` but
different labels on a set `S` of inputs that `b` answers. On `S` the true
error probabilities differ, while `b` is the same for both, because it never
saw `Q`. The bound cannot be valid for both unless it declines `S`. Pushed to
the limit, this is `offline_rate_insufficient` (§5): a module that never fails
offline can fail always in situ. A guarantee on `Q` therefore requires
observations from `Q`. The question is how few, and how to use them
without spending the guarantee on their noise.

### 17.4 The audit

An **audit** is a sample of inputs from `Q`, labeled by a teacher, used only
for calibration decisions. It is distinct from the practice queue (§16),
whose labels are chosen by risk to train better experts. Audit inputs must
be drawn so that their distribution is known: uniformly from the deployment
stream (the default), or with known inclusion probabilities `π(x) > 0`, in
which case every audit quantity is weighted by `1 / π(x)` and remains
unbiased for its population value (`horvitz_thompson`). The second option
lets practice labels drawn with probability proportional to risk be reused
for auditing. Their weights are inversely proportional to risk, so
low-risk inputs, rarely drawn, count heavily.

Two uses of the audit are complementary.

**Recalibration (estimation).** Refit each rung's temperatures on audit
items (glyphs read in deployment, with teacher labels) instead of on
reference data. This moves the risks toward calibration *on average over
`Q`* and reduces the deficit `D`. It gives no finite-sample guarantee: the
fitted temperatures carry estimation error, and average calibration is not
pointwise validity.

**Risk control (guarantee).** Treat the controller as a policy family and
certify a member of it with the audit, as follows.

### 17.5 Risk control by fixed-sequence testing

**Policy family.** For an inflation factor `λ ≥ 1`, policy `π_λ` runs the
controller with target `δ / λ` and answers when the final bound satisfies
`λ · b ≤ δ`. Larger `λ` means more refinement and more caution. For a fixed
bound function the answered sets are nested (`inflated_answered_mono`), and
the family always contains a *trivially safe* member in the limit: never
answer. The true selective risk of a policy on `Q` is

> `R(λ) = P_Q(wrong | answered by π_λ)`,

and `π_λ` is *safe* when `R(λ) ≤ δ`. Nothing requires `R` to be monotone in
`λ`, and empirically it need not be.

**Test of one candidate.** Run `π_λ` on the `m` audit expressions. Among the
`n_λ` it answers, let `k_λ` be wrong. Conditional on `n_λ`, the wrong answers
are a binomial sample with parameter `R(λ)` (audit expressions are drawn
independently from `Q`, and the policy is fixed before seeing their labels).
The exact one-sided Clopper–Pearson upper bound

> `U(k, n; α) = the largest r with P(Binomial(n, r) ≤ k) ≥ α`

satisfies `P(R(λ) > U(k_λ, n_λ; α)) ≤ α`. Declare `λ` safe when
`U(k_λ, n_λ; α) ≤ δ`. When `λ` is unsafe (`R(λ) > δ`), declaring it safe
requires `U < R(λ)`, which has probability at most `α`: each test is valid
at level `α`.

**Fixed sequence.** Fix an order of the candidates, test them in that
order, and stop at the first one not declared safe. By `fixed_sequence_le`:

> `P(some accepted candidate is unsafe) ≤ α`,

with no correction for the number of candidates and no monotonicity
assumption. Since the event covers *every* accepted candidate at once, any
accepted candidate may be deployed, and in particular the one answering the
most audit expressions. If none is accepted, the system abstains on
everything.

**Choosing the order.** The guarantee requires only that the order not
depend on the data the tests are run on. The natural order, from most to
least cautious, is a poor one. Cautious candidates answer few audit
expressions, so their upper bounds are wide, they fail, and testing stops
before reaching anything useful (§17.8). The audit is therefore split: one
part runs every candidate and orders them by their Clopper–Pearson bound
there, most certifiable first; the other part runs the tests. Candidates
with `λ < 1` (answering above the bound) are admissible too. The test, not
the bound, decides their safety, and they pay off where the bound is
conservative. The proof is two lines: any acceptance of an unsafe candidate
passes through the *first* unsafe candidate `k*` in the order (a fixed index,
since safety is a property of `Q`, not of the audit). Reaching past `k*`
requires its test to have wrongly declared it safe, an event of probability
at most `α`.

**The guarantee.** With probability at least `1 − α` over the audit, the
deployed policy's error rate among answered inputs on `Q` is at most `δ`.
It holds for any experts, any calibration (good or bad), and any shift
between `P` and `Q`. What it assumes:

- audit and deployment inputs are independent draws from the same `Q`;
- the policy family and the order are fixed before the audit is labeled;
- for a weighted audit, the inclusion probabilities are known.

Calibration quality no longer affects validity. It affects only *efficiency*:
better risks put the safe candidates further down the sequence, so a less
cautious, higher-coverage policy is certified.

### 17.6 How many audit labels

When a candidate answers `n` audit expressions and errs on none, it is
declared safe exactly when `(1 − δ)^n ≤ α`, that is when
`n ≥ ln(1/α) / −ln(1 − δ) ≈ ln(1/α) / δ`:

| `δ` | `α = 0.1` | `α = 0.05` |
|---:|---:|---:|
| 0.2 | 11 | 14 |
| 0.05 | 45 | 59 |
| 0.01 | 230 | 299 |

These are *answered* audit expressions with no errors. With errors the
requirement grows, since `U(k, n; α) ≈ k/n + O(√(k log(1/α))/n)`. Two
consequences follow. Strict targets need audits in the hundreds. And because
only answered expressions count, low-coverage policies need proportionally
larger audits: coverage and certifiability are linked. Recalibration on the
same audit raises coverage, so the two uses reinforce each other. To keep
the guarantee, the audit is split: one part fits temperatures, the other
tests the sequence. Reusing the fitting part for testing would make the
policy depend on the labels it is tested on.

### 17.7 Expected outcomes

The theory makes falsifiable predictions for the experiment.

1. **Validity.** With risk control at level `α`, the error rate among
   answered test expressions stays at or below `δ` in at least a fraction
   `1 − α` of independent audit draws, at every length and target. With
   reference calibration alone it does not, at strict targets on long inputs.
2. **Price.** Risk control costs coverage relative to the uncontrolled
   controller at the same `δ`. The cost is largest where the uncontrolled
   controller was violating the target.
3. **Recovery.** Recalibrating on audit glyphs lowers the deficit
   (mean bound closer to observed error) and returns coverage under risk
   control.
4. **Labels.** Certification fails at strict targets when too few answered
   audit expressions remain (§17.6), and the controller then abstains on
   everything. This is the honest answer when evidence is insufficient.

### 17.8 Results

`nca.certify`, with the base ladder (cheap, expensive and second-look
digit readers; operator reader and its second look). Calibration uses 2000
reference glyphs. The `test` half of the MNIST test set is divided by image
index into an audit part and an evaluation part (300 expressions). Each audit
draw holds 200 + 200 expressions: the first half recalibrates the rungs (for
the *audit* calibration) and orders the candidates, the second half tests
them. Inflations are `λ ∈ {4, 2, 1.5, 1.25, 1, 0.75, 0.5}` with `α = 0.1`,
over three independent audit draws.

| glyphs | δ | calibration | uncontrolled: coverage, error answered | risk control: λ per draw | coverage | error answered |
|---:|---:|---|---|---|---|---|
| 15 | 0.2 | reference | 0.917, 0.102 | 0.5, 0.5, 0.5 | 0.980 | 0.112 |
| 15 | 0.2 | audit | 0.87–0.95, 0.07–0.11 | 0.5, 0.5, 0.5 | 0.97–0.99 | 0.110–0.125 |
| 15 | 0.05 | reference | 0.793, 0.046 | 1, 1.5, 0.5 | 0.79, 0.71, 0.86 | 0.046, 0.038, **0.070** |
| 15 | 0.05 | audit | 0.57–0.87, 0.029–**0.065** | 0.75, 4, 0.5 | 0.66, 0.55, 0.90 | 0.030, 0.036, **0.071** |
| 63 | 0.2 | reference | 0.480, 0.139 | –, 1, 1 | 0, 0.48, 0.48 | –, 0.139, 0.139 |
| 63 | 0.2 | audit | 0.25–0.51, 0.08–0.15 | –, 0.75, 0.75 | 0, 0.47, 0.38 | –, 0.141, 0.106 |
| 63 | 0.05 | reference | 0.143, **0.070** | –, –, – | 0 | – |
| 63 | 0.05 | audit | 0.01–0.17, 0–**0.080** | –, –, – | 0 | – |

Bold marks error above `δ` on the evaluation set; "–" means no candidate was
certified, so the system abstained on everything. The reference-calibrated
uncontrolled policy does not depend on the audit.

Against the predictions of §17.7:

1. **Validity: confirmed.** Uncontrolled, reference calibration violates the
   target at 63 glyphs and `δ = 0.05` (0.070), as §16 suggested. Under risk
   control 22 of 24 configurations meet the target. Both misses come from one
   audit draw (draw 2, 15 glyphs, `δ = 0.05`: 0.070 and 0.071), and their
   intervals (`[0.044, 0.107]`, `[0.046, 0.108]`) include the target. Each
   draw may fail with probability up to `α = 0.1`, and a draw's failures are
   correlated because all its tests share one audit.
2. **Price: confirmed, and it depends on the order.** With the
   most-cautious-first order, risk control at 63 glyphs abstained on
   everything in 4 of 6 configurations at `δ = 0.2`. Cautious candidates
   answered too few audit expressions to be certified, and testing stopped
   there. Ordering on the first audit half certifies a policy in 4 of 6, at
   the uncontrolled coverage. At 15 glyphs and `δ = 0.2` it certifies
   `λ = 0.5` in every draw and *raises* coverage from 0.92 to 0.98, because
   the bound is conservative there.
3. **Recovery: refuted.** Recalibrating on 200 audit expressions did not
   reliably help. Its coverage varied widely between draws (0.25–0.51 at
   63 glyphs, `δ = 0.2`). Uncontrolled, it *caused* violations at 15 glyphs
   and `δ = 0.05` (0.061, 0.065) where reference calibration had none. This
   is the distinction §17.4 drew: refitting temperatures moves calibration
   on average over `Q`, which is not the pointwise validity that the
   selected, answered inputs need. Only the test-based guarantee is robust.
4. **Labels: confirmed.** At 63 glyphs and `δ = 0.05` no candidate is ever
   certified. A pass needs about 59 answered audit expressions with no errors
   (§17.6), and at that strictness candidates answer 15–30 of the 200.
   Abstaining is the correct outcome: the evidence does not support the
   claim.

**Conclusion.** The guarantee on deployment comes from testing, not from
calibration. Calibration (reference or recalibrated) determines only how
much is certified. A label-efficient path to strict targets on long inputs
needs larger audits, or better calibrated risks so that fewer candidates
answer near the boundary.

## 18. A second domain: noisy Boolean formulas

### 18.1 The task

Everything up to §17 was shown on handwritten arithmetic. The machinery is
meant to be generic, so the claim needs a second task that shares nothing
with the first except the kernel: different inputs, different experts, and
a different structure of what the answer depends on.

**Input.** A Boolean formula in prefix (Polish) notation, written as text
whose words have passed through a noisy channel (typing errors). The
vocabulary is `true`, `false`, `not`, `and`, `or`, `xor`. For example, the
formula `and or true false not false` might arrive as
`anf ot tru fasle nto flase`. Prefix notation needs no brackets: arities
alone determine the formula (§18.5).

**Output.** The formula's truth value.

**Channel.** Each character independently, at noise level `ν`, is replaced by
a random letter with probability `ν/2`, deleted with probability `ν/5`,
followed by an inserted random letter with probability `ν/5`, or swapped with
the next character with probability `ν/10`. A word never becomes empty (a
fully deleted word keeps one random letter). Spaces are not corrupted, so
word boundaries are known. A distribution shift is a larger `ν` in use than
in calibration.

**Formulas.** Complete binary trees of depth `d` (`n = 2^d` leaves) whose
levels alternate between `and` and `or` (root chosen at random), with uniform
random leaves, each leaf negated (`not`) with probability ¼. A variant
replaces each connective by `xor` with probability `x`.

### 18.2 What carries over, and what must not be added

The kernel, the planner, ladders, calibration, refinement and certification
are reused unchanged. The domain contributes only experts: a tokenizer, two
word readers and a formula evaluator, each with an ordinary contract. Two
generic extensions are needed. Each is proved, and each reduces exactly to
the earlier behavior on arithmetic.

1. **Grouped decisions (§18.3).** A decision may choose a *group* of classes,
   not one class. Restriction (§16) is the special case of singleton groups.
2. **Value-dependent certificates (§18.4).** Which readings the answer
   depends on may depend on the readings themselves. Static demand (§14) is
   the special case that ignores them.

### 18.3 Grouped decisions

To parse a prefix formula, the evaluator needs every word's **arity**: 0 for
`true` and `false`, 1 for `not`, 2 for the connectives. It needs a word's
identity only where that word's value is used (§18.5). A decision of the
first kind chooses among the groups `{true, false}`, `{not}` and
`{and, or, xor}`.

**Definition.** A *grouped decision* is a partition `G` of a set `C` of a
reading's classes. Given a reading `p`, it chooses the group `g*` that
contains the most probable class of `C`. Its risk is

> `1 − p(g*) / p(C)`,

the probability, under the reading, that the true class lies in `C` but
outside the chosen group. With singleton groups this is the restricted risk
`1 − max_C p / p(C)` of §16. With `C` all classes and singleton groups, it is
the class risk `1 − max p`.

**Theorem** (`grouped_risk_le`, `lean/NCA/Certificate.lean`). If the chosen
group contains the most probable class `a`, then `p(a) ≤ p(g*)`, so the group
risk is at most the class risk `1 − p(a) / p(C)`. Coarser decisions never
carry more risk than finer ones under the same reading.

The group is chosen by the most probable *class*, not the heaviest group,
because that is the decision the consumer actually makes: it reads the word
as its most probable class and takes the arity from there. Choosing the
heaviest group could pair a word's identity with a different word's arity.

**Calibration.** As in §16, each decision gets its own temperature. It is
fitted by negative log-likelihood of the *group* labels on held-out inputs
whose label lies in `C`, the group probability being the sum of the
temperature-scaled class probabilities in the group. The inequality above
holds under one temperature. With separately fitted temperatures it may
fail numerically, so the controller never assumes it: it computes every
risk it uses.

### 18.4 Value-dependent certificates

In arithmetic every demanded reading matters whatever the other readings
say. Here that is false: `and false x` is `false` whatever `x` is, so once
`false` is read with confidence, the identity of every word inside `x` is
irrelevant, and only its arity (needed to find where `x` ends) is not.

**Definition.** Let `r` be the readings of all items and `t` the truth. A
*certificate* assigns, to each reading `r`, an agreement relation
`∼_{cert(r), i}` for each item `i`: equality of class, equality of group, or
the total relation ("nothing demanded"). It *certifies* `f` when

> `∀ r t, (∀ i, t_i ∼_{cert(r), i} r_i) ⇒ f(t) = f(r)`.

The certificate is computed from the reading. It never needs the truth,
which is unknown. Note the asymmetry: `cert(t)` may differ from `cert(r)`,
and only `cert(r)` matters.

**Theorem** (`certificate_error_le`, `certificate_error_le_support`). For any
distribution of the truth given the reading `r`,

> `P(f(t) ≠ f(r) | r) ≤ Σ_i P(t_i ≁_{cert(r), i} r_i | r)`,

and items demanding nothing contribute nothing. The proof: if every
demanded agreement holds, the answer is right, so a wrong answer violates
some demanded agreement, and the union bound applies.

With per-decision risks calibrated given the reading, the bound is
`Σ_{i ∈ cert(r)} risk_i(decision_i)`. This is the same premise as in §16: each
item's error probability, given the readings, is its calibrated risk. Static
demand is the certificate that ignores `r`. `DemandSound` (§14) is the
special case where all readings agreeing on a fixed demand give the same
answer.

**Choice of certificate.** One reading can have several valid certificates
(`and false false` can use either child). The controller may choose the one
with least risk. The choice depends on `r` only, so validity is unaffected.

### 18.5 Certificates for prefix formulas

**Trees.** The Lean model has formula trees with an annotation at each node
(for a reading: the node's risks), evaluated in the usual way. A certificate
is a tree of choices:

- `leaf` at constants;
- `not c` at negations;
- `both c d` at a connective, evaluating both children;
- `left c` (or `right c`) at a connective, evaluating one child and skipping
  the other.

A certificate is *valid* for a reading when it skips a child only if the
other child's read value is *absorbing* for the connective: `false` for
`and`, `true` for `or`, never for `xor`. A truth `t` *agrees* with the reading
`r` on a certificate when it has the same constructor, connective and
constant at every evaluated node. Skipped subtrees are unconstrained.

| Theorem | Statement |
|---|---|
| `cert_sound` | if `c` is valid for `r` and `t` agrees with `r` on `c`, then `t` and `r` have the same value |
| `bestCert_valid`, `bestCert_le` | with a weight per node (`w_full` where evaluated, `w_shape` throughout skipped subtrees), the node-by-node choice `bestCert` is valid and weighs no more than any valid certificate |
| `bestCert_le_full` | `bestCert` weighs no more than evaluating every node |
| `code_prefix` | if one formula's arity sequence followed by `a` equals another's followed by `b`, the arity sequences are equal and `a = b` |

**Words.** The words of a formula are its preorder. By `code_prefix`, the
arity sequence of a word sequence determines the tree's shape and where each
subformula ends. If every word's arity decision is right, the read tree and
the true tree have the same shape, and the node at preorder position `k` is
word `k` in both. The word-level certificate is therefore:

- the **arity decision** at every word;
- the **full decision** at every word that is a node `bestCert` evaluates.

Agreement on these gives agreement on the tree certificate, and `cert_sound`
gives the right answer, so this certifies the evaluator in the sense of
§18.4. If the read arities do not form a formula, no answer is certified:
some arity decision is certainly wrong.

**Weights.** For a word evaluated in the certificate, the weight is the risk
of its full decision. For a skipped word, it is the risk of its arity
decision. `bestCert` is then the least-risk certificate, computed bottom-up in
one pass over the words. Its bound never exceeds the static bound that
decides every word fully (`bestCert_le_full`).

### 18.6 How certificates scale

**Theorem** (`alternating_cert_leaves`). Every complete alternating
`and`/`or` tree of depth `d`, whatever its leaf values, has a valid certificate
evaluating at most `2^⌈d/2⌉` of its `n = 2^d` leaves: about `√n`.

*Proof idea.* Write `L(d)` for the number of leaves needed. An `and` node
reading `true` needs both children. Each child is an `or` reading `true`, so
it needs one child, an `and` two levels down. An `and` node reading `false`
needs one child. That child is an `or` reading `false`, so it needs both of
its children. Either way `L(d) ≤ 2 · L(d − 2)`, with `L(0) = 1` and
`L(1) ≤ 2`. `or` nodes are dual. Negated leaves leave this unchanged: a
negation sits on a leaf and is evaluated with it.

The evaluated connectives along these paths number `O(√n)` as well. So for
per-word risks `ρ_full` (full decision) and `ρ_shape` (arity decision), the
certificate bound on a formula with `m ≈ 2.25 n` words is about

> `m · ρ_shape + c √n · ρ_full`,

against `m · ρ_full` for static demand. The length limit of §16
(`length_limit`) changes from `n ≲ δ / ρ_full` to roughly
`n ≲ (δ / ρ_full)²`, until the shape term dominates at
`n ≈ δ / ρ_shape`. Arity decisions are easy: `true`/`false` look nothing like
the connectives. So `ρ_shape ≪ ρ_full`, and the gain is large exactly where
static demand fails.

**Control.** `xor` has no absorbing value, so on all-`xor` formulas every
valid certificate evaluates everything, and the certificate bound equals the
static bound. The `xor` variant is the experiment's control.

### 18.7 Refinement with certificates

`refine` (§16) generalizes as follows:

1. Read every item on its bottom rung.
2. Ask the consumer for its least-risk certificate of the current readings.
   The consumer receives the readings and a function returning any item's
   risk under any decision.
3. If the certificate's bound is at most `δ`, answer.
4. Otherwise climb the item with the largest contribution to the bound among
   the certificate's items that have a rung left.
5. If none has, abstain. If the readings determine no answer, climb the
   riskiest item.

A consumer that declares no certificate gets the static certificate: every
item with its fixed decision. That is the old procedure, step for step.

Remarks:

- **Termination.** Every iteration climbs a rung, and ladders are finite.
- **Certificates move.** Climbing an item can change its reading, and
  therefore the certificate. A child read `false` may now read `true`, and
  its sibling, skipped until then, becomes needed. The bound is always
  recomputed from the current readings, so the decision to answer is a
  function of the final reading, and §18.4 applies to it. As in §16, the
  latest reading of an item is used, never the least risky one.
- **Efficiency.** The certificate costs one bottom-up pass over the words
  per climb. That is symbolic work, small next to an expert call. Items
  outside the certificate are never climbed, which is where the compute
  saving comes from.

### 18.8 Experts

| Module | Contract | Notes |
|---|---|---|
| tokenizer | text → sequence of noisy words | splits on spaces |
| edit reader | noisy word → word distribution | `p(w) ∝ exp(−d(x, w))`, with `d` the edit distance counting adjacent transpositions; symbolic, no training |
| character reader | noisy word → word distribution | a small network on one-hot characters, trained on the noisy words of training formulas at the calibration noise level, with a quarter of the connectives `xor` so that it knows every word |
| formula evaluator | sequence of word distributions → truth value | parses the most probable words; declares the certificate of §18.5 |

The two readers share a contract, so they form one ladder, cheapest first,
exactly as the digit readers do. The map body applies a reader directly to
each word. In arithmetic a fuser combines two readings per glyph. The
refinement adapter accepts both shapes, and a certificate is declared on
readings the consumer reads directly.

### 18.9 Predictions

1. **Validity.** At the calibration noise level, the error among answered
   formulas is at most `δ` with the certificate bound, as with the static
   one.
2. **Coverage.** At the same `δ`, certificates answer more formulas than
   static demand. The gap grows with depth, and vanishes on all-`xor`
   formulas (the control).
3. **Scaling.** The number of fully decided words grows like `√n`, not `n`:
   on alternating trees at most `2^⌈d/2⌉` leaves are evaluated.
4. **Compute.** At the same `δ`, certificates spend less: items outside the
   certificate are never climbed.
5. **Shift.** At a higher noise level in use, the uncontrolled error among
   answered formulas can exceed `δ`, and the risk control of §17 restores the
   target, with `certify` unchanged.

### 18.10 Results

`nca.logic`, calibration noise `ν = 0.1`. The edit reader (650 operations
per word) and the character reader (103k FLOPs per word, trained on 6000
depth-4 training formulas) form the ladder. Calibration uses the words of
100 depth-4 validation formulas, and evaluation 300 test formulas per depth.
On noisy words of uniformly drawn vocabulary words, the edit reader errs on
1.8% of words (0.29% in arity), the character reader on 0.8% (0.32%). A
wider character reader (807k FLOPs) did no better, so the character reader
sits at the channel's floor. Arithmetic output of `nca.selective` is
identical before and after the two generic extensions.

**Certificate size** (true formulas, fewest leaves a valid certificate
evaluates): 2, 4, 8 and 16 leaves at depths 2, 4, 6 and 8, for every one of
the 300 formulas. This is exactly `2^⌈d/2⌉` (`alternating_cert_leaves` is
tight at even depths). On all-`xor` formulas it is all `2^d` leaves.

**Selective answering**, `and`/`or` formulas (coverage; compute in kFLOPs per
formula):

| depth | words | δ | static coverage | certificate coverage | static compute | certificate compute |
|---:|---:|---:|---:|---:|---:|---:|
| 2 | 8 | 0.2 / 0.05 / 0.01 | 0.977 / 0.957 / 0.927 | 0.977 / 0.957 / 0.927 | 31 / 47 / 87 | 31 / 47 / 86 |
| 4 | 35 | 0.2 | 0.900 | 0.910 | 409 | 370 |
| 4 | 35 | 0.05 | 0.813 | 0.843 | 720 | 608 |
| 4 | 35 | 0.01 | **0** | **0.267** | 3641 | 2719 |
| 6 | 143 | 0.2 | 0.497 | 0.557 | 7602 | 6721 |
| 6 | 143 | 0.05 | **0** | **0.213** | 14892 | 11864 |
| 8 | 575 | 0.2 | 0 | 0.017 | 59800 | 58883 |

Across every row, no answered formula was wrong. The upper ends of the 95%
intervals are below each `δ` wherever more than 100 formulas were answered.
When forced to answer, error is 0.02, 0.04, 0.23 and 0.58 at depths 2 to 8.

**Control**, all-`xor` formulas: the two systems agree to within one or two
formulas at every depth and target. Coverage is 0.877/0.877 at depth 2 and
`δ = 0.2`, and 0.383/0.390 at depth 4. The error among answered formulas
stays within `δ` (at most 0.060 at `δ = 0.2`). The tiny differences come
from `xor` words misread as `and`/`or`, which allow a skip. Here the
character reader matters: it halves the depth-4 error when forced to answer
(0.38 → 0.19), because `xor` and `or` differ by one letter.

**Shift**, noise 0.2 in use with the certificate system, three audit draws
of 200 + 200 formulas at the deployment noise:

| depth | δ | uncontrolled: coverage, error answered | risk control: λ per draw | coverage | error answered |
|---:|---:|---|---|---|---|
| 4 | 0.2 | 0.687, 0.024 | 0.5, 0.5, 0.5 | 0.757 | 0.026 |
| 4 | 0.05 | 0.520, 0.013 | 0.5, 0.5, 0.75 | 0.58, 0.58, 0.56 | 0.023, 0.023, 0.024 |
| 6 | 0.2 | 0.157, 0 | 0.5, 0.5, 0.5 | 0.313 | 0.011 |
| 6 | 0.05 | 0.007, 0 | –, –, – | 0 | – |

Against the predictions of §18.9:

1. **Validity: confirmed.** Error among answered formulas is within `δ`
   everywhere, and far below it in the `and`/`or` family.
2. **Coverage: confirmed.** Certificates answer at least as many formulas
   everywhere. The gap grows with depth and strictness: where static demand
   answers nothing (depth 4 at `δ = 0.01`, depth 6 at `δ = 0.05`),
   certificates answer 27% and 21%. The gap vanishes on the `xor` control.
3. **Scaling: confirmed, exactly.** Evaluated leaves are `2^⌈d/2⌉ = √n` on
   every formula.
4. **Compute: confirmed.** At equal targets certificates spend 10–16% less
   where both answer, because skipped words are never climbed.
5. **Shift: refuted as stated.** At double the noise, the uncontrolled
   policy never exceeded `δ`: the bound is conservative here, unlike for
   handwriting (§17.8). Risk control, unchanged, therefore did the opposite
   of repair: it certified the boldest candidate (`λ = 0.5`) and *raised*
   coverage, from 0.16 to 0.31 at depth 6. Where the audit could not support
   the claim (depth 6, `δ = 0.05`), it abstained.

**The arity term limits depth.** The theory assumed `ρ_shape ≪ ρ_full`
because `true`/`false` look nothing like connectives. That holds for them,
but `not` looks like `and`, `or` and `xor` (`xor` → `not` is the commonest
arity confusion). Measured arity error is a third (edit reader) to
two-fifths (character reader) of word error, not orders of magnitude below
it. The arity term `m · ρ_shape` grows with all `m` words. At depth 8
(575 words) it alone nearly exhausts `δ = 0.2`, and only 1.7% of formulas
are certified.

**Why the bound is conservative.** A hypothesis, not yet tested: prefix
notation is an error-detecting code. A single wrong arity changes
`Σ (arity − 1)`, so the words no longer parse, the certificate reports no
answer, and the controller climbs or abstains. A wrong arity can go
undetected only if at least one other compensates, so the arity term,
summed as if every arity error were silent, overstates the risk roughly
quadratically. A bound that credits this detection would charge the arity
term only for pairs of errors. That needs either a premise of independent
word errors, or the audit's test of §17 to stay valid. It is the natural
next refinement, and it targets exactly what limits depth.

**Conclusion.** The kernel, planner, ladders, calibration, refinement and
certification carried over to a task with different inputs, different
experts and a different dependency structure. The new domain needed two
generic extensions, grouped decisions and value-dependent certificates.
Both reduce exactly to the old behavior on arithmetic. Certificates turn
the union bound's `n` into `√n` for the decisions that matter, and that
makes formulas answerable where static demand must abstain.

## 19. Error detection by the format

### 19.1 The observation

Two findings of §18.10 point to the same place:

1. the certificate bound was conservative, with no answered formula wrong at
   mean bounds near 0.1;
2. its arity term `Σ ρ_shape`, charged at every word, limits depth.

Both suggest the arity term overcharges. It is a union bound that treats
every arity error as silent. But the format is redundant. A prefix formula's
arity sequence is constrained, the reading is answered only if it parses,
and the truth parses too. Errors that break the constraint are *detected*
(the controller climbs or abstains). Only errors that preserve it can make
an answer wrong.

### 19.2 Single errors are detected

**Theorem** (`code_sum`, `lean/NCA/Detection.lean`). Every formula's
preorder arity sequence sums to one less than its length:
`Σ_k (a_k − 1) = −1`.

**Theorem** (`code_no_single_change`). Two formulas with the same number of
words whose arity sequences agree everywhere except possibly at one
position have the same arity sequence.

*Proof.* Equal lengths and `code_sum` give equal sums. Lists of equal length
and equal sum agreeing outside one position agree there too
(`List.eq_of_sum_eq_of_agree`).

The premise is that word boundaries are known, so the reading and the truth
have the same number of words. The channel never corrupts spaces. Then, given
that the reading parses, the set of words whose arity is misread has size 0
or at least 2.

### 19.3 What a wrong answer requires

Let the reading `r` parse, let `t` be the truth, and let `E` be the words the
reading's certificate evaluates. Write `A_k` for "word `k`'s arity is
misread" and `W_k` for "word `k` is misread but its arity is right".

- If no arity is misread, the trees align node by node (`code_prefix`). A
  wrong answer then needs a disagreement on an evaluated node (`cert_sound`),
  that is, some `W_k` with `k ∈ E`.
- If some arity is misread, at least two are (§19.2).

Hence

> `wrong ⊆ (⋃_{k ∈ E} W_k) ∪ {at least two A_k}`

and (`detected_error_le`)

> `P(wrong | r) ≤ Σ_{k ∈ E} P(W_k | r) + P(at least two A_k | r)`.

**Evaluated words.** `P(W_k)` is the probability that the true word lies in
the read word's arity group `g` but differs from it, `p(g) − p(r_k)`. This is
at most the risk `1 − p(r_k) / p(g)` of the decision restricted to `g`
(`joint_le_restricted`), which §16 already calibrates. For `not`, alone in
its group, it is 0.

**Arity.** What remains is the probability of at least two arity failures
among all words.

### 19.4 Two bounds on two failures

Write `ρ_k` for word `k`'s arity risk and `S = Σ_k ρ_k`.

**Without further premises** (`two_occur_le_half`). The number of failures
`N = Σ_k 1[A_k]` has mean `S`. By Markov's inequality,
`P(N ≥ 2) ≤ S / 2`. Detection halves the arity term, using nothing but the
format.

**Without positive correlation** (`two_occur_le_pairs`). If failures at two
different words are never positively correlated given the readings,
`P(A_i ∩ A_j | r) ≤ ρ_i ρ_j`, then

> `P(N ≥ 2 | r) ≤ e₂(ρ) = Σ_{i<j} ρ_i ρ_j ≤ S² / 2`,

quadratically small when `S` is small. The premise is plausible because
each word is corrupted and read independently. It is not automatic: the
truth is a formula, and conditioning on that couples words (it is what
rules out single errors). So it is a premise to test, not a theorem. If it
fails in use, the audit of §17 still certifies a policy honestly. Both
bounds are valid under the premise, so the controller charges
`min(S/2, e₂)`.

A sharper bound would also use the sign of the errors: undetected errors
must cancel in `Σ (a − 1)`, and a dynamic program over the net arity change
computes that probability under independence. Since `e₂` is already
quadratic, this is not pursued.

### 19.5 Choosing the certificate

With detection, the arity charge covers all words whichever certificate is
chosen. The least-risk certificate therefore minimizes the evaluated words'
within-group risks alone: `bestCert` with `w_full` the restricted risk and
`w_shape = 0`.

### 19.6 Risk accounts

The bound is no longer a sum of per-item decision risks: `e₂` is a product
over pairs. The generic interface therefore moves one step:

- A consumer's certificate returns each item's **charge**, and the bound is
  the sum of charges.
- `refine` climbs the open item with the largest charge.
- Validity of the account is the consumer's theorem.

| account | charge of item `k` |
|---|---|
| static | risk of its fixed decision (as before) |
| certificate (§18) | risk of the decision it serves |
| detection, Markov | `ρ_k / 2`, plus its restricted risk if evaluated |
| detection, pairs | `ρ_k (S − ρ_k) / 2` (these sum to `e₂`), plus its restricted risk if evaluated |

### 19.7 Scaling

Over `m` words with arity risk `ρ` each, the arity term is

- `m ρ` without detection,
- `m ρ / 2` with Markov,
- about `(m ρ)² / 2` with pairs.

Under a target `δ` the length limit on that term moves from `m ≲ δ / ρ` to
`m ≲ √(2δ) / ρ`. For `δ = 0.2` and `ρ = 10⁻³` that is 632 words instead of
200.

### 19.8 Predictions

1. **Validity.** The Markov account needs no new premise: the error among
   answered formulas stays within `δ`. The pairs account stays within `δ` if
   its premise holds; the experiment tests this.
2. **Coverage.** Markov raises coverage modestly. Pairs raises it strongly
   where the arity term dominates: depths 6 and 8, where §18 certified 21%
   (depth 6, `δ = 0.05`) and 1.7% (depth 8, `δ = 0.2`).
3. **Tightness.** The mean bound among answered formulas moves toward the
   observed error.
4. **Compute.** Less: arity charges no longer force climbs on words whose
   arity is merely uncertain.

### 19.9 Results

`nca.logic`, with the setup of §18.10 (same readers, calibration and 300
test formulas per depth). Coverage, with compute in kFLOPs per formula in
brackets:

| depth | δ | static | certificate | Markov | pairs |
|---:|---:|---:|---:|---:|---:|
| 2 | 0.01 | 0.927 (87) | 0.927 (86) | 0.940 (75) | 0.970 (32) |
| 4 | 0.2 | 0.900 (409) | 0.910 (370) | 0.923 (322) | 0.973 (124) |
| 4 | 0.05 | 0.813 (720) | 0.843 (608) | 0.857 (559) | 0.963 (162) |
| 4 | 0.01 | 0 | 0.267 (2719) | 0.713 (1158) | 0.937 (274) |
| 6 | 0.2 | 0.497 (7602) | 0.557 (6721) | 0.687 (4798) | 0.817 (2833) |
| 6 | 0.05 | 0 | 0.213 (11864) | 0.440 (8514) | 0.707 (4497) |
| 6 | 0.01 | 0 | 0 | 0.113 (13302) | 0.557 (6764) |
| 8 | 0.2 | 0 | 0.017 (58883) | 0.097 (54236) | 0.247 (45391) |
| 8 | 0.05 | 0 | 0 | 0.003 (59614) | 0.080 (55227) |
| 8 | 0.01 | 0 | 0 | 0 | 0.007 (59426) |

No answered formula was wrong under any account. The mean bound among
answered formulas at `δ = 0.2` falls from 0.032 (certificate) to 0.025
(Markov) and 0.006 (pairs) at depth 4, and from 0.103 to 0.092 and 0.048 at
depth 6.

**Shift**, noise 0.2 in use with the pairs account, audits as in §18.10:

| depth | δ | uncontrolled: coverage, error answered | risk control: λ per draw | coverage | error answered |
|---:|---:|---|---|---|---|
| 6 | 0.2 | 0.410, 0.008 | 0.5, 0.5, 0.5 | 0.460 | 0.029 |
| 6 | 0.05 | 0.257, 0 | –, 0.5, – | 0, 0.353, 0 | –, 0.009, – |
| 8 | 0.2 / 0.05 | 0, – | –, –, – | 0 | – |

At depth 6 the certificate account answered 0.157 and 0.007 of these
formulas uncontrolled (§18.10).

Against the predictions of §19.8:

1. **Validity: confirmed.** The Markov account, which needs no premise,
   made no error. Neither did the pairs account in distribution. Under shift
   it made one error in 123 answered formulas at `δ = 0.2`, far within `δ`.
   This does not establish the pairs premise: with no errors anywhere, every
   account is conservative, and a mild positive correlation would go
   unseen. It shows only that, if the premise fails here, it fails by less
   than the slack the bound already has.
2. **Coverage: confirmed, more strongly than predicted for Markov.** At
   depth 6 and `δ = 0.05`, coverage rises from 0.213 to 0.440 (Markov) and
   0.707 (pairs). At depth 4 and `δ = 0.01`, Markov alone lifts it from 0.267
   to 0.713, because halving the arity term is decisive where that term
   barely exceeds `δ`. At depth 8 and `δ = 0.2`, pairs certifies 0.247
   against 0.017.
3. **Tightness: confirmed in direction.** Mean bounds fall severalfold,
   while the observed error stays at zero, so the bound remains conservative.
4. **Compute: confirmed.** Pairs spends 2.4–10× less than the certificate
   account where both answer, and Markov 10–57% less. Words whose arity is
   merely uncertain are no longer climbed.

When forced to answer, the pairs account also errs less (0.040 → 0.027 at
depth 4 and 0.223 → 0.163 at depth 6, at `δ = 0.2`). Its charges direct the
climbs to different words; why that helps the readings was not
investigated.

**Depth 8 is still limited, as §19.7 predicts.** On 30 depth-8 formulas,
the top rung gives `S ≈ 0.71` per formula, so `e₂ ≈ 0.28` alone exceeds
`δ = 0.2`. The evaluated words' restricted risk is about 0.02. Most readings
(18 of 30) do not parse even at the top rung. With the measured per-word
arity risk, the length limit `√(2δ) / ρ` is about 520 words, below the 575
of depth 8. Pairs helps only while `S < 1`. Beyond that, what limits depth
is the readers' arity error itself, not the account.

**Conclusion.** Prefix notation detects every single arity error, a fact
proved once in Lean and used by the evaluator alone. Crediting it turns the
arity term from linear in the number of words into half of that with no
premise, or quadratic under a premise of uncorrelated failures. The kernel
needed one generic change: certificates return per-item charges instead of
demands. That roughly doubles to triples certified coverage at depth 6,
cuts compute severalfold, and keeps every answered formula correct.

## 20. Higher-order experts and budgeted requests

### 20.1 What is missing

Experts can already ask the kernel for sub-results (§14): by delegation,
which replaces their output, or by continuation, which resumes with the
answer. Both are invisible to the planner, which has two costs:

1. **No cost up front.** A route's cost (§13) does not include what its
   experts will request, so the planner cannot choose the cheapest way to
   serve those requests, and cannot compare a route that delegates with one
   that does not.
2. **No recursion.** Requests terminate because the requester chain excludes
   every expert already in it (`RequestChain.length_le`). That also forbids
   an expert from asking its own question again on a smaller input, which is
   exactly what divide and conquer needs.

Two extensions address them:

- **slots**, sub-goals declared in the contract, which the planner fills
  and costs like any other goal;
- **budgets**, which replace chain exclusion as the termination argument
  for dynamic requests.

`map` is the first example of the first kind: a built-in combinator whose
body is a planned sub-goal. Slots make it one library expert among others.

### 20.2 Slots

A contract with slots (`HContract`, `lean/NCA/Slots.lean`) adds a list of
sub-goals `[a₁, …, aₖ] ⇒ b` to the inputs and output. A plan
`apply c fs ps` fills slot `i` with the plan `fs[i]` and input `j` with
`ps[j]`. The expert receives the fillings as functions and may call them
during its invocation. It never learns which experts implement them.

**Typing** (`HTyped`). It extends §1 with one premise. A slot filling must be
a well-typed plan from *exactly the slot's inputs* to the slot's output:

| Rule | Premises | Conclusion |
|---|---|---|
| given | `t ∈ avail` | `given t : t` |
| apply | `lib c`; `fs[i] : sᵢ.out` under inputs `sᵢ.in`; `ps : c.inputs` under `avail` | `apply c fs ps : c.output` |

A filling cannot read the surrounding task's inputs, only what the expert
passes it. As with `map`'s body, this is what lets the kernel plan it
separately.

The library is a predicate, not a list, so that it can contain families
such as `map` at every pair of types.

**Theorem** (`HTyped.mono`). Installing experts never invalidates a plan.

### 20.3 `map` is a higher-order expert

`map` at element types `a`, `e` is the contract `mapContract a e` with slot
`[a] ⇒ e`, input `seq a` and output `seq e`. It calls its slot once per
element.

**Theorem** (`embed_wellTyped`). Every plan well-typed in the sense of §1 is
expressed by a plan in which `map` is a library expert with zero own cost
and call bound `L`. The new plan has the same type and the same cost on
sequences of length `L`.

So nothing is lost by removing `map` from the kernel. Other combinators
become experts of the same form, each declaring its call bound:

| expert | slots | inputs → output | calls per slot |
|---|---|---|---|
| `map` | `[a] ⇒ e` | `seq a → seq e` | `L` |
| `fold` | `[s, a] ⇒ s` | `s, seq a → s` | `L` |
| `filter` | `[a] ⇒ bool` | `seq a → seq a` | `L` |
| fallback | `[x] ⇒ y`, `[x] ⇒ y` | `x → y` | 1 and 1 (expected: 1 and `P(unsure)`) |

The fallback expert is the confidence cascade of §14. As a hand-written
module it hard-codes its two recognizers. As a higher-order expert its two
recognizers are fillings, chosen by the planner.

### 20.4 Cost

An expert `c` costs `κ c` per invocation and calls each slot at most `ν c`
times per invocation. Then

> `cost(apply c fs ps) = κ c + ν c · Σᵢ cost(fs[i]) + Σⱼ cost(ps[j])`.

`map` has `κ = 0` and `ν = L`, recovering §13.

**Theorem** (`HPlan.cost_le_pow`). If `1 ≤ N` and every expert calls its
slots at most `N` times, a plan costs at most `N^nest` times its cost with
every slot called once. Here `nest` is the slot nesting depth, the largest
number of fillings enclosing an expert.

With `N = L`, plans whose fillings contain no further fillings are linear
in `L`, as in `Plan.cost_linear`. The polynomial degree of a composition is
visible from its shape before anything runs.

**Worst case and expected cost.** `ν` is a worst-case bound and certifies a
budget. Many higher-order experts call their slots lazily. Fallback calls its
second slot only when unsure, and a short-circuit `and` calls its second
operand only when the first is true. If a filling's cost does not depend on
whether or how often it is called, linearity of expectation gives

> `E[cost(apply c fs ps)] = κ c + Σᵢ E[Nᵢ] · cost(fs[i]) + Σⱼ cost(ps[j])`,

with `Nᵢ` the number of calls to slot `i`. An expert may therefore declare
two numbers per slot:

- the bound `ν`, used for budgets and guarantees;
- the expected number of calls `ν̄`, used as the planner's cost objective.

For fallback, `ν̄ = (1, P(unsure))`, which is `cascade_expected_cost`.

### 20.5 Planning with slots

A slot is a sub-goal whose available inputs are the slot's inputs. That is
the situation of `map`'s body, so the planner's state `(available, type,
depth)` is unchanged. An expert with slots spawns one sub-goal per slot,
alongside one per input.

**Theorem** (`HPlan.cost_mono`, optimal substructure). Cost is monotone in
the cost of every filling and every argument. Replacing either by a cheaper
plan of the same type never makes a plan dearer.

**Consequences.**

1. **Cheapest plans.** The cheapest filling of a slot is the cheapest plan
   for its sub-goal. It does not depend on the expert using it or on `ν`,
   because multiplying by `ν ≥ 0` preserves order. So the Bellman
   recursion of `planMin` (§13) extends with one term: an expert with slots
   costs `κ c + ν c · Σ` (cheapest fillings) `+ Σ` (cheapest arguments).
   Memoization keeps each sub-goal solved once. A slot whose sub-goal
   recurs (for example, `[glyph] ⇒ digit` in several experts) is planned
   once for all of them.
2. **Cheapest plans under an error target.** By the union bound, a filling
   called `ν` times contributes `ν` times its error. Dominance of
   (cost, error) pairs is invariant under scaling both by `ν > 0`. So each
   sub-goal's Pareto frontier, scaled, is the frontier of its contribution.
   The frontier recursion of `planPareto` extends unchanged: combine the
   scaled frontiers of the slots and arguments, then prune.
3. **Cascades built by the planner.** With fallback as an expert, the
   cheapest route within an error target may now be a cascade, and the
   planner picks both of its components. Before, a cascade was hand-built.
   Its expected cost `κ₁ + κ₂ · P(unsure)` enters the objective through
   `ν̄`. Its error is `P(C ∩ W₁) + P(Cᶜ ∩ W₂)` (`cascade_error_eq`). That
   error is a property of the pair, not a sum of per-filling errors, so the
   fallback expert declares it per filling pair from audit data.

### 20.6 Budgeted requests

Static slots cover requests whose shape is known before the input is seen.
Requests that depend on intermediate values, such as recursion on
subformulas, stay dynamic. For those, chain exclusion is replaced by a
budget (`serve`, `lean/NCA/Continuation.lean`):

- A question `q` is answered by an expert program `expert q`, a `Prog` of
  §14, whose invocation costs `κ q > 0`.
- The kernel pays `κ q` from the budget `b` before running it. If
  `κ q > b`, it refuses.
- The program's own questions are served recursively, with the budget that
  remains.
- No expert is excluded, so a program may ask its own question again.

The definition is accepted by Lean through well-founded recursion on the
budget, which strictly decreases with every invocation. That acceptance is
the termination proof: every run ends, recursive or not.

| Theorem | Statement |
|---|---|
| `serve_sound` | if every expert's program is safe for its question's specification, every answer is correct, at any budget and recursion depth |
| `serve_spent` | an answer leaves at most `b − κ q`: every invocation is paid from the budget |
| `Prog.runB_le` | serving a program's questions never increases the budget |

**Consequences.**

- With every invocation costing at least `κ_min`, a question served from
  budget `B` makes at most `B / κ_min` invocations. Its requests nest at
  most `B / κ_min` deep, and its total compute is at most `B`. All of this
  is known before it starts.
- A refusal is not an error. Out of budget, the kernel returns no answer.
  The consumer treats that like an unparseable reading: the controller
  climbs or abstains.

The two termination arguments coexist:

| argument | bounds | recursion |
|---|---|---|
| chain exclusion (§14) | chain length by library size | forbidden |
| budget | total cost by the budget | allowed |

The runtime already counts invocations against a budget. Measured in cost
units, with repeats in the chain allowed when a budget is set, it becomes
`serve`.

### 20.7 Predictions

1. **Exactness.** With `map` moved from the kernel into the library, routes,
   outputs and costs of the arithmetic tasks are identical (`embed_wellTyped`).
2. **Planner optimality.** The slot-aware cost and Pareto planners agree
   with exhaustive enumeration of searchable plans on random libraries,
   including libraries where the cheapest route uses a higher-order expert.
3. **Automatic cascades.** Given the digit recognizers and the fallback
   expert, the planner's cheapest route within the error target is the
   cascade that §14 built by hand, with matching cost and error.
4. **Budgets.** A recursive expert (one that asks its own question on
   subinputs) runs within its declared budget, and is refused rather than
   wrong when the budget is too small.

## 21. Decoding by the format

### 21.1 From detection to correction

§19 used the prefix format to **detect** arity errors: a reading that does
not parse is refused, and the controller climbs or abstains. At depth 8,
that is what limits coverage. Even at the top rung, 18 of 30 readings do not
parse, so the formula cannot be answered at any cost.

A refused reading is still evidence. Its words' arity distributions say
which arities are likely, and the format says which arity sequences are
possible. The posterior over *possible* sequences picks out the most
probable formula. An error-detecting code used this way corrects errors.

### 21.2 The model

For each word `k`, let `qₖ(a)` be the calibrated probability that its arity
is `a ∈ {0, 1, 2}`: the arity decision's grouped reading (§18.3), under that
decision's temperature. Let `L_m` be the set of arity sequences of formulas
with `m` words.

**Premise (P).** Given the readings, the posterior probability of an arity
sequence `a` is

> `π(a) = Πₖ qₖ(aₖ) · 1[a ∈ L_m] / Z`,  `Z = Σ_{a ∈ L_m} Πₖ qₖ(aₖ)`.

(P) holds exactly when two things are true:

1. words are corrupted and read independently given the truth (the channel
   corrupts each word separately, and each reader sees one word);
2. the prior over arity sequences is the readers' own per-word prior,
   restricted to the sequences that parse.

The second part is a modeling choice. The evaluator knows the format, but
not the process that generated the formulas. Complete alternating trees are
far more constrained than (P) assumes; for one thing, the word count
determines the tree's shape. Using that would hardcode the task's generator
into the expert, against the requirement that experts be generic. (P) uses
only the format, the least informative prior consistent with it. Whether
the resulting risks are calibrated is an empirical question (§21.8), and
risk control (§17) remains the backstop.

### 21.3 The format is a regular language

**Definition** (`await`, `lean/NCA/Decoding.lean`). The counter automaton
of prefix notation has states `some n`, meaning `n` subformulas are still
awaited, and a dead state `none`. A word of arity `a` read while `n + 1`
subformulas are awaited leaves `n + a` awaited. Reading anything when none
are awaited kills the run. A sequence is accepted when, started from one
awaited subformula, it ends with none awaited.

| Theorem | Statement |
|---|---|
| `await_code` | reading a formula's arity sequence consumes exactly one awaited subformula |
| `code_accepted` | every formula's arity sequence is accepted |
| `accepts_iff_codes` | a sequence of arities at most 2 is accepted from `n` awaited exactly when it is the concatenated arity sequence of `n` formulas |

So `L_m` is exactly the set of length-`m` words the automaton accepts. The
decoded sequence is therefore always a formula, and every formula is a
candidate.

### 21.4 Decoding by dynamic programming

For any deterministic automaton and position-wise weights `wₖ`, define the
score of a sequence as its weight product if accepted, else 0.

| Theorem | Statement |
|---|---|
| `dpSum_eq` | the sum-product recursion over states equals the total score of all sequences |
| `dpMax_ge` | with nonnegative weights, no sequence scores more than the max-product recursion |
| `dpMax_attained` | unless the maximum is 0, some sequence attains it; backtracking the maximizing choices finds it |

With `wₖ = qₖ`:

- `dpSum` from state `some 1` is `Z`;
- `dpMax` is `Πₖ qₖ(âₖ)` for the most probable parseable arity sequence
  `â`, the **decoded** sequence.

**Marginals.** Forward sums `F_k(n)` and backward sums `B_k(n)` over the
same states give each word's posterior arity distribution:

> `π(aₖ = a) = Σₙ F_k(n + 1) · qₖ(a) · B_{k+1}(n + a) / Z`.

Each is the sum-product theorem applied to a prefix and a suffix.

**Cost.** At position `k`, at most `min(k + 1, m − k)` subformulas can be
awaited and still be completed, because every awaited subformula needs at
least one more word. That leaves about `m² / 4` live states, with three
arities each. Forward, backward and max passes then take about `2.25 m²`
multiply-adds.

| depth | words | decoding ops | bottom-rung reading | top-rung reading |
|---:|---:|---:|---:|---:|
| 6 | 143 | 46k | 93k | 14.9M |
| 8 | 575 | 744k | 374k | 59.8M |

Decoding costs at most about 1% of a top-rung pass. It is computed once per
refinement step, in log space.

When the sequence of each word's most probable arity parses, it is `â`: it
maximizes the unconstrained product and is feasible. So decoding departs
from per-word decisions only where those decisions do not parse.

### 21.5 The risk of a decoded formula

Under (P), the decoded arity sequence is wrong with posterior probability
exactly

> `R = 1 − Πₖ qₖ(âₖ) / Z`.

**Theorem** (`exact_risk_le_union`, `one_sub_prod_le_sum`). Since `Z ≤ 1`,
`R ≤ 1 − Πₖ qₖ(âₖ) ≤ Σₖ (1 − qₖ(âₖ))`. Correction is never worse than the
union bound over the decoded arities.

Detection's bounds charged the probability that two or more arity
decisions fail, whether or not the failures leave a parseable sequence.
`R` counts only failures that do, and it conditions on the truth being a
formula, which §19.4 had to set aside.

**Identities.** Given the arity sequence, (P) makes the words' identities
independent. Word `k`'s identity is distributed as its reading restricted
to the group `âₖ`. So each word is decoded as the most probable class within
its decoded arity group. That pairs every word's identity with its own
arity, which resolves the objection of §18.3 to choosing groups by mass.
With `E` the words the decoded formula's least-risk certificate evaluates
(§19.5), and `rₖ` the restricted risks, the argument of `detected_error_le`
gives

> `P(wrong | readings) ≤ R + Σ_{k ∈ E} rₖ`.

### 21.6 Charges for refinement

Let `μₖ = 1 − π(aₖ = âₖ)` be word `k`'s posterior arity risk after decoding.
`μₖ` uses every other word's evidence through the format. A word whose
reading is uncertain can still have a small `μₖ` when only one arity fits
its neighbours.

**Errors come in pairs.** The truth and `â` are both formulas of `m` words,
so they differ in no position or in at least two (`code_no_single_change`).
Applied to the posterior measure, Markov's inequality on the number of
differing positions (`two_occur_le_half`) gives

> `R ≤ ½ Σₖ μₖ`.

The account charges word `k`

> `R · μₖ / Σⱼ μⱼ`, plus `rₖ` if `k ∈ E`.

The charges sum to the bound of §21.5. Refinement climbs the word with the
largest charge, the word most likely misread *given the format*, not merely
the least confident reading.

**Interface.** The certificate needs the calibrated distribution of the
arity decision, not only its risk. The controller already computes it to
obtain the risk. The generic change is to pass the consumer a calibrated
distribution for any grouped decision it names, alongside the risk.

### 21.7 Scaling

For words with arity risk `ρ` each and `S = mρ`:

- **detection:** abstains on every unparseable reading, whose probability
  approaches 1 as `S` grows past 1 (§19.9);
- **correction:** answers every reading, and charges `R`.

`R` is small when the competitors of `â` are improbable. The nearest
competitors differ in two positions, with opposite net arity change, so `R`
behaves like `e₂` restricted to cancelling pairs, divided by `Z`. Correction
therefore removes the hard limit `S < 1`, beyond which detection answers
nothing. What remains is the slower growth of the posterior weight of
cancelling pairs.

### 21.8 Testing the premises

Two premises are now in use. Each yields a prediction about counts over
independent formulas, which can be tested on held-out data.

**Calibration of `R` (premise P).** Over `N` formulas, let `O` be the number
whose decoded arity sequence is wrong. Under (P) with calibrated readings,
`O` is a sum of independent Bernoulli(`R_f`) variables, so
`E[O] = Σ_f R_f`. The test compares `O` with the Poisson-binomial
distribution of that sum (two-sided), overall and in bins of `R`. It runs at
the bottom rung, where errors are frequent enough to count, at depths 4 to
8 and under the noise shift.

**The pairs premise of §19.** Let `O₂` be the number of formulas whose
per-word reading has at least two arity failures. If failures are not
positively correlated, `E[O₂] ≤ Σ_f e₂(f)`. A one-sided Poisson-binomial
test rejects the premise if `O₂` is significantly larger. A direct check:
over pairs of words, the observed rate of joint arity failures against the
product of the marginal rates, for adjacent and for distant pairs
separately.

These replace the indirect evidence of §19.9 (no errors, so no
contradiction) with a test that can fail.

### 21.9 What correction cannot do: hard style

In the arithmetic task, the parser fixes the kind of every position:
digits at even positions, operators at odd ones (§14). A misread digit is
another digit, and a misread operator another operator. Either way, the
reading still parses. The format has no redundancy against such errors,
so neither detection nor correction has anything to work with.

Of the remaining hard-style errors:

- **Ambiguity between operators** (about 20%: `+` against `×` under
  rotation) lies inside a decision the format leaves free. Its Bayes risk is
  a floor: no reader, however strong, certifies such a glyph below it.
- **Erased digits** (7%), when the segmenter misses them, change the
  length's parity. Such readings do not parse and are already detected.
  When an erased digit is segmented but misread, it is an ordinary digit
  error.

For hard style, the efficient policy is to recognize early that a glyph's
risk cannot reach the target and abstain, rather than climb (§22).

### 21.10 Predictions

1. **Coverage.** Correction answers formulas whose readings do not parse.
   At depth 8, where 18 of 30 top-rung readings fail to parse, coverage
   rises well above detection's (0.247 at `δ = 0.2`), and readings refused
   for not parsing disappear.
2. **Error when forced.** The decoded formula is right more often than the
   per-word reading. Error when forced to answer falls at every depth, most
   at depth 8 (0.57 for pairs).
3. **Validity.** If (P) is calibrated (§21.8), the error among answered
   formulas stays within `δ`. (P) is the strongest premise used so far, so
   this is the prediction most likely to fail. Risk control under shift is
   the remedy if it does.
4. **Compute.** Decoding adds about 1% to a top-rung pass. Climbs go to
   words that are likely wrong given the format, so fewer are needed.

## 22. Abstaining early

### 22.1 The most expensive outcome

An abstention costs the most of any outcome. The controller climbs until no
item can be climbed, and only then gives up. At depth 8 and `δ = 0.01`, the
pairs account spent 59.4M FLOPs per formula, nearly the 59.8M of top rungs
everywhere, to answer 0.7% of formulas (§19.9). Compute spent on a formula
that will be refused anyway is wasted.

### 22.2 Selection never breaks the guarantee

Each answered formula's bound is at most `δ`, so its posterior error is at
most `δ`. A policy that abstains on some of these formulas, deciding from
observed readings only, leaves every remaining answer's guarantee intact. So
early abstention trades coverage for compute and never costs validity. The
only question is which formulas to give up on, and when.

### 22.3 Sound floors

A **floor** is a lower bound on every bound refinement can still reach. If
the floor exceeds `δ`, refinement would end in abstention anyway, so
abstaining at once changes no answer and saves the remaining climbs.

Readings at the top rung never change. Call those words *fixed*.

- **Detection accounts.** `min(S / 2, e₂)` is monotone in the arity risks
  (`detection_account_mono`). Setting every open word's risk to zero gives
  the floor `min(S_F / 2, e₂(F))` over the fixed words `F`. Within-group
  charges are nonnegative, and an unparseable reading has bound `∞`, so
  every reachable bound is at least this floor.
- **The certificate account of §18.** Every word is charged at least its
  arity risk, so `Σ_{k ∈ F} ρₖ` is a floor.
- **Static and demand accounts (arithmetic).** The bound is a sum of
  nonnegative charges, and a fixed item's charge no longer changes. The sum
  over fixed items is a floor.

The consumer declares its floor, alongside its certificate, from the
readings, the risks and the set of fixed items. The controller abstains as
soon as the floor exceeds `δ`. Answers are identical. Only the value
reported for an abstained formula (the "forced" value of the experiments)
can differ, because it comes from an earlier reading.

**Correction has no such floor.** `R` is not monotone in the open words'
risks. An open word becoming certain can rule out the competitor that made
a fixed word uncertain. For the correction account, early abstention must be
predictive.

### 22.4 Predictive abstention

For any account, let `s` be the controller's state after a step, and let
`A` be the event that refinement eventually answers. A stopping policy
trades coverage against compute. The policy that maximizes coverage minus
`λ` times compute stops at `s` when

> `P(A | s) < λ · E[remaining cost | s]`.

Both terms are estimated on calibration formulas from a few features of the
state: the ratio of bound to `δ`, the charge mass on open words, and the
cost already spent. Since selection never breaks the guarantee (§22.2),
estimation errors cost only coverage or compute, never validity. Varying `λ`
traces the coverage–compute frontier. The sound floors of §22.3 are its
zero-loss end.

### 22.5 Predictions

1. **Identical answers under sound floors.** For the detection, certificate
   and arithmetic accounts, early abstention by floor gives the same answers
   with less compute.
2. **Savings where abstention dominates.** Savings are largest at depth 8
   and strict targets. At about `10⁻³` arity risk per fixed word, the pairs
   floor reaches `δ = 0.01` once roughly 140 words are fixed, against 575
   climbed now. That predicts several-fold less compute on abstained
   formulas.
3. **Hard style.** Glyphs whose top-rung risk alone exceeds `δ` end
   refinement at once. That accounts for most of the compute saved on hard
   expressions.

### 22.6 Results

`refine` takes a consumer's `floor(readings, risk, fixed)`, or, for the
default additive account, sums the fixed items' charges
(`additive_floor`). `FormulaEvaluator.floor` implements §22.3. For the
certificate account it charges each fixed word the smaller of its full and
arity risks, because under separately fitted temperatures either may be the
smaller (§18.3). A generic stopping rule (`nca.ladder.stopping_rule`) bins
refinement states by `log₁₀(bound / δ)`. It abstains in a bin where the
fraction of fitted states that went on to answer is below `λ` times their
mean remaining cost.

**Formulas** (`nca.logic --floors`, setup of §19.9): compute per formula in
kFLOPs, without and with floors.

| depth | δ | certificate | Markov | pairs |
|---:|---:|---:|---:|---:|
| 4 | 0.2 | 370 → 181 | 322 → 180 | 124 → 124 |
| 4 | 0.05 | 608 → 132 | 559 → 96 | 162 → 128 |
| 4 | 0.01 | 2719 → 1697 | 1158 → 247 | 274 → 193 |
| 6 | 0.2 | 6721 → 2619 | 4798 → 2377 | 2833 → 2450 |
| 6 | 0.05 | 11864 → 2876 | 8514 → 837 | 4497 → 2595 |
| 6 | 0.01 | 14892 → 1738 | 13302 → 616 | 6764 → 2201 |
| 8 | 0.2 | 58883 → 4127 | 54236 → 3545 | 45391 → 15542 |
| 8 | 0.05 | 59800 → 728 | 59614 → 731 | 55227 → 3026 |
| 8 | 0.01 | 59800 → 550 | 59800 → 547 | 59426 → 1612 |

Every row answered the same formulas with the same values, all 27 of them.
On abstained formulas the compute falls, for example, from 59,862 to 20,239
(pairs, depth 8, `δ = 0.2`) and from 59,805 to 1,602 (pairs, depth 8,
`δ = 0.01`).

**Arithmetic** (`nca.selective --floors`, additive floor, 300 expressions
per length): MFLOPs per expression.

| glyphs | δ = 0.2 | δ = 0.05 | δ = 0.01 |
|---:|---:|---:|---:|
| 3 | 11.6 → 10.7 | 18.2 → 13.8 | 29.6 → 19.4 |
| 15 | 114 → 70 | 232 → 84 | 424 → 106 |
| 63 | 1785 → 328 | 2720 → 356 | 3204 → 367 |

Answers are again identical in every row. With `--hard` (same library and
calibration, hard-style test expressions), compute falls from 93 to 45 MFLOPs
(3 glyphs, `δ = 0.2`), from 767 to 117 (15 glyphs, `δ = 0.01`) and from
3227 to 339 (63 glyphs, every `δ`), with identical answers.

**Predictive abstention** (pairs, depth 8, rule fitted on 150 validation
formulas): coverage and kFLOPs per formula, compared with floors alone.

| δ | floors | λ = 10⁻¹⁰ | λ = 10⁻⁸ | λ = 3·10⁻⁸ | λ = 10⁻⁷ |
|---:|---|---|---|---|---|
| 0.2 | 0.247, 15542 | 0.163, 1246 | 0.163, 1246 | 0.097, 651 | 0.043, 384 |
| 0.05 | 0.080, 3026 | 0.050, 1064 | 0.000, 413 | 0.000, 377 | 0.000, 374 |

No answered formula was wrong at any `λ`.

Against the predictions of §22.5:

1. **Identical answers: confirmed.** All 27 formula rows and all 9
   arithmetic rows, plus the 9 hard-style rows, answered exactly the same
   inputs with the same values.
2. **Savings where abstention dominates: confirmed, and larger than
   predicted.** At depth 8 compute falls 14× (certificate, `δ = 0.2`) to
   109× (certificate and Markov, `δ = 0.01`), and 37× for pairs at
   `δ = 0.01`. The prediction that about 140 words must be fixed was too
   pessimistic. The controller climbs the riskiest words first, whose
   top-rung arity risks are well above the average `10⁻³`. So the pairs floor
   passes `δ = 0.01` after about a dozen climbs (1.6M FLOPs on abstained
   formulas, against 0.37M for the bottom pass). The floor is weakest for
   pairs at loose targets: `min(S_F / 2, e₂)` is quadratic in `S_F`, so at
   depth 4 and `δ = 0.2` it never reaches `δ` and saves nothing.
3. **Hard style: confirmed for compute, but calibration fails.** At 15 and
   63 glyphs, floors cut compute by 6.5× and 9.5× at strict targets. They
   cannot repair what hard style breaks. This library's recognizers are not
   the normalized ones of §15, and its ladders are calibrated on the
   standard style, so the error
   among answered expressions is far above `δ` (0.40 at 3 glyphs,
   `δ = 0.2`), the shift failure of §17. Floors make that failure cheap, not
   correct.

**Predictive abstention.** The frontier is coarse. With 150 fitted formulas
most bins contain no state that went on to answer, so any `λ > 0` stops in
them. Its first step is still useful: at `δ = 0.2` it keeps two thirds of
the coverage (0.163 of 0.247) for one twelfth of the floors' compute (1.2M
against 15.5M FLOPs). Every answer stays within its bound, as §22.2
guarantees.
