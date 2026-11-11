# 52. Teaching by takeover

A learner acts, a teacher corrects it at its first wrong action, and the learner repairs itself. This chapter bounds the
number of corrections by the size of what is taught, under two assumptions about what the teacher will answer.

## 52.1 Model

A skill is a function `f : A* → O` from the history of observations to the next action, computed by a machine as in 51.1.
The learner holds a conjecture, a machine of its own. A **takeover** is a history `w` on which the conjecture's action
differs from `f w`. The learner then sees `f` on `w` and on the histories the teacher's demonstration passes through.

Two kinds of teacher are distinguished. A **hypothetical** teacher also answers `f` on any history the learner names,
whether or not it occurred. A **reachable** teacher answers only on histories that occur while the learner or the teacher
acts.

## 52.2 Takeovers with a hypothetical teacher

The conjecture is built from a table as in 51.2: each state `q` has an access history, the conjecture's action in `q` is
`f` of that history, and the start state's access history is empty.

**Theorem 52.1 (a takeover exposes a merge).** If the conjecture and `f` differ on `w`, then `w = u ++ a :: v` for some
cut such that `f` differs on `access q ++ a :: v` and `access q' ++ v`, where `q` is the state after `u` and `q'` the
state after `u ++ [a]`.

The table had given `access q ++ [a]` the row of `access q'`. The suffix `v` now separates them.

**Theorem 52.2 (a takeover adds a state).** A history with the row of `t` on the table's suffixes, separated from `t` by
a new suffix, is separated from every history the table holds.

**Theorem 52.3 (separated histories bound).** Histories that `f` separates pairwise number at most the states of any
machine computing `f`.

Together: the table starts with one history and each takeover adds one, so a skill with a machine of `n` states is learned
after at most `n - 1` takeovers, whatever the length of the episodes. Finding the cut of 52.1 takes one answer per position
of `w`, or about `log₂ |w|` by bisection, and each is a question about a spliced history.

## 52.3 Takeovers with a reachable teacher

A spliced history joins the start of one episode to the end of another. Where the observations do not depend on the
learner's actions, every history can be presented and the two teachers coincide. Where they do, the environment decides
what follows `access q`, a spliced history may never occur, and 52.1 gives the learner nothing it can ask. The learner
then has corrections alone. With counterexamples and no chosen questions, machines cannot be learned in polynomial time
in the worst case (Angluin 1990); the result is cited, not proved here, and a demonstration gives somewhat more than a
single counterexample.

The number of corrections is still bounded, by counting.

**Theorem 52.4 (a wrong majority halves).** If the guessed action is held by at least as many candidates as the true
action, and is wrong, at most half the candidates give the true action.

**Theorem 52.5 (halving bound).** If each of `k` corrections at least halves the candidates and one remains, then
`2 ^ k` is at most the number of candidates.

Take as candidates the machines with `n` states over the observations and actions seen. There are `n^(n|A|) |O|^n` of
them (Theorem 52.6 with no helper), so a learner acting by majority needs at most `n (|A| log₂ n + log₂ |O|)` takeovers. The bound holds for any
environment and any length of episode. It says nothing about compute: the majority is over an exponential set.

## 52.4 What the two bounds say

| Teacher | Takeovers | Other cost |
|---|---|---|
| Hypothetical | `n - 1` | about `log₂ |w|` spliced questions per takeover |
| Reachable | `n (|A| log₂ n + log₂ |O|)` | compute exponential in `n` as stated |

In both, the teacher's effort grows with the size of the skill and not with the time spent acting. The reachable bound
is larger by a factor of about `|A| log₂ n`, and an efficient learner that attains it is an open requirement, to be
approached by merging states on the histories that did occur. Both assume a teacher who answers consistently and takes
over at the first wrong action.

## 52.5 A skill as an action

Let `m` helpers be given, each a function from histories to actions, for example skills taught earlier. A machine may
then take as a state's action either a fixed action or the answer of one helper on the history so far.

**Theorem 52.6 (candidates with helpers).** The machines on `n` states whose actions are fixed actions or helpers number
`n^(n|A|) (|O| + m)^n`.

With 52.5, a rule that chooses among helpers with a controller of `k` states needs at most
`k (|A| log₂ k + log₂ (|O| + m))` takeovers from a majority learner. The same skill taught without helpers is bounded by
its own size `n`, which can be as large as the product of the controller and the helpers' machines. Each helper costs a
term `log₂ (|O| + m)` per state and no more, so many helpers may be offered at little cost in this bound.

A demonstrated action does not say which choice produced it: the fixed action explains it, and so does every helper
that gave the same answer. A merging learner therefore keeps, for each history, the set of choices that explain its
action, and lets histories share a state while some choice explains them all. The counting bound is for the majority
learner and is not shown for merging.

## 52.6 A late teacher

Let the teacher take over some steps after the learner's first wrong action. That action and those after it take effect,
so the episode leaves the teacher's path, and the teacher acts from wherever it has got to. The learner sees that a
takeover happened and what the teacher then does. It is not told which of its own actions was wrong.

**Theorem 52.7 (judged actions are right).** If the delay never exceeds `u`, every action the learner took more than `u`
steps before a takeover was right.

So the learner may record those earlier actions as right and must leave its last `u` unjudged. Nothing here bounds the
number of takeovers. The argument of 52.2 needs the history that was answered wrongly, and the halving argument of 52.3
needs each correction to remove the candidates that agree with the guess at one known history; a late takeover removes only
those that agree with it at every one of the last `u` steps. Whether teaching by a late teacher has a bound in the size of
the skill is open.

## 52.7 A teacher whose choices vary

Let each state of the skill have a nonempty set of good actions. The teacher, when it acts, takes any good action, and
may take different ones after the same history. It takes over exactly when the learner's action is not good. Its choices
are then inconsistent and its judgements are not: whether an action is good after a history depends on the state alone.

A learner that takes two different shown actions as a contradiction separates histories that end in the same state, and
its machine grows without limit. What the model does establish is this.

**Theorem 52.8 (conflicting judgements separate).** If an action is accepted after one history and rejected after
another, the two histories end in different states.

So the evidence about a history is two sets, the actions known good there (shown by the teacher, or taken by the learner
and let stand) and the actions known bad (taken by the learner and rejected), and two histories may share a state unless
an action is known good at one and known bad at the other. A shared state may take any action known good at one of its
histories. If that action is bad at another of them, the takeover that follows records it as bad there, and by 52.8 the
two can no longer share a state. Every takeover therefore rules out the machine that caused it.

**Theorem 52.9 (a popular action).** If every candidate holds some action good at a history, one action is held good
there by at least a share `1 / |O|` of the candidates.

**Theorem 52.10 (share bound).** If each of `k` corrections leaves at most a share `d / (d + 1)` of the candidates and
one remains, then `(d + 1)^k ≤ d^k` times the number of candidates.

A learner that takes the most popular action loses at least a share `1 / |O|` of its candidates at each takeover. With
`n` states the candidates number `n^(n|A|) (2^|O| - 1)^n`, so the takeovers are at most

`(n |A| log₂ n + n log₂ (2^|O| - 1)) / log₂ (|O| / (|O| - 1))`.

For three actions the divisor is 0.585, where a consistent teacher has 1 (52.3): about 1.7 times as many takeovers, plus
the larger count of candidates. The cost of free choice grows with the number of actions, roughly in proportion to it.
As in 52.3 the bound is for a learner that counts candidates, and merging is not shown to attain it. A consistent teacher
is the case where every action but the shown one is known bad.
