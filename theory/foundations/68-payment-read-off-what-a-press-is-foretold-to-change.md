# 68. Payment read off what a press is foretold to change

A learner taught by payment alone must find, in the picture before a press, whatever decides
whether the press is paid. Where that is a relation between things that stand apart, descent has
nothing to begin from. This chapter states why, and what is gained when the learner first learns
what its presses change and reads payment off that.

## 68.1 Model

A picture has finitely many **places**. A **context** is everything a picture shows but one thing,
the **paid place**. A press made in a context **lands** at a place, which the context and the press
decide; the press is **paid** exactly when it lands on the paid place. The frame gives places,
contexts and presses no meaning.

A **map** gives every place a number. The map of a place is one there and nought elsewhere. A
**window** reads the maps at one place and nothing of any other place; a reading by windows applies
the same window at every place and takes the largest of what it gives.

A **foretelling** names, for a context and a press, a set of places. It is **wide** when the place
the press lands at is among them.

## 68.2 No step before the press

**Proposition 68.1 (the context alone tells nothing).** For every context and press there is
exactly one place the paid place can be for the press to be paid. So where the paid place is
equally likely to be anywhere and does not turn on the context, the chance of payment is the same
at every context: one in the number of places.

**Proposition 68.2 (the paid place alone tells nothing).** Where a press lands at every place from
equally many contexts, the number of contexts in which it is paid is the same for every paid
place.

So under these two evennesses no reading of the context alone, and none of the paid place alone,
goes with payment at all: whatever such a reading gives, payment is as likely with it as without.
A learner that changes its readings by how they go with payment has nothing to change either by
until it holds both at once. That a network taught by descent then waits, and for how long, is a
matter of the literature and of measurement (68.5).

## 68.3 One window after the press

**Proposition 68.3 (one window tells paid from unpaid).** Lay the map of the place a press lands
at on the map of the paid place and add them place by place. The largest sum at any place is two
exactly when the press is paid, and at most one when it is not.

So given where a press lands, payment is told by a window of two weights, the same at every
place, the largest over the places, and one threshold. That reading is of one thing, the sum at a
place, and goes with payment from the first: there is a step. The window has as many weights as it
reads maps, whatever the number of places.

Where a press lands is itself shown to the learner on every press it makes, paid or not, by the
picture that follows: a number for every place where payment gives one number for the press.

## 68.4 A foretelling that names too much

**Proposition 68.4 (a wide foretelling misses nothing and errs only where it named).** If a wide
foretelling is read in place of the landing place, with the window firing when a named place is
the paid place, then every paid press fires; and an unpaid press fires only if the paid place is
one of the places named besides the one the press lands at.

So places named in excess (where the thing left, a counter that changed) cost nothing unless the
paid place can stand at them, and a blurred foretelling errs toward answering "paid" too often,
never toward missing payment, as long as the true place is within it.

## 68.5 What is assumed and what is left open

Assumed: that a press lands at one place decided by the context and the press, and is paid exactly
when that is the paid place; for 68.1 that the paid place is evenly spread and does not turn on
the context, for 68.2 that landings are evenly spread over the contexts. Tasks meet these roughly,
not exactly; the propositions say what holds at the even limit.

Left open, and matters of measurement recorded in the research diary: that a network taught by
descent is slow where no reading of one thing goes with what it is taught (shown for networks of
two layers on inputs without structure by Abbe, Boix-Adsera and Misiakiewicz, 2023; for pictures
an analogy); how many presses and how much teaching a foretelling needs to be wide and narrow
enough; whether a learned map of where the picture changes holds the landing place; and what
replaces the single landing place where payment turns on more than where one thing lands, or
comes only after several presses.

In Lean 68.1 is `NCA.paid_once_over_places`, 68.2 `NCA.paid_alike_over_contexts`, 68.3
`NCA.window_two_iff` over `NCA.shown`, and 68.4 `NCA.wide_map_misses_none` with
`NCA.wide_map_wrong_only_at_named`.
