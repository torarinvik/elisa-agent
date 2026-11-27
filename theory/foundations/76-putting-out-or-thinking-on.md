# 76. Putting out or thinking on

A learner that acts in time has two things to settle at each step: what to do, and whether to do
it now. Chapter 16 treats an answer withheld where a reading is unsure. This chapter treats the
second question as a weighing of two risks, states what the plain rule earns at one step and
over a trial, what misread risks cost, why a learner under the rule cannot rest in doing
nothing, and what it costs to ask several readings in turn, and what an asking of the kernel is worth. It
gives hypotheses, chances and risks no meaning.

## 76.1 Model

At a step there are **hypotheses**, each something that could be done now, and for each a
**chance** that doing it now is right. The **best** hypothesis is one of the largest chance. The
**risk of putting out now** is the chance that the best hypothesis, taken now, is wrong; where
nothing else reads it, it is one less the best chance. The **risk of going on** is the chance
that the trial ends badly if nothing is put out at this step. The **rule** takes the best
hypothesis where its chance reaches a threshold `τ_p` and the risk of going on is at least a
threshold `τ_r` times the risk of putting out now, and otherwise goes on.

The architecture diagram also prints a selectable upper bound on the quotient of waiting risk
and acting risk. For positive acting risk this alternative takes the best hypothesis when its
chance reaches `τ_p` and waiting risk is at most `τ_r` times acting risk. The runtime treats the
quotient as infinite when acting risk is zero. The propositions below concern the lower bound.

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

## 76.10 A dearer concept, asked where the cheaper is unsure

Let two concepts be asked in turn, the cheaper at cost k and the dearer at cost K ≥ 0, and let
the cheaper give its best hypothesis the chance c. Two thresholds, b ≤ a, say where the cheaper
is taken at its word: at c ≥ a its best hypothesis is held to the rule of 76.1 with no more
asked, at c ≤ b the step is settled and nothing is put out, and between them the dearer concept
is asked. If that happens at a share q of the steps, a step costs k + qK, which is at most k + K
(76.5).

What the saving can lose is bounded on both sides. Where c ≥ a, no concept can give a
hypothesis a chance above one, so not asking loses at most 1 - a. Where every one of m
hypotheses has at most b, the chance that any of them is paid is at most the sum of their
chances, hence at most mb; that is all a concept that saw everything could have had there. Both
bounds take the cheaper concept's chances to be true chances given what it reads (76.2 says what
a reading that is off costs). So thresholds near one and nought lose little and save the dearer
concept wherever the cheaper is sure either way; a task in which the cheaper is sure at every
step never pays for the dearer one.

A hypothesis that is taken and judged not at once but by what it leads to is worth, by 76.3,
the best chance of the steps left; its lesson is that worth, read as 76.9 says: at the next
step at which the rule itself put out, by whichever concept was had there, or how the trial
ended where there was none.

## 76.11 A step of going on charged a share

By 76.3 and 76.9 going on at a step is taught to be worth the chance at the step where the rule
next puts out. Where going on shows nothing new, that chance is the chance of putting out now,
and the rule of 76.1 is left to a tie between two readings of one thing: which way it falls is
their noise, and a learner whose readings are honest waits about as often as not, for nothing.
Going on is not free: the world may change and time runs out. Let a step of going on be taken
to lose a share δ of what is to be had, with 0 < δ ≤ 1, so that going on for n steps to a step
worth v is worth (1 - δ)ⁿ v.

**Proposition 76.11 (a tie puts out, and the charge costs little).** Where the later step is
worth what now is worth, c > 0, going on for any n ≥ 1 steps is worth less than c, so the rule
puts out. And where the rule puts out now with chance c because (1 - δ)ⁿ v ≤ c, it gives up at
most v - c ≤ n δ v: a share δ of the later worth for each step it did not wait.

So the charge decides the ties and is paid only where waiting would have gained less than the
charge. Where waiting gains much, as before a question is asked, (1 - δ)ⁿ v stays far above the
chance of putting out now and the rule goes on as it did.

## 76.12 Going on held to what the last concept says

The chance of going on is read by the first concept, before the dearer ones are asked, and by
76.3 it is taught what the rule's next putting out was held to be worth. Read so, it is what
going on is worth over the steps that look alike to the first concept, and a dearer concept
tells those steps apart: where it gives its best hypothesis less than they are worth on the
whole, the rule of 76.1 waits. Where going on shows nothing new the dearer concept will say
at the next step what it says now, and the wait gains nothing; it is made again at every such
step until the time since the last judgement moves the reading.

Let the last concept asked give its best hypothesis the chance c, and let going on show at
every later step what is shown now. Then by 76.11 going on for n ≥ 1 steps is worth
(1 - δ)ⁿ c.

**Proposition 76.12 (held to the last word, the rule puts out and gives up nothing).** Where
going on shows what is shown now, what it is worth is at most (1 - δ) c, so holding the chance
read of going on to the smaller of itself and (1 - δ) c takes from it nothing that going on is
worth. And with it so held, for c > 0 and δ > 0, the risk of going on is above the risk of
putting out, whatever was read: the rule puts out.

What this presumes is that going on shows the same again. It is false where the world moves
of itself, and there a concept asked last and held to in this way puts out where waiting was
right; whether a world stands still is not read here but taken, and where it is taken wrongly
the cost is that of 76.11 with the later worth in place of c.

76.13 to 76.22, what an asking of the kernel is worth and how that is learned, are in
[Asking while unsure](76b-asking-while-unsure.md).

In Lean, 76.1 is `NCA.rule_risks_least`, `NCA.least_risk_le` and `NCA.share_le_iff`; 76.2 is
`NCA.read_risks_cost_little` and `NCA.threshold_costs_little`; 76.3 is `NCA.paid_le_best` and
`NCA.out_where_best_paid`, over `NCA.bestBy`, `NCA.outWhereBest` and the `NCA.readBy` of chapter
75; 76.4 is `NCA.never_out_unpaid` and `NCA.out_more_pays`; 76.5 is `NCA.cost_le_all`, over
`NCA.costBy`; 76.8 is `NCA.share_rises` and `NCA.shares_rise_alike`; 76.9 is
`NCA.largest_overrates`; 76.10 is `NCA.unsure_costs_less`, `NCA.sure_costs_little` and
`NCA.settled_costs_little`; 76.11 is `NCA.charged_tie_puts_out` and `NCA.charge_costs_little`; 76.12 is
`NCA.still_worth_within` and `NCA.held_to_last_puts_out`.
