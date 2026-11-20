# 69. Looking where the picture is unusual

A learner that reads a whole picture pays, in weights and in what it must be shown, for every
point of it, though most points never bear on what it is taught. This chapter treats a learner
given only a window of the picture, laid where the picture differs from what it usually shows:
when that window holds all that varies, what the cut saves, and where it fails.

## 69.1 Model

A **picture** gives a value to every one of finitely many **points**. The learner **looks back**
over some pictures seen before, at least one. A value is **usual** at a point when no value was
held there in more of the pictures looked back over; a point has a usual value, and several where
values tie, of which the learner takes one. A point of a picture is **unusual** when its value
there is not the usual one. The frame gives points and values no meaning.

A point has a row and a column, both whole numbers. The **window** of **half-width** `h` about a
**middle** holds the points whose row is within `h` of the middle's row and whose column is within
`h` of its column; its **side** is `2h + 1`. The **middle of some numbers** is the one at the middle
place when they stand in order. The learner's middle has the middle of the rows of the unusual
points and the middle of their columns, each point counted once. A **reading** has one weight for
every point it is given.

## 69.2 The usual value

**Proposition 69.1 (most of the pictures decide).** If a point held one value in more than half of
the pictures looked back over, that value is usual there and no other is, whatever the remaining
pictures held. So where the pictures looked back over never differed at a point, a picture that
agrees with them there is not unusual there; and a point that held one value, its ground, in more
than half of them is unusual in exactly the pictures where it does not hold its ground.

So the learner need not be told what is ground and what is thing: a thing that moves leaves each
point bare more often than not, and is unusual wherever it stands. A few odd pictures among those
looked back over, fewer than half, change nothing.

**Proposition 69.2 (what is unusual lies where pictures vary).** Let `R` be a set of points such
that outside `R` every picture looked back over holds what the present picture holds. Then every
unusual point of the present picture lies in `R`.

So the learner is never drawn to the part of the picture that stays as it is, however large that
part is and whatever it shows.

## 69.3 The window holds what varies

**Proposition 69.3 (one line).** Let all unusual coordinates lie between `a` and `b` with
`b − a ≤ h`, and let the middle be any number between two unusual coordinates. Then the middle
lies between `a` and `b`, and the window of half-width `h` about it holds every coordinate from
`a` to `b`. The same is true of a window that would reach past an edge of a picture of side at
least `2h + 1` and is moved whole to lie inside it.

**Proposition 69.4 (rows and columns).** Let a picture have an unusual point, and let its unusual
points lie in a box whose rows span at most `h` and whose columns span at most `h`. Then the window
of half-width `h` about the middle row and the middle column of the unusual points holds the whole
box.

So where all that varies keeps to a box half as wide as the window, the window holds that box in
every picture, wherever in it the unusual points stand, and the learner need not be told where
the box is. Only that the middle lies among the unusual coordinates is used; any other such middle
serves as well. The bound is on the half-width, not the side, and by 69.7 it cannot be loosened
for a middle that falls at an end.

## 69.4 What the cut saves

**Proposition 69.5 (weights by the window).** A window of half-width `h` has at most
`(2h + 1)(2h + 1)` points, whatever the picture. With side `w` for the window and `n` for the
picture, `w ≤ n` gives `w·w ≤ n·n`, with equality only when `w = n`.

So a reading with a weight for every point it is given, or for every place of a coarser grid laid
over what it is given, has as many weights as the window has points and not as the picture has,
and a larger picture adds none. That fewer such weights want fewer pictures to be taught from is
not proved here; it is a matter of the literature (69.6).

## 69.5 Where it fails

**Proposition 69.6 (what stands still is not looked for).** A point at which no picture, past or
present, differs is never unusual. And a point further than `h` below every unusual coordinate, or
above every one, is in no window about a middle chosen among them.

So if what decides payment stands at a point that never varies, the window is laid without regard
to it and holds it only where it happens to stand near what does vary. By 69.1 the same befalls a
thing that rests at one point for more than half of the pictures looked back over: it becomes the
usual value there, and the point is unusual once the thing has left.

**Proposition 69.7 (too far apart).** Two coordinates further apart than `2h` are in no one
window of half-width `h`, whatever its middle. And a middle at one end of a stretch longer than
`h` leaves the other end out.

So unusual points in two groups further apart than the window is wide are never both held. Between
`h` and `2h` they are held or not by where the middle falls; it falls at an end when more than
half of the unusual points stand in the end row or column.

## 69.6 What is assumed and what is left open

Assumed: that the learner looks back over at least one picture; for 69.2 that outside `R` the
pictures do not vary at all, which tasks meet roughly (a counter, a flicker, a slow drift of the
ground are unusual as much as any thing); for 69.3 and 69.4 that the unusual points keep to a
stretch or box of the stated size; for the moved window that the picture is as wide as the window.

Left open, and matters of the literature or of measurement recorded in the research diary: that a
reading with fewer weights learns from fewer pictures. For a mark of `d` values standing at one of
`k` places, a reading by one window shared over the places learns from about `k + d` samples where
one with weights of its own for each place needs about `k·d` (Lahoti, Karp, Winston, Singh and Li,
2024); for readings by kernels built of windows, the samples needed grow with the window and not
with the picture (Misiakiewicz and Mei, 2022). Both are shown for those readings and tasks; for
the learner's own reading they are an analogy. Also open: how many pictures to look back over and
how often to form the usual values anew; what to give the learner while no point is unusual; what
replaces one window where 69.6 or 69.7 bite; and that the middle falls at an end when more than
half of the unusual points stand there, which is said in 69.5 and not proved.

In Lean the usual value is `NCA.Usual` over `NCA.timesHeld`, with `NCA.usual_exists`; 69.1 is
`NCA.most_is_usual` and `NCA.usual_is_most`, with `NCA.same_is_usual`, `NCA.agreeing_not_unusual`
and `NCA.unusual_iff_off_ground`; 69.2 is `NCA.unusual_within`; 69.3 `NCA.middle_between` and
`NCA.window_holds` over `NCA.Near`, with `NCA.moved_window_holds`; 69.4 `NCA.window_holds_box`
over `NCA.middle`, `NCA.middle_mem`, `NCA.rows` and `NCA.cols`; 69.5 `NCA.window_points_le`,
`NCA.cut_saves` and `NCA.cut_saves_unless_whole`; 69.6 `NCA.agreeing_not_unusual` and
`NCA.still_point_missed`; 69.7 `NCA.far_apart_not_both` and `NCA.long_stretch_cut`.
