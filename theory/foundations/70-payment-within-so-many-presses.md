# 70. Payment within so many presses

Chapter 67 counts how far a state is from payment and teaches that count on the trials that were
paid. Where several presses are needed, paid trials are few, and most presses teach the count
nothing. This chapter treats a learner that keeps one reading for each number of presses, each
taught from the readings below it: what such a reading is to say, that every press carries its
lesson whether or not the trial was paid, and what a learner that follows the readings is
guaranteed.

## 70.1 Model

Tasks, states, presses, ways and distances are those of 67.1. A state is **within** `k` when it
has a way of length at most `k`; within nought is paid. **Level** `k + 1` is to say of a state
and a press whether the state the press leads to is within `k`: level one, whether the press is
paid at once. A level **answers** for a press when it says yes. The frame gives the states and
presses no meaning, and nothing names how many levels a task needs.

## 70.2 What a level is taught

**Proposition 70.1 (a level's lesson is the answers below it at the state after).** A state is
within `k + 1` exactly when it is paid or some press leads from it to a state within `k`.

So whether level `k + 1` is to answer for a press is settled by the state the press led to: it
is to answer exactly where that state is paid or level `k` answers there for some press. The
lesson needs neither payment nor the end of a trial. Every press that is followed by a state
carries it, in a paid trial or an unpaid one, where by 67.1 the count of chapter 67 is taught
only on the states of paid trials. And the lesson of a level is formed from the level below it
alone, which is held as it is while the level is taught.

**Proposition 70.2 (a level answers from the distance up).** With a state's distance `n`, the
state is within `k` exactly when `n ≤ k`. A level holds what every lower level holds.

So the levels are the count of chapter 67 said otherwise, one yes or no for each number in place
of one number: the least level at which a state is within is its distance.

## 70.3 Following the levels

**Proposition 70.3 (the lowest level that answers).** At a state of distance `n + 1`, a press
for which level `n + 1` answers begins a shortest way, and no lower level answers for any press
there.

**Proposition 70.4 (a learner that follows them is paid).** Let a learner press, at every state
of distance `m + 1` it stands at, a press for which level `m + 1` answers. Then from a state of
distance `n` it is paid after exactly `n` presses.

So a learner whose levels are right needs no count of where it stands: it presses a port for
which the lowest answering level answers, and each such press brings the next lower level to
answer. The state reached is a sub-goal in the sense of 67.3, now marked for every number of
presses and from every press, not only along paid trials.

## 70.4 After a wrong press

**Proposition 70.5 (a mended trial).** After any press, a learner that follows the levels from
the state reached is paid in the least number of presses from there.

So on a forgiving task (67.5) a wrong press costs the presses it adds and no more: a trial with
at least as many presses left as the state reached is from payment is still paid.

**Proposition 70.6 (ranking presses by the state after).** At a state of distance `n + 1`, a
press whose state after is no further from payment than the state after any other press begins
a shortest way.

So a choice that ranks the presses by how soon their levels answer, the lowest answering level
first, is right without knowing the distance of the state itself.

## 70.5 What is assumed and what is left open

Assumed as in 67.4: a press from a state leads to one state; the learner can tell the states
apart from what it is shown; and, for 70.3 to 70.6, that the levels are right at the states met.

Left open, and matters of the literature or of measurement recorded in the research diary. How
well a learned level is right, and how wrong answers add up: a level is taught the answers of
the level below, so what that level has wrong is taught on, and over `k` levels the errors can
add (the bound of Munos and Szepesvári, 2008, for value functions fitted one from another grows
with the number of fittings). That a level taught from levels held fixed learns where one reading
taught by its own answers at the state after does not: the lesson of the first does not move
while it is taught, the lesson of the second does (Riedmiller, 2005; van Hasselt and others,
2018). That level one can say "none": taught only on a learner's own well-paid presses it holds
few states where no press pays, and what it then answers at such states is not taught. How
many levels to keep, and what to press where no level answers. And tasks in which chance decides
where a press leads, where a state after is not one state.

In Lean being within is `NCA.Within`, with `NCA.within_zero` and `NCA.within_mono`; 70.1 is
`NCA.within_succ`, 70.2 `NCA.within_iff_least`, 70.3 `NCA.lowest_level_begins_shortest` and
`NCA.lower_levels_silent` with `NCA.within_gives_way`, 70.4 `NCA.followed_is_paid` over
`NCA.run`, 70.5 `NCA.mended_is_paid` and 70.6 `NCA.nearest_after_begins_shortest`.
