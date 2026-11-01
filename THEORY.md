# Theory

Mathematical foundations of the agent: composing modules, planning routes,
answering selectively under a risk target, and decoding by the input format.
Theorems are numbered by section.

## 1. Types and contracts

Semantic types `Ty` are abstract, with decidable equality and a sequence
former: `seq : Ty → Ty`, recognized by a partial inverse `elem?` with
`elem? u = some t ↔ u = seq t`.

A **contract** is a list of input types and one output type. Modules are known
to the system only through their contracts; two values are compatible exactly
when their types are equal.

A **plan** is a composition graph:

| Plan | Meaning |
|---|---|
| `given t` | a task input of type `t` |
| `apply c ps` | contract `c` applied to the outputs of sub-plans `ps` |
| `map a body src` | `body` run on each element (of type `a`) of the sequence `src` produces; inside `body` the element is the only input |

**Well-typedness** `WellTyped lib avail p t`: `p` uses
only installed contracts `lib` and available inputs `avail`, and produces `t`.

| Rule | Premises | Conclusion |
|---|---|---|
| given | `t ∈ avail` | `given t : t` |
| apply | `c ∈ lib`, `ps : c.inputs` pointwise | `apply c ps : c.output` |
| map | `body : e` under inputs `[a]`, `src : seq a` | `map a body src : seq e` |

**Theorem 1.1 (monotonicity).** If `lib ⊆ lib'`, every plan
well-typed under `lib` is well-typed under `lib'`. Installing modules never
invalidates an existing valid composition.

## 2. Planning

`plan lib avail n t` searches
backward from the goal with depth bound `n`:

1. If `t ∈ avail`, return `given t`.
2. Otherwise try contracts in installation order; the first `c` with
   `c.output = t` whose inputs are all plannable at depth `n - 1` wins.
3. Otherwise, if `t = seq e`, try each candidate element type `a` (elements of
   sequence types that are available or produced by some contract, in that
   order); succeed when `e` is plannable from `[a]` and `seq a` from `avail`.

**Derivability** `Derivable lib avail n t` is the specification: a composition
of depth at most `n` exists (for `map`, with `a` a candidate element type).

**Theorem 2.1 (soundness).** `plan lib avail n t = some p` implies
`WellTyped lib avail p t`.

**Theorem 2.2 (completeness).** `Derivable lib avail n t` implies
`plan lib avail n t` succeeds.

**Type checking.** `infer lib avail p`
computes the type a plan produces: `given t` needs `t ∈ avail`; `apply c ps`
needs `c ∈ lib` and the argument types to equal `c.inputs`; `map a body src`
needs `body` to type-check under `[a]` and `src` to produce `seq a`.

**Theorem 2.3 (decidability).** `infer lib avail p = some t ↔
WellTyped lib avail p t`. Plans not produced by the planner, such as
hand-written pipelines and proposed upgrades, are admitted by checking.

## 3. Routing stability

The add-and-freeze protocol requires that installing a module does not
change how already solved tasks are solved.

**Theorem 3.1 (instability).** The plain planner is not stable.
With `need1 : [x] → g`, `from2 : [y] → g`, input `y`, the planner routes `g`
through `from2`; installing `make1 : [y] → x` makes the higher-priority
`need1` applicable and the route changes, although the old route remains valid.

**Generation-layered planning** `planStable`: plan with the first `k`
installed contracts, for the smallest `k = 0, 1, …, |lib|` that succeeds.

**Theorem 3.2.** Layered planning is
sound and complete in the same sense as `plan`.

**Theorem 3.3 (stability).** If `planStable lib avail n t`
succeeds, then `planStable (lib ++ extra) avail n t = planStable lib avail n t`
for every `extra`.

Cost: at most `|lib| + 1` planner runs per goal; results can be cached per
installation generation.

## 4. Compositional reliability

Let an execution consist of finitely many invocations `i`, invocation `i`
failing on an event `fail i` with `μ(fail i) ≤ εᵢ`, and suppose the
**propagation hypothesis**: if no invocation fails, the result is correct
(`⋂ᵢ (fail i)ᶜ ⊆ correct`). Exact modules (parsers, arithmetic) have
`εᵢ = 0`.

**Theorem 4.1 (union bound).** For any measure,
`μ(correctᶜ) ≤ Σᵢ εᵢ`.

**Theorem 4.2 (independent product bound).** If μ
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

**Definition (`ShiftBound ν ν₀ δ`).** `ν(s) ≤ ν₀(s) + δ` for every measurable
`s`. For probability measures this is equivalent to total variation distance
at most `δ`.

**Theorem 5.1 (shifted composition bound).** If
invocation `i` receives `gᵢ(ω)`, fails on `Bᵢ`, has offline failure rate at
most `εᵢ`, and `ShiftBound (gᵢ)_*μ ν₀ᵢ δᵢ`, then under the propagation
hypothesis `μ(correctᶜ) ≤ Σᵢ (εᵢ + δᵢ)`.

**Theorem 5.2.** There are probability measures and
a failure set with offline failure rate 0 and in-situ failure rate 1. Offline
rates alone bound nothing; the shift term cannot be dropped.

**Theorem 5.3.** Every valid shift bound satisfies
`δ ≥ ν(B) − ν₀(B)`. The measured excess of in-situ over offline failure rate is
therefore a lower bound on the distribution shift the composition induces,
and can be measured per module.

Design consequence: an upstream module's output convention is part of the
downstream module's contract. A segmenter that centers crops differently from
the recognizer's training data is type-correct but induces a shift `δ` that
the composition pays for in full.

## 6. Algorithms of the handwritten-arithmetic pipeline

**Symbol fusion.** With operator
distribution `q` over `{+, −, ×, none}` and digit distribution `p`:
`P(op) = q_op`, `P(d) = q_none · p_d`. The result is a probability
distribution over the 13 symbols whenever `p` and `q` are.

**MAP parsing.** The grammar `digit (op digit)*` fixes the
class of each position. Under independent per-position distributions the
probability of a token string factorizes, so the most probable well-formed
expression is the per-position argmax restricted to the position's class.
Even-length sequences have no parse.

**Evaluation** (`Evaluator`). `×` binds tighter than `+` and `−`; terms are
accumulated left to right.

**Comparison chains.** `a₀ r₁ a₁ … rₖ aₖ` is true iff
every adjacent relation `aᵢ₋₁ rᵢ aᵢ` holds.

## 7. Measuring accumulation

For deterministic modules, an unchanged route implies identical answers, so
Theorem 3.3 predicts **zero changed answers** on every previously
covered task. The changed-answer count is the stricter regression metric:
equal accuracy can hide offsetting changes; zero changed answers cannot.

Stability is a guarantee about *unrequested* change. It also means a newly
installed module never improves an already covered task on its own: adopting
a better route must be an explicit, evaluated decision (for example,
reordering or replacing modules after comparing both routes on the suite),
not a side effect of installation.

## 8. Explicit route upgrades

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

## 9. Module substitution

Plans refer to modules only through contracts, so replacing a module by one
with an identical contract leaves every
plan's shape and type unchanged; `infer` confirms the substituted route still
type-checks. Behavior is what changes.

Let `disagree i` be the event that invocation `i` of the substitute gives a
different decision than the original's, with in-situ probability at most `dᵢ`,
and suppose the answer can change only if some such invocation disagrees.

**Theorem 9.1.** `P(answer changes) ≤ Σᵢ dᵢ`.

**Theorem 9.2.** If original-correct and unchanged imply
substitute-correct, then `P(correct) ≤ P(correct′) + P(answer changes)`.

**Theorem 9.3.** Hence
`P(correct′) ≥ P(correct) − Σᵢ dᵢ`.

The bound is only as tight as the choice of events. Every invocation of the
substitute is a valid event set, but the arithmetic parser reads digit
distributions only at even positions and only through their argmax, so the
answer changes only if an even-position invocation's argmax disagrees.
Restricting `disagree` to those invocations keeps the hypothesis true and
removes the substitute's (irrelevant) disagreements on operator glyphs.
Choosing the smallest event set that still covers every way the output can
change is how a composition's structure tightens its guarantees.

## 10. Complementarity

The mixed task `a op b rel c` requires arithmetic and comparison together.
Systems are compared by the composition gain
`G = Q(A⊕B) − max(Q(A), Q(B), Q(A+B), Q(baselines))` on held-out inputs, where
`A⊕B` adds integration modules to the installed capabilities and the
baselines are the majority class and a monolithic model trained on the task.

**Product-of-experts fusion.** With operator distribution
`q`, relation distribution `r` (each including a "none of mine" outcome) and
digit distribution `p`: `P(op) ∝ q_op r_none`, `P(rel) ∝ r_rel q_none`,
`P(d) ∝ q_none r_none p_d`. This treats the two recognizers as independent
evidence; unlike the two-recognizer fuser it is an assumption, not an
identity.

**Constrained MAP parsing.** Grammar
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

**Accuracy intervals.** For `k` successes in `n` samples
the 95% Wilson score interval is
`(p̂ + z²/2n ± z·√(p̂(1−p̂)/n + z²/4n²)) / (1 + z²/n)` with `z ≈ 1.96`. It stays
inside `[0, 1]` and remains accurate near 0 and 1, where accuracies cluster.

**Paired differences.** Systems are compared
on the same samples, so their difference is estimated from per-sample
differences `dᵢ = 1[second correct] − 1[first correct]`: mean `d̄`, interval
`d̄ ± z·s_d/√n`. Shared successes and failures contribute zero, which makes the
interval far narrower than one derived from two independent accuracy
intervals.

## 12. Lazy loading and scalable discovery

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

By Theorem 12.13, a task sequence costs only at route changes, so the
remaining lever is the number of changes: independent tasks grouped by route
switch once per route. Least-recently-used eviction is not optimal in general:
when one route runs a shared expert first and the next route runs its own
expert first, recency marks the shared expert as the victim, and it is
reloaded at once.

## 13. Efficiency

**Goal.** Cost proportional to a task's dependency structure, not to the size
of the library or to all pairs of inputs. For local, compositional tasks that
means linear in input length and constant in library size; quadratic cost
should appear only in modules whose contracts require all-pairs interaction,
and only there.

**Cost model.** Each contract costs `κ(c)` per
invocation . On
sequences of length `L`:
`cost(given t) = 0`, `cost(apply c ps) = κ(c) + Σ cost(pᵢ)`,
`cost(map a body src) = L · cost(body) + cost(src)`.
Cost is additive by definition: a composition has no interaction term between
its modules.

| Theorem | Statement |
|---|---|
| 13.1 | `cost_L(p) ≤ (L + 1)^nest(p) · cost_1(p)`: polynomial degree is the map nesting depth |
| 13.2 | plans without nested maps cost at most `(L + 1) · cost_1(p)`: linear in length |
| 13.3 | installing modules never changes the cost of an existing route |

Together with Theorem 12.2 (§12), a task's cost and memory are
independent of library size.

**Minimum-cost planning**.
`planMin` keeps, at every type and depth, the cheapest candidate: a Bellman
recursion over the AND/OR structure of plans (a type needs *one* producer; a
producer needs *all* its inputs). *Searchable* plans are the well-typed plans
whose map elements are candidate element types, the space the planner
enumerates.

| Theorem | Statement |
|---|---|
| 13.4 | the returned plan is well-typed and its cost is the reported cost |
| 13.5 | it costs at most any searchable plan of smaller depth |

With memoization the recursion visits each `(available, type, depth)` once.
Minimizing total compute is polynomial; minimizing the number of *distinct*
experts (memory) is a set-cover problem and is handled as a constraint, not an
objective.

**Cost under an error target.** By the union bound
(§4) a route's error is at most the sum of its invocations' failure rates, so
error composes exactly like cost, with map bodies counted `L` times. The
planner keeps the Pareto frontier of non-dominated (cost, error) pairs at each
type; combining sub-goal frontiers and discarding dominated results yields the
exact frontier for two additive objectives, from which the cheapest route
within an error target is read off. Since error composes like cost, a plan's
error bound is `p.cost ε L` for per-invocation failure rates `ε`, and the
recursion is `planMin` with `best` replaced by dominance pruning
:

| Theorem | Statement |
|---|---|
| 13.6 | pruning dominated options loses nothing: every option is dominated by a survivor |
| 13.7 | every option is a well-typed plan with its reported cost and error bound |
| 13.8 | every searchable plan within the depth bound is dominated by a returned option |
| 13.9 | if a searchable plan meets error target `τ`, a returned option meets it at no greater cost |

**Length–accuracy coupling.** Every route's cost and error bound grow linearly
in `L`, so the cheapest expert meeting a fixed target changes with length, and
beyond some length no route meets it. The planner reports infeasibility
rather than silently degrading. Keeping error constant as inputs grow
requires per-glyph failure rates falling as `1/L`, or redundancy and
refinement (sub-goal requests) spent where uncertainty is high.

**Comparison with attention.** A transformer over `T` tokens of width `d` with
`ℓ` layers costs about `ℓ(24Td² + 4T²d)` floating-point operations; the
quadratic term dominates once `T > 6d`. At glyph granularity and moderate
lengths the linear term dominates and costs are comparable; at
image-patch granularity the quadratic term dominates and cost grows
superlinearly. The modular pipeline's cost is proved linear at every length.

## 14. Kernel-mediated requests and refinement

Modules never invoke one another. A module may return a `Request` instead of
its output, delegating that output to the kernel: "produce a value of this type
from these inputs, without me". The kernel plans the request over the
installed modules minus every module in the current request chain, executes it
under the same budget, records it in the workspace, and uses its result as the
requester's output.

| Theorem | Statement |
|---|---|
| 14.1 | a resolved request is a well-typed plan producing the requested type from the request's inputs |
| 14.2 | it never invokes a module in the request chain |
| 14.3 | every chain of nested requests is at most as long as the number of installed modules, whatever the budget |

Termination follows from freshness: each new requester is a module of a plan
resolved with the chain excluded, so the chain has no repeats and is bounded
by the library.

**Confidence-triggered refinement.** A cheap module answers when confident
(event `C`) and otherwise requests refinement, served by a fallback. With
`W₁`, `W₂` the cheap and fallback error events, the composite errs exactly on
`(C ∩ W₁) ∪ (Cᶜ ∩ W₂)`.

| Theorem | Statement |
|---|---|
| 14.4 | `P(error) = P(C ∩ W₁) + P(Cᶜ ∩ W₂)` |
| 14.5 | if `P(C ∩ W₁) ≤ P(C ∩ W₂)` (confidence is selective), the composite is at least as accurate as the fallback alone |
| 14.6 | expected cost is `κ₁ + κ₂ · P(Cᶜ)` |

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
| 14.7 | `P(error, gated) ≤ P(error, ungated) + P(Cᶜ ∩ Gᶜ ∩ R)`: gating costs at most the relevant requests it skips |
| 14.8 | if the gate is sound (`R ⊆ G`), gated and ungated refinement err exactly equally |
| 14.9 | gated refinement costs `κ₁ + κ₂ · P(Cᶜ ∩ G)` |

Requests are therefore resolved lazily: a pending request is decided when
its value is consumed. The *consumer* supplies the gate, since only the reader
knows what it reads. A gate judged from provisional values is in general not
sound, and its cost is the extra term of Theorem 14.7.

**Demand-driven evaluation (a sound gate).** Soundness is easy to obtain when
the gate comes from what a consumer provably reads rather than from what a
value looks like. A *readable* type pairs values `V` with demands `D` and, for
each demand, an agreement relation `v ≈_d v'` ("`v` and `v'` look the same to a
reader with demand `d`"). A module `f : V → W` with demand map `δ : D_W → D_V`
is *demand-sound* when `v ≈_{δ d} v'` implies `f v ≈_d f v'`: whatever the
module's input differs in outside `δ d` cannot be seen in its output under `d`
.

| Theorem | Statement |
|---|---|
| 14.10 | demand-sound modules compose: `g ∘ f` is sound with `δ_f ∘ δ_g` |
| 14.11 | modules on a pair are sound when each component's demand is |
| 14.12 | `map f` is sound on lists with per-element demand `(i, n) ↦ δ (d i n)` |
| 14.13 | at a top demand under which agreement is equality, agreeing inputs give equal answers |

So inputs whose demand is empty can be replaced by anything, in particular
never computed, and the answer is unchanged. Skipping the requests raised for
them is therefore a sound gate: by Theorem 14.8, gated and
ungated refinement err exactly equally.

**Continuation requests.** Delegation replaces the requester's output; an
expert that needs a sub-result and then keeps computing is instead a program
over questions:
`Prog := pure a | ask q (k : A q → Prog)`, composed by `bind`. The kernel is a
handler `h q : Option (A q)` (no route is `none`); `run h p` returns the result
and the number of requests made. Each question `q` has a specification
`R q a`, and `Safe R post p` holds when `p` meets `post` whatever correct
answers it receives.

| Theorem | Statement |
|---|---|
| 14.14 | a handler returning only correct answers gives results meeting `post` |
| 14.15 | a sequence is safe when the first program establishes what the continuation needs |
| 14.16 | a program of question depth `n` makes at most `n` requests on any run |
| 14.17 | depths add under `bind` |

Continuations are needed when the sub-result has a different type from the
output, which delegation cannot express (for example, splitting a value and
requesting each part).

## 15. Normalization against shift

**Theory.** A normalizer `N : X → Y` is a module
placed before a recognizer, which is then trained and evaluated on normalized
inputs. A style shift is a map `T` applied to reference inputs, so the shifted
distribution is `T_*ν₀` and the recognizer sees `N_*T_*ν₀` instead of `N_*ν₀`.

| Theorem | Statement |
|---|---|
| 15.1 | normalization never increases a shift (data processing) |
| 15.2 | if `N ∘ T = N` on `G`, the normalized shift is at most `ν₀(Gᶜ)` |
| 15.3 | if `N ∘ T = N` everywhere, the shift is removed |

With §5 this gives the design rule: a normalizer pays off exactly to the
extent that it undoes the style, and no normalizer can help where the style
destroys the information that separates classes (then `N(T x) = N(T x')` for
`x`, `x'` of different classes, and any recognizer after `N` errs on one of
them).

## 16. Knowing when to be unsure

**Problem.** A long expression is answered correctly only if every glyph is
read correctly, so with per-glyph error `ε` the answer error grows like
`1 − (1 − ε)^L`: about 47% at `L = 63` for `ε = 0.01`.
Errors cannot be corrected without redundancy, but they can be *located*:
calibrated confidences say which glyphs are doubtful, compute can be spent
there, and the system can decline to answer when doubt remains.

**Theory.** Each input carries an error bound
`b`, the sum of its glyphs' calibrated error probabilities `1 − max p`
(union bound, §4). Refining glyph `i` costs `κ i` and lowers the bound by
`β i`.

| Theorem | Statement |
|---|---|
| 16.1 | if the true error probability is at most `b` and only inputs with `b ≤ δ` are answered, the error rate among answered inputs is at most `δ` |
| 16.2 | for a price `λ` per unit of compute, refining exactly `{i : λ κ i ≤ β i}` minimizes bound plus priced compute over all refinement sets |
| 16.3 | if every item's risk is at least `ρ`, a bound of at most `δ` needs `n · ρ ≤ δ`: holding `δ` as inputs grow needs floors shrinking like `1 / n` |

So the efficient policy is local: refine a glyph when its expected bound
reduction pays for its cost, and sweep `λ` (equivalently the target `δ`) to
trade compute for reliability.

**Decision demand.** What of an input can change the consumer's *decision*,
not only its value, is a demand too. Readings need to enter the bound only
where decision-demanded. Agreement on decisions is coarser than agreement on
values, so this is demand-soundness for a coarser reader
. The fuser's operator input only
rescales digit entries by `q_none`, and a positive rescaling leaves the digit
argmax unchanged, so while `q_none > 0` digit decisions need the digit reading
alone and operator decisions the operator reading alone.

**Decision-relative risk.** A decision may range over only some of a
reading's classes: at an operator position the parser chooses among
operators, never "not an operator". With `C` the classes it ranges over, the
item's risk becomes the error probability of that restricted decision,
`1 − max_C p / Σ_C p`. When the most probable class lies in `C` this never
exceeds `1 − max p` (Theorem 16.4), so the bound only tightens.
Renormalizing the full output's calibrated probabilities does not calibrate
the restricted decision, which can be over-confident. Each rung therefore
fits a separate temperature per restricted decision, on the held-out inputs
whose label is among its classes.

**Practice queue.** Abstentions
and doubtful glyphs show where the library is weakest. In use, glyphs with
calibrated risk `r ≥ θ` are queued for a teacher's label.

| Theorem | Statement |
|---|---|
| 16.5 | each queued label is expected to correct at least `θ` errors |
| 16.6 | at most `θ` expected errors per unqueued glyph escape the queue |
| 16.7 | the queue holds all but `θ · n` of the expected errors among `n` glyphs |
| 16.8 | drawing glyphs with probability `∝ r` finds `Σ r² / Σ r ≥ Σ r / n` expected errors per label, never fewer than random labels |

## 17. Calibration under distribution shift

### 17.1 The problem

Theorem 16.1 promises that the error rate among answered inputs is at
most `δ`, under one premise: the bound is valid, `q(x) ≤ b(x)` for every
input `x`, where `q(x)` is the true probability that the answer to `x` is
wrong and `b(x)` the controller's bound. The bound is a sum of calibrated
per-item risks, and calibration is *fitted*. Temperatures minimize negative
log-likelihood on held-out data from a reference distribution `P`, which
makes risks right *on average over `P`*. It makes them neither pointwise
valid nor right on average over the distribution `Q` met in use.

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
(Theorem 17.1):

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
  grows by at most `W` (Theorem 17.2). A deficit measured on `P` thus
  bounds the deficit on `Q` up to the factor `W`, which is unknown in
  practice and can be large.

### 17.3 Why reference data alone cannot suffice

Fix any procedure that maps reference data to a bound `b`. Take two
deployment distributions `Q₁` and `Q₂` with the same inputs as `P` but
different labels on a set `S` of inputs that `b` answers. On `S` the true
error probabilities differ, while `b` is the same for both, because it never
saw `Q`. The bound cannot be valid for both unless it declines `S`. Pushed to
the limit, this is Theorem 5.2 (§5): a module that never fails
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
unbiased for its population value (Theorem 17.3). The second option
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
bound function the answered sets are nested (Theorem 17.4), and
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
order, and stop at the first one not declared safe. By Theorem 17.5:

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
before reaching anything useful. The audit is therefore split: one
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

**Theorem 18.1.** If the chosen
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

**Theorem 18.2.** For any
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

**Trees.** Formula trees carry an annotation at each node
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
| 18.3 | if `c` is valid for `r` and `t` agrees with `r` on `c`, then `t` and `r` have the same value |
| 18.4 | with a weight per node (`w_full` where evaluated, `w_shape` throughout skipped subtrees), the node-by-node choice `bestCert` is valid and weighs no more than any valid certificate |
| 18.5 | `bestCert` weighs no more than evaluating every node |
| 18.6 | if one formula's arity sequence followed by `a` equals another's followed by `b`, the arity sequences are equal and `a = b` |

**Words.** The words of a formula are its preorder. By Theorem 18.6, the
arity sequence of a word sequence determines the tree's shape and where each
subformula ends. If every word's arity decision is right, the read tree and
the true tree have the same shape, and the node at preorder position `k` is
word `k` in both. The word-level certificate is therefore:

- the **arity decision** at every word;
- the **full decision** at every word that is a node `bestCert` evaluates.

Agreement on these gives agreement on the tree certificate, and Theorem 18.3
gives the right answer, so this certifies the evaluator in the sense of
§18.4. If the read arities do not form a formula, no answer is certified:
some arity decision is certainly wrong.

**Weights.** For a word evaluated in the certificate, the weight is the risk
of its full decision. For a skipped word, it is the risk of its arity
decision. `bestCert` is then the least-risk certificate, computed bottom-up in
one pass over the words. Its bound never exceeds the static bound that
decides every word fully (Theorem 18.5).

### 18.6 How certificates scale

**Theorem 18.7.** Every complete alternating
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
(Theorem 16.3) changes from `n ≲ δ / ρ_full` to roughly
`n ≲ (δ / ρ_full)²`, until the shape term dominates at
`n ≈ δ / ρ_shape`. Arity decisions are easy: `true`/`false` look nothing like
the connectives. So `ρ_shape ≪ ρ_full`, and the gain is large exactly where
static demand fails.

**Control.** `xor` has no absorbing value, so on all-`xor` formulas every
valid certificate evaluates everything, and the certificate bound equals the
static bound, which makes the `xor` variant a control.

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

## 19. Error detection by the format

### 19.1 The observation

The certificate bound of §18 charges its arity term `Σ ρ_shape` at every
word, so that term grows linearly with the formula and limits depth. It
overcharges: it is a union bound that treats
every arity error as silent. But the format is redundant. A prefix formula's
arity sequence is constrained, the reading is answered only if it parses,
and the truth parses too. Errors that break the constraint are *detected*
(the controller climbs or abstains). Only errors that preserve it can make
an answer wrong.

### 19.2 Single errors are detected

**Theorem 19.1.** Every formula's
preorder arity sequence sums to one less than its length:
`Σ_k (a_k − 1) = −1`.

**Theorem 19.2.** Two formulas with the same number of
words whose arity sequences agree everywhere except possibly at one
position have the same arity sequence.

*Proof.* Equal lengths and Theorem 19.1 give equal sums. Lists of equal length
and equal sum agreeing outside one position agree there too.

The premise is that word boundaries are known, so the reading and the truth
have the same number of words. The channel never corrupts spaces. Then, given
that the reading parses, the set of words whose arity is misread has size 0
or at least 2.

### 19.3 What a wrong answer requires

Let the reading `r` parse, let `t` be the truth, and let `E` be the words the
reading's certificate evaluates. Write `A_k` for "word `k`'s arity is
misread" and `W_k` for "word `k` is misread but its arity is right".

- If no arity is misread, the trees align node by node (Theorem 18.6). A
  wrong answer then needs a disagreement on an evaluated node (Theorem 18.3),
  that is, some `W_k` with `k ∈ E`.
- If some arity is misread, at least two are (§19.2).

Hence

> `wrong ⊆ (⋃_{k ∈ E} W_k) ∪ {at least two A_k}`

and (Theorem 19.3)

> `P(wrong | r) ≤ Σ_{k ∈ E} P(W_k | r) + P(at least two A_k | r)`.

**Evaluated words.** `P(W_k)` is the probability that the true word lies in
the read word's arity group `g` but differs from it, `p(g) − p(r_k)`. This is
at most the risk `1 − p(r_k) / p(g)` of the decision restricted to `g`
(Theorem 19.4), which §16 already calibrates. For `not`, alone in
its group, it is 0.

**Arity.** What remains is the probability of at least two arity failures
among all words.

### 19.4 Two bounds on two failures

Write `ρ_k` for word `k`'s arity risk and `S = Σ_k ρ_k`.

**Without further premises** (Theorem 19.5). The number of failures
`N = Σ_k 1[A_k]` has mean `S`. By Markov's inequality,
`P(N ≥ 2) ≤ S / 2`. Detection halves the arity term, using nothing but the
format.

**Without positive correlation** (Theorem 19.6). If failures at two
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

## 20. Higher-order experts and budgeted requests

### 20.1 Limits of plain requests

Experts can already ask the kernel for sub-results (§14): by delegation,
which replaces their output, or by continuation, which resumes with the
answer. Both are invisible to the planner, which has two costs:

1. **No cost up front.** A route's cost (§13) does not include what its
   experts will request, so the planner cannot choose the cheapest way to
   serve those requests, and cannot compare a route that delegates with one
   that does not.
2. **No recursion.** Requests terminate because the requester chain excludes
   every expert already in it. That also forbids
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

A contract with slots adds a list of
sub-goals `[a₁, …, aₖ] ⇒ b` to the inputs and output. A plan
`apply c fs ps` fills slot `i` with the plan `fs[i]` and input `j` with
`ps[j]`. The expert receives the fillings as functions and may call them
during its invocation. It never learns which experts implement them.

**Typing.** It extends §1 with one premise. A slot filling must be
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

**Theorem 20.1.** Installing experts never invalidates a plan.

### 20.3 `map` is a higher-order expert

`map` at element types `a`, `e` is the contract `mapContract a e` with slot
`[a] ⇒ e`, input `seq a` and output `seq e`. It calls its slot once per
element.

**Theorem 20.2.** Every plan well-typed in the sense of §1 is
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

**Theorem 20.3.** If `1 ≤ N` and every expert calls its
slots at most `N` times, a plan costs at most `N^nest` times its cost with
every slot called once. Here `nest` is the slot nesting depth, the largest
number of fillings enclosing an expert.

With `N = L`, plans whose fillings contain no further fillings are linear
in `L`, as in Theorem 13.2. The polynomial degree of a composition is
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

For fallback, `ν̄ = (1, P(unsure))`, which is Theorem 14.6. The
premise matters: a filling whose cost is correlated with being called (a
cascade nested in a cascade, deferring on the same inputs) breaks it
(§26).

### 20.5 Planning with slots

A slot is a sub-goal whose available inputs are the slot's inputs. That is
the situation of `map`'s body, so the planner's state `(available, type,
depth)` is unchanged. An expert with slots spawns one sub-goal per slot,
alongside one per input.

**Theorem 20.4** (optimal substructure). Cost is monotone in
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
   `ν̄`. Its error is `P(C ∩ W₁) + P(Cᶜ ∩ W₂)` (Theorem 14.4). That
   error is a property of the pair, not a sum of per-filling errors, so the
   fallback expert declares it per filling pair from audit data.

### 20.6 Budgeted requests

Static slots cover requests whose shape is known before the input is seen.
Requests that depend on intermediate values, such as recursion on
subformulas, stay dynamic. For those, chain exclusion is replaced by a
budget (`serve`):

- A question `q` is answered by an expert program `expert q`, a `Prog` of
  §14, whose invocation costs `κ q > 0`.
- The kernel pays `κ q` from the budget `b` before running it. If
  `κ q > b`, it refuses.
- The program's own questions are served recursively, with the budget that
  remains.
- No expert is excluded, so a program may ask its own question again.

The definition is by well-founded recursion on the
budget, which strictly decreases with every invocation. That acceptance is
the termination proof: every run ends, recursive or not.

| Theorem | Statement |
|---|---|
| 20.5 | if every expert's program is safe for its question's specification, every answer is correct, at any budget and recursion depth |
| 20.6 | an answer leaves at most `b − κ q`: every invocation is paid from the budget |
| 20.7 | serving a program's questions never increases the budget |

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

## 21. Decoding by the format

### 21.1 From detection to correction

§19 used the prefix format to **detect** arity errors: a reading that does
not parse is refused, and the controller climbs or abstains. Once the summed
arity risk is near 1, most readings do not parse at any rung, and those
formulas cannot be answered at any cost.

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

**Definition** (`await`). The counter automaton
of prefix notation has states `some n`, meaning `n` subformulas are still
awaited, and a dead state `none`. A word of arity `a` read while `n + 1`
subformulas are awaited leaves `n + a` awaited. Reading anything when none
are awaited kills the run. A sequence is accepted when, started from one
awaited subformula, it ends with none awaited.

| Theorem | Statement |
|---|---|
| 21.1 | reading a formula's arity sequence consumes exactly one awaited subformula |
| 21.2 | every formula's arity sequence is accepted |
| 21.3 | a sequence of arities at most 2 is accepted from `n` awaited exactly when it is the concatenated arity sequence of `n` formulas |

So `L_m` is exactly the set of length-`m` words the automaton accepts. The
decoded sequence is therefore always a formula, and every formula is a
candidate.

### 21.4 Decoding by dynamic programming

For any deterministic automaton and position-wise weights `wₖ`, define the
score of a sequence as its weight product if accepted, else 0.

| Theorem | Statement |
|---|---|
| 21.4 | the sum-product recursion over states equals the total score of all sequences |
| 21.5 | with nonnegative weights, no sequence scores more than the max-product recursion |
| 21.6 | unless the maximum is 0, some sequence attains it; backtracking the maximizing choices finds it |

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

**Theorem 21.7.** Since `Z ≤ 1`,
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
(§19.5), and `rₖ` the restricted risks, the argument of Theorem 19.3
gives

> `P(wrong | readings) ≤ R + Σ_{k ∈ E} rₖ`.

### 21.6 Charges for refinement

Let `μₖ = 1 − π(aₖ = âₖ)` be word `k`'s posterior arity risk after decoding.
`μₖ` uses every other word's evidence through the format. A word whose
reading is uncertain can still have a small `μₖ` when only one arity fits
its neighbours.

**Errors come in pairs.** The truth and `â` are both formulas of `m` words,
so they differ in no position or in at least two (Theorem 19.2).
Applied to the posterior measure, Markov's inequality on the number of
differing positions (Theorem 19.5) gives

> `R ≤ ½ Σₖ μₖ`.

The account charges word `k`

> `R · μₖ / Σⱼ μⱼ`, plus `rₖ` if `k ∈ E`.

The charges sum to the bound of §21.5. Refinement climbs the word with the
largest charge, the word most likely misread *given the format*, not merely
the least confident reading.

### 21.7 Scaling

For words with arity risk `ρ` each and `S = mρ`:

- **detection:** abstains on every unparseable reading, whose probability
  approaches 1 as `S` grows past 1;
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

Unlike the absence of observed errors, these tests can fail.

### 21.9 What correction cannot do: hard style

In the arithmetic task, the parser fixes the kind of every position:
digits at even positions, operators at odd ones (§14). A misread digit is
another digit, and a misread operator another operator. Either way, the
reading still parses. The format has no redundancy against such errors,
so neither detection nor correction has anything to work with.

Of the remaining hard-style errors:

- **Ambiguity between operators** (`+` against `×` under rotation) lies
  inside a decision the format leaves free. Its Bayes risk is
  a floor: no reader, however strong, certifies such a glyph below it.
- **Erased digits**, when the segmenter misses them, change the
  length's parity. Such readings do not parse and are already detected.
  When an erased digit is segmented but misread, it is an ordinary digit
  error.

For hard style, the efficient policy is to recognize early that a glyph's
risk cannot reach the target and abstain, rather than climb (§22).

## 22. Abstaining early

### 22.1 The most expensive outcome

An abstention costs the most of any outcome. The controller climbs until no
item can be climbed, and only then gives up, so at strict targets almost
all compute can go to formulas that are refused in the end. Compute spent on
a formula that will be refused anyway is wasted.

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
  (Theorem 22.1). Setting every open word's risk to zero gives
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
an abstained formula would have been forced to can differ, because it comes
from an earlier reading.

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

## 23. Efficient decoding

### 23.1 Decoding is paid once per climb

§21.4 prices one decoding at about `2.25 m²` multiply-adds, about 1% of a
top-rung pass over all words. But refinement climbs one word per step and
must recompute the bound after each climb. At depth 8 a full decoding
(744k operations) costs about seven top-rung word readings (103k FLOPs
each). Over the hundreds of climbs a depth-8 formula takes, exact decoding
from scratch at every step would cost more than the reading it serves. This
section makes each step's decoding cost small without giving up a valid
bound. Two facts suffice: almost all posterior weight lies near the reading
(**banding**), and a climb changes one word (**splitting**).

### 23.2 The tail outside a band

Fix a reference sequence `r`, for instance each word's most probable arity.
Word `k` has weights `qₖ` (its calibrated arity probabilities, summing to at
most 1) and off-reference mass `ρₖ = Σ_{a ≠ rₖ} qₖ(a)`; let `S = Σₖ ρₖ`.

| Theorem | Statement |
|---|---|
| 23.1 | the total weight of the sequences differing from `r` in at least `j` positions, parseable or not, is at most `e_j(ρ)`, the elementary symmetric polynomial |
| 23.2 | `j! · e_j(ρ) ≤ S^j` for nonnegative `ρ` (a Maclaurin-type inequality) |
| 23.3 | the accepted sequences among them weigh at most the same tail |

So the weight outside `j − 1` changes is at most `U_j = S^j / j!`. For
`j = 2` this is `e₂` of §19.4. Here it is a statement about the decoding
model's weights, so it needs no premise beyond (P).

**From changes to states** (Theorem 23.4). Arities are at most 2, so
two sequences differing in `d` positions have sums at most `2d` apart. The
same holds for every prefix. Hence the counter of `await` (one plus the
prefix sum of `a − 1`) of a sequence within `j − 1` changes of `r` stays
within `2(j − 1)` of `r`'s counter at every position. A dynamic program
restricted to the **band** of counter values `|n − n_r(k)| ≤ 2(j − 1)`
therefore sees every such sequence. The band has `W = 4(j − 1) + 1` states
per position, against up to `min(k + 1, m − k)` live states unbanded.

### 23.3 A certified banded risk

The banded passes compute:

- `Z_band`: the total weight of accepted sequences inside the band. It is at
  least the weight of accepted sequences within `j − 1` changes.
- `â`: the most probable accepted sequence inside the band, with weight `x`.

Every other accepted sequence lies outside `j − 1` changes, so the true
normalizer satisfies `Z ≤ Z_band + U_j`.

**Theorem 23.5.** If `x ≥ 0`, `Z > 0` and
`Z ≤ Z_band + U`, then `1 − x / Z ≤ 1 − x / (Z_band + U)`.

The controller answers with `â` and charges `R_band = 1 − x / (Z_band + U_j)`.
That is an upper bound on `â`'s exact posterior risk, so every guarantee of
§21 holds unchanged. The cost is at most the slack `U_j`, at most
`U_j / Z_band` in relative terms.

**Exactness certificate.** Each sequence outside the band weighs at most
`U_j`. So if `x ≥ U_j`, the banded `â` is a most probable parseable sequence
overall, the same answer exact decoding gives.

**Relative slack.** The charged risk exceeds the exact one by at most a
fraction of the band's own weight.

**Theorem 23.6.** If `x ≤ Z`, `0 < Z` and `Z_band ≤ Z ≤ Z_band + U`, then `(1 − x / (Z_band + U)) − (1 − x / Z) ≤ U / (Z_band + U)`.

*Proof.* The difference is `x (Z_band + U − Z) / (Z (Z_band + U))`. The
numerator's second factor is at most `U`, and `x / Z ≤ 1`.

So a slack target must be relative: `U_j ≤ η · Z_band` gives a charged risk
within `η` of the exact risk. An absolute target `U_j ≤ η` is not enough, since
`Z`, the weight of all parseable sequences, can be far below 1 when many
readings do not parse.

**Choosing `j`.** `Z_band` is known only after the banded passes, so `j` is
found by widening. Start from the least `j` with `S^j / j! ≤ η` (the band is
then at least as wide as needed when `Z = 1`), run the passes, and increase
`j` while `U_j > η · Z_band`. This terminates whenever `Z > 0`: widening never
lowers `Z_band`, and once `2(j − 1) > m` the band covers every live state (the reference
counter at position `k` lies in `[1 − k, 1 + k]`, live states in `[0, m − k]`).
Then no sequence lies outside it, the tail term can be taken as 0, and the
banded result is exact. Each widening costs one more banded pass.
The starting `j` for `η = 10⁻⁴`:

| `S` | `j` | band width `W` |
|---:|---:|---:|
| 0.04 | 3 | 9 |
| 0.18 | 4 | 13 |
| 0.71 | 7 | 25 |
| 3 | 14 | 53 |

The rows span top-rung readings at depths 8, 6 and 4 (`S` scales with the
word count) and the order of magnitude of bottom-rung readings at depth 8.

### 23.4 Splitting at the climbed word

**Theorem 23.7.** The sum over all sequences splits at any
position into prefixes, each weighted by the sum over suffixes from the state
the prefix ends in. Grouping prefixes by their end state gives

> `Z = Σₙ F_k(n) · Σₐ qₖ(a) · B_{k+1}(δ(n, a))`,

with `F_k` the forward vector before word `k` and `B_{k+1}` the backward
vector after it.

**Theorem 23.8.** With nonnegative weights, the best score splits the same
way, with `max` in place of the sums:

> `x = maxₙ F^max_k(n) · maxₐ qₖ(a) · B^max_{k+1}(δ(n, a))`,

where `F^max_k(n)` is the best weight of a prefix ending in state `n` and
`B^max_{k+1}` the best score of a suffix. Nonnegativity is needed because
`c · max(u, v) = max(c u, c v)` only for `c ≥ 0`.

A climb changes only `qₖ`. With `F_k` and `B_{k+1}` current, the new `Z` and
the new maximal weight cost `O(3 · Wₖ)` operations, where `Wₖ` is the
number of states at `k`. What must be maintained are the vectors themselves:

- `F_i` depends only on words before `i`;
- `B_i` depends only on words from `i` on.

After a climb at `p`, every `F_i` with `i ≤ p` and every `B_i` with `i > p`
stays valid. The next climb at `k` needs `F_k`, which costs recomputing the
forward vectors from `p` to `k` (or the backward ones, if `k < p`). The
split point moves like a cursor, and each step costs the states it sweeps.
Refinement climbs in charge order, which is spatially unordered.

**Theorem 23.9.** Over all ordered pairs of positions among `m`,
`Σᵢ Σⱼ |i − j| = (m³ − m) / 3`.

So if consecutive climbs fall at independent uniform positions, the cursor
sweeps `(m² − 1) / (3m) < m / 3` positions per climb on average. Climbs that
cluster sweep less; the premise is an upper reference, not a guarantee.

**Charges need not be fresh.** The account's validity requires only that
the charges sum to the bound (§19.6). The bound `R_band + Σ_{k ∈ E} rₖ` is
recomputed exactly at every step. `E` comes from the certificate dynamic
program over the decoded tree, which costs `O(m)`. The bound is split in
proportion to marginals `μₖ` from the last full refresh. Stale marginals can
only change which word climbs next, never the validity of the bound. A full
refresh of the marginals costs one banded forward–backward pass and can be
amortized, for instance once every `√m` climbs.

**Theorem 23.11 (stale priority allocation).** Let nonnegative priorities
`hₖ` have positive sum `H`, and let the current sequence risk be `R ≥ 0`.
The charges `cₖ = R hₖ / H` are nonnegative and sum exactly to `R`,
regardless of when the priorities were computed. Thus stale priorities may
allocate the current risk without changing its total. This does not permit
caching the risk itself: `R` and the within-certificate risk must still be
current. If every priority is zero, a nonempty set of `m` items can instead
receive uniform charges `R / m`.

**Theorem 23.12 (revision cache invariant).** Suppose a cached quantity
is a deterministic function `f(v)` of an item's revision `v`. Reusing a
cached value `f(v₀)` is exact whenever `v = v₀`. The revision must identify
both the observation and its calibration; equality of raw observations
alone is insufficient. Revisions are scoped to one refinement run, whose
experts and calibration parameters remain fixed.

**Theorem 23.13 (one-sided numerical allowance).** Let `q(x)` be the
true error probability, `b(x)` a valid real-valued bound, and `b̂(x)` its
numerical evaluation. Suppose `q(x) ≤ b(x) ≤ b̂(x) + ε(x)`. Answering only
where `b̂(x) + ε(x) ≤ δ` bounds the weighted error among answered inputs
by `δ` times their total weight, for any nonnegative input weights.
This follows by applying selective risk to the upper envelope `b̂ + ε`.
The allowance must be justified for the actual calculation; a maximum
observed on finitely many examples does not establish the premise.

**Threshold stability.** If two evaluations differ by at most `ε`, their
answer/refuse decisions agree whenever the reference evaluation is either
at most `δ − ε` or strictly greater than `δ + ε`. Between these margins,
arbitrarily small numerical changes can change a threshold decision.
This concerns numerical evaluation of a valid bound, separately from
whether its statistical modeling assumptions hold.

Without a certified pointwise numerical allowance, the distribution-level
audit of §17 can instead certify the entire answering policy. Candidate
policies must be fixed independently of the checking sample and must use
the same numerical decision rule during checking and deployment. A change
to that rule produces a new policy; observed agreement on a finite sample
does not itself transfer the earlier policy's guarantee.

The decoded sequence must still be recovered after each step, to evaluate
the formula and find `E`. It too is read from the split, without a sweep.

**Theorem 23.10.** Let a prefix `u` of the first `k` words end in state `n`,
let `v` be a suffix of the remaining words from state `δ(n, a)`, and let
`u a v` be accepted. Its weight is

> `w(u) · qₖ(a) · w(v)`.

If `w(u) = F^max_k(n)`, `w(v) = B^max_{k+1}(δ(n, a))`, and `(n, a)` attains
the maximum of Theorem 23.8, then `u a v` is a best sequence.

The best prefix ending in `n` is traced backwards through the forward max
vectors: at each position, a predecessor state and arity whose product
attains the vector entry. The best suffix is traced forwards through the
backward max vectors in the same way. With the vectors current on either
side of the climbed word, as they are after Theorem 23.8 scores it, the
decoded sequence costs `O(3 m)` comparisons and no recomputed vectors.

**Banding with a moving cursor.** Theorems 23.1–23.6 hold for *any*
reference sequence `r`, not only the per-word argmax. So the reference, and
with it the band's centre at every position, is fixed when the band is
built and kept through later climbs, even where a climb changes a word's
most probable arity. Only `S = Σₖ ρₖ`, with `ρₖ` the climbed word's mass off
`rₖ`, changes, and it is updated in `O(1)` per climb. A climb that moves a
word's mass away from its reference raises `S`, and with it `U_j`; the band is
rebuilt wider (§23.3) only when `U_j > η · Z_band`.

With the centre fixed, the band is a position-dependent restriction of the
counter automaton: pair each state with its position and send states outside
the band to the dead state. That is again a deterministic automaton, so the
splits of Theorems 23.7 and 23.8 apply to the banded programs unchanged, and
the cursor sweeps `W` states per position instead of up to `min(k + 1, m − k)`.

### 23.5 Predicted operation counts

Per refinement step, counting multiply-adds over the arity alternatives:

- **exact from scratch:** forward, backward and max passes, `2.25 m²`;
- **banded from scratch:** `9 m W`, capped by the live states;
- **incremental:** a sweep of `m / 3` positions for the sum and max forward
  vectors, `0.5 m²` exact or `2 m W` banded.

`W` is taken at the top-rung `S` for each depth, with `η = 10⁻⁴`.

| depth | words `m` | `W` | exact | banded | incremental exact | incremental banded | one top-rung word |
|---:|---:|---:|---:|---:|---:|---:|---:|
| 4 | 35 | 9 | 2.8k | 2.8k (no gain) | 0.6k | 0.6k | 103k |
| 6 | 143 | 13 | 46k | 17k | 10k | 3.7k | 103k |
| 8 | 575 | 25 | 744k | 129k | 165k | 29k | 103k |

At depth 8, banding and splitting together cut the per-step decoding cost
from about seven word readings to about a quarter of one, a factor of 26.
At depth 4 the band already covers every live state, and only splitting
helps.

### 23.7 Exact decoding in linear space

Before banding, the exact passes can be made cheap per operation. The
log-space recursion of §21.4 pays a logarithm and an exponential for every
transition. In linear space with each forward row rescaled to total 1, a
transition is one multiply-add. If `c_k` is the total of forward row `k`
computed from the rescaled row `k − 1` (`c_0 = 1`), then `log Z = Σ_k log
c_k`. With the backward rows divided by the same totals, a marginal is
`F̂_k(n) q_k(a) B̂_{k+1}(δ(n, a)) / c_{k+1}`. The rescaling only factors
constants out of `dpSum`, so the results are exact. The most probable sequence
stays in log space, where it needs only additions.

The same rescaling serves the cursor of §23.4. Store each forward row as
`F̂_k = F_k / C_k` with `log C_k`, and each backward row as `B̂_k = B_k / D_k`
with `log D_k`. A row recomputed from its neighbour costs one multiply-add per
transition, one division per state and one logarithm per row:
`log C_{k+1} = log C_k + log Σₙ F̃_{k+1}(n)`, with `F̃_{k+1}` the unnormalized row
computed from `F̂_k`. The split of Theorem 23.7 becomes

> `log Z = log C_k + log D_{k+1} + log Σₙ F̂_k(n) Σₐ qₖ(a) B̂_{k+1}(δ(n, a))`,

since both factors come out of the double sum. The band restricts which
states a row holds, not how it is scaled, so banding is unaffected. A row
whose total is 0 has no accepted continuation through it; it is stored as
zeros with `log C = −∞`, and so is every row computed from it.

## 24. When the prior is wrong

### 24.1 The question

The decoder of §21 is exact under premise (P): a prior over arity
sequences that is the readers' per-word prior restricted to sequences that
parse. The formulas of §18.1 come from a different generator, complete
alternating trees. This section asks how wrong the
decoded formula's risk `R` can then be, what can be guaranteed with no
prior at all, and what the premise tests of §21.8 should show.

Readings are the same under both priors; only the prior differs. Let `π*`
be the generator's prior over arity sequences of `m` words, and
`π_P(a) ∝ Πₖ πₖ(aₖ)` the prior of (P), with `πₖ` the per-word prior the
calibrated readings carry. Since the readings' likelihoods agree, the true
posterior weight of a sequence `a` is the model's weight `w(a) = Πₖ qₖ(aₖ)`
times the **prior ratio**

> `ρ(a) = π*(a) / π_P(a)` (up to a constant, which cancels).

The decoded sequence `â` is a single sequence, so only two numbers matter:

- `C = max_{a ≠ â} ρ(a)`, the largest ratio at a competitor;
- `c = ρ(â)`, the ratio at the decoded sequence.

Let `Λ = C / c`, and `R*` be the true posterior risk of `â`.

### 24.2 Bounded ratio

| Theorem | Statement |
|---|---|
| 24.1 | reweighting nonnegative weights by `ρ ≤ C` on an event and `ρ ≥ c` off it multiplies the event's odds by at most `C / c` |
| 24.2 | `R* ≤ Λ R / (1 − R + Λ R)` |
| 24.3 | for `Λ ≥ 1`, `R* ≤ Λ R` |
| 24.4 | if `ρ(â) ≥ ρ(a)` for every competitor (`Λ ≤ 1`), `R* ≤ R` |

The bound is in odds: the true odds of an error are at most `Λ` times the
model's. For small `R` it is close to `Λ R`. Exchanging the roles of the two
priors (Theorem 24.1 applied to the inverse ratio) gives a lower bound of
the same form, with the *smallest* ratio at a competitor in place of the
largest. Together they bracket how far the model's risk can be from the truth.

Only the ratio at competitors *relative to the decoded sequence* enters.
A prior that differs wildly from (P) does no harm where it treats `â` and
its competitors alike. A prior that removes mass from competitors, and not
from `â`, makes the model's risk conservative.

### 24.3 The generator of complete alternating trees

A complete alternating tree of depth `d` has `2^d − 1` connectives and `2^d`
leaves, each negated with probability 1/4. With `m` words, the number of
`not`s is fixed, `m − 2^{d+1} + 1`. So every arity sequence the generator
produces at that length has the same **histogram** of arities, and its
probability depends only on which leaves are negated:
`(1/4)^{nots} (3/4)^{2^d − nots}`, the same for all of them. Let `S_m` be
this support.

`π_P` is a product of one per-word prior, the same at every position,
because one reader reads every word. So it too depends only on the
histogram, and is constant on `S_m`. Hence

> `ρ = κ` on `S_m`, `ρ = 0` off it.

Two cases follow, and nothing in between:

1. **The decoded sequence is a complete tree** (`â ∈ S_m`). Then
   `ρ(â) = κ ≥ ρ(a)` for every competitor, so `R* ≤ R`
   (Theorem 24.4). The true risk is `R` restricted to the support:
   competitors the generator never produces drop out.
2. **The decoded sequence is not a complete tree** (`â ∉ S_m`). Then
   `ρ(â) = 0`, `Λ = ∞`, and the bound says nothing. Indeed the truth lies in
   `S_m` and differs from `â`, so `R* = 1`: the decoded formula is certainly
   wrong, whatever `R` says.

So for structured generators `Λ` is unbounded in general. Their support is
a thin subset of `L_m`, and the decoder, knowing only the format, can land
outside it. In that case the bound of §24.2 is vacuous. The model's risk is
then a claim that only data can check: the calibration test of §21.8 or the
audit of risk control (§24.5).

### 24.4 No prior, no guarantee

**Theorem 24.5.** Put weight 1 on a competitor of positive
weight `w'`, weight `t` on the decoded sequence (weight `ŵ`), and 0
elsewhere. The true risk is `w' / (w' + t ŵ) ≥ 1 − t ŵ / w'`, which tends to
1 as `t → 0`.

Every such prior is supported on `L_m`, so the format alone guarantees
nothing about a corrected answer. Correction answers formulas whose
readings do not parse because it assumes a prior. The coverage it gains is
paid for by that assumption.

The accounts differ in what they assume about the joint distribution of
word errors given the readings:

| account | assumes | checked by |
|---|---|---|
| certificate (§18) | each word's risk calibrated | per-word calibration on held-out words (§16) |
| detection, Markov (§19) | each word's arity risk calibrated given the readings | the same, approximately |
| detection, pairs (§19) | the above, and failures at different words not positively correlated | the pairs test (§21.8) |
| correction (§21) | the whole joint posterior, (P) | the calibration test of `R` (§21.8) |

Down the table, the premises are strictly stronger, and coverage rises with
them. Per-word calibration is fitted on held-out formulas from the
generator, so it is checked by data in distribution. (P) is not fitted to
anything.

### 24.5 Risk control certifies any account

Risk control (§17) never uses the account's premises. It treats each
candidate threshold `δ / λ` as a policy, answers audit formulas drawn from
the deployment generator, and tests each policy's error rate among answered
formulas in a fixed order (Theorem 17.5). With probability at least
`1 − α` over the audit, every certified policy's error rate among answered
formulas is at most `δ`, whether or not (P) holds. The account decides
*which* formulas a policy answers, and so how much it covers. Only the
audit decides whether the guarantee holds.

The price is audit labels. A policy with no errors on `n` answered audit
formulas is certified when the Clopper–Pearson bound `1 − α^{1/n}` is at
most `δ`, that is `n ≥ ln(1/α) / −ln(1 − δ)`. For `α = 0.1` that is 11
answered formulas at `δ = 0.2`, 45 at `δ = 0.05` and 230 at `δ = 0.01`.

The distribution-level guarantee does not need the prior, only labeled
formulas from where the system is used. The per-formula bound `R` is a
model's claim, and §24.3 shows when it fails.

**A better prior is an expert.** Theorems 21.4–21.6
hold for any deterministic automaton and any position-wise weights. A prior
given by a weighted finite automaton over arities, for example one fitted
to training formulas, enters the same dynamic program through a product
automaton. Its cost grows with the number of states. Such a prior would
then be declared by an expert rather than written into the evaluator, so
the evaluator stays generic over generators.

## 25. Which word to climb, and when to stop

Two questions about the controller remain: how many climbs pass before a
floor exceeds `δ`, and what a predictive stopping rule needs to trace a fine
coverage–compute frontier. Both depend on how the controller picks the next
climb and when it stops.

### 25.1 Climbing order

Refinement solves a covering problem. Let `D` be the amount by which the
bound must fall to reach `δ`. Climbing item `i` costs `cᵢ` and lowers the
bound by `dᵢ`, a quantity revealed only after the climb.

**Theorem 25.1.** If no climb
lowers the bound by more than `r` per unit of compute, then any set of
climbs that lowers it by `D` costs at least `D / r`, in any order.

`D / r` is the optimum of the fractional relaxation. In that relaxation,
climbing in order of largest drop per unit cost is optimal: each unit of
compute buys the most bound it can.

For whole climbs, neither greedy rule is optimal. Take `D = 10`:

| items `(dᵢ, cᵢ)` | largest drop first | largest drop per cost first | optimum |
|---|---|---|---|
| `(10, 2)`, `(6, 1)`, `(4, 1)` | `(10, 2)`: cost 2 | `(6, 1)`, then `(10, 2)`: cost 3 | 2 |
| `(10, 5)`, `(6, 1)`, `(4, 1)` | `(10, 5)`: cost 5 | `(6, 1)`, `(4, 1)`: cost 2 | 2 |

The ratio rule loses at most one climb's cost over the fractional optimum:
it stops when the cumulative drop first reaches `D`, so only its last
climb can overshoot. The controller charges by risk, not by expected drop
per cost. That is the ratio rule with three simplifications:

- every climb is assumed to remove most of the item's charge;
- equal costs are assumed within a ladder step;
- drops are not known in advance.

The second assumption holds exactly when one ladder serves every item, as
in both domains. This connects to Theorem 16.2 (§16): refining
exactly the items whose bound reduction exceeds `λ` times their cost
minimizes risk plus `λ` times compute. Greedy by charge implements that
rule one item at a time.

### 25.2 Why floors pass `δ` early

Fixing a word means bringing it to its top rung. The controller fixes the
riskiest words first, and those are not typical words. Words with large
bottom-rung risk are mostly genuinely ambiguous ones, such as `not`
misread as a connective, and they keep large risk at the top rung.

**Theorem 25.2.** If `t` risks are each at least `a ≥ 0`,
their pairs function (the `e₂` of §19.4) is at least
`t (t − 1) / 2 · a²`.

So the pairs floor exceeds `δ` once

> `t ≳ 1 + √(2δ) / a`,

where `a` is the smallest top-rung risk among the words fixed so far. For
the Markov floor, `S_F / 2 ≥ t a / 2`, which needs `t ≳ 2δ / a`.

Replacing `a` by the per-word mean risk overestimates `t`. The relevant
quantity is an order statistic: the `t`-th largest top-rung risk among the
words the controller climbs first, which lie in the upper tail of the risk
distribution.

### 25.3 Stopping

Each formula is a stopping problem. In a state `s`, the controller may
abstain, with reward 0, or climb, paying `λ` times the climb's cost. Once
the bound reaches `δ`, refinement stops and earns reward 1, one answered
formula. Maximizing coverage minus `λ` times compute is maximizing this
reward.

**Model.** A finite tree of states. At each state the
controller may stop with reward `g`, or pay `c` and move to a random next
state. The *lookahead set* is the set of states where stopping now is at
least as good as one more step followed by stopping. The problem is
*monotone* if every next state of a state in the lookahead set is also in
it.

| Theorem | Statement |
|---|---|
| 25.3 | in a monotone problem, every state of the lookahead set is worth exactly its stopping reward: stopping there is optimal |
| 25.4 | outside the lookahead set, continuing is worth strictly more than stopping |

So for monotone problems, the optimal policy is the one-step rule.

**Floors are the monotone part.** The fixed set only grows, and floors are
monotone in it (Theorem 22.1). So once the floor exceeds `δ`,
it does so in every later state. There, no continuation ever answers.
Stopping is worth 0 and every climb costs, so these states form a lookahead
set closed under continuation, and abstaining there is optimal by
Theorem 25.3, at every `λ ≥ 0`. This is §22.3's soundness, seen
as optimal stopping.

**Bound states are not monotone.** A state whose bound is far above `δ`,
with the floor still below it, is in the lookahead set for most `λ`: one
climb rarely reaches `δ`. Yet later climbs can. Such a state can lead to
states outside the lookahead set, so the one-step rule would stop too
early. The predictive rule of §22.4 must therefore estimate the eventual
probability of answering, `P(A | s)`, not the one-step one, for instance by
binning calibration states.

### 25.4 Why the frontier is coarse

The rule bins states by one feature, `log₁₀(bound / δ)`. That mixes states
that will answer with states that will not.

- **A state can be far from `δ` for two different reasons.** Many open
  items with moderate charges can still answer. A few fixed items with
  large risks cannot. The bound alone does not separate them, so most bins
  contain no state that later answers. In those bins any `λ > 0` stops,
  and the frontier jumps.
- **Better features follow from §25.2–25.3.**
  - The *floor ratio* `floor / δ`: states with floor ratio above 1 never
    answer, and the ratio rises monotonically.
  - The *open charge mass* `bound − floor`: the most that remaining climbs
    can remove.
  - The number of open items whose charge exceeds the gap `bound − δ`.

  The estimate becomes finer when `P(A | s)` is estimated over the pair
  (floor ratio, open mass / δ). States with floor ratio near 1 are then
  separated from states that have room to fall.

## 26. Composing cascades

### 26.1 The failure

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

### 26.2 Exact cost of a fallback

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

### 26.3 Error and cost of a chain

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

### 26.4 What the planner needs

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

### 26.5 Choosing among many cascades on one audit

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

## 27. Priors as experts

### 27.1 The idea

§24 showed that a corrected answer's risk is only as good as the prior over
arity sequences. The format-only prior of (P) has more support than the
generator, so the decoder can land outside the generator's support, where
its risk claim fails completely (§24.3). The remedy suggested there: let an
expert supply the prior. The evaluator stays generic, decoding under
whatever prior it is given. The prior is a typed value produced by an
expert, which the kernel plans and selects like any other.

### 27.2 Weighted automata and the product

A **prior automaton** has states `τ`, a start state, transitions `ε`, a
weight `v(t, a) ≥ 0` for reading arity `a` in state `t`, and a final weight
`f(t) ≥ 0`. A sequence's prior weight is the product of the weights along
its run, times the final weight (`prior`).

Decoding under the format automaton (§21.3) and a prior automaton together
runs the dynamic program on their product. A product state pairs a format
state `s` with a prior state `t`. Reading `a` moves to `(δ s a, ε t a)` with
weight `qₖ(a) · v(t, a)`. A run is accepted when the format accepts, with
final weight `f(t)`.

| Theorem | Statement |
|---|---|
| 27.1 | the product sum-product recursion equals the sum over all sequences of score × prior |
| 27.2 | with nonnegative weights, no sequence's score × prior exceeds the product max-product recursion |
| 27.3 | unless the maximum is 0, some sequence attains it; backtracking decodes it |
| 27.4 | with the one-state prior of weight 1, the product program is the format-only program `dpSum` |

So everything in §21 carries over unchanged under any prior automaton:

- the decoded sequence `â` (`pdpMax`);
- the normalizer `Z` (`pdpSum`);
- the risk `R = 1 − score(â) · prior(â) / Z`;
- the marginals, by forward–backward over product states;
- the charges and the pairing argument of §21.6.

The pairing argument holds whenever the prior's support lies in `L_m`.

**Cost.** Per position, the work is the number of live product states
times the arities allowed from each. In general that is at most
`|σ_live| · |τ|`.

If the prior's support lies inside `L_m` (every sequence it weights
parses), the prior state determines the format state. The awaited count is
then a function of the prior state. The product then has no more live
states than the prior automaton alone, and the format component can be
dropped.

### 27.3 The contract

A prior expert has the contract

> `length → arity.prior.v1`,

producing, for a formula of `m` words, a prior automaton over arities
`{0, 1, 2}`. The evaluator consumes it alongside the word distributions. It
decodes under the product, and the format-only prior is the default
(Theorem 27.4).

Nothing about a generator is written into the evaluator. A generator's
structure enters as a separately installed, separately chosen expert, as
readers do.

A prior is a second, cheap input to the evaluator that depends only on the
length, so it is naturally the filling of a slot `[length] ⇒ arity.prior.v1`
(§20).

### 27.4 Prior experts

| prior | states | support | `Λ` for complete alternating trees (§24) |
|---|---|---|---|
| format only | 1 | `L_m` | unbounded |
| `n`-gram over arities | `3^{n−1}` (times format states) | `L_m` | unbounded |
| height at most `D` | at most `(D + 1) · 2^D` | trees of height `≤ D` | unbounded if `D` exceeds the generator's height, else as below |
| complete alternating trees of depth `d` | about `2^{d+1}` | `S_m` | 1 |

**Format only.** The prior of §21: one state, weight 1.

**`n`-gram.** The state is the last `n − 1` arities. Weights are conditional
frequencies counted on training formulas. Support is all of `L_m`. It
lowers the chance of decoding outside `S_m`, but cannot exclude it, so `Λ`
stays unbounded in the worst case (§24.3).

**Height at most `D`.** In preorder, keep a stack of the height budgets of
subtrees still awaited, and the current node's budget `h`.

- A node of arity 2 at budget `h ≥ 1` pushes `h − 1` for its right child and
  continues into its left child with budget `h − 1`.
- A node of arity 1 continues with `h − 1`.
- A leaf pops the next budget.
- No node of positive arity is allowed at budget 0.

Every pushed budget is smaller than the one below it, so the stack is a
strictly decreasing sequence from `{0, …, D − 1}`, that is, a subset. With
the current budget, there are at most `(D + 1) · 2^D` states. The language
is regular, and the stack's size plus one is the format's awaited count, so
the format component is redundant (§27.2).

**Complete alternating trees of depth `d`.** This is the generator's own
support `S_m`. The same stack automaton applies, with two restrictions:
nodes at budget `h ≥ 1` must be connectives (arity 2), and at budget 0 a
leaf is either a constant (arity 0) or `not` followed by a constant (arity
1, then 0). The states are the pending budgets, a subset of
`{0, …, d − 1}`, with one extra flag for "after a `not`": about `2^{d+1}`
states, with at most two transitions each.

Length determines depth. A depth-`d` formula has
`m ∈ [2^{d+1} − 1, 3 · 2^d − 1]` words, and these ranges are disjoint for
different `d`. So `length → arity.prior.v1` is a function.

**Why the complete-tree prior is exact.** On `S_m` the generator's prior and
(P)'s prior are proportional (§24.3). With the complete-tree prior's
weights all 1, the effective prior is (P)'s restricted to `S_m`, which is
proportional to the generator's. The prior ratio `ρ` is constant on the
whole support, and `â` always lies in it. So `Λ = 1` in both directions
(Theorem 24.4 and its exchange): under per-word calibration and
independent readings, `R* = R` exactly. Decodings outside `S_m`, which §24.3
showed are certainly wrong, cannot occur.

**Height-bounded priors** sit between the two. With `D` equal to the
generator's height (`d + 1`, since `not` adds a level), the support is a
superset of `S_m`, much smaller than `L_m`. The two-case analysis of §24.3
applies with this smaller support in place of `L_m`.

**Cost at depth 8** (`m = 575`, `d = 8`). Every `(position, state)` pair is
bounded by `m · 2^{d+1} ≈ 294k`, with at most two transitions each, about
0.6M multiply-adds per pass. The format-only program does about 0.25M per
pass (`2.25 m²` over three passes, §21.4). The exact prior costs at most a
few times the format-only one and still well under one top-rung word pass
per formula. Most stack states are unreachable at a given position, so the
live count is smaller than this bound. The banding of §23 applies to the
product unchanged.

### 27.5 Choosing a prior without labels

Which prior expert to use is a choice the kernel can make from **unlabeled**
readings. For readings `x` of a formula, the evidence under prior expert
`e`, with support weights `π_e`, is

> `p_e(x) = Σ_a π_e(a) Πₖ p(xₖ | aₖ) ∝ Z_e(q) / Z_e(π)`,

where:

- `Z_e(q)` is the product program with the calibrated arity
  distributions as weights (the decoder's normalizer);
- `Z_e(π)` is the same program with the readers' per-word priors `πₖ` as
  weights (the prior's own normalizer);
- the constant `Πₖ p(xₖ) / Πₖ πₖ(·)` is shared by all priors, so it cancels.

Both terms are instances of Theorem 27.1. The kernel selects the prior with
the largest summed log-evidence over held-out formulas, a label-free audit.

**What evidence rewards.** `−log Z_e(π)` rewards small support: an Occam
term. `log Z_e(q)` penalizes supports that exclude sequences the readings
favor. A prior that excludes the truth loses evidence on every formula
whose readings are confident about it. Asymptotically, evidence selects the
candidate closest to the generator in Kullback–Leibler divergence. This is
the standard consistency of Bayesian model selection over a finite family,
used here as a heuristic, not proved.

**The risk of a wrong but confident prior.** Selection can still pick a
prior that excludes some true sequences, when the readings rarely make the
exclusion visible. For formulas whose truth lies outside the prior's
support, §24.4 applies with the roles reversed: `R* = 1` whatever `R` says.

Two safeguards:

1. Prefer the largest support among priors whose evidence is statistically
   indistinguishable from the best. Of priors that fit equally, keep the one
   least likely to exclude the truth.
2. Keep risk control (§24.5) on the deployed policy. It certifies the error
   rate among answered formulas whatever the prior.

The prior changes which formulas are answered; the audit decides whether
the guarantee holds.
