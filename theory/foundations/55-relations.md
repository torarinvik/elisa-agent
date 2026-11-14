# 55. Relations between what is read

Chapters 53 and 54 find which readings a target depends on. A reading there is a value: of a component, or of a place
found from an anchor. A target that depends on how two values stand to one another, whatever they are, is a function of
those two readings, but one a learner must be shown at each value. This chapter adds readings that say how two values
stand to one another, and states what a learner that reads only those is spared.

## 55.1 Model

An observation gives a value, or nothing, at each of a set of **slots**. Slots are grouped into **kinds**: two values
of one kind can be compared for equality, and the values of an **ordered** kind are linearly ordered. A **sameness**
probe of two slots of one kind reads whether their values are equal. An **order** probe of two slots of an ordered
kind reads which value is the greater: `−1`, `0` or `1`. Either reads nothing where a slot holds nothing.

The kinds, and which of them are ordered, are the contributor's. The frame assigns no meaning to a value or a kind.
The learner is that of 53 or 54 with these probes among its components; a probe is a component whose reading is
computed from two others, and nothing else changes.

## 55.2 What values read alone leave open

**Proposition 55.1 (judgements on some values do not settle sameness on others).** Let the target be that slots `i`
and `j` hold the same value, and let every judgement so far have been made on observations whose value at `i` lies
in a set `U`. Then two functions of the pair of values agree with every judgement and differ at `(v, v)` for each
`v ∉ U`: sameness, and sameness of a value in `U`.

Both are functions of the two values, and they agree wherever the first value lies in `U`. So a learner that reads
the two values, and whose hypotheses include every function of them, is not told by its judgements what holds at a
value it has not been shown. With `m` values of the kind the two slots form `m²` classes of 53.1, and a judgement
settles one of them. With the sameness probe the target is a function of one probe with two classes.

## 55.3 What a relation is unchanged by

**Proposition 55.2 (renaming and rescaling).** A sameness probe reads the same in an observation and in that
observation with the values of a kind replaced through any one-to-one map. An order probe reads the same after any
strictly increasing map.

`σ a = σ b` exactly when `a = b` for one-to-one `σ`, and `f a < f b` exactly when `a < b` for strictly increasing `f`.

So a learner whose view holds only sameness and order probes makes the same choice in the two observations: what it
was taught on some values holds on every value of the kind, shown or not. This is 54.12 with values in place of
positions. There the readings are unchanged by moving the scene, here by renaming what it holds. In both, the
learner is spared a judgement for each image of a situation under the changes its probes do not see, and the price
is the same: a target that does depend on which value is held is not a function of such probes, and needs a value
probe as well.

## 55.4 The pool

For kinds with `n_k` slots the pool holds `Σ_k n_k(n_k − 1)/2` sameness probes, and as many order probes for the
ordered kinds, whatever the number of values. Which of them matter is found as any component is (53.4, 54.4). What
remains given is which slots are of one kind and which kinds are ordered.

## 55.5 Relations between relations

Where the values of an ordered kind can be subtracted, the **step** between two slots is the difference of their
values, and a probe may read whether two steps are the same or how they are ordered: a relation between relations.
A step is unchanged when one amount is added to every value of the kind, as a bearing is unchanged by moving the
scene (54.12), so the sameness of two steps is unchanged by that as well as by 55.2.

Probes are built from one another without limit, and all pairs of pairs grow as the fourth power of the number of
slots of a kind. Where the slots of a kind stand at places in `ℤⁿ`, two pairs **stand alike** when the second slot
of each lies at the same displacement from the first, and the pool offers the sameness of two steps only for pairs
that stand alike: that `b` is to `a` as `d` is to `c`. For `s` places a displacement is shared by fewer than `s`
pairs, so the pool holds fewer than `s³` such probes; nine places in a square give 52.

Let the places be named from one of them. A probe then names displacements only, and reads nothing where a place it
names holds nothing, so one pool serves arrangements of every extent within its reach, and what is taught on a
small arrangement is asked unchanged of a larger one (54.12).

What is given grows with this: besides the kinds, the places of the slots, and values that can be subtracted. An
order of values without a unit, as of shades or shapes, has no steps until each value is given a number.

## 55.6 What this does not cover

Kinds are given, not found. A relation reads two named slots, so things in variable number are outside it: "the
latest of those that match" is not a relation of two slots. Where those things are the candidates of one choice,
each is judged by its own relations and 53.7 orders the acceptable ones. Counting is not covered. The gain is in
judgements only: a relation costs the two readings it compares.

## 55.7 Probes built on what is held

Let the slots of a kind stand at places in `ℤⁿ` and let a learner hold a probe built from a step `σ`. Moving every
slot of `σ` by one displacement gives a step that stands alike elsewhere; the **translates** of `σ` are those all
of whose slots exist, one at each place the greatest slot of `σ` can be moved to. They read one number at each
such place, as the values of a kind do. The **lift** of what is held is the analogies (55.5) between the
translates of each step it is built from: whether two pairs of translates that stand alike take the same step.

The lift is one storey above what is held, and lifting again what a learner of the lift comes to hold is one
storey above that. Along a row write `Δ` for the step from the place before. The sameness of two neighbouring
steps says the row continues with a constant `Δ`; its lift offers the sameness of two neighbouring steps of
steps, a constant `Δ²`; and so on.

**Proposition 55.3 (each storey fixes the continuation).** For integers, the last two of `k + 2` consecutive
`k`-th steps `Δᵏ` are the same exactly when the last value is one fixed combination of those before it: `c = 2b −
a` for `k = 0`, `d = 3c − 3b + a` for `k = 1`, `e = 4d − 6c + 4b − a` for `k = 2`. So among candidates for the
last place, a probe of storey `k` reads true of exactly one value.

**Proposition 55.4 (the storey below does not tell).** There are two rows of five values that are ordered alike,
hold the same value nowhere, take the same step for no two pairs of places that stand alike, and of which one has
a constant `Δ²` and the other has not. The relations of the pool (55.4, 55.5) read the two alike; the lift of the
sameness of two neighbouring steps does not.

So a learner whose pool stops at one storey cannot be taught a rule of the next through relations, whatever its
judgements, and can be once the pool is lifted.

The lift may be taken of the whole pool or only of what a learner holds. A translate needs all its slots to
exist, so a step that spans more has fewer translates and the storeys run out: a row of `s` places has none above
storey `s − 3`. Lifting what is held offers one family of translates for each step held, with fewer than `s³`
analogies; lifting the whole pool offers one for every step in it. The lift changes what can be asked, and
lifting only what is held keeps what is asked to the families that have paid; it does not change the order of
growth, which the places bound in either case.

What this does not give: lifting only what is held, a rule of storey `k` is reached through rules of the storeys
under it, each taught, and not otherwise. And the lift is of steps only: a held sameness or order is not carried
up, and a rule that multiplies has no storey.

## 55.8 Relations read without values

The probes of 55.1 and 55.5 read whether two values are equal, which is the greater, and whether two pairs take the
same step. None reads a value. So what stands in a slot need not be given a value at all: it is enough that two
things of a kind can be **compared**, by a reading of the pair that says whether they are the same, and for an
ordered kind which is the greater and by what step. By 55.2 this is also all that a value could add, since the
probes are unchanged by renaming and rescaling.

**Proposition 55.5 (a comparison stands for a value exactly when it is an equivalence).** A reading of whether two
things are the same is the equality of some value of each if and only if it is reflexive, symmetric and transitive.

A comparison read from two pictures, as a distance under a divide, is reflexive and symmetric by construction and
need not be transitive. Where it is not, it is wrong somewhere, and this shows without a label:

**Proposition 55.6 (a broken triple holds an error).** Where the true sameness is transitive, three things of which
the first and second are read the same, the second and third the same and the first and third different have at
least one of the three read wrongly.

The share of triples broken is therefore a measure of a comparison that needs no labels. It does not rank
comparisons alone: reading every pair the same, or every pair different, breaks no triple. It is a check on a
comparison that separates two heaps of distances, as the divide of the pairs' distances does.

What may be compared in a thing cut from a picture is not derived here. A patch set off from its ground has a
place, an extent, an outline and what fills the outline, whatever the picture is of, and each can be compared
between two patches without being named: by how far apart, by the ratio of extents, by how much of the outlines
overlap when laid on one another, by how far the fillings differ. Whether these comparisons tell what a task's
figures differ in is measured in the research diary.
