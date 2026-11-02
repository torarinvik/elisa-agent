# 40. Audits by agreement

## 40.1 A second opinion in place of a label

Audits (§35, §38) need labels, and labels are what an open system has
least of. Two experts with the same contract can audit each other
without them. Run both on the same in-situ inputs and record whether
their decisions agree. If both are right they agree, so a disagreement
means at least one of them is wrong.

Let expert `A` report `aᵢ` and expert `B` report `bᵢ` on input `i`, both
fixed once their outputs are observed, and let `Dᵢ` indicate that they
disagree.

**Theorem 40.1 (audit by agreement).** If both experts' reports are
calibrated given the observations, then `P(Dᵢ | observations) ≤
min(1, aᵢ + bᵢ)`. So the audit of §35, run with the reports
`min(1, aᵢ + bᵢ)` and the disagreements as failures, is valid. Without
independence its p-value is the total over the disagreements (Theorem
35.1); with disagreements conditionally independent across inputs it is
the Poisson-binomial tail (Theorem 35.2).

*Proof.* `Dᵢ` implies that `A` or `B` fails on `i`; the union bound and
calibration give `P(Dᵢ) ≤ aᵢ + bᵢ`, and a probability is at most 1. The
audits of §35 assume only such a bound on each failure probability. ∎

A refutation says that at least one of the two is miscalibrated on these
inputs, not which; auditing against a third expert, or labeling a few of
the disagreements, tells them apart. When `B` is exact (`bᵢ = 0`), the
audit is a labeled audit of `A`.

## 40.2 What agreement cannot see

The test is one-sided in a second way: two experts that fail together
and agree on the same wrong output produce no disagreement. Correlated
errors, which a shared shift tends to cause, make the audit miss
miscalibration that a labeled audit would catch. It remains valid, since
it refutes only on disagreements, but its power depends on how
differently the two experts fail. Experts trained on different data, or
built differently, make better auditors of each other.
