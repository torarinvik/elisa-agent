# 37. Calibration by groups of inputs

## 37.1 Groups

A report calibrated on one distribution need not be calibrated on
another (§35), and one temperature fitted to a mixture serves neither
component: fitted to shifted inputs, it overstates the risk of clean
ones. Let a *grouping* `g` map each input to one of finitely many groups,
computed from the input alone, for example by a classifier that tells
the inputs an audit collected from those calibration saw. An expert
*calibrated by groups* reads each input through the rung (§16) fitted on
labeled inputs of that input's group.

Calibration within a group means: among the inputs of group `γ`, the
expected number of failures is at most the expected total report, with
the conditional premise of §33 holding within the group.

**Theorem 37.1 (groups transfer across mixtures).** If reports are
calibrated within every group under a labeled distribution `P`, they are
calibrated under every distribution `Q` that differs from `P` only in
the groups' proportions, `Q(· | γ) = P(· | γ)` for every group `γ`.

*Proof.* Under `Q`, the expected failures are `Σ_γ Q(γ) · E_P[F | γ]` and
the expected report `Σ_γ Q(γ) · E_P[R | γ]`; each term of the first is at
most the corresponding term of the second, and the weights are
nonnegative. ∎

The premise is that a shift moves mass between groups without changing
what each group contains. A grouping that separates the shifted inputs
from the others satisfies it for that shift; one that mixes them does
not, but is still calibrated under the proportions it was fitted on. The
grouping need not be accurate for the theorem, only fixed before the
rungs are fitted and audited, and each group's audit (§35) tests its own
premise.

## 37.2 Fitting and auditing

Labeled inputs from every source, such as the calibration set and the
audits, are pooled and routed by `g`. Each group's rung is fitted on one
part of its inputs and audited on another, as in §35.2. A group without
labeled inputs has no rung, and inputs routed to it are read uncalibrated
and reported as unknown risk, so they leave a ledger uncertified (§33.2).
