# 71. Choosing between readings by the payments they foretold

Chapter 69 gives a learner a window in place of the whole picture, and 69.5 states where the
window fails. Which of the two serves a task is not known before the task is played. This chapter
treats a learner that keeps several readings, each given the picture in its own way, teaches all
of them on every press, and lets the one that foretold the newest payments best choose the next
press: what that choice is guaranteed, what it costs, and where it fails.

## 71.1 Model

Presses are made one after another. There are finitely many **members**, at least one; a member
is a reading together with what it is given of the picture. Before a press is taught, every
member has given a chance that the pressed port is paid. A member's **loss** at the press is a
number saying how badly that chance foretold whether the press was paid; lower is better. A
**stretch** is finitely many presses. A member's **score** on a stretch is its losses there,
added. A member **leads** on a stretch when no member's score there is lower.

Before each press the **chooser** takes a stretch of presses already made, the stretch
**scored**, and a member that leads on it; that member chooses the press. In a **play**, what a
press shows is settled by who chose it, by what the members had learned and by the presses
before; every member is then taught on the press. The frame gives presses, pictures and members
no meaning, and nothing names what a member is given or how it reads.

## 71.2 The chooser's score

**Proposition 71.1 (the chooser's score is the least).** On any stretch some member leads. A
member that leads has a score no higher than any member's, and no higher than any mix of the
members' scores whose shares are not negative and sum to one. Over several stretches, each with a
member that leads on it, the leaders' scores together are no higher than any one member's over
the same stretches.

So on the presses scored the chooser's member foretold payment as well as the best member and
better than the members taken together. This is said of presses already made. Of the presses the
member then chooses it says nothing; 71.5 states how little can be said.

## 71.3 What the choice costs

**Proposition 71.2 (the choice costs no presses).** After a play of `n` presses every member has
been taught on all `n`, and what a member has learned is what those presses teach it in their
order, whoever chose them. So two plays of the same presses leave every member the same, though
the members that chose, and the rules by which they were chosen, differ.

So choosing takes no press from any member. None is set aside for scoring: a press is scored
before it is taught and is then taught, so every press is both a trial of the members and a
lesson to them (Dawid, 1984). And none is withheld from the members that did not choose. What the
choice costs is teaching, each press once for every member. The presses themselves do turn on who
chose: the choice bears on what a member learns through which presses are made, and through
nothing else.

## 71.4 A member that stays ahead

**Proposition 71.3 (a member that stays ahead is chosen).** Let one member's score be strictly
lower than every other member's on every stretch scored from some press on. Then that member
chooses every press from then on. The presses chosen by another member, however long the play,
are no more than the presses before. And if a press costs at most `b`, with `b` not negative,
the presses chosen by another member cost together at most `b` for each press before.

So once the scores have parted for good the chooser is the member ahead, and what the other
members' choosing cost is bounded by when the scores parted, not by how long the play is. Nothing
here says that scores part, and nothing that the member ahead in foretelling is the member whose
own presses are paid most (71.7).

## 71.5 Where it fails

**Proposition 71.4 (scores can cross).** For every press `T` there are losses of two members,
each nought or one, such that on every stretch of presses before `T`, if it is not empty, the
first member's score is strictly the lower, and on every such stretch of presses from `T` on
strictly the higher.

So a chooser that scores any stretch of the past takes, at press `T`, the member that is the
worse at every press to come. What mends it is the second half of the proposition alone: a
stretch that lies wholly from `T` on. The stretch scored must therefore be of the newest presses,
and no longer than a lead is trusted to last.

**Proposition 71.5 (a rule by past losses can be wrong at every press).** Let a rule choose one
of two members before each press from the losses at the presses before. Then there are losses,
each nought or one, under which at every press the member chosen loses one and the other
nothing. Under them the two members' losses together are one for each press, so one of the
members loses at no more than half of the presses.

So no rule that chooses by past losses alone is safe against every run of losses: its member can
be the worse at every press while one of the members, left to itself, is the worse at half of
them. Nothing in this chapter therefore bounds in general what choosing loses. What bounds it is
an assumption on where the losses come from.

## 71.6 Where the choice settles

**Proposition 71.6 (losses from one unchanging source).** Take two members and `n` new presses.
Let the amounts by which the first member's loss is more than the second's at these presses be
independent, each within `b` of nought, and each expected to be at most `−δ`, with `b` more than
nought and `δ` not negative. Then the chance that the first member's score on the `n` presses is
not strictly the lower is at most `exp(−n δ² / 2 b²)`.

This is the inequality of Hoeffding (1963) for the sum of those amounts.

So where the losses lie in a range of length `b`, and one member is the better by `δ` a press in
what is expected, a stretch of `(2 b² / δ²) · ln(1/ε)` new presses takes the worse member with
chance at most `ε`. For a gap of a tenth of the range that is about 460 presses for a chance of
one in ten. The stretch needed grows as the gap shrinks, by its square; so 71.4 and 71.6 pull
against each other: a short stretch follows a lead that changes, a long one tells a small gap.

## 71.7 What is assumed and what is left open

Assumed: finitely many members, at least one; that every member is taught on every press, and
that what a press teaches does not turn on who chose it; for 71.3 that the scores part for good;
for 71.6 that the amounts are independent, bounded and apart by `δ` in what is expected. A loss by
the square of the miss lies between nought and one (Brier, 1950); a loss by the logarithm is
bounded only where the chances given are kept from nought and from one.

Play does not give what 71.6 assumes. The members are taught between presses, so their losses
drift; and the presses, and with them the pictures the members are scored at, turn on who chose,
so the source changes when the chooser does. Where the amounts are not independent but each, given
all before it, is expected to be at most `−δ`, a bound of the same kind is the inequality of Azuma
(1967); that is not proved here, and play is not shown to meet it either.

Left open, and matters of the literature or of measurement recorded in the research diary. That
the member which foretells payment better is the member whose own presses are paid more: a member
that does not choose is scored at pictures the chooser's presses led to, which it might not have
reached itself, and its score says nothing of the presses it would have made. How long the stretch
scored should be, between 71.4 and 71.6, and how often to choose anew. Which member to take where
two lead alike. Whether a chooser that takes a member by chance, more often the lower its score,
does better: such choosers escape 71.5 (Hannan, 1957; Littlestone and Warmuth, 1994) and are not
treated here. And the cost in teaching of keeping several members, which grows with their number.

In Lean a score is `NCA.scoreOn` and leading is `NCA.Leads`; 71.1 is `NCA.leader_exists`,
`NCA.leader_le_mix` and `NCA.leaders_le_member`; 71.2 is `NCA.presses_all_taught`,
`NCA.learned_from_presses` and `NCA.same_presses_same_learned` over `NCA.playedTo` and
`NCA.taughtOn`; 71.3 is `NCA.strict_leader_chosen`, `NCA.others_chosen_le` and
`NCA.others_cost_le`; 71.4 is `NCA.lead_can_end` over `NCA.crossing`, with
`NCA.crossing_bounded`; 71.5 is `NCA.chooser_always_worse` and `NCA.members_share_loss` over
`NCA.adverse` and `NCA.adversePast`, where the rule reads the members chosen before, which under
those losses settle every loss before; and 71.6 is `NCA.wrong_chosen_le`.
