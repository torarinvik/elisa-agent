# 38. In-situ audits

## 38.1 Sampling inside the route

Every rate and report the guarantees use is in situ: it concerns the
inputs an expert receives inside the route (§31.3), which earlier stages
shape. An audit on inputs drawn any other way, such as clean glyphs
rendered on their own rather than cut out of expressions by a segmenter,
tests a different premise and can pass while the route's error exceeds
its target.

An *in-situ audit* samples the invocations a route actually charges.
While a ledger is kept, each charged invocation of a selected expert is
kept with probability `q`, by a coin independent of everything else,
together with its inputs, its output and its report. Labels for the kept
invocations are obtained afterwards, and the audit of §35 is run on them.

**Theorem 38.1 (sampling preserves the audit).** Let the coins be
independent of the failures given the observations. If the reports of
the charged invocations are calibrated, the kept invocations satisfy
`E[F_kept] ≤ E[R_kept]`, and given the observations and the coins the
kept failures satisfy the premises of Theorems 35.1–35.2.

*Proof.* With `sᵢ` the coin of invocation `i`, `E[Σ sᵢ fᵢ | obs] =
q Σ P(fᵢ | obs) ≤ q Σ rᵢ = E[Σ sᵢ rᵢ | obs]`. Given the coins, the kept
set is fixed and each kept invocation is calibrated given the
observations, which is what Theorems 35.1–35.2 assume. ∎

The kept invocations are the charged ones, weighted as the route charges
them, so the audit tests calibration exactly where the ledger relies on
it. A shift that changes what an expert receives shows up in the audit
after about `n / q` charged invocations, if `n` labeled ones suffice to
refute.

## 38.2 Escalating experts

An escalating expert (§33.3) answers each input through one of its rungs,
and calibration belongs to the rung, not to the ladder. A kept invocation
is therefore attributed to the expert that answered it, so that each rung
is audited on the inputs that reached it, after the climbs that chose
them.
