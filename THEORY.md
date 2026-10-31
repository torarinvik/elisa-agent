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

**Eviction.** Least-recently-used eviction thrashes when tasks whose routes
together exceed the budget alternate: every switch reloads the evicted
recognizer. Route-aware eviction, which keeps the experts of upcoming routes,
is the corresponding refinement.

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
within an error target is read off. Both planners are tested against
exhaustive enumeration of all searchable plans.

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
