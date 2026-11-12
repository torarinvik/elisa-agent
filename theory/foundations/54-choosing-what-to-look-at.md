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
