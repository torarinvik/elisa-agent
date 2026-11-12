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

## 52.8 A late teacher whose choices vary

Combine 52.6 and 52.7: the teacher takes any good action, and takes over up to `u` steps after the learner's first bad
one. Three things are then known. An action the teacher shows is good. By Theorem 52.7, an action of the learner more
than `u` steps before a takeover, or in an episode with none, is good. And among the learner's last `u`
actions before a takeover at least one is bad, without saying which.

The merging rule of 52.7 has nothing to work on here, since no action is ever known bad at a particular history. A
candidate machine, with a set of good actions for each state, is refuted by a takeover exactly when it holds all `u`
actions of that window good.

Let the learner draw one surviving candidate at random and follow it until the next takeover. Sort the candidates by the
actions they would themselves take along the window; there are at most `K = |O|^u` such classes, and every candidate in
the class of the one followed holds the whole window good and is refuted with it.

**Theorem 52.11 (agreement with a random candidate).** For candidates sorted into `K` classes, the number sharing a
candidate's class, summed over the candidates, is at least the square of their number divided by `K`.

So a takeover removes, on average over the draw, at least a share `1 / |O|^u` of the candidates. By the usual argument
on the logarithm of their number, which is not proved here, the expected number of takeovers is at most

`|O|^u ln |C|`, with `ln |C| = n |A| ln n + n ln (2^|O| - 1)`.

The bound is polynomial in the size of the skill and exponential in the delay, counted in steps. For `u = 0` it has the
form of 52.7. Whether the exponential is necessary is open: a learner that puts at most one doubtful action in each
window would learn one fact per takeover, but it needs actions it already knows to be good around the doubtful one, and
at the start it knows none.

What the bound says for design is that the delay matters as a number of steps and not as time. A learner that decides
less often than the teacher reacts has `u` near one, and pays `|O|` where it would pay `|O|^u`. The bound is again for a
learner that holds all candidates; an efficient learner for this case is not given here.

## 52.9 A teacher who is sometimes later than assumed

Let the learner assume a delay of one step, as 52.8 recommends, and blame its last action before a takeover. A person
does not always react within one step. When the reaction is a step late, the blamed action is the one after the bad
one: an action that may be good is marked bad, and the bad one goes unjudged. Call such a mark *wrong*.

Under the rule of 52.7 one wrong mark is never withdrawn. The history it sits on can no longer share a state with the
histories where that action is good, and the same follows for the histories before it that lead there. Each wrong mark
therefore costs states, and a machine with more states draws more takeovers, some of them late in turn.

The remedy is to believe a mark only on repeated evidence, and the question is where to gather it, since a long history
seldom occurs twice. Take the current machine and call the pair of a state and the observation read from it a
*transition*. Every judged action after a history belongs to the transition that history ends on. For one transition
and one action, let `b` be the marks against it and `g` the times it was recorded good.

If the machine is right about the state before, all histories on one transition end in one state of the skill.

- Where the action is bad in that state, it is never recorded good there, by Theorem 52.7 with one more action left
  unjudged: `g = 0`, and every repetition of the mistake adds a mark.
- Where the action is good, marks against it are all wrong, and they arrive only when the action before was bad and
  the teacher was late; every other time the action stands it adds to `g`.

The learner believes the marks of a transition while `b ≥ k` and `b > θ (b + g)`, for a count `k` and a share `θ`.

**Theorem 52.12 (what belief takes).** If `num (b + g) < den b` then `num g < (den - num) b`.

With `θ = 1/4` a mark is believed only while `g < 3b`: wrong marks on a good action must number at least a third of
the times it stood. A bad action is believed after `k` marks, so each split costs `k` takeovers where it cost one.

The machine is not right at the start, and a transition of a wrong machine mixes states. So nothing believed is kept:
after every takeover each mark is judged again on the machine as it then is, the machine is rebuilt from the marks
believed, and this repeats until the beliefs settle or a fixed number of rounds has passed. That this converges is not
proved. It is measured in the research diary.

## 52.10 Unjudged steps

A step the teacher did not show contributes no good judgement at its history, so that history carries no evidence
from the step. The learner's answer after such a history is unchanged by the step. §52.9 applies the same margin to
the actions before the marked one. The rule is in `taken_over`, which takes a missing action as an unjudged step.

## 52.11 Reading more often than deciding

Let time run in ticks. The learner reads an observation at every tick but decides only every `k` ticks, and holds its
action in between. The teacher watches every tick and judges the action in force against the state of the skill at that
tick, which the observations up to it determine.

A judgement at tick `t` is a fact about `f` after the history up to `t`. A learner whose histories are read only at
decisions files it under the history of the last decision, `t₀ ≤ t`. The two histories differ by the observations of the
ticks `t₀ + 1, …, t`. Call the mark *misfiled* when they end in different states of the skill. A judgement that the held
action is bad at `t` may then be filed against a decision that was right when it was made.

**Theorem 52.13 (misfiled marks are bounded by changes).** For a skill whose state after a history is determined by
its last observation, a judgement made in a step with no change of observation since the decision is filed correctly.
For any skill, the steps that contain a change number at most the changes.

For the first part, the history up to the judgement and the history of the decision end in the same observation, so
they end in the same state. For a skill with longer memory nothing is claimed: the steps without a change are only the
ones where misfiling cannot come from the reading rate. The count holds because each change falls in one step, so the
steps containing one are the image of the changes. The count is proved in Lean as `steps_with_change_le_changes`.

So misfiling grows with `k`, because a longer step contains more changes. Deciding every tick removes it but lengthens
the window of 52.8: a reaction spread of `s` ticks spans `s / k` decisions, and the bound of 52.8 is exponential in
that. This is the trade-off measured in the research diary, where a shorter step helped a teacher who judges every tick
and hurt one who judges at decisions.

The trade-off disappears if the learner keeps its histories at the rate it reads and not at the rate it acts. A mark is
then filed under the history up to the tick it judges, which is exact. The window still counts decisions, since the
action is held between them.

**Theorem 52.14 (held actions do not widen the window).** Within `w` consecutive ticks there are at most
`(w - 1) / k + 2` distinct decisions, so the candidate classes of 52.8 along such a window number at most
`|O|^((w - 1) / k + 2)`.

The ticks of the window fall into the steps `⌊t / k⌋` for `t` from `t₁` to `t₁ + w - 1`, an interval of integers of
length at most `(w - 1) / k + 2`, and a held action repeats one decision. This is not yet proved in Lean.

The design that follows is a learner that reads every tick, decides every `k` ticks, files marks and good judgements at
the tick they concern, and counts its unjudged margin in decisions. It is a prediction to be tested. Nothing here shows
that state merging attains the bound.

## 52.12 Judgements of uncertain time

§52.11 files a judgement at the tick it concerns, but the learner sees only the tick it is made. A teacher who judges
every tick concerns the tick it judges. One who judges decisions concerns the tick the decision was made. An action the
teacher shows and holds concerns the tick it was chosen, which may lie before the current step: a teacher who takes
over in the middle of a step holds what it chose earlier. Which tick a judgement concerns is not known to the learner
and differs between teachers.

**Theorem 52.15 (a judgement whose ticks agree is filed exactly).** Let a judgement concern some tick of a set `I` of
ticks at or before the one it is made. If the skill is in the same state after every history ending at a tick of `I`,
filing it under any tick of `I` files it under the state it concerns, whichever tick that is. For a skill whose state
is set by its last observation this holds when the observation is the same at every tick of `I`.

This follows from the definition. Two cases make `I` a single tick. A teacher who reconsiders its shown action at every
decision of the learner has, at a decision tick, just chosen it there, so a shown action filed only at decision ticks is
filed exactly for every such teacher. The action the teacher held before the step is not judged by being held. The
learner's own steps between decisions are judged by whether the teacher let them pass, and for those `I` runs from the
decision to the tick, so 52.15 files them exactly when the ball did not cross a band in between.

Filing shown actions only at decision ticks keeps one of every `k` of them. Whether leaving the learner's changed steps
unjudged as well is worth the judgements it loses is not shown here and is measured in the research diary.
