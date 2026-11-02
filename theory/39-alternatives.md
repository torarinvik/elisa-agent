# 39. Answering over alternatives

## 39.1 Forks

A route commits to each expert's output, so an early mistake, such as a
wrong segmentation, passes unchanged to everything after it. An expert
may instead *fork*: offer candidate outputs `o₁ … o_m` with numbers
`q₁ … q_m` such that, given the observations, `o_k` is the correct output
with probability `Q_k ≥ q_k`, the events being disjoint. The rest of the
route is evaluated once for each candidate, giving an answer `a_k` and a
ledger charge `c_k` (§33), at most 1 and set to 1 if the ledger is
uncertified.

**Theorem 39.1 (answers over alternatives).** Choose an answer `a` and let
`A = {k : a_k = a}`. Under sound demands and calibrated reports for the
invocations after the fork, and if the fork's inputs are correct,

  `P(answer a is wrong | observations) ≤ 1 − Σ_{k∈A} q_k (1 − c_k)`.

*Proof.* Split on which candidate, if any, is correct. If `o_k` is
correct with `k ∈ A`, the route after the fork computes the correct
answer unless one of its relevant invocations fails, which has
conditional probability at most `c_k` (Theorem 33.1), and then answers
`a`; so `a` is wrong with probability at most `c_k`. For `k ∉ A`, and when
no candidate is correct, bound the probability by 1. Summing over the
partition,

  `P(wrong) ≤ Σ_{k∈A} Q_k c_k + Σ_{k∉A} Q_k + (1 − Σ_k Q_k) = 1 − Σ_{k∈A} Q_k (1 − c_k)`,

and replacing each `Q_k` by `q_k ≤ Q_k` only raises the bound, since
`1 − c_k ≥ 0`. ∎

The invocations before the fork add their own charge `c₀` by the union
bound, so the answer's bound is `c₀ + 1 − Σ_{k∈A} q_k (1 − c_k)`. The
answer minimizing it is the one with the largest *support*
`Σ_{k∈A} q_k (1 − c_k)`, and selective answering (Theorem 33.2) answers
when the bound is at most `δ`. Several candidates agreeing on the answer
add their support. A wrong candidate costs nothing beyond its missing
support, so offering more candidates never raises the bound of the
answer chosen.

## 39.2 Calibrated candidates

The numbers `q_k` must be lower bounds that hold on the inputs the fork
receives in the route (§38). One way: group inputs by an observable
*stratum*, such as how many candidates there are or how the first
candidate looks, and for each stratum and candidate rank count, on `n`
labeled in-situ inputs of that stratum, the `s` on which that rank's
candidate was correct. The Clopper–Pearson lower bound on `s / n` at level
`β / m`, over the `m` cells of the table, holds in every cell together
with probability at least `1 − β`. For inputs drawn like the labeled
ones, the cell's rate is the probability that the candidate is correct
given the stratum; it is a bound given everything observed only insofar
as the stratum captures what matters, as with any calibration.
