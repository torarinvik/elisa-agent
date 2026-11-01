# 22. Abstaining early

## 22.1 The most expensive outcome

An abstention costs the most of any outcome. The controller climbs until no
item can be climbed, and only then gives up, so at strict targets almost
all compute can go to formulas that are refused in the end. Compute spent on
a formula that will be refused anyway is wasted.

## 22.2 Selection never breaks the guarantee

Each answered formula's bound is at most `δ`, so its posterior error is at
most `δ`. A policy that abstains on some of these formulas, deciding from
observed readings only, leaves every remaining answer's guarantee intact. So
early abstention trades coverage for compute and never costs validity. The
only question is which formulas to give up on, and when.

## 22.3 Sound floors

A **floor** is a lower bound on every bound refinement can still reach. If
the floor exceeds `δ`, refinement would end in abstention anyway, so
abstaining at once changes no answer and saves the remaining climbs.

In exact arithmetic, a sum of fixed nonnegative charges is such a lower
bound for an additive account. In floating-point arithmetic, each accumulated
partial sum must be bounded from below to preserve that ordering. The
real-number induction holds for any sequence of lower-bounding additions;
it does not prove a particular floating-point implementation or an arbitrary
user-supplied floor.

Readings at the top rung never change. Call those words *fixed*.

- **Detection accounts.** `min(S / 2, e₂)` is monotone in the arity risks
  (Theorem 22.1). Setting every open word's risk to zero gives
  the floor `min(S_F / 2, e₂(F))` over the fixed words `F`. Within-group
  charges are nonnegative, and an unparseable reading has bound `∞`, so
  every reachable bound is at least this floor.
- **The certificate account of §18.** Every word is charged at least its
  arity risk, so `Σ_{k ∈ F} ρₖ` is a floor.
- **Static and demand accounts (arithmetic).** The bound is a sum of
  nonnegative charges, and a fixed item's charge no longer changes. The sum
  over fixed items is a floor.

The consumer declares its floor, alongside its certificate, from the
readings, the risks and the set of fixed items. The controller abstains as
soon as the floor exceeds `δ`. Answers are identical. Only the value
an abstained formula would have been forced to can differ, because it comes
from an earlier reading.

**Correction has no such floor.** `R` is not monotone in the open words'
risks. An open word becoming certain can rule out the competitor that made
a fixed word uncertain. For the correction account, early abstention must be
predictive.

## 22.4 Predictive abstention

For any account, let `s` be the controller's state after a step, and let
`A` be the event that refinement eventually answers if it continues to
completion. A stopping policy trades coverage against compute. Comparing
stopping immediately (reward zero) with committing to that full continuation
gives a positive expected reward exactly when

> `P(A | s) > λ · E[remaining cost | s]`.

The implementation stops when the inequality is reversed strictly and
continues on a tie. It estimates both terms on held-out refinement traces,
binning by the bound-to-target ratio. Applying the rule again at later states
can improve on or differ from committed continuation; the comparison alone
does not establish global optimality over all stopping policies (§25.3).
Since selection never breaks the guarantee (§22.2),
estimation errors cost only coverage or compute, never validity. Varying `λ`
traces the coverage–compute frontier. The sound floors of §22.3 are its
zero-loss end.

For deterministic refinement, multiple pure stopping policies can share one
trace: each selects its first stopping state, or the terminal state if it
never stops. Appending later states cannot change an earlier policy's chosen
state. Saved readings and costs must remain independent snapshots, and the
consumer must evaluate saved readings without dependence on later session
mutations. Sharing computation is an evaluation optimization; reported cost
for each policy remains the cost at its own selected state.

[Theory index](../THEORY.md)
