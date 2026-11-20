# 72. Looking ahead through states foretold

Chapter 70 keeps a reading for each number of presses, each taught from the readings below it.
The lesson of such a reading is made of estimates: the largest of the answers the readings below
give at the state after, which is wrong wherever one of them is wrong upward, and what is wrong
is taught on. This chapter treats the other way to the same question. One reading is kept, that
of a press paid at once, and beside it a **foretelling** of the state a press leads to. Whether
payment can be had within several presses is then asked of the foretelling, press by press.
The chapter states when that answer is the world's, what a foretold state has to be for it, and
what a foretelling cannot give.

## 72.1 Model

Tasks, states, presses, ways and being within `k` are those of 67.1 and 70.1, with `step` giving
the state a press leads to and `paid` the states that are paid. A foretelling has states of its
own: `fore` gives, for one of them and a press, another, and `told` says of one whether it is
paid. They need not be states of the world; a foretold picture is a picture no screen showed. A
foretold state `t` **stands for** a state `s` for `k` more presses, `stands k s t`, under two
conditions on the relation. **Read alike:** where `t` stands for `s`, `told t` exactly when
`paid s`. **Kept under a press:** where `t` stands for `s` for `k + 1` presses, `fore t a` stands
for `step s a` for `k`, for every press `a`. The state shown stands for itself.

The lesson of a foretelling is the state that came. Every press that is followed by a state
carries it, in a paid trial or an unpaid one, as in 70.2; and it is formed from no estimate, so
no answer of another reading, right or wrong, enters it.

## 72.2 The foretelling's ways are the world's

**Proposition 72.1 (the same ways).** Where `t` stands for `s` for `n` presses, the foretelling
has a way of length `n` from `t` exactly when the world has one from `s`.

By induction on `n`. At nought it is reading alike. A way of `n + 1` begins with a press, after
which the two states stand for one another for `n` by keeping, and the rest is the hypothesis.

**Proposition 72.2 (within so many presses).** Where standing for a state for `k + 1` presses
is standing for it for `k`, and `t` stands for `s` for `n`, the foretelling is within `n` of
payment from `t` exactly when the world is from `s`.

So a search over the foretelling answers the question of every level of chapter 70 at once,
from one foretelling and the first reading alone.

**Proposition 72.3 (the first depth found is the distance, and its press begins a shortest
way).** Let `s` be `n + 1` presses from payment and `t` stand for it that long. A press after
which the foretelling has a way of `n` begins a shortest way in the world. And for no press does
the foretelling have a way shorter than `n` after it.

The first is 72.1 at the state after and 70.3. For the second, such a way would by 72.1 be a way
in the world, of fewer than `n + 1` presses in all. So a search that deepens one press at a time
and stops at the first depth at which some press is foretold to lead to payment has found the
distance, and may press what it found.

## 72.3 What a foretold state has to be

72.1 does not ask that the foretold state be the state that came. It asks that the two be read
alike and stay so. For a learner the reading is its own first reading, and a foretold picture
serves when that reading gives it what it gives the picture that came. This is the value
equivalence of Grimm, Barreto, Singh and Silver (2020): a model need agree with the world only
through the functions that read it.

It says which errors of a foretold picture matter. Measured by how far it lies from the picture
that came, a picture can be nearly right and useless (a mover drawn faintly at several places it
might stop is near every one of them), and far off in points that no reading uses without harm.
A foretelling taught only to lie near the picture that came is taught a number that need not
move with what its user gains (Lambert, Amos, Yadan and Calandra, 2020). Whether to teach a
foretelling the reading as well as the picture that came is a matter of measurement, recorded in
the research diary; 72.1 says only that the reading is what its states are to keep.

## 72.4 What is not seen cannot be foretold

**Proposition 72.4.** Let a foretelling give a point of the state after from a part of the state
before. Of two states alike in that part it says the same; where the world's states after differ
at the point, it is wrong of one of them.

A network whose layers see so many points each way is such a foretelling for every point: what
moved further than they see has left the part from which the place it stops is given. No
teaching mends this; the part has to be widened. Where a thing can cross the picture the
foretelling has to see across it.

## 72.5 Cost, what is assumed and what is left open

With `b` presses a search to depth `d` foretells `b^(d−1)` states at its deepest, as in 56.4. A
bound on the states foretold at one depth bounds the depth, the sooner the more presses there
are; a distance beyond it is not found.

Assumed as in 67.4 and 70.5: a press from a state leads to one state, and the learner can tell
the states apart from what it is shown. For 72.1 to 72.3: that the foretold states met stand for
the world's for the presses looked ahead, which for a learned foretelling and a learned first
reading is an assumption about both at the states met, to be measured.

Left open, and matters of measurement recorded in the research diary. How the errors add along
one way: a way of `n` presses is judged through `n − 1` states foretold one on the other and one
reading at the end, so it is misjudged only where one of those is wrong, and the errors add once
for each press looked ahead; the lesson that taught them holds none of them, where by 70.5 the
lesson of a level holds the errors of the levels below. A search does not judge one way but every
way, and how the errors add over them is 72.6. How many presses a foretelling needs before its
states stand for the world's. That the first reading can say "none" at a foretold state it never
met. Tasks in which chance decides where a press leads, and tasks whose state is not all in the
picture, where a foretold picture cannot stand for what is hidden. And a search that need not
foretell every way.

In Lean 72.1 is `NCA.foretold_way`, with `NCA.foretold_way_always` for a foretelling that stands
for the world however long; 72.2 is `NCA.foretold_within` over `NCA.stands_fewer`; 72.3 is
`NCA.foretold_begins_shortest` and `NCA.foretold_silent_below`; 72.4 is `NCA.unseen_not_foretold`.

## 72.6 Errors over all the ways looked at

A search that stops at the first depth at which some press is foretold paid stops short of the
distance wherever one reading below the distance says "paid" falsely: one reading among all it
makes, not one along a way.

**Proposition 72.5 (false short ways).** Let a search make `N` readings below the distance, and
let each be false in at most `e` of the trials. Then the trials in which the search stops short
are at most `N · e`; and they are as many as that where no two readings are false in the same
trial.

With `b` presses and a distance `d`, `N = b + b² + … + b^(d−1)`: the allowance for one reading is
the allowance for the search divided by a number that grows as the states foretold do, where
along one way it is divided by `d`. A first reading that is right nine times in ten on the steps
it was taught on is far from enough four presses out with four presses (`N = 84`).

What mends it is in the search's own play. A false reading that is acted on leads to a press that
is made and not paid, which is a lesson for the first reading at that very state (73.14, the
first mismatch of a way held). The lesson has to reach the reading while states of its kind are
still met; a reading taught only when the steps held have grown by some share is taught the more
seldom the more it holds. How many such lessons are needed is not bounded here, and what the
teaching between the reading's own teachings gains is a matter of measurement recorded in the
research diary.

In Lean 72.5 is `NCA.false_stops_few`, with `NCA.false_stops_all` where no two readings are false
in the same trial.
