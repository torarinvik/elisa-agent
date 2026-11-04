# 20. Higher-order experts and budgeted requests

## 20.1 Limits of plain requests

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

## 20.2 Slots

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

## 20.3 `map` is a higher-order expert

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

## 20.4 Cost

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

## 20.5 Planning with slots

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

## 20.6 Budgeted requests

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

## 20.7 Control flow

The kernel has no control-flow primitives. Control flow is the use of data,
and each way of using data is a higher-order expert: an **eliminator** of a
type constructor, with one slot per case of the data.

- **Choice.** A value of type `either(l, r)` is one of two alternatives. Its
  eliminator `case` has contract `either(l, r) → b` with slots `[l] ⇒ b` and
  `[r] ⇒ b`. It calls the slot of the alternative it receives, once.
- **Iteration.** A value of type `seq(a)` is a finite list. Its eliminator
  `fold` has contract `seq(a), s → s` with slot `[s, a] ⇒ s`. It calls the
  slot once per element, threading the state.
- **Recursion of unknown depth.** A budgeted request (§20.6) asks the
  expert's own question again on smaller data. The budget bounds its total
  cost.

Conditionals are choices: `bool` is `either(unit, unit)`, and an optional
value is `either(unit, a)`. Products `pair(a, b)` need no eliminator beyond
the experts that read them. With polymorphic contracts (§1.2, §2.1–2.2), one
`case` and one `fold` serve every type. Their variables are determined by
the data they receive and by the goal. Like any expert, they can be replaced,
and a contributor can add an eliminator for a new type constructor without
changing the kernel.

**What plans can express.** Plans built from experts with `case` and `fold`
terminate on every input, since each call of an eliminator calls its slots
finitely often. Their worst-case cost is known before they run (Theorem
20.3, with `N = L` for `fold`). Budgeted requests add general recursion and
trade that up-front bound for the budget's.

**Cost of a choice.** `case` calls one slot per invocation, but which one
depends on the data. Declaring `ν = 1` for each slot charges both branches,
which overestimates the cost and keeps budgets sound.

**Theorem 20.8 (choice).** An invocation that calls exactly one of its
slots, slot `i`, costs `κ + cost(fᵢ) ≤ κ + maxⱼ cost(fⱼ) ≤ κ + Σⱼ cost(fⱼ)`.

So the maximum over branches is a tighter worst case, and the sum declared
by `ν = 1` per slot remains sound.

**Types underdetermine fillings.** A slot whose inputs include its output
type, such as `fold`'s `[s, a] ⇒ s`, is always filled by the projection
onto `s`, which ignores the element. That plan is well-typed, so planning by
type alone cannot tell a meaningful step from the trivial one. A step is
determined either by a state type that says more, as `running-total(int)`
says more than `int`, or by a filling given explicitly and admitted by type
checking (§2), or by requiring the filling to use its inputs (§20.8).
Eliminators whose slots do not contain their output, like `case` with
`l ≠ b`, are not affected.

**Search.** An eliminator's output is a bare variable, so it is a candidate
for every goal. Pattern search then enumerates every value of the eliminated
type it can derive, and every way of filling the slots. Without further
pruning, installing `case` and `fold` makes every failing goal pay for that
enumeration; §12 (Theorem 12.19) prunes it.

## 20.8 Positional inputs and relevant slots

A plan that names an available input by its type cannot tell two inputs of
the same type apart. In `fold` with state and elements of one type, the step
`[s, a] ⇒ s` has two inputs of type `s`, and a step meant to add the element
to the state may read either one twice. A **positional plan** names each
input by its position among the available types instead.

**Theorem 20.9 (positions are types).** Reading each position as the type
available there turns a positionally typed plan into a plan typed in the
sense of §1, of the same type. Conversely, every plan typed in that sense
has a positional version, reading each input at a position where its type
is available.

So positions change which input a plan reads, never which plans exist. The
inputs a positional plan **uses** are the positions of its leaves; a `map`
body reads only its element, so a `map` uses what its source uses.

A slot may declare **relevant** inputs, positions that every filling must
use. `fold` declares both of its step's inputs relevant, and a planning goal
may require some of its own inputs in the same way.

**Theorem 20.10 (requirements).**

1. An application uses every position in `R` exactly when each position in
   `R` is used by one of its arguments.
2. A single input never uses two distinct positions.
3. A typed plan uses only positions that exist.

By part 1, a requirement is planned by giving each required position to one
argument and requiring it there, trying every such assignment. By part 2,
the projection that returns a fold's state unchanged is not a step of
`fold`. Relevance excludes fillings that ignore an input. It does not choose
between fillings that use the same inputs differently, such as `s + a` and
`s · a`: types and relevance still underdetermine those, and a filling is
then fixed by a type that says more, by cost (§13), or explicitly.

[Theory index](../THEORY.md)

## 20.9 Capability gaps

Requests and slots are served only from installed experts; a goal no route
reaches has, so far, no answer at all. A *gap* names what is missing: a unary
contract `A → B` such that installing any expert with it creates a route. The
kernel can then pose the gap as a typed sub-goal to an acquirer, such as a
learner whose result passes the upgrade gate (§43), rather than failing.

Model the installed unary experts as steps `E` between types, and let
`E + (a → b)` add one.

**Theorem 20.11 (gaps).** If `E` has no route from `s` to `g`, then
`E + (a → b)` has one if and only if `a` is reachable from `s` and `g` from
`b` under `E`.

*Proof.* (⇐) Follow `s →* a`, the new step, then `b →* g`. (⇒) By induction
on the route: before its first use of the new step it is a route of `E` to
`a`, and after its last use a route of `E` from `b`; a route never using it
contradicts the hypothesis. ∎

So the gaps are exactly the products of the types producible from the inputs
with the types from which the goal is reachable: no gap is missed, and every
requested connector, once supplied, is used. The theorem covers unary steps.
For experts with several inputs, each candidate is confirmed by planning with
a stand-in, so the set returned agrees with the planner; whether a candidate
is learnable, and in what order to ask, is the acquirer's concern.

When any connector may be requested, the direct connector `s → g` is always a
gap, so one is always enough. Several are needed only when an acquirer refuses
some, for lack of data or because what it learns fails the gate. Let `N`
relate the types between which a connector may still be obtained, and let
`Repair E N k s g` hold when `g` is reached from `s` by routes of `E` joined by
at most `k` connectors allowed by `N`.

**Theorem 20.12 (repairs).**

1. Whatever connectors `F ⊆ N` are added, a route using them `n` times is a
   repair with `n` connectors.
2. A repair with `k` connectors is realized by adding a list of at most `k`
   connectors from `N`, used at most `k` times.

*Proof.* (1) By induction on the route: an installed step extends a repair,
and an added one extends it by one connector. (2) By induction on `k`, adding
each connector of the repair. ∎

So the least `k` with a repair is the least number of connectors that must be
obtained, and a 0-1 shortest-path search, where installed steps cost nothing
and allowed connectors cost one, finds it. Each refusal removes a pair from
`N`; the search is repeated over what remains, so connectors already supplied
are reused and none is requested twice.

**Inventing intermediate types.** Every connector so far joins existing types.
A *medium* founded on a type `b` is a fresh content-addressed constructor (§29)
joined to `b` by identity connectors in both directions. Model the types as
`Option τ`, with `none` the medium.

**Theorem 20.13 (founding).** Founding a medium on `b` leaves reachability
among existing types unchanged, and the medium is reachable from `x` exactly
when `b` is.

*Proof.* Mapping the medium to `b` sends every route of the founded types to a
route of the original ones, since both identity connectors become `b`'s
trivial route; conversely every original route is a founded one, and a route
to `b` extends to the medium. ∎

So founding alone adds nothing. A medium adds routes only through members
connected to it from evidence beyond the request at hand, each attached by
data shared with any existing member (§29.5), and then every pair of members is
two connectors apart. Its routes inherit the attachment-depth bound of
Theorem 29.5.

**Certified acquisition.** An acquirer may supply anything with the requested
contract, including a memorized table that fails on every value it has not
seen. Admission therefore tests what was learned: the `k`-th request fits on
training cases and is admitted only after zero errors on `m_k` fresh cases,
with `log(1/α_k) ≤ ε m_k` and `α_k = δ/((k+1)(k+2))` (§43.7).

**Theorem 20.14 (certified acquisition).** If the fresh cases are independent
draws from the distribution of use, the probability that any admission, over
any number of requests, admits a connector whose error rate exceeds `ε` is at
most `δ`.

*Proof.* A connector erring at rate `ℓ > ε` passes `m_k` cases with
probability `(1 − ℓ)^{m_k} ≤ α_k` (Theorem 43.1's zero-loss step), and the
`α_k` sum to below `δ`. ∎

Each admitted connector then carries rate `ε` into route risk (§31). Whether a
fitter generalizes is not assumed; it is what the test measures.

The test may stop at its first disagreement: it then admits exactly when the
full test would and never reads more cases, so Theorem 20.14 is unchanged and
a rejection costs only the cases read up to its first error.

**Experts with several inputs.** A unary connector cannot compute what depends
on two inputs, so gaps must allow experts `(A₁, …, Aₙ) → b`. Read every ground
expert as a Horn rule: a type is derivable from the given types when it is
given or the output of an expert whose inputs are all derivable.

**Theorem 20.15 (gaps with several inputs).** If the goal `g` is not
derivable from `S`, adding an expert `A → b` makes it derivable if and only if
every type in `A` is derivable from `S` and `g` is derivable from `S ∪ {b}`.

*Proof.* (⇐) Derive `A`, apply the new expert, then cut `b` into the
derivation of `g`. (⇒) By induction on the derivation, every derived type is
either derivable without the new expert, or `A` is derivable and the type is
derivable with `b` given. ∎

Theorem 20.11 is the case `|A| = 1`. Candidates are multisets of at most `n` producible types, paired with each
target from which the goal is derivable. Repeated types retain separate
argument positions; the set-based reachability theorem alone does not prove
that distinct supplied values are used. Requiring every task input position
to occur in the plan is a separate relevance condition, discharged across
application arguments by `PPlan.uses_apply`. There are
`O(|P|ⁿ)` of them for `|P|` producible types, so the arity bound is a
resource limit stated by the caller, not a limit of the theory.

**Screening impossible contracts.** Let a case be `(x,y)`, and let `a(z,y)`
denote agreement. An input key must identify inputs on which every predictor
under consideration gives the same output. A separation predicate `s(y,y′)`
must imply that no output agrees with both labels. These are semantic
assumptions: unequal labels need not be separated under approximate agreement.
The predictor is deterministic in its declared inputs; relevant state must
therefore be included in those inputs.

**Theorem 20.16 (contradiction screen).** From `n` cases choose `c` disjoint
pairs, each with equal input keys and separated labels. Every compatible
predictor makes at least `c` errors on those cases. If a fixed compatible
predictor of population error at most `ε` exists, and the cases are fresh
independent draws, rejecting when `c ≥ r` has probability at most
`binom(n,r) εʳ`. Consequently, choosing `r` before inspecting the cases so
that this quantity is at most `η/((k+1)(k+2))` bounds the probability of any
false discard over any finite number of screens by `η`. If no such threshold
exists, the screen is inconclusive.

*Proof.* Each pair forces an error at one endpoint; disjointness makes these
errors distinct. If `r` errors occur, some `r`-subset of the original cases
are all errors. Each subset has probability at most `εʳ`; a union bound over
the `binom(n,r)` subsets proves the per-screen bound. The spending levels sum
to at most `η`. For adaptive requests these sampling and existence assumptions
must hold conditional on the history before each screen. The witness
predictor may depend on that history, but not on the new cases. Selected pairs
need not be independent. ∎

A passing prefix establishes no learnability guarantee. It may be reused for
training, but final admission still requires fresh certification cases under
Theorem 20.14. False discard and false admission have separate budgets `η`
and `δ`; their union has probability at most `η + δ`. Statistical refusal is
not a permanent impossibility proof for other distributions, agreement rules,
state representations or predictor classes.

**Durable scoped refusals.** A scope identifies a fixed distribution,
agreement rule, input-key semantics and compatible predictor family. Refusal
keys contain this scope, the entire contract and the tolerance and confidence
budgets. Only an actual rejection under Theorem 20.16 establishes a refusal;
failure to fit or to pass final certification does not prove impossibility.

**Theorem 20.17 (durable spending and refusal replay).** Let every new test
reserve a distinct natural position before observing its cases. Position `k`
uses level `η/((k+1)(k+2))`; positions may be skipped because of crashes,
unrelated records or eviction. Suppose the per-test bound holds conditional
on prior history. Across any finite set of reserved positions the probability
of a false refusal, including any number of later reuses in the same scope,
is at most `η`.

*Proof.* The finite set of used positions is contained in a sufficiently
large initial interval of natural numbers. Its spending sum is bounded by
that interval's telescoping sum, at most `η`. A wrong reused refusal must
originate in a wrong original rejection; reuse adds no event to that union.
The same argument applies separately to admission confidence. ∎

The reservation must survive restarting, eviction and failure; reopening an
older snapshot starts a different statistical experiment. Missing cache
entries merely cause another test at a fresh position. The scope's semantic
identity and faithful restoration of stored evidence are hypotheses, not
properties inferred from matching type names. A bounded cache can forget a
refusal without weakening the risk bound, provided its spending clock does
not rewind. A successfully learned implementation requires its own artifact
storage; this refusal history does not supply one.

**Staged acquisition.** Instead of choosing a single training size, declare
strictly increasing sizes `b₁ < … < b_R = B` before observing new cases.
Fit on the first `b_r` available training cases at stage `r`, then freeze
the candidate and test it on fresh independent cases. Stop at the first
passing candidate. A failed test's observed cases may join training for later
stages, up to the maximum training size `B`; they must never serve as those
later stages' fresh tests. A failed fit may advance without spending its
unused test allocation. No rate of learning or monotonic improvement is
assumed.

**Theorem 20.18 (adaptive training with fresh certification).** Give each of
request `k`'s `R_k` stages level `α_k/R_k`, where
`α_k = δ/((k+1)(k+2))`. Under the conditional fresh-case sampling assumption
of Theorem 20.14, the probability of ever admitting a candidate with error
greater than `ε` is at most `δ`, despite early stopping and reuse of failed
tests as training for later candidates.

*Proof.* Conditional on the history before a stage's test, its frozen
candidate is already chosen. A candidate of error above `ε` passes its fresh
test with probability at most `α_k/R_k`, by the zero-loss argument of
Theorem 20.14. A union bound over the declared stages is at most `α_k`, and
another over requests is at most `δ`. Skipping unused levels and stopping
early only remove events from this union. Reusing earlier observations for
fitting changes the chosen candidate, not the freshness of its next test. ∎

This does not guarantee a saving: repeated fitting and stricter per-stage
tests may cost more than one well-chosen training size. At most `B` cases
are supplied to any fit, and at most `R_k` fits are attempted; testing has its
own separately charged case cost. The case budget, schedule and learning
procedure are parameters, rather than knowledge of any particular task.

**Prioritizing acquisition.** A predictor may supply a score for each valid
single-connector gap. Ranking these candidates changes only their order:
validity is still determined by the contracts and reachability. Ranking must
not remove candidates; equal scores preserve the original order. A finite
attempt budget can still prevent reaching a low-ranked useful candidate.

**Theorem 20.19 (valid ranking and acquisition exchange).** (i) Every
permutation of a list of valid candidates remains valid. (ii) Consider two
attempts with fixed independent success probabilities `q_a,q_b` and expected
costs `c_a,c_b`, followed by a common suffix of expected cost `T` if both
fail. The difference in expected cost between order `a,b` and order `b,a`
is `c_a q_b − c_b q_a`. Thus `a` first is no worse when
`c_a q_b ≤ c_b q_a`; for positive costs, this is decreasing `q/c`.

*Proof.* (i) Permutations preserve membership. (ii) Subtract
`c_b+(1−q_b)c_a+(1−q_b)(1−q_a)T` from
`c_a+(1−q_a)c_b+(1−q_a)(1−q_b)T` and cancel the equal suffix terms. ∎

Under these fixed-probability assumptions adjacent exchanges give the
cost-minimizing order. Learned estimates need not equal those probabilities,
and an acquisition's failure can change later learning opportunities; the
exchange result alone gives no optimality guarantee for adaptive predictions.
Ranking introduces no new admission rule: candidates still require their
ordinary certification. The score model and its features are replaceable
policies; no domain semantics follows merely from a contract's shape.


**Retaining unmatched observations.** For a fixed prefix, form an ordered graph
whose vertices are observations and whose edges join an earlier observation
to a later one with an equal input key and semantically incompatible labels.
Maintain every unmatched vertex. At each arrival, match it to the earliest
incompatible unmatched vertex with the same key, if one exists; otherwise retain
it. Compatible labels do not justify discarding an observation: repeated labels
can supply distinct endpoints for later contradictions.

**Theorem 20.20 (maximal contradiction witnesses).** The procedure produces
disjoint valid contradiction pairs. No edge has both endpoints unmatched after
any prefix. If m pairs are produced and a maximum matching has k pairs, then
k ≤ 2m. Each deterministic predictor therefore makes at least m errors under
the key and separation hypotheses of Theorem 20.16.

*Proof.* Initially there are no unmatched edges. Retaining a vertex adds no
edge among unmatched vertices, since all earlier unmatched vertices with the
same key were checked. Matching removes one earlier vertex and consumes the
new one; removal preserves absence of unmatched edges. Thus every edge touches
a matched endpoint. From each edge of any alternative matching choose one such
endpoint. Disjointness of the alternative matching makes those chosen endpoints
distinct. There are only 2m available endpoints, so k ≤ 2m. The error lower
bound follows from Theorem 20.16 for the resulting disjoint pairs. ∎

The procedure need not find a maximum matching, and changing greedy choices
need not improve every sample. The rejection threshold and confidence allocation
remain those of Theorem 20.16. Semantic callbacks must be pure and keys faithful.
Storing all unmatched observations uses linear space in the fixed prefix and
may require quadratic separation checks within one key bucket; no distribution
or label-equivalence shortcut is assumed. Passing remains inconclusive.

**Theorem 20.21 (bounded certification overdraw).** Partition a fixed finite
outcome stream into consecutive batches of size at most a positive integer B.
Draw a batch before evaluating its cases in order, and stop evaluating at the
first failure, drawing no later batches. Admission is equivalent to every
outcome in the entire stream being successful. Drawn observations never exceed
the stream length; admission draws the entire stream. If E observations were
evaluated and D drawn, then D < E + B, so D − E ≤ B − 1.

*Proof.* Each successful batch is fully evaluated, adding the same number to
D and E. In a rejected batch of length b ≤ B, at least one case is evaluated;
its unscored suffix therefore has length at most b − 1 ≤ B − 1. No later batch
is drawn. If no batch fails, every observation is evaluated and D = E.
Conjunction across batches equals conjunction across their concatenation. ∎

This is a deterministic accounting result, conditional on exact-size replies
and faithful sequential evaluation. Incomplete or oversized replies are
inconclusive and may violate the overdraw bound. Fresh conditional IID sampling,
a frozen candidate and the sample count of Theorem 20.14 are still required for
the statistical guarantee. A batch cap changes neither that count nor the
admission predicate on a fixed stream. Different physical samplers may produce
different streams when their call sizes change. Smaller batches can require
more sampler calls; no universal compute or label improvement is claimed.

**Theorem 20.22 (fixed-size error-tolerant certification).** Fix n and an integer
cutoff k before seeing validation cases. For a frozen candidate with IID loss
probability p, admit iff at most k of the n cases are errors. If a conservative
upper bound on P(Binomial(n, ε) ≤ k) is below α, then for every p > ε the
probability of admission is at most α. The stage/request allocations of Theorems
20.14 and 20.18 therefore apply unchanged. Rejecting early at error k+1 preserves
the full fixed-stream admission rule and never evaluates more than n cases.

*Proof.* Couple Bernoulli errors at ε and p using the same independent uniform
variables. Every error at ε is also an error at p, so the latter count is at
least the former, pointwise. The event of at most k errors at p is contained in
the event at ε. The binomial law and conservative numerical bound imply the
claimed probability. The existing union bound composes levels across stages and
requests. Once k+1 errors occur, extending the stream cannot reduce that count;
otherwise admission requires evaluation of all n cases. ∎

The count-event containment is formalized conditional on a coupling and the
reference probability bound. The IID binomial law, existence of the uniform
coupling for the actual sampler, and conservative numerical CDF implementation
remain explicit trusted boundaries. A fixed finite cutoff can be selected by
searching counts with a conservative CDF comparison; uncertain comparisons may
refuse but never justify admission. If even zero errors cannot certify at n,
the attempt is inconclusive before fitting or sampling. No optional peeking
at case values may choose n or the cutoff. Positive-error admission does not
permit reusing training observations or changing the candidate during testing.
Larger held-out budgets can admit useful nonzero-error experts, at additional
label and compute cost; no universal efficiency or capability claim follows.
