# 75. A read by the newest match

Chapter 73 says what a memory read by its contents must find, with a match that says yes or no
of a key. This chapter treats a read whose match is a chance, and asks the one thing a memory of
any size needs of it: that what a learner was taught with few items held is still what it reads
with many. It states what such a read takes and leaves, how much older items can move it however
many they are, what limits it instead, what a weighted mean does in its place, and what the read
costs.

## 75.1 Model

Items are held in the order they came, and there is a step of now. A reading gives each item,
from what that item and the step of now hold, a **chance** of matching, a number from nought to
one, and a **value** no larger than a bound `B`. Neither turns on how many items are held or on
where the item lies among them. Taking the items newest first, the **weight** of an item is its
chance times one less the chance of every newer item, and what a run of items **leaves** is one
less each of their chances, multiplied together. The **read** is the sum of the values, each
times its weight. This is the geometric attention of Csordás, Irie and Schmidhuber (2022) and
the stick-breaking attention of Tan and others (2024). The frame gives items, chances and values
no meaning, and nothing says how the reading comes by them.

## 75.2 What is taken and what is left

**Proposition 75.1 (taken and left make one).** The weights of any run of items and what the run
leaves sum to one.

So the weights never sum to more than one, and what all the items leave is the weight of
nothing having matched: a read that found nothing is nought, and says so by its size.

**Proposition 75.2 (a match leaves little).** A run of items one of which has chance `m` leaves
at most `1 − m`, wherever in the run that item lies.

## 75.3 More items held

**Proposition 75.3 (older items weigh what was left).** The weight of an item does not turn on
any item older than it. The read of a run of items with older items laid after it is the read of
the run and, times what the run leaves, the read of the older items. So older items, however
many and whatever their chances, move the read by at most `B` times what the newer ones leave;
and where one of the newer items matches with chance at least `1 − ε`, by at most `ε B`.

This is the sense in which the memory may be of any size. A learner taught with `n` items held
reads, with `N` held, what it read with the newest `n`, to within `ε B`, for every `N`: the
bound holds no count of items. Nothing is asked of the older items. They may match as surely as
the newest one does, as the first frames of earlier trials do; the newest match has taken the
weight before they are reached. What was stored stays as it was, and only what is newer than an
item bears on its weight, so nothing held is revalued when more is held.

## 75.4 What limits it

**Proposition 75.4 (newer items that match falsely).** A run of `k` items, each of chance at
most `δ`, leaves at least `1 − k δ`.

So an item of chance `m` with `k` newer items before it, none of them wanted and each matching
with chance at most `δ`, has weight at least `m (1 − k δ)`. The weight of the item wanted falls
with the number of items newer than it and with the chance that such an item matches falsely,
and with nothing else. The law is therefore in the distance and not in the size: a read within
`η` of the value wanted needs `k δ` and `1 − m` of the order of `η`, however much older memory
there is. What limits the read first is items that look like the one wanted and came after it.

## 75.5 What a weighted mean does

Let each item have a score above nought and a weight that is its score over the sum of all
scores, as in attention by a weighted mean.

**Proposition 75.5 (a weighted mean wears).** An item held with `n` others, each of score at
least `c` times its own, has weight at most `1 / (1 + n c)`.

So for any `c` above nought the weight of the item wanted goes to nought as `n` grows. A
weighted mean is right at every size only if the scores of the other items fall as their number
rises, which a reading that scores an item from the item and the step of now cannot arrange. A
score given the item's age can, for the ages it was taught at.

## 75.6 Cost

Read newest first and stop when what the items read leave is at most `τ`. By 75.3 the read so
made is within `τ B` of the read of all, and the items read are those down to the first point
where so little is left: their number does not turn on how many older items are held. Where
nothing matches, every item is read, and the cost is in proportion to the holding; bounding that
needs keys put to an index (73.7), which is not treated here.

**Proposition 75.6 (a read stopped where little is left).** Where the items read leave at most
`τ`, the read of them is within `τ B` of the read of them and any number of older items. Reading
on leaves no more: what a run and an older run leave together is the product of what each
leaves. So the items may be taken a run of a fixed length at a time and the stop looked for only
at the end of each run; the read stops no more than one run past the first item that left so
little, and the bound is kept.

Reading further back only where nothing nearer matched is a way of thinking on (76.5): the cost
is paid at the steps that need it.

A chance and a value are made from what an item holds, and by 73.17 a form of the entry serves
where it keeps apart the entries the choice tells apart. Where the form is made by a reading
held fixed (73.11), it is made once, when the item is written, and a teaching reads forms and
not entries.

## 75.7 What is assumed and what is left open

Assumed. That the chance and the value of an item turn only on that item and the step of now;
that values are bounded; that the order of the items is the order they came in. The bounds hold
for whatever the chances are. They do not say the chances are good: that teaching finds a
reading whose false matches `δ` are few and whose miss `ε` is small is measured, and so is
whether they stay so on kinds of item that were never held while it was taught.

Left open. A choice that turns on an item that is not the newest of its kind, the one before the
newest or the first: one read by the newest match does not give it, and a chain of reads, each
among the items older than what the last one found, would. A choice that turns on several items
at once, which takes several reads. How a reading that is held fixed is come by, and when a new
one has to be made. And the index of 75.6.

In Lean what a run leaves is `NCA.leftBy`, the weights summed `NCA.takenBy` and the read
`NCA.readBy`. 75.1 is `NCA.taken_add_left`; 75.2 is `NCA.left_le_of_match`, over
`NCA.left_between`; 75.3 is `NCA.read_append`, `NCA.more_held_moves_little` and
`NCA.sure_match_fixes_read`, over `NCA.read_within`; 75.4 is `NCA.newer_leave_most`; 75.5 is
`NCA.mean_wears`; 75.6 is `NCA.stopped_read_within` and `NCA.reading_on_leaves_less`, over
`NCA.left_append`.
