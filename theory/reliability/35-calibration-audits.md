# 35. Calibration audits

## 35.1 Testing reports

The guarantees of §33 rest on calibrated reports: given everything
observed, each invocation fails with probability at most its report. A
report fitted on one distribution need not stay calibrated on another,
and nothing in a route's execution reveals the difference. An *audit*
compares reports with failures on labeled invocations of one expert.

Let `n` audited invocations have reports `r₁ … rₙ`, fixed once the
expert's outputs are observed, failures `F = Σᵢ fᵢ` and total report
`R = Σᵢ rᵢ`.

**Theorem 35.1 (audit without independence).** If the reports are
calibrated given the observations, then `P(F ≥ k | observations) ≤ R / k`
for every `k > 0`.

*Proof.* Conditionally, `E[F] = Σᵢ P(fᵢ) ≤ R`, and Markov's inequality
gives `P(F ≥ k) ≤ E[F] / k`. ∎

**Theorem 35.2 (audit with independence).** If moreover the failures are
conditionally independent, as when the audited inputs and their labels
are drawn independently, then `P(F ≥ k | observations) ≤ T(r, k)`, the
probability that independent Bernoulli trials with success probabilities
`r₁ … rₙ` succeed at least `k` times.

*Proof.* The tail of a sum of independent Bernoulli variables is
nondecreasing in each success probability (couple `fᵢ` with a
Bernoulli(`rᵢ`) variable that is at least `fᵢ`), and each `P(fᵢ) ≤ rᵢ`. ∎

Either bound, evaluated at the observed `F`, is a p-value: an audit that
*refutes* the expert's calibration when it is at most `α` does so wrongly
with probability at most `α`. An audit that does not refute proves
nothing. It tests a consequence of calibration, `E[F] ≤ R`, and only on
the audited distribution.

## 35.2 Recalibration

A refuted expert can be recalibrated on the audit's labels: refit its
temperatures (§16) on one part of the audit and audit the refit on the
other part. The refit's reports are then fixed before the second part is
seen, so Theorems 35.1–35.2 apply to it unchanged. If it is not refuted,
its temperatures are attested (§28.4) and installed in place of the old
ones; the old attestation stays in the store as the record it was.

The guarantee carried by the new reports is the same kind as before:
calibration on the distribution the audit sampled. Audits therefore have
to be repeated as long as the distribution can move, and their frequency
bounds how long a shift can go undetected, as spot checks bound purity
violations (§32.2).
