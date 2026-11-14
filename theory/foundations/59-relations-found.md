# 59. Relations found, not given

Each relation of §55 beyond sameness and order was written after a failure was understood: that two steps are
the same (55.5), that a step is a value (55.13), that two rows agree (55.14), that two rows have the same excess
(55.15). A learner so equipped reasons with what its teacher thought of. This chapter lets the learner compose
the relations itself from the readings they are all built of, take one up only when the judgements pay for it,
and offer what it has found wherever the places stand alike, on the task it was found on and on others.

## 59.1 What can be composed

Over slots that hold numbers, a **number** is the value at a slot, the step between two numbers, or the step from
a value to a step. A **relation** is whether two numbers are the same. Its **size** is how many values it reads.
With `k` slots there are `k` values, `k(k − 1)` steps between two values and at most `k · k(k − 1)` steps from
a value to those, and a relation is a pair of them: with nine slots, 729 numbers and about 265,000 relations.

**Proposition 59.1 (what was written is among them).** Whether two values are the same is a relation of size
two. That a step is a value (55.13) is one of size three; that two steps are the same (55.5), of size four; that
two lines of three have the same excess (55.15), of size six. So is one that was not written: that two lines of
three have the same total, since `a + b + c = a′ + b′ + c′` exactly when `c′ − b − a = c − b′ − a′`. A line that
holds the values of another in another order has its total.

Nothing in the composing says which of the 265,000 matter. That is found from judgements.

## 59.2 Paying for a name

Take `n` judgements, a share `q` of them good, and a relation that divides them into classes: where it holds,
where it does not, and where it reads nothing. A class of `m` judgements with a share `p` good **tells**
`m · D(p ‖ q)` bits of the verdicts, where `D(p ‖ q) = p log₂(p / q) + (1 − p) log₂((1 − p) / (1 − q))`, and the
relation tells the sum over its classes: how much shorter the verdicts are to write down once the relation's
reading of each judgement is known.

Among many relations some tell much by chance. A relation of size `s` is one of `N_s`, and saying which costs
`log₂ N_s` bits. It is taken up only if it tells more than `log₂ N_s + log₂ n + c` bits, with a margin `c`
given.

**Proposition 59.2 (the bar bounds the chance).** If each relation of one size that tells nothing of the
verdicts passes a bar of `t` bits with chance at most `(n + 1) 2⁻ᵗ`, then with `N_s ≤ 2ᵃ`, `n + 1 ≤ 2ᵇ` and
`t = a + b + c` the chance that any of that size passes is at most `2⁻ᶜ`.

The premise is the bound of the method of types for a class of two verdicts (Cover and Thomas, Theorem 11.1.4);
for three classes the factor is a higher power of `n + 1`, and the bar as used is not claimed tight. What it
gives is the order: a relation costs its name, a longer name costs more, and so of two relations that tell the
same the smaller is taken, and a relation over many values is not taken on a few judgements. That is the price
of 54.1 for a pool that is not written out.

## 59.3 Dividing by need

The judgements are divided by the relation that tells most beyond its bar; each class it leaves that is not all
of one verdict is divided likewise, and so on while some relation pays. The relations so taken are what is
found. As in 54.2 a relation is sought only where the judgements are not yet explained, here class by class: a
rule that governs few judgements is looked for among those the commoner rules leave.

A rule that governs too few judgements to pay for its name is not found. Written relations do not have that
limit, and are knowledge given; found ones are bought with judgements.

## 59.4 Offering what is found where the places stand alike

A relation is found on particular slots. A **move** is a one-to-one map of the slots onto themselves, given by
whoever knows which places stand alike: for values in rows and columns, exchanging rows, exchanging columns, and
exchanging the two.

**Proposition 59.3 (a moved relation reads the moved situation).** The image of a relation under a move reads,
of a situation, what the relation reads of the situation with its values moved back.

So where a rule may hold between any places that stand alike, a relation found for it between some of them is
offered between all, at no further cost in judgements; the learner of §54 then takes up the images it needs. The
same holds between tasks whose slots stand alike: relations found on one are offered on another, which buys
their names once.

In Lean 59.1 is `NCA.written_relations_are_composed`, 59.2 `NCA.name_paid_bounds_chance` and 59.3
`NCA.moved_relation_reads_moved`.
