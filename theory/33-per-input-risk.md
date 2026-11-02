# 33. Per-input risk on any route

## 33.1 Two accounts, one charge

Section 16 answers an input only when a bound on its error probability is
at most `δ`, computed from the readings of that input; selective
refinement (§22, §25) builds that bound for one route shape, a producer
mapped over a sequence and read by one consumer. Section 31 bounds any
route's error by charging each invocation a rate, averaged over inputs.
Both are the same charge, read at different times: before execution with
rates, or during execution with each invocation's own risk.

An expert *reports* its risk if, from its output on an input, it gives a
number `r` with `P(fail | everything observed) ≤ r`, where *fail* is a
failure in the sense of §31.1. A calibrated reader's `1 − max p` is such a
number when its probabilities are calibrated (§16); an exact expert, an
adapter or a requirement reports `0`.

## 33.2 Answering within δ

During execution, the *ledger* of an input sums the reported risks of the
invocations whose output the answer reads (§31.6), including those inside
packages, which run their own routes on the same ledger.

**Theorem 33.1 (per-input charge).** Under sound demands, if every relevant
invocation reports its risk, the probability that the answer is wrong,
given everything observed on the input, is at most the ledger's total.

*Proof.* Conditionally on the observations, a wrong answer has a relevant
failure (§31.6); the union bound over the relevant invocations gives at
most the sum of their failure probabilities, each at most its report. ∎

**Theorem 33.2 (selective answering on any route).** Answering exactly the
inputs whose ledger total is at most `δ` gives an error rate among the
answered inputs of at most `δ`.

*Proof.* Theorem 16.1 with the ledger total as the bound. ∎

An invocation that reports no risk leaves the input uncertified: a rate
averaged over inputs does not bound a conditional probability on this
input, so it cannot be mixed into the per-input sum. Such inputs are not
answered under a target.

The static bound of §31 remains the planner's estimate. The expected
ledger total over inputs is at least the expected number of relevant
failures, and when reports are exactly calibrated it equals the static
charge computed from the same experts' in-situ rates.
