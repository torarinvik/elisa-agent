# 79. Readers given whole plays

One reader taught on the lessons of two kinds of play is moved by both. A step of teaching on the
lessons of one kind changes the loss on the other, to first order, by minus the step times the
product of the two gradients: where they point apart, teaching on one undoes the other, and
where one kind has far more lessons it is the other that is undone. This chapter is about giving
each play to one of several readers, so that teaching on one play's lessons moves no reader of
another; how a play may be given its reader without being told what it is; and how a reader's
teachings are counted, so that a new play is taught as often as it would be alone.

## 79.1 Model

There are **readers**, each with weights of its own, and a **gate** that gives each step one of
them; what is read at a step is what the reader the gate gives it reads. A **play** is a run of
steps that the host says belong together, as those met since a task was begun. Each play is
**given** one reader, once, and every lesson of the play is a lesson of that reader alone. A
**teaching** of a reader changes its weights and no other's. The gate is taught after the
readers, to give each step of a play the play's reader.

## 79.2 What teaching one reader leaves of the others

**Proposition 79.1 (a reader not taught keeps its reading).** Teaching one reader leaves the
reading as it was at every step the gate gives another reader.

So the crosstalk between plays given different readers is nought, whatever their lessons pull
towards, and what is left of it is where the gate gives a step the wrong reader. Plays given one
reader share it as before.

## 79.3 Whether a reading foretells anything

A reading gives each lesson an amount; the lessons are of ports, each paid at its own rate. The
reading is **rescaled** by adding to each port's rate, on the logit, the amount, standardised,
times a **factor**, fitted to lessons with a penalty of half its square. Its **gain** on lessons
is how much smaller their loss is under the rescaled reading than under each port's rate alone.

**Proposition 79.2 (a rescaling nests the rates).** With the factor nought the rescaled reading
is each port's rate. So on the lessons the factor was fitted to the gain is never below nought,
whatever the reading.

So a reading that tells nothing seems to tell a little on the lessons it was rescaled on, and
only lessons kept out of the fitting can show that it tells nothing: the factor is fitted on
every other lesson and the gain taken on the rest, and then the other way round. Nor is a gain
above nought a sign that two plays are of a kind: a reader of one kind tells a little of
another wherever the two show the same things. The gain chooses only among readers already
found alike.

## 79.4 Whether a play's steps can be given their reader

The gate must give every step of a play the play's reader. Take as many steps of a play as of
the plays a reader has, teach a linear reading on half of each to tell them apart, and take the
share of the other halves it tells apart. A play is given a reader of its own only where that
share reaches a bound for every reader: below it, a reader of its own would be read in place of
the other's, and the other's in place of its own, at steps the gate cannot tell. Among the
readers a play is not told from, it is given the one whose rescaled reading gains most on its
lessons, held out. Where it is told from every reader's plays it is given a reader that has
none, made where there is none, up to a stated number of readers; past that, the reader that
gains most.

This rests on an assumption: that steps a linear reading tells apart, the gate, which is a
richer reading, gives apart too. Where the gate could tell steps that a linear reading cannot,
two plays share a reader that could have had one each, which is no worse than one reader.

## 79.5 Counting the lessons per reader

Let a reader be taught each time its lessons have grown by a share `g` since its last teaching.

**Proposition 79.3 (a shared count starves a new play).** The lessons held at successive
teachings grow each time by at least `1 + g`, so at the `i`-th teaching after a first there are
at least `(1 + g)^i` times as many as at the first. Where the count is of all the learner's
lessons and a play begins when `M` are held, a play that ends with `M + m` has teachings `0` to
`k` within it only where `(1 + g)^k M ≤ M + m`.

So with `g` a tenth, a play that brings a third as many lessons again as the learner held is
taught at most four times within it, where alone, from a first teaching at sixty-four lessons
and a growth of sixteen at the least, it would be taught over twenty times. A teaching shrinks
what was taught before it (chapter 77), and four teachings do not bring a reader up from
nothing. Counted per reader, a reader's teachings turn on the lessons of its own plays alone,
so the reader of a new kind of play is taught at the counts at which a learner that met only its
plays would be.

## 79.6 What is assumed and what is left open

Assumed. That the host says where a play begins and that a play is of one kind throughout; and
the assumption of 79.4. Nothing is assumed of what the readers compute.

Left open. A play of two kinds in turn, which is given one reader and shares it; the share of
steps the gate gives the wrong reader, which is measured and not bounded here; whether plays
given different readers could teach each other what they share, which here they do not; and
when readers that have grown alike should be made one.

In Lean the reading through a gate is `NCA.gatedReading`. 79.1 is `NCA.untaught_keeps_reading`;
79.2 is `NCA.rescaled_nests_rates`; 79.3 is `NCA.counts_grow` and `NCA.shared_count_starves`.
