# 77. Teaching on as lessons grow

A learner that gathers its lessons as it plays is taught many times, each time on all it holds.
Teaching it from where it stands is cheap; teaching it from nothing is what a count of lessons
is known to allow. This chapter keeps the account of what earlier teachings leave in the
weights, under a teaching that first multiplies the weights by a factor, and states the law
that ties the factor to how often the learner is taught. It does not say that what early
teachings left is what harms: that is measured.

## 77.1 Model

A reader has weights. A **teaching** multiplies each weight by a **factor** between nought and
one and then adds to it; what it adds is whatever its steps on the lessons then held make, and a
jog of the weights counts as part of it. Nothing is assumed of what a teaching adds: it may turn
on the weights it started from. With the factor one the reader is taught on from where it
stands, and with the factor nought from nothing.

## 77.2 What earlier teachings leave

**Proposition 77.1 (the account).** The weights after a run of teachings are what the newest
`k` of them would have made from nought and, times the factor `k` times over, the weights the
earlier ones left.

**Proposition 77.2 (earlier teachings fade, or do not).** Where each teaching adds at most `A`
to a weight and the factor `s` is below one, the earlier teachings bear on a weight after `k`
more by at most `s^k A / (1 − s)`. With the factor one the weights are the plain sum of what
every teaching added: what the first teaching fitted, on the few lessons there were, is in them
whole however many lessons come after.

## 77.3 The law in the lessons

Let the reader be taught each time its lessons have grown by a ratio `r` above one.

**Proposition 77.3 (fading against growth).** Where `s r^m ≤ 1` for a whole number `m`, the
factor over `k` teachings is at most one over the growth of the lessons across them, `m` times
over.

So what the reader fitted when it held `n₀` lessons counts, when it holds `n`, at most
`(n₀ / n)^m` of what it did. The factor and the ratio trade against each other through `m`
alone: taught at each growth by a tenth, a half gives `m = 7`, and four fifths gives `m = 2`.
By the time the lessons have doubled the first leaves under a hundredth of what was fitted and
the second a quarter.

## 77.4 What is assumed and what is left open

Assumed. That a teaching is the factor and an addition, and for 77.2 that additions are
bounded. The account is of weights. That a reading whose weights hold little of an early
fitting reads like one taught from nothing is not shown here; it is measured, with the factor
one, four fifths and a half, against teaching from nothing at the same counts of lessons.

Left open. What the factor costs just after it is applied, before the teaching has made up for
it, and so how few steps a teaching may have; 77.5 says how large that cost is in a reader of
several layers, not how many steps make up for it. When a learner should be taught from nothing
instead.

## 77.5 A factor on every layer

The account above is of one weight. A reading is made by layers, one after another, and the
factor is put on the weights of each.

A layer is **even** where multiplying what it is given by a number that is not below nought
multiplies what it gives by the same number. A layer that multiplies by its weights and then
keeps what is above nought is even; one that adds a weight of its own to every place is even
only as far as what it adds is small beside the rest.

**Proposition 77.4 (the factor compounds).** A reading through `L` even layers, each with its
weights multiplied by a factor `s` that is not below nought, gives `s^L` times what it gave.

So a half on each of three layers leaves an eighth of a reading, and on each of five a
thirty-second: the same factor is a far harder start for a deeper reader, and a teaching of the
same length makes up for less of it. For the whole reading to be multiplied by `s` the factor
on each layer is the `L`-th root of `s`. The account of 77.2 and 77.3 stands, of the weights;
what the proposition adds is that how much of a reading a factor leaves turns on the depth,
which the law of 77.3 does not see.

In Lean the weights after the teachings are `NCA.weightsAfter`. 77.1 is `NCA.weights_append`;
77.2 is `NCA.old_teachings_fade`, over `NCA.weights_within`, and `NCA.warm_keeps_all`; 77.3 is
`NCA.fade_in_lessons`; 77.4 is `NCA.factor_on_every_layer`.
