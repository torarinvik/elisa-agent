# 66. A trunk of blocks that are never taught twice

Experts that learn from what a shared part gives them are only as lasting as that part. If the shared
part is taught further, what it gives changes and every expert built on it is in doubt; if it is never
taught further, nothing new can be learned in it. This chapter treats a shared part that grows by
addition only, and states what that guarantees and what it does not.

## 66.1 Model

A **block** is a function from an input to what it gives; the frame gives a block a name and no
meaning. A **library** assigns blocks to names, and may have no block at a name. A library is changed
in two ways only: a block is **added** at a name that has none (a name that has a block keeps it), and
a block is **taken away**.

An **expert** is a list of names, its **reading**, and a **last part** that turns what the named
blocks give into an output. Its output on an input is defined when every block it reads is present.
The blocks need not be alike, nor the experts.

## 66.2 What addition leaves alone

**Proposition 66.1 (fixed by what is read).** Two libraries that agree at every name an expert reads
give that expert the same output on every input.

**Proposition 66.2 (addition preserves).** If every block an expert reads is present, adding a block
leaves the expert's output unchanged on every input.

**Proposition 66.3 (any run of additions preserves).** The same holds after any finite run of
additions.

The outputs are equal, not close, and on every input, those the expert was taught on and those it
never met. No measurement is needed to know it and no old input need be kept to restore it. The
guarantee is bought by the rule that a block is not taught after it is added: it says nothing of a
library whose blocks change.

By 66.1 what an expert costs to run is the cost of the blocks it reads and its last part. A library
may hold any number of blocks; an expert that reads `m` of them needs `m` loaded.

## 66.3 What may be taken away

**Proposition 66.4 (an unread block).** Taking away a block an expert does not read leaves the
expert's output unchanged on every input.

**Proposition 66.5 (a read block).** Taking away a block an expert reads leaves the expert without an
output.

So a block may be dropped exactly when no kept expert reads it, and a library needs to know, for each
block, whether it is read. Space is recovered by dropping unread blocks and the experts no longer
wanted, at no cost to those kept. Replacing several blocks by one smaller block is not covered: the
experts that read them would then read something else, and what that costs them has to be measured.

## 66.4 Choosing a reading

A new expert may be taught on several readings: a new block of its own, some earlier blocks, or both.
Let each reading tried have a **loss**, a number measured on cases held back from its teaching, and
let the reading of least loss be chosen, the expert's own block being among those tried.

**Proposition 66.6 (no worse than its own).** The chosen reading's loss is at most that of the
expert's own block, and at most that of every reading tried.

This is a statement about the held-back loss. That the chosen reading is no worse on cases not yet
met needs the held-back cases to stand for them, which is an assumption about how they were drawn and
how many they are, and is the subject of chapter 30; choosing among more readings on the same
held-back cases weakens it.

## 66.5 What is assumed and what is left open

Assumed: a block is a function of its input alone and is not changed once added; a name is given to
one block only. Left open: which earlier blocks are worth trying when the library is large; whether
blocks taught by some tasks help others, which is a matter of measurement; and how several blocks may
be made one with a stated bound on what the experts that read them lose.

In Lean 66.1 is `NCA.expertOutput_congr`, 66.2 `NCA.added_block_preserves`, 66.3
`NCA.added_blocks_preserve`, 66.4 `NCA.removed_unread_preserves`, 66.5 `NCA.removed_read_fails`, and
66.6 `NCA.chosen_not_worse` with `NCA.chosen_least`.
