# 76. Putting out or thinking on

A learner that acts in time has two things to settle at each step: what to do, and whether to do
it now. Chapter 16 treats an answer withheld where a reading is unsure. This chapter treats the
second question as a weighing of two risks, states what the plain rule earns at one step and
over a trial, what misread risks cost, why a learner under the rule cannot rest in doing
nothing, and what it costs to ask several readings in turn. It gives hypotheses, chances and
risks no meaning.

## 76.1 Model

At a step there are **hypotheses**, each something that could be done now, and for each a
**chance** that doing it now is right. The **best** hypothesis is one of the largest chance. The
**risk of putting out now** is the chance that the best hypothesis, taken now, is wrong; where
nothing else reads it, it is one less the best chance. The **risk of going on** is the chance
that the trial ends badly if nothing is put out at this step. The **rule** takes the best
hypothesis where its chance reaches a threshold `τ_p` and the risk of going on is at least a
threshold `τ_r` times the risk of putting out now, and otherwise goes on.

**Proposition 76.1 (the rule takes the smaller risk).** With `τ_p = 0` and `τ_r = 1` the rule
risks the smaller of the two risks, and putting out with any chance at the step risks at least
that.

One number says where the risk lies: the share of the two risks that is in putting out now,
nought where all the risk is in going on and one where all of it is in putting out. The rule
puts out exactly where that share is at most `1 / (1 + τ_r)`, a half for `τ_r = 1`. The share
decides; it is not what is learned, since nothing that happens has it as its chance, while each
risk is the chance of something that does.

## 76.2 Risks that are misread, and other thresholds

**Proposition 76.2 (what misreading costs).** If each risk is read within `e` of what it is,
the rule applied to the readings risks at most `2e` more than the smaller risk. With the risks
exact and a threshold `τ_r ≤ 1`, it risks at most the smaller risk and `(1 − τ_r)` times the
risk of putting out now.

So the rule is as good as its two readings are near, and no better. A threshold on the chance
adds nothing where the risks are exact; it is a guard for where they are not. A learner whose
two risks are each read from few lessons loses by the rule what it would not lose by a reading
it holds more surely, which is measured.

## 76.3 A trial of several steps

A trial is a run of steps. Putting out at a step ends the trial, paid with a chance of that
step; where nothing is ever put out the trial ends unpaid. A **way of putting out** gives each
step a chance of putting out there. What it is paid is the read of 75.1 with the steps, soonest
first, as its items: the chance of putting out as the chance of a match and the chance of the
step as the value. The chance that the trial ends paid if nothing is put out at a step is what
the way of putting out is paid over the steps after it, and one less it is the risk of going on.

**Proposition 76.3 (the best of the steps left).** No way of putting out is paid more often
than the largest chance of a step. Putting out at each step whose chance is at least the largest
chance of a later step, and going on otherwise, is paid that often.

## 76.4 Why it does not rest in doing nothing

**Proposition 76.4 (never putting out is unpaid; putting out more pays).** A way of putting out
that never puts out is paid nought. Raising the chance of putting out at a step whose chance is
at least what going on from it is paid does not lower what the way is paid, whatever is done at
the steps before.

Under a way that goes on everywhere, going on is paid nought at every step, so the rule puts
out at every step whose chance is above nought. A learner that reads the risk of going on from
how its own trials ended therefore leaves doing nothing as soon as it has seen such trials end
unpaid. A share given to doing nothing among the hypotheses holds no such correction: it is
only what the others leave, and it can pass the largest of them while they together hold more.

## 76.5 Concepts asked in turn

A **concept** is whatever gives, at a cost, an opinion of the step: chances for hypotheses, and
where it reads them the two risks. Concepts are asked in an order, and after each the rule is
applied to what has been said; the first time it takes a hypothesis no later concept is asked.

**Proposition 76.5 (asking in turn costs no more).** Where each concept is asked only if no
earlier one settled the step, the cost of thinking is the sum of each concept's cost times the
chance that it is reached, which is at most the cost of asking all.

So concepts are ordered cheaper first, and a dear one is paid for only at the steps the cheap
ones leave open. What is given up is what the later concepts would have said where an earlier
one was sure and wrong; that is the risk of putting out now, and is bounded by 76.2 as far as
that risk is read truly.

## 76.6 The scratchpad, and asking the kernel

What a concept works out at a step it may leave as a **note**, under a name, for the concepts
after it and for later steps. A note given a life of `l` steps and written at step `i` is read
at step `n` exactly when `i ≤ n < i + l`, as an entry of a channel of capacity `l` is (64.1); a
note with no life stays until it is written again or dropped. A note written again takes the
place of the one before, so what is worked out once at a step is read by every later concept at
no further cost, and a thought may be refined within a step.

A hypothesis may be an **asking of the kernel** (§20): produce a value of a type from these
inputs. Taken, it is not put out: the kernel serves it within the step, the answer is noted
under the type asked for, and the concepts are asked again from the first. At most `r` askings
are served at a step, so with `n` concepts thinking at a step asks a concept at most
`(r + 1) n` times. What the kernel guarantees of a request it guarantees of an asking: the route
is well typed, and a refusal for lack of budget is no value and never a wrong one.

## 76.7 What is assumed and what is left open

Assumed. That putting out ends the trial; where an output is passed over, putting out and going
on are paid alike there and the rule's tie puts out. That a trial in which nothing is put out
ends unpaid. That the chances and risks are what they are said to be: a learner has them only
as readings taught on its own trials, gathered under a way of putting out that was itself
changing, and how near they come is measured. That a concept's opinion does not turn on which
later concepts will be asked.

Left open. Thresholds that follow what was paid, and what they should follow. A risk of going
on that counts what thinking itself costs in time. A concept that knows no later one could
change the step, and how it may know. Steps paid in amounts and not by a chance.

## 76.8 A chance of its own for each hypothesis

The rule of 76.1 asks of a hypothesis only the chance that taking it now is right. Let the
chances instead be shares of one whole: amounts a_i > 0, the share of i being a_i over their
sum S, with going on counted among the hypotheses. A lesson is given only on the hypothesis that
was taken. Lower one amount by d, 0 < d < S, and leave the others: every other share goes from
a_j / S to a_j / (S - d), which is larger, and all of them by the one factor S / (S - d). So
what a hypothesis loses by a lesson is given to the others as they stand, to one that was never
judged as much as to one that was. Where going on is seldom or never judged, its share is then
made by what the ports were paid and says nothing of what going on is worth; where every port
taken has been unpaid, it holds nearly the whole, the rule puts nothing out, and no further
lesson comes.

Hence each hypothesis is given a chance of its own, taught on that hypothesis alone, and going
on is not a hypothesis among them: its worth is the risk of going on, read and taught apart
(76.1, 76.3). Chances of their own need not sum to one, and 76.1 to 76.5 ask nowhere that they
do.

## 76.9 What the risk of going on is taught by

By 76.3 going on at a step is worth the best chance of the steps left. A learner has those
chances only as readings. Let each trial give two readings x and y of later steps. Over any
trials the sum of the larger of the two is at least the larger of the two sums,

    max(Σ x, Σ y) ≤ Σ max(x, y),

with equality only where one reading is the larger in every trial. So where the later steps of
a trial are readings of one and the same chance, as in a world that stands still, the largest
of them overrates it, the more so the more steps are read, and a learner taught so holds going
on above its best hypothesis and waits. The reading at one named step does not: the step at
which the rule itself next put out. Where the rule put nothing out again, what going on came to
is how the trial ended, which is no reading at all.

In Lean, 76.1 is `NCA.rule_risks_least`, `NCA.least_risk_le` and `NCA.share_le_iff`; 76.2 is
`NCA.read_risks_cost_little` and `NCA.threshold_costs_little`; 76.3 is `NCA.paid_le_best` and
`NCA.out_where_best_paid`, over `NCA.bestBy`, `NCA.outWhereBest` and the `NCA.readBy` of chapter
75; 76.4 is `NCA.never_out_unpaid` and `NCA.out_more_pays`; 76.5 is `NCA.cost_le_all`, over
`NCA.costBy`; 76.8 is `NCA.share_rises` and `NCA.shares_rise_alike`; 76.9 is
`NCA.largest_overrates`.
