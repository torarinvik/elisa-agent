# 53. Judgements that carry across observations

Chapter 52 counts corrections by the states of the skill taught, and each observation there is a symbol of its own. When
observations are readings of many components, the number of distinct observations grows exponentially in the number of
components, and a learner that keeps a judgement only where it was made must be corrected at each of them. This chapter
lets a judgement carry to every observation that agrees with it on the components that matter, and bounds the
corrections by how few components matter rather than by how many observations there are.

## 53.1 Model

An observation `o` has components `o₁, …, oₙ`, each from a finite set of at most `d` values. A **judgement** `(o, a, v)`
says that action `a` at observation `o` is good (`v = ⊤`) or bad (`v = ⊥`). Judgements come from a **target**
`t : O → A → Bool`, and a correct teacher only makes judgements that agree with it.

A set `S` of components **suffices** for `t` if two observations that agree on every component of `S` have the same
target: `t o = t o'`. A skill whose action is a function `f` of the observation has the target `t o a = (a = f o)`. A
choice among candidates, where each candidate is an observation and the only action is to take it, has the target
`t o take = (o is acceptable)`.

Some components may be read always, such as which kind of situation an observation belongs to. They can split the
problem: each of their values, a **context**, gets its own family of sets, so different components may matter in
different contexts. Nothing below changes within a context, and the count of 53.4 is summed over the contexts that
occur.

## 53.2 Consistent sets

A set `S` is **consistent** with judgements `J` if no two judgements of `J` on observations that agree on `S` give the
same action opposite verdicts. Two observations that agree on `S` are in the same **class** of `S`.

**Theorem 53.1 (a sufficient set is never refuted).** If every judgement of `J` agrees with `t` and `S` suffices for
`t`, then `S` is consistent with `J`.

Two judgements in one class of `S` and on one action both equal `t` there, and `t` is the same on the class. Proved in
Lean as `sufficient_set_consistent`.

**Theorem 53.2 (refutation is permanent).** A set consistent with `J` is consistent with every subset of `J`, and every
superset of a set consistent with `J` is consistent with `J`.

So a set refuted by the judgements so far stays refuted as judgements accumulate, and the smallest consistent sets can
be searched by size. Proved in Lean as `consistent_of_subset_judgements` and `consistent_of_subset`.

## 53.3 Learning by voting

Fix a family `H` of candidate sets, for instance all sets of at most `k` components. The learner keeps the sets of `H`
consistent with its judgements. For an observation `o` and an action `a`, a consistent set **votes** good or bad if its
class of `o` holds a judgement of `a`, with that judgement's verdict, which consistency makes unique; otherwise it
abstains.

At each decision the learner is offered pairs `(o, a)`: one observation and its actions, or many candidate observations
and one action. It chooses a pair whose good votes outnumber its bad votes. If no pair has such a majority it guesses,
preferring pairs without a bad majority. The teacher takes over only when the chosen pair `x` is bad. It then marks `x`
bad and shows a pair `y` it judges good.

**Theorem 53.3 (what a takeover removes).** Let `S*` in `H` suffice for `t`. Every takeover either gives `S*` its first
judgement of `y`'s action in `y`'s class of `S*`, or refutes at least half of the sets that voted on `x` or on `y`, and at
least one.

If `x` was chosen with a good majority, at least one set voted, the sets that voted good on `x` are at least half of
those that voted on `x`, and the new bad judgement of `x` refutes each of them. Otherwise no pair had a good majority. If
`S*` already held a judgement of `y`'s action in `y`'s class, that judgement is good by 53.1, so `S*` voted good on `y`.
Since `y` had no good majority, the sets voting bad on `y` were at least as many as those voting good, so at least half
of those voting and at least one, and the good judgement of `y` refutes each of them. If `S*` held no such judgement, it
has one now.

**Theorem 53.4 (corrections bounded by what matters).** If some set of `H` with at most `k` components suffices for `t`,
the learner of 53.3 is taken over at most `|A| · dᵏ + |H|` times. With `H` all sets of at most `k` of `n` components this
is at most `|A| · dᵏ + Σ_{j ≤ k} C(n, j)`.

Each takeover lowers by at least one the number of pairs of a class of `S*` and an action still without a judgement, at
most `|A| · dᵏ`, plus the number of consistent sets in `H`, at most `|H|`, and neither grows. The count of steps that
lower a natural-number potential is proved in Lean as `steps_le_potential`.

A learner that keeps each judgement only at its own observation is the case `k = n`, with `dⁿ` classes. For a fixed `k`
the bound of 53.4 is polynomial in `n` instead.

## 53.4 What this does not cover

Theorems 53.1 to 53.4 assume a correct teacher; §53.5 replaces them for one who is not. A judgement made late, as in
§52.6 and §52.9, contradicts the sufficient set like any other error. The theorems cover a target that depends on the
current observation only. A skill with memory, as in §52, also needs states, and how the classes of this chapter combine
with the merging of states is not settled here. When every consistent set votes, each takeover of the first kind in 53.3
refutes half of the sets left, and the halving argument of §52.3 bounds those takeovers by `log₂ |H|`; abstaining sets
weaken this, and only the count of 53.4 is claimed.

Which components exist is the domain's choice, as the sensor of a game is. The learner chooses only which of them
matter.

## 53.5 A teacher who contradicts themselves

A person does not judge by a fixed target. They take over when they prefer another placement, not only when the proposal
is unacceptable, and they weigh what the components do not show. Then no set of `H` may be consistent with the
judgements, every set is refuted, and the learner of 53.3 can only guess. The bound of 53.4 holds only for a correct
teacher.

Let each set keep a weight instead. A set **predicts** a verdict for an action at a class when its judgements of that
action there lean one way, and it is **contradicted** by a new judgement that goes the other way. Its weight is `βᵐ`,
where `m` counts its contradictions and `0 ≤ β < 1`, and the votes of 53.3 are weighted. With `β = 0` a contradicted set
weighs nothing, which is the learner of 53.3. With `β > 0` no set is lost, and a set contradicted less often outweighs
one contradicted more often.

**Theorem 53.5 (weighted majority).** Let `0 < β < 1`. Suppose every set predicts at every takeover's chosen pair, that
`N` sets start with weight one, and that some set is contradicted `m*` times. If each takeover follows a weighted
majority that the teacher contradicts, the learner is taken over at most `(ln N + m* ln(1/β)) / ln(2 / (1 + β))` times.

This is the bound of Littlestone and Warmuth. At each such takeover the sets that predicted wrongly hold at least half
the weight and keep a share `β` of it, so the total weight falls by at least the factor `(1 + β) / 2`. After `M`
takeovers it is at most `((1 + β) / 2)ᴹ N` and at least the weight `β^{m*}` of the best set. The step from a
per-takeover factor to the power is proved in Lean as `weight_le_pow`.

When some sets abstain, only the weight of the sets that predicted falls, and the bound is not claimed. A learner may
drop a set whose weight is a negligible share of the best set's in its context; its votes could not change a decision
unless the sets outnumbered the inverse of that share.
