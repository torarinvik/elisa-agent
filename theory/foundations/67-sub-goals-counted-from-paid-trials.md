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

In Lean 67.1 is `NCA.trial_gives_way` with `NCA.least_le_trial`, 67.2 `NCA.reached_is_least`, and
67.3 `NCA.falls_iff_begins_shortest` with `NCA.marked_iff_begins_shortest`.
