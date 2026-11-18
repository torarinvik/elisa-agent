# 64. Working memory: what looking back is served

Chapter 43 treats records kept for good. This chapter treats what is held only for a while: the recent
past of what a system took in and what it did, which experts look back in, and from which a part is
kept. It asks how far back a holding of a given size serves, when an entry can still be kept, and what
is gone.

## 64.1 Model

Time is a count of **steps**. A **channel** is a stream that is written at steps, an entry being named by
the step it was written at; the frame gives a channel a name and no meaning. A channel has a **capacity**
`c`: at step `n` it **holds** the entry written at step `i` when `i ≤ n < i + c`. The **age** of an entry
is `n - i`.

Apart from what a channel holds, an entry may be **kept**: pinned in the holding, or written to the
durable store of chapter 43. An entry is **available** at a step when it is held or kept.

## 64.2 How far back

**Proposition 64.1 (served by age).** An entry of age `d` is held if and only if `d < c`.

So an expert that looks back `d` steps is served at every step exactly when the capacity exceeds `d`,
and what an expert needs of a channel is one number, which it can state before it is loaded. A kernel
that knows the capacities can refuse, at loading, an expert it could not serve.

**Proposition 64.2 (a larger holding serves all a smaller one does).** If `c ≤ c'`, every entry held at
capacity `c` is held at capacity `c'`.

Capacity is therefore a single dial: raising it never takes away what an expert could see.

## 64.3 Channels read together

An expert that asks what one channel held when another was written reads both at one step.

**Proposition 64.3 (the smaller capacity governs).** The entries of two channels written at step `i` are
both held at step `n` if and only if a channel of the smaller capacity would hold an entry of step `i`.

Looking back across channels is as short as the shortest channel read. Capacities that are meant to be
read together should be set together, in steps, whatever their entries cost to hold.

## 64.4 Keeping, and what is gone

Often what makes an entry worth keeping is learned after it was written: a payment that follows a press
by some steps, an answer shown after the question.

**Proposition 64.4 (kept in time).** A decision made `d` steps after an entry was written can keep it if
and only if `d < c`.

The capacity a system needs is thus the longest delay between seeing a thing and knowing it mattered,
and no more. Past that delay an entry that was not kept cannot be:

**Proposition 64.5 (gone when unkept).** An entry that is not kept is available at no step `n ≥ i + c`,
and an entry that is kept is available at every step from its own on.

What a holding costs is the sum over channels of capacity times the size of an entry. By 64.4 the
capacity is fixed by a delay in steps, so the cost is brought down by what an entry is, not by holding
fewer of them: which form of an entry serves the experts that read it is a matter of measurement, not
of this chapter.

## 64.5 Slots

A reader may keep a few entries by pinning them, in `k` **slots** filled first in first out: an entry
kept when the slots are full takes the place of the one kept longest, which is released. Count the keeps
as they are made; the entry of keep number `q` is in a slot, when `m` keeps have been made, if `q ≤ m`
and fewer than `k` keeps came after it.

**Proposition 64.6 (a slot is held by keeps, not by steps).** The entry of keep `q` is in a slot after
`m ≥ q` keeps if and only if `m - q < k`; and with more slots, every entry that was in a slot still is.

No step appears in the condition. By 64.5 an entry in a slot is available at every step while it is
there, so a reader with `k` slots can look back at what it kept over any number of steps in which it
keeps fewer than `k` more; and at every step it reads at most the entries its channels hold and `k`
others, whatever their age. What the proposition does not give is which entries to keep: by 64.4 that
must be decided while an entry is still held, and how it is decided is a matter of learning and of
measurement, not of this chapter.

In Lean 64.1 is `NCA.held_iff_age`, 64.2 `NCA.held_mono`, 64.3 `NCA.held_together`, 64.4
`NCA.kept_in_time`, 64.5 `NCA.gone_when_unkept` with `NCA.kept_is_available`, and 64.6
`NCA.slotted_iff_few_since` with `NCA.slotted_mono`.
