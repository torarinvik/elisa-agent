# 51. Learning state machines from queries

Chapters 44 to 50 search for a route by enumeration, whose cost grows exponentially with route size. This chapter treats a
class of targets that can be inferred from evidence at a cost polynomial in their size, without enumeration.

## 51.1 Model

A machine has states `Q`, a start state, a step `Q → A → Q` over symbols `A`, and an answer for each state. It computes
`f : A* → O` if the answer of the state reached on `w` is `f w` for every sequence `w`. A learner may ask for `f w` on
sequences it chooses. Each distinct query is a label.

## 51.2 What a table of answers establishes

**Theorem 51.1 (distinguished prefixes need states).** If `f (s ++ e) ≠ f (t ++ e)` for some suffix `e`, every machine
computing `f` reaches different states on `s` and `t`.

An observation table holds prefixes that are pairwise distinguished by its suffixes, so it never holds more prefixes than the
smallest machine has states. For a target with a machine of `n` states, the table learner of Angluin (1987) therefore stops
growing at `n` and, with a source of counterexamples, returns a machine after a number of queries polynomial in `n`, the
alphabet size and the counterexample length. The polynomial bound is cited and not proved here.

## 51.3 What lies outside the class

**Theorem 51.2 (distinct answers need states).** A machine that gives `n` sequences pairwise distinct answers has at least
`n` states.

A target whose answers are unbounded, such as a count over sequences of any length, has no finite machine: the table gains a
state for each new answer and never closes. This is a property of the class and no query budget changes it. Such targets need
a richer class, for example a finite control with a register that transitions update.

Before any suffix is added, the table's states are exactly the distinct answers found. A first closure holding more states
than the labelled cases have distinct answers is therefore evidence that the target is outside the class, and stopping there
saves labels. This is a heuristic: it can abandon a learnable target, and it cannot admit a wrong one.

## 51.4 Cost and assumptions

Work per query is constant, so the cost is labels: about `n * (1 + |A|)` table cells times the number of suffixes, plus the
sequences used to look for counterexamples. Compute is negligible beside enumeration, and the count of labels replaces the
count of candidates as the quantity to minimize.

The learner assumes the target answers chosen sequences, including ones outside its usual inputs, where it may return a mark
for no answer. With labelled cases alone, random sequences share few prefixes, and state merging has little to merge on. A
machine that agrees with every case and random check is still a proposal over an alphabet seen in training. Certification on
fresh cases is separate and unchanged (20.22).

## 51.5 Counters by differences

Let answers lie in a commutative group, and let a machine also carry a register: each transition adds a gain fixed by the
state and the symbol, and the register is the answer. Such a target can take unboundedly many values, so 51.3 puts it outside
the finite class.

**Theorem 51.3 (differences rebuild).** For any `f`, adding the one-step differences `f (p ++ [a]) - f p` along a sequence
to `f []` gives `f` of the sequence.

**Theorem 51.4 (differences follow the control).** For a register machine, the difference made by one more symbol is the
gain of the control state reached and that symbol.

So the difference of a counter is a function of a finite control, and if the gains take finitely many values it has a finite
machine. The learner of 51.2 then applies to the difference unchanged, and 51.3 turns its machine into answers. Each
difference costs at most two answers, and a prefix-closed table shares most of them.

This needs an answer on the empty sequence and a group on the answers, which a domain supplies. A target whose gain depends
on the register itself, such as a longest run or a distance from the origin, is outside the class. A finite machine can still
approximate it on bounded sequences, and whether that is good enough is for the gate to decide.

## 51.6 How long a sequence tells two machines apart

Sort the states of a machine by the answers they give to every sequence of at most `k` symbols. As `k` grows the
classes only split, and a step that splits none leaves none to split later, because the answers to sequences of
`k + 1` symbols are the state's own answer and the classes, at `k`, of the states one symbol on. There are at most as
many classes as states.

**Theorem 51.5 (short sequences settle it).** Two states of a machine of `N` states that answer alike every sequence
of at most `N - 1` symbols answer alike every sequence.

**Theorem 51.6 (two machines agree if they agree on short sequences).** Machines of `n` and `m` states that give the
same answer to every sequence of at most `n + m - 1` symbols give the same answer to every sequence.

51.6 is 51.5 in the machine that holds both. So a machine of `m` states that is wrong about a target of `n` states is
wrong on a sequence of fewer than `n + m` symbols: whatever is wrong can be found on short sequences, and nothing is
hidden in the long ones. How many short sequences must be tried is another matter. A target can hold a state that one
sequence alone reaches, and then all `|A|^(n + m - 1)` may be needed.
