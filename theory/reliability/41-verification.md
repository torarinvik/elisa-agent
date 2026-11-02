# 41. Verification

## 41.1 Checking instead of bounding

A ledger's charge grows with every relevant invocation (§33), so a long
route's bound grows with its length, and long chains of reasoning end up
abstaining however reliable each step is. A *verifier* checks a route's
answer against the route's inputs and accepts or rejects it. Answering
only accepted answers replaces the route's accumulated charge by what the
verifier can miss.

Let `W` be the event that the answer is wrong and `A` that the verifier
accepts it. A verifier has *miss rate* at most `m` and *false-rejection
rate* at most `f` if, given the observations made before the check,
`P(A | W) ≤ m` and `P(not A | not W) ≤ f`.

**Theorem 41.1 (verified answers).** If the route's charge `c < 1` bounds
`P(W)` given the observations before the check (Theorem 33.1), and
`f < 1`, then given those observations and acceptance

  `P(W | A) ≤ m c / ((1 − c)(1 − f))`.

If `m = 0` the bound is `0` for every `c`.

*Proof.* `P(W ∧ A) ≤ m P(W)` and `P(A) ≥ P(A ∧ not W) ≥ (1 − f)(1 − P(W))`.
So `P(W | A) ≤ m w / ((1 − f)(1 − w))` with `w = P(W) ≤ c`, and the right
side is nondecreasing in `w`. With `m = 0`, `P(W ∧ A) = 0`. ∎

Selective answering (Theorem 33.2) then answers accepted answers whose
verified bound is at most `δ`. The bound no longer grows with the route's
length as long as `c` stays away from 1: an exact verifier (`m = 0`)
resets it to zero, and an inexact one multiplies it by
`m / ((1 − c)(1 − f))`. A rejected answer is not answered; the route may
then refine, or try another candidate (§39) and verify that.

## 41.2 Estimating a verifier's rates

An exact verifier is one whose acceptance implies correctness by
construction, such as substituting a solution back into the equation it
solves; its rates are attested, not measured (§31.5). An inexact one,
such as an independent route whose answer must agree, has its rates
estimated on labeled in-situ answers: among the `n_W` wrong ones, the
Clopper–Pearson upper bound on the accepted fraction bounds `m`, and among
the `n_R` right ones the upper bound on the rejected fraction bounds `f`,
together with probability at least `1 − β` at level `β / 2` each. As with
every rate here, the estimate is the average over those inputs and holds
given the observations only as far as the verifier's behaviour does not
depend on them otherwise. An independent route that fails like the
route it checks has a large miss rate (§40.2) and verifies little.
