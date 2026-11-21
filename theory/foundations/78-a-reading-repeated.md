# 78. A reading repeated

Some things are known at a place only from what lies some way off: whether a way leads out is
known where it starts only from where it ends. This chapter is about a reading that gives each
place something from what is held at the places near it, by the same rule at every place, and
is then given its own result and applied again. It says how far off a thing may lie and still
bear on a place after a number of repeats, and when repeating may stop.

## 78.1 Model

There are **places**, and each place has the places **near** it; a place may be near itself.
A **holding** gives every place a value. A **reading** makes a holding from a holding. It is
**local** where what it gives a place turns only on what the holding has at the places near
that place: two holdings alike at every place near a place are read alike there.

What was first seen may be given again at every repeat: then a value is a pair of what was
seen and what has been read so far, and the reading leaves the first of the pair as it is.
That is a reading as above, and nothing below needs to treat it apart.

The places **within** nought of a place are that place alone; those within `k + 1` are the
places near some place within `k`.

## 78.2 How far a repeated reading reaches

**Proposition 78.1 (reach).** After `k` repeats of a local reading, what a place is given
turns only on what the first holding had at the places within `k` of it: two holdings alike
at all of those are read alike at that place after `k` repeats.

So a thing that lies further than `k` nears from a place bears nothing on it after `k`
repeats, whatever the reading has learned; and where a task turns on what lies `k` nears off,
no fewer than `k` repeats will do. The other way is not a theorem: `k` repeats let a thing
`k` nears off bear on a place, and whether it does is up to what the reading is. One reading
taken once and a largest over the places, as a reader of one layer has it, is one repeat.

## 78.3 When repeating may stop

**Proposition 78.2 (a reading that stands still stays).** Where one more repeat leaves a
holding as it was, every further repeat leaves it so: the holding after any greater number
of repeats is the same.

So repeating may stop at the first repeat that changes nothing, at no loss, and a reading
that is asked for an answer may be repeated until then: a few times where what bears on the
place is near, more where it is far. The number of repeats is then not written down
beforehand; it is how long the thinking took.

## 78.4 What is assumed and what is left open

Assumed. That the reading is local, which a reading of each place with those about it by the
same weights is. Nothing is assumed of what it computes.

Left open. Whether a reading taught with one number of repeats reads rightly with more; how
many lessons it takes to learn a reading that carries what it should; and what is lost where
the last read is of all the places as they lie and not of one place, which is not local and
is what the reader this chapter was written for does.

In Lean the places within are `NCA.within` and a local reading is `NCA.Local`. 78.1 is
`NCA.repeats_reach`; 78.2 is `NCA.stood_still_stays`.
