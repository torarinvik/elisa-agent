# 57. Wholes judged by their parts

A learner of 53 to 55 judges a situation through one view. Where a situation is made of parts that are each right
or wrong in the same way, that learner must be shown the way once for each part, since each part is read through
probes of its own. This chapter judges the parts one at a time through one view, and states what that spares and
what a takeover then tells of each part.

## 57.1 Model

A situation is split into named **parts**, each of a **sort**. What is seen of a part is an observation in its own
right, and parts of one sort are read through the same probes. A whole is good exactly when every part is, and
whether a part is good is one function, for its sort, of what is seen of it. The split and the sorts are the
contributor's; the frame assigns no meaning to a part or a sort.

One learner of 53 or 54 serves each sort. A whole is chosen that has the fewest parts judged bad, and among those
the one whose parts gather the least weight against them.

## 57.2 What judging the parts alike spares

**Proposition 57.1 (parts exchanged).** A whole is good exactly when the whole with its parts of one sort exchanged
among themselves is.

The same parts are judged, by the same function. So the learner's judgement of a whole is unchanged by which part
shows what, and a judgement made of one part is a judgement of the class of 53.1 for every part of the sort, in
this whole and any other. A learner that reads `m` parts through probes of their own, each with `c` classes, is
settled by `m·c` judgements at the least; one that reads them alike by `c`, whatever the number of parts. This is
54.12 and 55.2 once more: there the readings are unchanged by moving the scene or renaming the values, here by
exchanging the parts. The price is the same. A part that is right in a way of its own is not judged by the
function of its sort, and needs a sort to itself or a reading that says which part it is.

## 57.3 What a takeover tells of the parts

A teacher judges wholes. Let the proposal be judged bad and the teacher's choice good.

**Proposition 57.2 (the blame lies where the two differ).** Every part of the teacher's choice is good, and some
part of the proposal that differs from the same part of the teacher's choice is bad.

A part the two share is a part of a good whole, and the proposal has a bad part. So a takeover yields a judgement
of every part of the choice, and where the two differ in one part, of that part of the proposal. Where they differ
in several, the proposition names no one of them.

**Proposition 57.3 (a bad part shows what no good part shows).** Let whether a part is good be a function of what
some set of probes reads of it. Then that set reads of a bad part what it reads of no good part.

Two parts the set reads alike are both good or both bad. So among the differing parts a bad one is found where
some set of probes reads what it has read of no part recorded good, and a part of which every set reads what a
good part has shown is, for all the learner has been told, good.

The learner therefore records the parts of the teacher's choice first, and then ranks the differing parts: by its
present votes, and among equals by how many sets of at most `k` probes read of the part what they have read of no
good part. The lowest are judged bad. `k` is the contributor's; it need be no more than the probes a part's worth
depends on, and the sets number as the `k`-th power of the pool. This is a rule for choosing among the differing
parts and not a consequence of the model: a part may show something new and be good. Where nothing tells the
differing parts apart all are judged bad, which is right where each part has one good value, the rest being as
shown, and wrong elsewhere.

Where the wholes offered do not all have the same parts, a part that only one of the two has is not judged. What
differs there is that the part is present, which is no reading of the part; it is a reading of the whole, and is
judged where the whole's own readings are made a part.

## 57.4 What this does not cover

The split is given, not found. A whole whose worth depends on how its parts stand to one another is not the
conjunction of its parts' worth; such a relation must itself be made a part. Nothing here orders wholes that are
all good.

## 57.5 What every whole offered tells

A takeover is told of the one whole the learner proposed. Where the right whole is known after every choice,
whether or not the learner's choice stood, the other wholes offered are known too, and by 57.2 each has a bad part
among those in which it differs from the right one. A learner corrected only when it chooses wrongly is told
nothing in the cases where it chose rightly for want of a reason against, and those are the cases it will get
wrong another time.

**Proposition 57.4 (where each part has one good value, every differing part is bad).** If, the rest being as
shown, each part has one good value, a part of any whole offered that differs from the same part of the right
whole is bad.

That each part has one good value is given, as in 57.3, and is wrong where two values of a part would both do.
Under it one case judges every part of the right whole good and every differing part of every other whole bad,
with no part left to choose among. The learner records only the judgements its votes do not already give: a
part of the right whole it does not vote good, and a differing part it does not vote bad. What it already holds
is not written down again, so the judgements kept stay few and each is one the learner would have got wrong.
In Lean 57.4 is `NCA.differing_part_bad_where_one_is_good`.
