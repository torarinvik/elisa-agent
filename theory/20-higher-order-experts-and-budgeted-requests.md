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
checking (§2). Eliminators whose slots do not contain their output, like
`case` with `l ≠ b`, are not affected.

**Search.** An eliminator's output is a bare variable, so it is a candidate
for every goal. Pattern search then enumerates every value of the eliminated
type it can derive, and every way of filling the slots. Without further
pruning, installing `case` and `fold` makes every failing goal pay for that
enumeration.

[Theory index](../THEORY.md)
