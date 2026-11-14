# 58. The same under a renaming

The relations of §55 compare values that stand at given places: the value here with the value there. A thing made
of parts that nothing names has no places. Two drawings of one network put its parts anywhere, and whether they
are the same network is whether the parts of one can be paired with the parts of the other so that what is joined
stays joined. No probe over fixed slots reads that, since which slot answers to which is the question.

## 58.1 Model

A **structure** is a finite set of parts, a **mark** for each part, which is whatever is read of the part alone,
and a relation between two parts, **joined**, that holds both ways. A **renaming** of one structure onto another
is a one-to-one map of the parts of the first onto the parts of the second under which each part has its
partner's mark and two parts are joined exactly when their partners are. Two structures are **the same under a
renaming** when there is one. This is sameness as a description that names no part can tell it: every statement
about marks and joins that holds of one structure holds of the other.

What can be counted without pairing is kept by a renaming: how many parts there are, how many joins, and for each
number how many parts have that many joins. Counting is not enough:

**Proposition 58.1 (as many parts, as many joins at every part, and not the same).** Six parts joined in a ring
and six parts joined in two rings of three have every part joined to two others, and no renaming takes one onto
the other: three parts joined each to each are found in the second and not in the first.

## 58.2 Parts described by what they are joined to

Describe each part, round after round. At first a part's description is its mark. At each later round it is the
part's description so far together with the descriptions so far of the parts it is joined to, as many times as
each occurs. After one round a description tells how many joins a part has and to parts of which marks; after
two, how many joins each of those has; and so on outward.

**Theorem 58.2 (a renaming keeps every description).** Under a renaming each part has, after every round, the
description of its partner. So the two structures hold the same descriptions as many times each.

*Proof.* By induction on the rounds. At first the descriptions are marks, which a renaming keeps. If it holds
after `n` rounds, then the parts joined to a part's partner are the partners of the parts joined to it, and by
the hypothesis they carry the same descriptions as many times each. ∎

Two things follow. Structures whose descriptions differ in number are not the same, with no pairing tried. And
in seeking a renaming a part need only be paired with parts described as it is: no renaming is lost by that. A
round that tells no two parts apart that the round before did not tells nothing further in any later round, so
the rounds stop there, after at most as many as there are parts.

The descriptions are not enough either. In Proposition 58.1 every part of both structures has one and the same
description after every round, since each is joined to two parts described as it is.

## 58.3 Seeking the pairing

The renaming is sought part by part. The parts of the first structure are taken in turn, those with the fewest
parts described like them first. Each is paired with a part of the second not yet taken that is described as it
is and whose joins to the partners already chosen are those of the part to the parts already paired. Where no
such partner is left the last choice is undone and the next tried.

**Proposition 58.3 (said only where it holds, and found wherever it does).** A pairing the search completes is a
renaming: marks were compared when the descriptions were, and every two parts were compared for being joined when
the later of them was paired. If there is a renaming the search finds one: by Theorem 58.2 it pairs every part
with a part described alike, so its choices are among those tried.

In the worst case the choices tried grow as the factorial of the parts described alike, as for the two
structures of 58.1 enlarged. The descriptions are what keep it short where the parts differ.

To a learner this is a relation like those of §55, read of two things that each have parts: whether they are the
same under a renaming. What a part's mark is and what counts as joined are given by whoever reads the things.

## 58.4 Where the reading is in doubt

What is read of a thing may not say what joins what. A run drawn over a third part reads as the run, as its two
halves, or as the run with either half or both (55.16), and the drawing is the same for all of them. A structure
read with such **doubts** is then several structures: the joins that are sure with, for each doubt, one of the
ways it may be read.

Two things so read **may be the same** when some reading of the one is the same under a renaming as some reading
of the other.

**Proposition 58.4 (what may be the same misses no sameness).** If the things as they are lie among their
readings and are the same under a renaming, they may be the same. The converse does not hold: readings that are
not how the things are can agree.

So "may be the same" errs only by saying it of things that differ, and does that only where the doubts of the
two happen to make up for how they differ; "the same as first read" errs both ways, and wherever a doubt is read
differently in the two it says "not the same" of things that are. Which of the two a task pays for is not given:
both are readings a learner may look at. Readings are tried only against readings with as many parts described
alike (Theorem 58.2), which leaves few.

In Lean 58.1 is `NCA.counting_joins_does_not_tell` and 58.2 is `NCA.renaming_keeps_descriptions` with
`NCA.renamed_structures_described_alike`; 58.3 is not in Lean and is tested against trying every pairing; 58.4 is immediate from the definition.
