# 25. Which word to climb, and when to stop

Two questions about the controller remain: how many climbs pass before a
floor exceeds `δ`, and what a predictive stopping rule needs to trace a fine
coverage–compute frontier. Both depend on how the controller picks the next
climb and when it stops.

## 25.1 Climbing order

Refinement solves a covering problem. Let `D` be the amount by which the
bound must fall to reach `δ`. Climbing item `i` costs `cᵢ` and lowers the
bound by `dᵢ`, a quantity revealed only after the climb.

**Theorem 25.1.** If no climb
lowers the bound by more than `r` per unit of compute, then any set of
climbs that lowers it by `D` costs at least `D / r`, in any order.

`D / r` is a lower bound, not necessarily the optimum of the fractional
relaxation: the highest-ratio climbs may not supply enough drop. For
example, reaching `D = 10` with climbs `(6, 1)` and `(4, 100)` requires
both even in the fractional relaxation, so the optimum is 101 rather than
`10 / 6`. With independent, known nonnegative drops and costs, the fractional
relaxation is solved by taking available climbs in descending drop-to-cost
order, taking a fraction of the last if needed.

For whole climbs, neither greedy rule is optimal. Take `D = 10`:

| items `(dᵢ, cᵢ)` | largest drop first | largest drop per cost first | optimum |
|---|---|---|---|
| `(10, 2)`, `(6, 1)`, `(4, 1)` | `(10, 2)`: cost 2 | `(6, 1)`, then `(10, 2)`: cost 3 | 2 |
| `(10, 5)`, `(6, 1)`, `(4, 1)` | `(10, 5)`: cost 5 | `(6, 1)`, `(4, 1)`: cost 2 | 2 |

For independent known drops, the ratio rule loses at most one climb's cost
over the fractional optimum: only its last climb can overshoot. These
assumptions need not hold for state-dependent certificates or ladder steps.
The controller charges by risk, not by expected drop per cost. Interpreting
that as a ratio heuristic requires additional assumptions:

- every climb is assumed to remove most of the item's charge;
- equal costs are assumed within a ladder step.

Actual drops are not known before the climbs, so these assumptions may not
hold on a given input.

Even when one ladder serves every item, items at different rungs can have
different next-climb costs. With different ladders the cost disparity can be
larger. For example, at target 0.41, two independent charges 0.4 and 0.3
can each be reduced to 0.001, at respective incremental costs 100 and 1.
The largest-charge rule spends 100, although refining the second item alone
reaches 0.401 at cost 1. Theorem 16.2 (§16) instead applies when the actual
independent reductions and costs are known; ordering by current charge does
not in general implement its threshold rule.

The generic controller can instead accept a caller-supplied priority based
on the item, current charge, and next invocation cost. One available
heuristic ranks charge per declared cost, treating free invocations first.
For positive binary64 costs, the controller compares the rounded quotients
first; when those tie, it compares the exact represented input ratios using
cross-products of integers. This distinguishes overflow and underflow ties
and preserves input order for genuinely equal ratios.
The charge is only a proxy for the unknown reduction, so this is not an
optimality guarantee. Each selected answer must still meet the same bound;
the conditional error-bound premise must hold for the states selected by
the new policy, rather than being inferred from another policy's calibration.

**Theorem 25.5 (incremental independent account).** Suppose each item's
charge depends only on its current observation and fixed calibration. After
one item climbs, replacing its old charge with its newly computed charge
produces the same account as recomputing all charges. This does not apply to
a certificate whose charges may depend on other items. The implementation
still sums the current charges in the same order at every step, so this
identity does not rely on floating-point addition being associative.

## 25.2 Why floors pass `δ` early

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

## 25.3 Stopping

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

## 25.4 Why the frontier is coarse

The default rule bins states by one feature, `log₁₀(bound / δ)`. That mixes states
that will answer with states that will not.

- **A state can be far from `δ` for two different reasons.** Many open
  items with moderate charges can still answer. A few fixed items with
  large risks cannot. The bound alone does not separate them, so most bins
  contain no state that later answers. In those bins any `λ > 0` stops,
  and the frontier jumps.
- **Candidate features follow from §25.2–25.3.**
  - The *floor ratio* `floor / δ`: states with floor ratio above 1 never
    answer, and the ratio rises monotonically.
  - The *open charge mass*, the sum of the current charges on items that
    can still climb. For a general account it need not equal `bound − floor`:
    changing open readings can change the charges of fixed items too.
  - The number of open items whose charge exceeds the gap `bound − δ`.

  The implementation can optionally split each bound bin by the fraction
  of current charge on open items. If no account is available and the bound
  is infinite, the controller instead bins the open charge relative to the
  target; these charges are refinement priorities, not a certified bound.
  For two groups of trace states, with
  sizes `n₁, n₂` and empirical answer rates `p₁, p₂`, their split reduces
  the in-sample sum of squared prediction errors by

  `n₁ n₂ (p₁ − p₂)² / (n₁ + n₂)`.

  This is nonnegative, but it does not guarantee improvement on new inputs:
  smaller bins can have noisier estimates, and unseen bins continue by
  default. A valid floor is a separate feature, not inferred from the open
  charge mass.

[Theory index](../THEORY.md)
