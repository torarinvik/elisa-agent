# 73. What a memory has to hold, find and follow

Chapter 64 says what a holding of a given size serves: how far back, how long a slot lasts, what
keeping at random or by rank gives. It does not say what a learner needs of its memory. This
chapter starts from the choice a learner is judged on. It asks which steps a memory must give
for the choice to be as good as with the whole history, how many must be held at once, what can
be known of them when they are written, what a memory read by its contents gives in place of
one that keeps, and what holding a run of presses found by looking ahead (chapter 72) is worth.

## 73.1 Model

Steps, entries, channels, capacity and slots are those of 64.1 and 64.5. A **history** gives an
entry for each step. A learner is **judged** on a choice, and `best` gives, for a history, the
choice that is judged right. The choice **turns on** a set `D` of steps when two histories alike
at every step of `D` have the same best choice. A learner **holds** a set `K` of steps when what
it chooses is given by the entries of `K` alone. The frame gives entries, choices and steps no
meaning, and nothing says how a learner comes to hold what it holds.

## 73.2 What has to be held

**Proposition 73.1 (holding what the choice turns on is holding all).** If the choice turns on
`D` and a learner holds `K ⊇ D`, there is a way of choosing from what it holds that is the best
choice at every history.

For the entries outside `K` may be filled in anyhow: the history so made is alike the true one
on `D`, so its best choice is the true one's. The steps held beside `D` do no harm.

**Proposition 73.2 (what is not held is chosen wrongly somewhere).** Let two histories be alike
at every step but `i` and have different best choices. A learner that does not hold `i` chooses
wrongly at one of them, whatever it does with what it holds.

For it is given the same entries at both. So the steps a memory has to give are exactly those the
choice turns on: all of them, and no others are needed. Neither proposition mentions the age of a
step.

## 73.3 How many at once

Let `needs t` be the steps the choice judged at step `t` turns on, all at or before `t`. A step
`i` is **open** at step `n` when `i ≤ n` and some choice judged after `n` turns on it.

**Proposition 73.3 (the open steps are what to carry).** A step a later choice turns on is open
at every step from its own until that choice. A step open at `n + 1` is step `n + 1` itself or
was open at `n`. What the choice at `n + 1` turns on is step `n + 1` or was open at `n`. And a
step that is not open is turned on by no later choice.

So a learner that holds at each step the steps open then has, by 73.1, all that every judged
choice needs; it never has to bring back a step it let go; and every other step may be let go at
once, a step that was open as soon as the last choice that turns on it is made. The slots this
takes is the largest number of steps open at one step. A channel's reach counts steps by age
(64.1); this counts them by use, and a step open for a thousand steps costs one slot. An open
step younger than the capacity is held by its channel without a slot, so the slots are needed
for the open steps older than that.

**Proposition 73.4 (fewer states than histories told apart).** Let a memory be in one of `M`
states at the moment a question comes, and let every two of `H` histories be told apart by the
best answer to some question. If `M < H`, the learner answers wrongly at some history and
question, whatever it keeps and however. In particular, with `n` steps open, any of which the
question may ask for, and entries of at least two kinds, a memory of `s < n` slots that each hold
an entry answers wrongly somewhere, whatever is written in the slots; and `n` slots serve.

For two histories are brought to one state of the memory, and at the question that tells them
apart one answer cannot be right for both. The slots may hold anything of the size of an entry,
not only entries as they came: no way of packing `n` free entries into fewer slots exists. So
the count of 73.3 is not only enough but needed, at the moment and for the task where every open
step may be asked for.

**Proposition 73.5 (which step is kept is itself a state).** With two steps, entries of two
kinds and one slot that holds truly the entry of the step it names, a learner free to choose
which step it keeps answers rightly for both steps at every history.

It keeps the first step where the two are alike and the second where they differ. So the bound
of 73.4 is on the states of a memory, and a rule that keeps by what an entry holds gains the
states of its choice: `s` slots chosen among `n` steps have as many states as there are choices
of the slots times the entries they can hold. Where entries are of many kinds, as pictures are,
that gain is small beside what a slot holds, and the count of slots governs.

## 73.4 When to write

By 64.4 a step must be kept while it is still held; by 73.3 it need be kept only if it is open,
which turns on choices not yet made. What a learner can know of that, and when, is the matter of
this section.

**Proposition 73.6 (the test of an entry put otherwise).** If the best choice changes when the
entry of step `i` is put otherwise, every set the choice turns on holds `i`. The converse fails:
there is a choice and a history at which putting one entry otherwise changes nothing, though the
choice does not turn on the other steps alone.

So a test that tries a judged choice again with one earlier entry replaced, and marks the step
where the choice changes, marks no step that does not matter, and can miss one that does: a step
that matters only together with another, or whose replacement happens to give the same choice.
The test is made at a judgement, on steps then available; it teaches what to keep, and cannot
keep what is already gone.

Before anything is taught, and for whatever teaching has left unknown, a rule keeps without
knowing which step will be asked for. Such a rule may use chance, and what it keeps may turn on
anything but the question to come.

**Proposition 73.7 (no rule does better for its worst step than even keeping).** Whatever rule
keeps at most `r` of `n` steps, some step is held with chance at most `r / n`.

For the chances of the `n` steps sum to the mean number held, which is at most `r`. Keeping at
random as in 64.6 holds every step with chance exactly `r / n` (64.7). So against a task that
may ask for any step, no rule that does not know the task holds the step asked for more surely
than that one does, and a rule without chance holds some step never. This is the sense in which
nothing can be known at the time of writing: the histories of two tasks that ask for different
steps are the same until the question, so a rule that reads only the history keeps the same in
both.

**Proposition 73.8 (several steps at once are rarely all kept).** Whatever rule keeps at most
`r` of `n` steps, for every `m ≤ n` there are `m` steps that are all held with chance at most
`C(r, m) / C(n, m)`, where `C(a, b)` counts the ways of choosing `b` of `a`. Keeping at random
as in 64.6 holds `m` of the first `r` steps since the mark all together, after `n` steps, with
exactly that chance.

For each way the rule can go holds at most `C(r, m)` sets of `m` steps, among `C(n, m)`. And
under 64.6 a step after the first `r` is kept with chance `r / n` and then takes the place of
one of the `m` with chance `m / r`, so all `m` stay with chance `(n − m) / n`, and the product
of these from `r + 1` to `n` is the ratio. For `r ≤ n` the ratio is at most `(r / n)^m`. With
three slots over twelve steps a single step is held with chance one in four, a pair with one in
twenty-two, three with one in two hundred and twenty. So keeping at random serves a choice that
turns on one step and fails a choice that turns on several, and no rule that keeps blind does
better. The remedy is not more chance: it is to know what to keep (73.6), to bring `n` down by
marking more often, or not to have to decide at writing at all, which is the next section.

## 73.5 Finding against keeping

Let every step be written with a **key**, and let a read be a **match**: a yes or no on keys,
made when the choice is, which gives the entries of the steps whose keys it says yes of. The
frame gives keys no meaning. Nothing is decided when a step is written but its key.

**Proposition 73.9 (what a match needs of the keys).** There is a match that finds exactly the
steps of `D` if and only if no step of `D` has the key of a step outside `D`.

So the keys need not say what an entry holds, nor be alike for steps that are alike: two steps
the choice must tell apart have to have keys that differ, and nothing else is asked of them. A
match that takes the keys a score likes best is the keeping by rank of section 64.7 with the
value given when the question is known, where there a value is given once, as the entry comes,
and an entry wrongly valued low is gone for good.

**Proposition 73.10 (found is as good as held).** If the choice turns on `D` and the match finds
every step of `D`, a learner that reads what is found can choose as one that holds the whole
history. A step the match does not find, on which the best choice turns at two histories alike
elsewhere, is chosen wrongly at one of them.

These are 73.1 and 73.2 with the found steps for the held. The entries read are those found,
however far back they lie, where a channel that reaches a step of age `d` reads more than `d`
entries (64.1). And the rule of writing is the same for every task, so 73.7 and 73.8 do not bear
on it: what is decided late is decided with the question in hand. What it costs is that every
step's key is kept and put to the match (section 73.7), and that the keys part what they must.

**Proposition 73.11 (keys that have gone stale).** Keys written under one reading and the keys
the present reading would write find the same steps if and only if the match says the same of
both at every step.

The keys themselves need not be equal; this is the sense of 72.3, that a thing kept need agree
with the thing it stands for only through what reads it. Where a reading is taught on after keys
were written, the match fitted to the new keys may say otherwise of an old one, and by 73.10 a
step so missed is a choice made wrongly. Writing the keys again needs the entries, so it costs a
read of every entry and can be done only for entries still available (64.5). A key is therefore
written by a reading that is held fixed, or carries the name of the reading that wrote it so
that a match is put only to keys it was fitted to.

## 73.6 A run of presses held

Tasks, states, presses, ways and least numbers of presses are those of 67.1; `fore`, `told` and
standing for a state for so many presses are those of 72.1. A **run** is a list of presses. A
learner that has looked ahead and found a run the foretelling says ends paid may hold it.

**Proposition 73.12 (a run found is paid without looking again).** Where the foretold state
stands for the state shown for as many presses as a run has, and the foretelling says the run
ends paid, pressing it ends paid in the world. And from any point along a run at which the
foretold state stands for the state that came, the rest of the run ends paid, whatever was the
case before that point.

By induction along the run, as in 72.1. So a run is right for as long as each state that comes
is one the foretold state stands for, and it can be taken up again at any such state.

**Proposition 73.13 (in the same number of presses).** Where standing for `k + 1` presses is
standing for `k`, the least number of presses the foretelling finds is the least in the world.
And after the first press of a shortest run, what is left is a shortest run from the state
reached.

So a run found at the first depth (72.3) and followed is paid in as few presses as any way, and
looking ahead again at a later state of it finds nothing shorter than what is held.

**Proposition 73.14 (where a run that failed went wrong).** Let `like` be a likeness of states
to foretold states under which payment is told alike. If the foretold state was like the state
shown, the foretelling said a run ends paid, and pressing it did not, then the run holds a press
such that at every point up to it the foretold state was like the state that came, and after it
it was not.

By induction along the run: were likeness kept to the end, it would give payment there. So a run
that fails either began at a state that was not as it was read, or the foretelling erred at one
press that can be named, the first at which likeness is lost; before it nothing was wrong. A
learner that holds with a run the states foretold along it, and compares each with the state
that comes, therefore knows the press at which to teach the foretelling and the state from which
to look ahead again (73.12).

**Proposition 73.15 (looking again costs under twice).** With `b ≥ 2` presses and `b^d` states
foretold to look `d` presses ahead, looking ahead again at every state of a run of `n` presses
foretells fewer than `2 · b^n` states in all.

For the sum of `b^d` over `d < n` is below `b^n`. So holding a run saves less than half of what
is foretold, and the first look is the dearest step whether the run is held or not. What holding
a run gives is not chiefly cost. A learner that looks again at each state reads the world each
time and is right wherever the held run is; a learner that holds the run and compares has, in
exchange for that, 73.14.

## 73.7 Cost

**Proposition 73.16 (entries read at a step).** A channel of capacity `c` holds at most `c`
entries at any step, and a learner that reads what a channel of reach `r` holds, `s` slots and
`m` steps found reads at most `r + s + m` entries at a step, whatever their ages.

Let an entry cost `e` to read and a key `κ` to put to a match, and let `N` keys be kept. A step
costs at most `(r + s + m) · e + N · κ` in time, and the holding is `r + s` entries with `N`
keys beside the entries they name, which may lie in the durable store of chapter 43. To serve a
choice that turns on `m` steps of age up to `d`: a channel alone reads `d + 1` entries a step,
every step; slots read `m`, and must have known them within the reach (64.4); a match reads `m`
and puts `N` keys to it. Finding is the cheaper where `N · κ < (d + 1 − m) · e`. Where keys are
matched exactly an index answers in work logarithmic in `N` (43.3), and the cost of a step does
not grow with how far back the steps lie at all.

By 64.4 what a holding costs is brought down by what an entry is. What an entry may be made
into, before it is held, is settled by the choice:

**Proposition 73.17 (a form of an entry that serves).** Let `f` give each entry a form. If the
best choice is the same at histories whose entries at the steps of `D` have the same forms, a
learner that holds only the forms of those entries can choose as one that holds the whole
history. And if two histories with different best choices have the same forms at every step, a
learner that holds the forms of all steps chooses wrongly at one of them.

So a form serves exactly when it keeps apart the entries the choice tells apart, as a key does
the steps (73.9) and a foretold state the states (72.3); it need keep nothing else. The count of
73.4 is then in the kinds of the form and not of the entry, and `e` is the cost of reading a
form. A form made by a reading that is taught on afterwards goes stale as a key does (73.11).

## 73.8 What is assumed and what is left open

Assumed. That the choice judged right is given by the history, one choice for each (no chance in
what is judged right); that an entry held, kept or found is the entry that was written. For 73.4,
that the histories counted all occur: where the entries that occur are few, or one follows from
another, fewer states are told apart and fewer are needed, and the bound counts those. For 73.7
and 73.8, that what the rule holds does not turn on the question to come. For 73.9 to 73.11,
that a key is written when its step is, and that the match is a yes or no on the key alone. For
73.12 to 73.14, the assumptions of 72.5: a press from a state leads to one state, and the
foretold states met stand for the world's for the presses left, which for a learned foretelling
is to be measured. For 73.15, a search that foretells every way.

Left open, and matters of the literature or of measurement recorded in the research diary. How
keys that part the steps are learned; the test of 73.6 gives, at each judgement, steps a choice
turned on, and steps it did not, to teach them on. A match by nearness of keys, where the steps
found are right only as often as the nearest keys are the needed ones. That keeping at random as
in 64.6 holds every set of `m` steps with the chance of 73.8, and not only sets among the first
`r` (it is a property of reservoir sampling, Vitter 1985; 64.7 proves it for one step). The test
of 73.6 with two entries replaced at once, which finds steps that matter only together at a cost
that grows as the square. Which form of an entry serves the choices of many tasks at once, and
how it is learned: 73.17 says what it must keep apart for one. Whether the likeness of 73.14 can
be read by the learner from what it is shown. Tasks in which chance decides what is judged right
or where a press leads. And how a learner that both keeps and finds is to share its entries read
between the two.

In Lean a choice turning on steps is `NCA.TurnsOn`, with `NCA.turnsOn_more`. 73.1 is
`NCA.held_chooses_as_whole` and 73.2 `NCA.unheld_step_errs`. 73.3 is `NCA.needed_is_open`,
`NCA.open_carried`, `NCA.open_holds_needed` and `NCA.closed_never_needed`, over `NCA.openAt`,
with `NCA.open_steps_serve` for what follows from them by 73.1. 73.4 is `NCA.short_memory_errs`,
with `NCA.fewer_slots_err` and `NCA.enough_slots_serve` for slots; 73.5 is
`NCA.which_kept_tells`. 73.6 is `NCA.changed_is_needed` and `NCA.unchanged_may_be_needed`; 73.7
is `NCA.some_step_kept_rarely`, and 73.8 is `NCA.some_steps_kept_rarely` with
`NCA.allKeptAtRandom_even` over the chance `NCA.allKeptAtRandom` that follows the rule step by
step. 73.9 is `NCA.parted_iff_found`, 73.10 `NCA.found_chooses_as_whole` and
`NCA.missed_key_errs`, 73.11 `NCA.stale_keys_found_alike`. 73.12 is `NCA.plan_paid` and
`NCA.plan_taken_up` over `NCA.led_append`; 73.13 is `NCA.foretold_least` and
`NCA.rest_of_plan_shortest`; 73.14 is `NCA.unpaid_plan_erred`; 73.15 is
`NCA.searching_again_under_twice`. 73.16 is `NCA.held_count_le` and `NCA.read_at_most`, and
73.17 `NCA.held_form_serves` and `NCA.merged_form_errs`.
