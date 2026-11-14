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

## 55.9 From comparisons to the numbers a step needs

Sameness needs a comparison and nothing more. A step does: by 55.5 an order has no steps until each value is given
a number. A comparison of an ordered kind supplies a magnitude for each thing, of which only the order is trusted
(how far an outline reaches, how light a filling is, how much of the circle that holds it an outline fills). The
things read the same form classes (55.5), and a class is numbered by its **place among the classes seen so far**,
in the order of their magnitudes. Where the magnitude itself has equal steps along the ladder, as the logarithm of
an extent has when sizes grow by a ratio, steps are counted in it directly and no places are needed.

**Proposition 55.7 (places keep the order and lose steps while rungs are unseen).** The place of a value among
those seen is ordered as the values are. While a rung between two seen values is itself unseen, two pairs that take
different steps on the ladder can read the same step in places.

So a learner numbered by places reads order rightly from its first observation and steps rightly only once the
rungs in play have all been seen; a rule of steps taught earlier is taught on numbers that later shift. The
ordering of each kind by its magnitude is given, as the kinds of 55.1 are, and is not found. In Lean 55.7 is
`NCA.places_keep_order_and_lose_steps`.

## 55.10 Comparing whatever the turn

A thing and the same thing turned are different pictures, and a comparison that lays one outline on the other
(55.8) reads them different. Where a task counts them the same, the comparison has to be blind to the turn. A
comparison is blind to a change when it compares through something the change leaves alone.

For a turn, let a **row around a circle** hold, for each of `n` directions from an outline's middle, how far the
outline reaches that way. Turning the outline by a multiple of the `n`-th part of a full turn moves the row along
the circle, and a turn between two such multiples nearly so. For a gap `g` let `A(g)` be the sum over the places
`p` of `row(p) · row(p + g)`: how alike the row is to itself moved `g` along.

**Proposition 55.8 (what a turn and a mirror leave alone).** For a row over a finite commutative group, `A` is
unchanged, for every gap, when the row is moved along by any amount and when it is mirrored.

So a comparison through `A` reads a thing and its turned self the same. It pays for this twice: it also reads a
thing and its mirror image the same, and two rows that are neither a turn nor a mirror of one another can share
`A`. It is coarser than sameness up to a turn, never finer. The squared magnitudes of the row's discrete Fourier
coefficients are the transform of `A` (the classical Wiener–Khinchin relation, not proved in Lean here), so they
hold exactly what `A` holds, and the lowest of them describe the outline's coarse form while leaving out what
single directions add. Dividing the row by its mean first makes the comparison blind to the outline's size as
well. In Lean 55.8 is `NCA.turning_and_mirroring_keep_alike_moved`.

## 55.11 A divide found from the things themselves

A comparison by a distance under a divide (55.8) needs the divide. Set by hand it is knowledge of one kind of
thing, in the units of one distance. Three ways of using a divide ask different things of the distances. Let the
things of one class lie within `r` of their class's middle and the middles of two classes at least `D` apart.

- **By pairs**: two things are the same when their distance is under the divide. Two of a class can be `2r` apart
  and two of different classes as near as `D − 2r`, so a divide exists only when `D > 4r`, and the greatest
  distance within a class grows as more of it is seen.
- **By middles**: a thing is of the class whose middle it lies nearest. This needs `D > 2r`, and needs the classes
  before it can be used.
- **By chains**: two things are the same when a chain of things joins them, each link under the divide. This
  needs only that no link crosses between classes and that each class hangs together. The longest link a class
  needs shortens as more of it is seen, since the things between two of its members fill in, while the nearest
  two things of different classes come no nearer than `D − 2r`.

**Proposition 55.9 (a chain reads sameness when no link crosses).** Let a true sameness be an equivalence. If no
two things read near are truly different, and any two things truly the same are joined by a chain of things read
near, then being joined by such a chain is being truly the same.

So chains are the comparison that data improves, and by 55.5 their classes are always an equivalence, with no
triple to break (55.6). What the distances do not hold is which divide is meant:

**Proposition 55.10 (a greater divide only joins).** Things joined by a chain under one divide are joined under
every greater divide.

The classes under all divides are therefore nested, from every thing alone to all things together, and each level
is an equivalence. Which level a task means by "the same" is not in the distances; a rule has to choose one. The
rule used takes the links of the shortest tree that joins the things seen, which are exactly the links at which
classes join as the divide grows, and puts the divide in the **widest gap, by ratio, between two successive links
above the median link**. Things that are the same picture are counted once. The rule carries no distance: it reads
the same when every distance is multiplied by a constant. It assumes that more than half the links lie within
classes, which holds once the things seen outnumber twice the classes, and that the classes sought are the finest
level that stands clear of what redrawing a thing changes. Whether it finds a task's classes is measured in the
research diary. In Lean 55.9 is `NCA.chain_reads_sameness` and 55.10 is `NCA.greater_divide_only_joins`.

## 55.12 Things with no pen given

What 55.8 compares is a patch set off from its ground. Finding the patches has so far leaned on what one kind of
picture is drawn with: a line of the darkest ink around each thing, a thin square around each group of things, a
fixed distance in colour that sets a pixel off its page. None of these is in the notion of a patch.

A picture drawn in flat colours has **colours of its own**: those some pixels wear together with all their
neighbours. Every other pixel lies where colours blend and is read as the nearest of the colours beside it, so
no distance in colour is given. A **patch** is a connected set of pixels of one such colour. The **ground** of a region is the
colour most of its edge wears. A patch may enclose pixels that are not its own; what it encloses is its
**inside**, which may be the ground showing through, another colour that fills it, or further patches, for which
it is in turn the ground. A **panel** is an outermost patch off the page together with all it encloses, large
enough to hold things. So one rule of two parts, applied twice, finds the panels of a frame and the things of a
panel: a thing is a patch off its ground, and a patch is ground for what it encloses. A thing drawn as a line
around a fill and a thing drawn as a flat shape are both patches; the first has an inside of another colour and
the second has none.

The outline of a thing is compared through how far it reaches in each direction from its middle (55.10). Taking
the reach as the farthest pixel in a direction leans on one pixel, which is a whole pixel wrong whatever the
thing's size, so the smaller the thing the worse the reading. All the pixels in a direction can be used instead:

**Proposition 55.11 (how much lies one way fixes the reach that way).** A part of a circle of reach `r` across an
angle `w` covers `r² w / 2`, and two reaches that cover the same across the same angle are equal.

So the reach in a direction is read as the square root of twice what the thing covers in a narrow angle that way,
over the angle. For a thing that every ray from its middle leaves once this is its reach where the reach is even
across the angle, and otherwise a mean of it; it is read from every pixel in the angle, each counted in parts to
either side of the angle's bounds. A thing drawn as a line has two such reaches, of all it encloses and of its
inside, and the middle of its line lies between them. In Lean 55.11 is `NCA.covered_fixes_reach`.

Not covered: a line too thin to hold a pixel with all its neighbours has no colour of its own and is not read,
so writing is not; things that touch are one patch when they share a colour; a mark laid over a thing breaks its
patch; and a comparison blind to the turn (55.10) reads a square and the same square stood on its corner as one
shape, which a task may count as two.

## 55.13 A step that is a value

The pool of 55.1 and 55.5 reads whether two values are the same, which is the greater, and whether two steps are
the same. A rule that the last of three values is the first plus the second is none of these:

**Proposition 55.12 (sameness, order and the sameness of steps do not tell a sum).** The rows 1, 3, 4 and 1, 3, 6
are ordered alike, hold no two values the same and have no two of their three steps the same; the first is a sum
and the second is not.

A learner given that pool can hold such a rule only as a table of the rows it has met, and chooses among
candidates by chance in a row it has not.

**Proposition 55.13 (a sum is a step that is a value).** `c = a + b` exactly when the step from `a` to `c` is `b`,
and `c = a − b` exactly when the step from `c` to `a` is `b`.

So the relation wanted is the sameness of a step and a value, and it is built from the probes already there.
It asks more of the values than a step does. A step is unchanged when one amount is added to every value (55.5);
whether a step is a value is not, so the values need a nothing that means nothing as well as a unit: counts have
it, places among classes seen (55.9) do not. For three slots in a line the pool offers the two probes of 55.13.
It does not offer them for longer lines, where the last would be the first plus all between. In Lean 55.12 is
`NCA.same_and_order_and_steps_do_not_tell_a_sum` and 55.13 is `NCA.sum_is_step_that_is_value`.

## 55.14 Rows that agree

A rule such as 55.13 is kept by every row of an arrangement or by none, and the row asked for is right when it
does as the rows shown do. What a probe reads of the asked row alone does not say whether it is right: under rows
that are sums a sum is right, under rows that are not, it is not. Read together with the same probe on a row
shown it does, but that takes two probes where a learner that takes probes up one at a time finds neither worth
taking alone (54.13).

**Proposition 55.14 (a rule kept by every row is told by two rows agreeing).** Whether the last row is right is
whether its reading is the same as a row's above, and is no function of its own reading alone.

So for any reading of a line, the pool also offers whether two lines that stand alike read the same: a relation
between relations (55.5), one probe that says "as the row above does". In Lean 55.14 is `NCA.agreeing_rows_tell`.

## 55.15 A sum where the nothing is not known

Whether a step is a value (55.13) needs values with a nothing. A rung on a ladder has a unit and no nothing: a
reader that numbers the rungs it has seen from the least numbers them from wherever the least seen happens to
stand, and a rule may itself count its rungs from one where the reader counts from nought. Under such a
numbering a row that keeps a sum does not read as one.

Call the **excess** of a row `a, b, c` what the step from `a` to `c` holds beyond `b`: `c − a − b`. A row is a
sum when its excess is nothing.

**Proposition 55.15 (the excess of two rows agrees wherever the nothing is put).** Add one amount `k` to every
value. Each row's excess falls by `k`, so two rows have the same excess after exactly when they had before;
whether a row's excess is nothing is not kept, since a sum's excess becomes `−k`.

So where the rows keep one sum, on a ladder numbered from anywhere, the asked row is right when its excess is the
excess of a row shown. This is 55.14 with a reading that is a number and not a truth: the pool offers, for
lines of three that stand alike, whether their excesses are the same, taking the step either way as in 55.13.
It still needs the unit: rungs numbered in steps that are not the rule's own do not keep it. In Lean 55.15 is
`NCA.excess_agrees_wherever_nothing_is`.

## 55.16 The parts of a thing

A thing of 55.12 is one patch, whatever it is made of. A thing drawn as thick places with thin runs between
them, as dots with lines, is so read as one thing, with nothing to say of how its places stand to one another
(§58). Its parts are found from its shape alone.

**Wear** a patch by taking away every pixel that has a neighbour outside it, and say a pixel has **depth** `d`
when it lasts `d − 1` wearings and not `d`. Across a run `t` pixels wide the deepest pixel has depth `⌈t / 2⌉`.

**Proposition 55.16 (wearing takes the runs and leaves the parts).** After `w` wearings a run `t` wide is gone
exactly when `t ≤ 2w`, and a place `T` wide still stands exactly when `T > 2w`. So where every run is at most
`t` wide and every part at least `T`, with `t < T`, the pieces left after `w` wearings are the parts, one piece
each, for every `w` with `t ≤ 2w < T`.

Neither width is given. Count the pieces after each number of wearings. While the runs last the thing is in few
pieces; through the stretch of 55.16 the count stays at the number of parts; beyond it the parts go one by one.
The parts are taken to be the pieces over the longest stretch of wearings in which the count does not change.
That is right where the stretch of 55.16, about `(T − t) / 2` wearings, is longer than the `t / 2` wearings the
runs last and than any stretch in which the parts go: where the parts are a good deal thicker than the runs and
about as thick as one another. A thing with no runs is one piece until it is gone, and one part.

Two parts are **joined** when a straight run of the thing lies between them, from outside the one to outside the
other. That joins are drawn straight is given. A run that passes over a third part reads as its two halves do,
so a drawing in which a join crosses a part does not say which is meant.

In Lean 55.16 is `NCA.wearing_takes_runs_and_leaves_parts`.

## 55.17 A link parts when it is long and joins many

The divide by chains of 55.11 is a length: every link longer than it parts. That asks two things of what is
seen that pictures do not grant. A class must hang together by links shorter than any between two classes; but
a class seen at many sizes has its smallest figures read coarsely, as a clump of their own a little way off.
And nothing may lie far from every class; but a figure misread once lies farther from everything than two
classes lie from one another. No length parts the classes, keeps the clump with its class, and leaves the
stray no class of its own.

What tells them apart is how much lies on each side. Join the things by their shortest tree, the shortest links
first, and say a link **joins** as many as the fewer of the things on its two sides when it joins them.

**Proposition 55.17 (a link that is long and joins many).** Let every link between two classes be at least `D`
long and join at least `m`; let a link within a class that joins more than `k` be at most `l` long, with
`l < D`; and let `k < m`. Then with any divide of length in `(l, D]` and any number in `(k, m]`, the links
that are longer than the divide and join at least the number are exactly the links between classes. A stray
joins few however far off it lies, and a clump within a class is near however many it holds; neither parts.
A weight made of the two, as their product, does not do this: a stray `L` away weighs `L` and a link between
classes `m · D`, and `L` may exceed `m · D`.

The length and the number are found together from the links. For each number, the links that join at least
as many are put in order of length and the divide is put in their widest gap, by ratio; among the links so found
long, those that join fewer stand below the number by a ratio too; the lesser of the two ratios says how clear
that parting is. Classes far apart part more clearly than the nearest two do, so the parting taken is the one
with the shortest divide among those at least half as clear, in the logarithm, as the clearest. A thing that
joins few is of the class it is tied to.

## 55.18 A size among its own kind

A size is read as how far a figure reaches (55.9). Figures of two shapes drawn at one size need not reach
alike: a drawer that rounds lengths to whole pixels draws a square a little smaller than a circle of the same
size, by a share that changes from size to size and can be half the step between two sizes. No divide on reach
then says of a square and a circle whether they are one size.

Where sizes are few, the reaches seen of one shape fall into **rungs**, and the rungs of two shapes stand in
the same order. A figure's size is then its rung, counted on its own shape's ladder.

**Proposition 55.18 (rungs keep what reaches lose).** Let each shape `s` draw size `i` at reach `r_s(i)`,
rising in `i`, and let the reaches be read to within `e` with `2e` less than the least gap between two rungs
of one shape. Then the rung of a figure on its shape's ladder is its size, for every shape, whatever the shapes'
reaches are to one another; while if `r_s(i) ≤ r_t(j)` for some shapes and sizes `i > j`, no rule on reach
alone orders the two figures as their sizes do.

A ladder is found from what was seen often: a reach seen seldom beside its shape's most seen is a misreading and
no rung. A shape not yet seen at every size has fewer rungs; they are laid along the ladder of the shapes that
have the usual number, in order, where they lie nearest in all. A size so read is a whole number with one step
between neighbouring rungs, so the steps and sums of 55.13 to 55.15 run on it as they stand. The ladder is
found from pictures alone, with nothing said of which answer is right; it is found before teaching and kept, so
that a size means the same from the first case taught to the last.

In Lean 55.17 is `NCA.long_links_joining_many_part` and 55.18 `NCA.rungs_keep_what_reaches_lose`.
