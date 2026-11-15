# 62. Answers composed along a chain

Chapter 51 learns a machine from answers to sequences it chooses, and chapter 58 treats things whose parts
nothing names. This chapter joins them for a situation that states how some of its parts stand to one
another and asks how two of them stand: what the statements settle, from what, and how little has to be
learned for it.

## 62.1 Model

A **situation** holds **names**, which differ from one situation to the next, and **statements**. A
statement is a **label** and two names in order; the label is whatever it says besides them. One statement
is **asked**, and the answer is one of finitely many. The rule is taken to be the same under a renaming of
the names (58.1), so it reads nothing of a name but which statements hold it.

The statements other than the asked one join the names into a network. A **path** from the asked
statement's first name to its second is a run of statements, each sharing a name with the next, and its
**word** is the run of their labels, each with whether it is passed from its first name to its second or
back. A rule is **composed** when the answer is read off the word alone, by a machine that starts in one
state and is moved by each symbol (51.1). Where no path joins the asked names there is no word, and that
case has an answer of its own.

## 62.2 What short chains settle for long ones

A table from words to answers grows with the length of the word: over `s` symbols there are `s ^ k` words
of length `k`. A table of moves does not: a machine of `q` states has `q * s` moves.

**Theorem 62.1 (moves met, words settled).** Two tables of moves that agree wherever a word takes the first
leave that word in the same state.

So once every move a word meets has been met by some word whose answer is known, the word's answer is
known, whatever its length. A word that meets a move never met is not settled, and nothing is said of it.

## 62.3 The answers as states

A learner that chooses its own sequences can find the states (51.2). One that is only paid or not for the
situations it is handed cannot ask, and needs the states given. They are given where the answer is
**carried**: two words with one answer keep one answer when each is lengthened by the same symbol.

**Theorem 62.2 (answers serve as states).** If the answer is carried, there is a table of moves between
answers that gives the answer of every word, starting from the answer of the empty word.

The table has at most `(a + 1) * s` moves for `a` answers, each found from a word that meets it last: a
paid word fixes its last move, and a word paid nothing rules one answer out for it. Moves met in the middle
of a word are searched, shortest words first, a move that keeps the answer before one that changes it.

Being carried is a property of the rule, not of the learner, and some rules lack it:

**Theorem 62.3 (the side of a sum is not carried).** Two sums can both lie above nought and, one step
back, one lie at nought and the other above it.

For such a rule no table of moves between answers fits, and the search ends without one; the state is then
an amount, and 51.5 applies to its differences where the sequences can be chosen.

## 62.4 What this assumes

That the names are told from the rest: here by being rare across situations where what a statement says
recurs. That the asked statement is told from the others: here as the label of which each situation has
one. And that one path is read. Where two paths join the asked names and the rule is composed, both give
the answer only if the statements agree, which a situation dealt to have one answer ensures and one dealt
with statements that need not have been read does not rule out.

In Lean 62.1 is `NCA.moves_agreeing_where_visited_agree`, 62.2 `NCA.answers_serve_as_states` and 62.3
`NCA.side_of_a_sum_is_not_carried`.
