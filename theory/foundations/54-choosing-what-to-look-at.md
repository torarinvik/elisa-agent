# 54. Choosing what to look at

Chapter 53 finds which components of an observation matter, among components the caller has chosen. This chapter lets
the learner choose them. A situation can be read in many ways, far more than a learner can look through at each
decision, and the learner starts by looking at nothing. Its judgements show when what it looks at is not enough, and
which further reading would explain them.

## 54.1 Model

A situation `s` can be read through any **probe** `p` of a finite pool `P`, giving a value `p(s)` from a finite set of
at most `d` values. A **view** `Q ⊆ P` shows the situation as the readings `(p(s))` for `p` in `Q`. Judgements `(s, a,
v)` come from a target `t`, as in 53.1, and a set `R ⊆ P` **suffices** for `t` if situations that agree on every probe
of `R` have the same target.

Reading a probe is a request and is counted. At a decision the learner reads only the probes of its view. A situation
that is judged is **studied**: every probe of the pool is read once and the readings are kept, so that a probe taken up
later can be read on the judgements already made. Decisions are many and judgements few, so the requests are dominated
by the size of the view.

## 54.2 When the view is not enough

**Theorem 54.1 (a contradiction lies outside the view).** Let `R` suffice for `t`, and let situations `s`, `s'` agree
on every probe of `Q` while `t s a ≠ t s' a` for some action `a`. Then some probe of `R` is not in `Q` and reads `s` and
`s'` differently.

If every probe of `R` either lay in `Q` or read the two alike, they would agree on all of `R`, and `t` would be the
same on both. Proved in Lean as `disagreeing_probe_outside_view`.

So two correct judgements that the view cannot tell apart, with opposite verdicts, show that the view lacks a probe the
target depends on, and that the missing probe is among those on which the two situations differ. One such pair does
not say which of the differing probes it is. Many judgements do, through what each candidate would explain.

## 54.3 What a set of probes explains

A set `S` of probes sorts the judgements of an action into classes, the situations that agree on `S` (53.2). Its
**errors** are the judgements outside the majority verdict of their class: the fewest verdicts that would have to be
reversed for `S` to be consistent. Its **cost** is its errors plus a price `λ ≥ 0` for each class it uses.

**Theorem 54.2 (a sufficient set has no errors).** If the judgements agree with `t` and `S` suffices for `t`, then `S`
has no errors, and its cost is at most `λ · |A| · d^|S|`.

By 53.1 `S` is consistent, so every class is unanimous; there are at most `d^|S|` classes for each action. Hence if a
target depends on at most `k` probes and all but one of them are in the view, the missing probe joined to `k − 1` probes
of the view has no errors, whatever the number of judgements.

A set's errors never rise when a probe is added to it, since the classes only split, and they usually fall by chance:
a probe that reads differently in most situations leaves most classes with one judgement and no error. The price of a
class charges for that. A probe that corrects one error by splitting one class in two changes the cost by `λ − 1`, so
with `λ ≥ 1` it is not cheaper than doing without.

## 54.4 Buying probes

The learner keeps a view `Q`, empty at the start, and learns over its readings by 53.3 or 53.5 with sets of at most `k`
probes. Write `c(Q)` for the least cost of a set of at most `k` probes of `Q`. After a judgement, while some probe `p`
outside `Q` joined to at most `k − 1` probes of `Q` costs less than `c(Q)`, the learner takes up the cheapest such
probe. It then reads the new view on the kept judgements and learns over it afresh.

**Proposition 54.3 (purchases are bounded by judgements).** Let costs be multiples of `1/q`. Among `m` judgements the
learner takes up at most `q · (1 + λ) · m` probes, and never more than `|P|`.

A judgement raises `c(Q)` by at most `1 + λ`: it adds at most one error and one class to the cheapest set. Each
purchase lowers `c(Q)` by at least `1/q`, and `c(Q)` is never negative (the counting step is 53.4's
`steps_le_potential`). The bound is loose. What is measured is in the research diary.

## 54.5 What this does not cover

- **Probes that matter only together.** If the target is a parity of two probes missing from the view, neither alone
  explains any judgement, and either is bought only when chance makes it seem to. The rule is directed to a missing
  probe when the rest of a sufficient set is already in view, or when the probe explains part of the judgements by
  itself.
- **A teacher the probes cannot explain.** Judgements that depend on something no probe reads, or that compare one
  action with another, leave errors under every set. The price bounds what is bought for them, but they are bought
  for.
- **The cost of studying.** A judged situation is read through the whole pool, and choosing a probe compares
  `|P| · C(|Q|, k − 1)` sets on every judgement kept. This suits a pool of tens or hundreds of probes, not one probe
  for each point of a large image.
- **Where probes come from.** The pool is the caller's. 54.6 builds one from the situation's own contents for
  situations that are values at positions; other kinds of situation need pools of their own.
- **Values that are nearly equal.** Readings are symbols. Two readings carry a judgement only if they are the same.

## 54.6 Probes placed by what the situation holds

Let a situation be a **scene**: a value at each position of a finite set of positions in `ℤⁿ`. A probe that reads a
fixed position is the plainest. A target that depends on what stands next to some object, wherever the object is, is
not a function of few such probes.

**Proposition 54.4 (fixed positions do not follow an object).** Let the target depend on the value at offset `δ` from
the one position holding a value `u`, and let `u` occur at each of `N` positions in some scene, with both verdicts
possible there. Then every set of fixed-position probes that suffices for the target has at least `N` probes.

For each of the `N` positions `x` there are two scenes with `u` at `x` that differ only at `x + δ` and have opposite
targets, so a sufficient set reads `x + δ`; the positions `x + δ` are distinct.

A value whose positions in a scene are exactly the positions of a box, one solid block, is an **anchor** there, placed
at the block's least corner. A value at one position is the smallest block; an object drawn as a filled rectangle of
one colour is a larger one. An **anchored probe** reads the value at a fixed offset from the anchor of a given value,
and a **bearing** reads the sign of the difference between two anchors along an axis; both read nothing where the
value is absent or does not form one block. The target of 54.4 depends on one anchored probe, whatever `N` is.

The pool of 54.4's learner is then every value as a candidate anchor, every offset within a reach `r`, and every pair
of values and axis: `v · ((2r + 1)ⁿ − 1) + n · v(v − 1)/2` probes for `v` values, independent of the size of the scene.
No value is named as an anchor. A value that never stands alone reads nothing, explains nothing, and is not bought;
which values are worth looking from is found by 54.4 like any other probe. What remains given is that situations are
scenes, the set of values, the reach, and that objects worth looking from are solid blocks of one value. Finding the
blocks reads the whole scene; only the probes of the view are read after that.

For pools of hundreds of probes the search of 54.4 is shortened: each probe is first joined to at most one probe of
the view, and only a shortlist of the cheapest is compared in full. A probe that explains the judgements only together
with two probes of the view can be missed by it.

## 54.7 Looking within a budget

So far a decision reads only the probes of the view, but placing an anchored probe needs the anchor's place, and
54.6 found it by reading the whole scene. Let each frame of a scene be read at no more than `B` positions, counting
every reading, and let the learner keep what it found from one frame to the next.

**Proposition 54.5 (finding a block).** Positions are read in a fixed order that visits each position of a scene of
`M` positions once. A block of `b` positions is first hit after at most `M − b + 1` readings, and after `(M + 1)/(b +
1)` on average over the orders.

The first is counting; the second is the expected place of the first of `b` marked items among `M` in a random order.
With `s` readings to spare in each frame, a block is found within about `M/(b·s)` frames of appearing.

**Proposition 54.6 (following a block).** A block of side at most `w` along each of `n` axes that moved as it last
did, or as far along another axis or the opposite way, is found again within `2n` readings and its corner within `n ·
w` more.

There are at most `2n` such places, each one reading, and from a position in the block the corner is reached by
stepping back along each axis in turn.

So a learner whose view holds `q` probes, placed from `m` anchors that keep their speed, decides a frame from at most
`q + m · (2n + n·w)` readings, whatever the size of the scene, and pays the search of 54.5 only when an anchor is
lost or new. The readings left over are spent on that search. Once the search has covered the scene and every block
found before is found again, nothing is known to be missing, and it is cut to a small share of the budget.

What a budget does not allow is checking the definition of 54.6: that a value forms one block and that the block is
solid. A value seen at two corners in a frame, or running further than the reach, is given up as an anchor; one that
merely has a second block the readings did not land on is taken for an anchor until they do. A judged frame is
studied beyond the budget, as in 54.1.

## 54.8 Actions that are one action turned

With a set for each action (53.8), `m` actions that do the same thing in `m` directions are taught `m` times. Let a
**turn** `g` be a permutation of the pool: it puts a probe `g(p)` in each probe's place. For scenes, the turns of 54.6's
pool are those induced by sending each axis to an axis, forwards or backwards: an offset goes to the turned offset,
and a bearing to the bearing along the turned axis, reversed where the axis is.

Action `b` **is action `a` turned by `g`** if `t s b` is the same function of the readings `(g(p)(s))` that `t s a` is
of the readings `(p(s))`. Then a judgement of `b`, with each probe `p` read as `g(p)`, is a correct judgement of `a`.

**Proposition 54.7 (a turned action shares its teacher).** If `b` is `a` turned by `g` and `S` suffices for `a`, the
judgements of `a` together with those of `b` read through `g` are consistent with `S`, and `g(S)` suffices for `b`.

Both kinds of judgement agree with the one target `o ↦ t o a` over the readings, so 53.1 applies to their union.

The learner is not told which actions are turns of which, or by what. For an action `b` and an earlier action `a`,
write `c(·)` for the least cost (54.3) of explaining a set of judgements by one probe or none. `b` **joins** `a` under
the turn `g` that makes `c(J_a ∪ g·J_b)` least, if that is less than `c(J_a) + c(J_b)`; otherwise it stays apart. By
54.7 and 54.2 the true turn adds no errors, and joining saves the price of the classes the two would each have paid
for. A wrong turn saves the same price but puts judgements with opposite verdicts in one class, at one error each, so
it loses once the judgements outnumber the classes. The choice is made again after every judgement.

A joined action is decided and taught through its turn: its view is `g` applied to the shared view, and one
correction of any of the `m` directions is a judgement of all of them.

Not covered: the comparison uses one probe, so two actions whose likeness shows only in a pair of probes are not
joined; an action that is another turned only in part is joined or not as a whole; and the turns offered are the
caller's. Turning offsets about a block's corner agrees with turning the scene only where the blocks sit alike about
their corners in every direction, as cells of a regular grid do.

## 54.9 Giving probes up

The view of 54.4 only grows. A probe taken up when the judgements were few, or before two actions were joined (54.8),
may explain nothing later. Let the view be **shed** to the union, over the actions, of each action's cheapest set of
at most `k` probes of the view.

**Proposition 54.8 (shedding costs nothing by the measure that buys).** The shed view has the cost `c` of the view it
was shed from, and at most `k` probes for each action that shares no judgements with another.

Each action's cheapest set is still in the view. So no probe is bought back at once: a purchase must lower the cost.

Shedding is not free by another measure. The learner of 53.5 lets every set of the view vote, and the sets besides
the cheapest carry judgements to observations the cheapest has not met; after shedding it learns afresh over fewer
sets. Whether the smaller view is worth the corrections it adds is measured, in the research diary, and is the
caller's choice.

## 54.10 Situations that are alike turned

54.8 lets two actions share judgements. A single action may also be judged alike in a situation and in the same
situation turned. Let a turn `g` act on situations as it acts on probes, `p(g·s) = (g·p)(s)`, and call `g` a
**likeness** of an action `a` if `f(s, a) = f(g·s, a)` for every `s`. The likenesses of an action form a group `G`.

Let `≤` be a total order on tuples of readings, and for a list of probes `L` let the **first image** of `s` be the
`g·s`, `g ∈ G`, whose readings through `L` come first. Judge and decide every situation in its first image.

**Proposition 54.9 (one image for all).** If every `g ∈ G` is a likeness, then (i) the first image of `s` has the
verdict of `s`; (ii) `s` and `g·s` have the same readings through `L` in their first images, so a judgement of one
is a judgement of the other in every class of every set of probes of `L`; and (iii) if `f` depends on a set `S`,
then the verdict of the first image depends on `S` read there, and the classes of `S` that hold first images number
at least the orbits of `G` on the classes of `S` and at most all of them.

(i) is the definition. For (ii), `s` and `g·s` have the same images, as `G` is a group, and so the same least tuple
of readings. (iii) follows from (i) and 54.2 applied to first images.

By (iii) the bound of 53.4 holds with the classes that hold first images in place of all classes. The lower count is
reached when `L` tells the images of a situation apart wherever `S` does, so that classes that are images of one
another are met in one image only. It is not reached by adding to each judgement its turned copies instead: a set of
53.1 is a conjunction of readings, and a target true of `m` images of one class is then `m` conjunctions, each
needing its own probes in the view.

The learner is not told `G`, nor what tells images apart.

- A turn is taken for a likeness unless one probe explains the judgements together with their turned copies for
  more than twice what one probe explains the judgements for, by more than `√n` for `n` judgements. A likeness adds
  no errors to a probe and its turned image read as one (54.7 with 54.2), and the turned copy pays for no classes
  of its own. A turn that reverses verdicts puts opposite verdicts in one class, at an error each, which grows with
  `n`. The tolerance is an assumption about chance, not a bound: the cost compared is a least over probes of a
  finite sample, and without tolerance the choice was seen to alternate.
- `L` is the readings of one probe, the **pivot**, in every image, followed by the view. The pivot is the probe with
  which the judgements, each in its first image, are explained most cheaply by one probe; it is kept until another
  is cheaper.

A likeness is of an action. Actions joined under 54.8 have their likenesses in common, in the frame of the action
they joined: `g` is a likeness of `a` exactly when `h g h⁻¹` is one of `a` turned by `h`. Actions not joined are
tested apart, each on its own judgements, and each has its own pivot.

A join of 54.8 and a likeness are one claim, that judgements read through a turn belong with others, and are held
by one test. Where likenesses are sought, `b` joins `a` under the turn that makes `c(J_a ∪ g·J_b)` least unless that
exceeds `c(J_a) + c(J_b)` by more than `√(|J_a| + |J_b|)`; the strict comparison of 54.8 would let an action go on
little evidence, and the action, alone with few judgements, would then refute no turn and take every one for a
likeness.

Not covered: the turns taken need not form a group, and (ii) then holds only for the turns taken; actions with
unlike targets are joined until their judgements refute it beyond the tolerance, and never if no one probe tells
their targets apart; a likeness that
holds for some situations only is taken or refused as a whole; until a false likeness is refused, its judgements
are shared wrongly, and the corrections that costs are measured in the research diary.

## 54.11 Looking for a block whose side is known

54.5 reads positions in an order chosen without regard to the block, and finds a block of `b` positions among `M`
after `(M + 1)/(b + 1)` readings on average and `M − b + 1` at worst. A block found once has shown how large it is.
Let its **side** `w` be the least run of its value from its corner along an axis, and let the **marked** positions
of a scene of sides `N_1, …, N_n` be those whose coordinates are all multiples of `w`; they number `L = ∏ ⌈N_i / w⌉`.

**Proposition 54.10 (a block of known side holds a marked position).** A solid block of side at least `w` along
every axis holds a marked position, wherever it lies. So the marked positions, read in any order, find it within
`L` readings, and within `(L + 1)/2` on average over the orders if it holds exactly one. No order of readings finds
every such block within fewer than `∏ ⌊N_i / w⌋`.

Along each axis the block covers `w` positions in a row, which include a multiple of `w`; the block is solid, so it
holds the position with those coordinates. For the bound, the scene holds `∏ ⌊N_i / w⌋` places for the block that
share no position, and an order must read a position of each.

So against 54.5 a block of side `w` along `n` axes is found in about a `w^n`-th of the scene at worst, where the
order of 54.5 needs nearly all of it, and the same holds near a block's last place: a block that moved no further
than `r` along any axis holds one of the `(⌊r/w⌋ + ⌈(r + w)/w⌉)^n` offsets from its old corner that are multiples
of `w`, where 54.6's rings read `(2r + 1)^n`.

The learner is not told `w`. It measures the side of each block when it first finds it, steps its rings by that
side, and when a block found before is missing reads the marked positions of the least side missing before the
order of 54.5, carrying on from frame to frame. A block that has since grown smaller may hold no marked position: a
pass over all of them that does not find it forgets the side, and the block is then sought as in 54.5 and measured
again.

Not covered: a block that is not solid, or that moves while it is sought, may be missed by a pass, and the side is
then forgotten for nothing; blocks never seen are still found by 54.5 alone; and with fewer than `L` readings to
spare a frame, a block that jumps stays unknown for about `L/(2s)` frames, with `s` readings spare, which no order
improves by more than the rounding.

## 54.12 Where a block has been

54.10 uses what a block is, not where it has been. Along an axis let a block's corner have been seen at coordinates
`c_0, c_1, …, c_m`, and let its **stride** there be `g = gcd(c_1 − c_0, …, c_m − c_0)`, with `g = 0` while it has
been seen at one coordinate only.

**Proposition 54.11 (a block that keeps its stride is met at its corner).** If the block's corner lies at `c_0 +
g·k` along each axis, then of the positions whose coordinate along each axis is `c_0` plus a multiple of `g`, one is
the corner. They number `∏ ⌈N_i / g_i⌉`, and where `g_i ≥ w` along every axis that is no more than the marked
positions of 54.10. If the corners a block may take along an axis are `c_0 + g*·k`, then `g* | g`, and `g = g*` once
two displacements seen have greatest common divisor `g*`.

The first is the definition and the count; `g* | g` because `g*` divides every displacement. So the stride seen is
never finer than the true one, and may be coarser: the positions it marks are then too few, and a block may lie on
none of them.

The two are mixed axis by axis, as both arguments are: along an axis whose stride is at least `w` the marked
coordinates are `c_0` plus multiples of the stride, and along the others the multiples of `w`. A pass over these
positions that does not find the block sets its stride aside, the positions of 54.10 are read next, and the stride
is taken up again, made finer by the new displacement, when the block is found.

Not covered: a stride is an assumption about the future drawn from the past, with no bound on how long a coarser
stride may hold before it fails; each failure costs a pass. Places are remembered only as a stride from one corner,
so a block that keeps to some other set of places gains nothing.
