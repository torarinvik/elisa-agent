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
them, so a learner acting by majority needs at most `n (|A| log₂ n + log₂ |O|)` takeovers. The bound holds for any
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
