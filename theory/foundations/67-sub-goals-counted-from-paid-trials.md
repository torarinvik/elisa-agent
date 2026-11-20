# 67. Sub-goals counted from paid trials

A learner taught by payment alone is told little by an unpaid trial of several presses: the trial
was lost, but not at which press. This chapter treats a count of how far a state is from payment,
learned from the trials that were paid, and states what a press over which that count falls by one
is guaranteed to be, and under what assumptions.

## 67.1 Model

A **task** has states, presses, and for each state and press the state the press leads to; some
states are **paid**. The frame gives the states and presses no meaning. A **way** of length `n` from
a state is a run of `n` presses that leads from it to a paid state; a paid state has the way of
length nought. The **distance** of a state is the length of its shortest way, where it has one.

A **trial** is a run of presses from some state; it is **paid** when it ends in a paid state. When a
paid trial of `m` presses stands at its `i`-th state it has `m − i` presses **left**.

A **count** assigns each state a number. It is **right** at a state when that number is the state's
distance.

## 67.2 What a paid trial tells of a state

**Proposition 67.1 (a paid trial bounds the distance).** If a paid trial had `l` presses left when
it stood at a state, the state has a way of length `l`, so its distance is at most `l`.

So what the paid trials had left at a state never falls below its distance, and equals it as soon
as one of them went from there by a shortest way. A count taught on what paid trials had left is
taught numbers that are distances exactly when those trials were shortest from where they stood;
where some were longer, the least of them is the better guide and the count taught on all of them
may stand above the distance.

## 67.3 A press over which the count falls by one

**Proposition 67.2 (the state reached).** If a state has distance `k + 1` and a press leads from
it to a state that has a way of length `k`, the state reached has distance exactly `k`.

**Proposition 67.3 (marked exactly when shortest).** Let a state have distance `n + 1`, and let the
count be right at it and at the state a press leads to. Then the count falls by one over the press
if and only if the press begins a shortest way from the state.

So a learner that teaches a press as good where its count fell by one over it, and that has a count
right at both states, teaches no press that leaves the shortest ways and misses none that keeps to
them. The state reached is a **sub-goal**: it is not paid, but it is known to be one press nearer.
Nothing in this names what the states hold; the count is formed from the learner's own paid
trials.

## 67.4 What is assumed and what is left open

Assumed: a press from a state leads to one state (no chance in the task); the learner can tell the
states apart from what it is shown; and, for 67.3, the count is right at the two states. Left open,
and matters of measurement: how often a learned count is right; what it gives at states no paid
trial stood at, where nothing was taught and nothing is guaranteed; how a count taught on trials
that were not shortest errs, which by 67.1 can only be upward in what it was taught; and tasks in
which chance decides where a press leads.

## 67.5 Where a trial goes on after a wrong press

Call a task **forgiving** where a trial may go on after a press that does not begin a shortest way:
the press costs what it cost, and payment can still be had. Two things change for a learner taught
by its trials.

**Proposition 67.4 (unmarked exactly when it leaves the shortest ways).** Let a state have distance
`n + 1`, and let the count be right at it and at the state a press leads to. Then the count does
not fall over the press, that is, it is at least `n + 1` at the state reached, if and only if the
press does not begin a shortest way from the state.

This is 67.3 from the other side: with a right count, the presses over which it does not fall are
exactly the wasted ones, so a learner may teach such a press as not good as surely as it teaches the
other as good.

**Proposition 67.5 (a long paid trial holds a wasted press).** If a paid trial has more presses
than the distance of the state it began at, some press of it did not begin a shortest way from the
state it was made at.

So on a forgiving task a learner that teaches every press of a paid trial as good teaches wasted
presses as good, at least one in every paid trial longer than it need have been; where every press
that leaves the shortest ways ends the trial, no paid trial is longer than it need be and the same
teaching is sound.
And a wasted press that was not the last of its trial is in no unpaid trial's last place: taught
only by the judgement of the trial, it is taught as good when the trial was mended and not at all
otherwise. What is then taught as not good are last presses alone, and whatever the frame shows of
how far a trial has run tells them from the rest without a port being read. Teaching each earlier
press by the count, as good where it fell by one and as not good where it did not fall, is by 67.3
and 67.4 right at every press where the count is right at both states, on a forgiving task or not.

## 67.6 A chance for each press

Let a learner give the presses at a state numbers that are taught towards one where the press was
good and towards nought where it was not.

**Proposition 67.6 (shares cannot hold two).** If the numbers at a state are not negative and sum
to at most one, then of any two presses one is given at most a half.

So where two presses both begin shortest ways, numbers that share one total cannot be right at
both, and what is taught of one is taken from the other; numbers given to each press by itself can
be one at both, and nought at all where no press brings payment nearer, without a further press
that stands for "none". Which of the two a learner learns from faster is a matter of measurement.

## 67.7 What is assumed and what is left open, for 67.5 and 67.6

Assumed as in 67.4. Left open: how a count taught on what paid trials had left, which on a
forgiving task includes trials longer than need be, comes to be right (by 67.1 it is taught too
high, never too low, and the least seen at a state is the better guide); and everything about how
fast a network learns under either way of giving numbers, of moving its pictures, or after it has
been taught long on little, which are matters of measurement recorded in the research diary.

In Lean 67.1 is `NCA.trial_gives_way` with `NCA.least_le_trial`, 67.2 `NCA.reached_is_least`, and
67.3 `NCA.falls_iff_begins_shortest` with `NCA.marked_iff_begins_shortest`; 67.4 is
`NCA.stays_iff_leaves_shortest`, 67.5 `NCA.long_trial_holds_wasted` over `NCA.Shortest` and
`NCA.least_exists`, and 67.6 `NCA.shares_halve`.
