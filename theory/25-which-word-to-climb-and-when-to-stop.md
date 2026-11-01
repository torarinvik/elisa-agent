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

[Theory index](../THEORY.md)
