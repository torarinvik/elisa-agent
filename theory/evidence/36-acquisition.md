# 36. Acquiring experts

## 36.1 Where to acquire

Audits (§35) and ledgers (§33) say where a route falls short. Summed over
a batch, a ledger's entries give each expert's share of the charged risk;
an expert with a large share, or one an audit refuted and recalibration
left uninformative, is where a better expert lowers the route's risk
most, by Theorem 31.3. *Acquisition* builds a challenger for that
expert's contract and lets the evidence decide between them.

## 36.2 Honest promotion of a trained challenger

The labeled invocations an audit collects are split, before any training,
into a training part `T` and an evaluation part `E`. A trainer, supplied
by the domain and arbitrary otherwise, maps `T` to a challenger with the
incumbent's contract. Both experts are then evaluated on `E`, and the
challenger is promoted by the paired sign test of §30.

**Theorem 36.1 (split promotion).** If `T` and `E` are independent, and
the test rejects with probability at most `α` for every fixed challenger
no better than the incumbent, then the probability of promoting a trained
challenger no better than the incumbent is at most `α`.

*Proof.* The challenger is a function of `T` alone. Conditionally on
`T`, it is fixed and `E` keeps its distribution, so a false promotion has
conditional probability at most `α`; averaging over `T` keeps the bound. ∎

The theorem fails if the trainer sees `E`, for instance by selecting
among training runs by their score on it, which is the overfitting the
split exists to prevent.

A promoted challenger reports risk only once it is calibrated; it is
calibrated and audited on `E` as in §35.2, which the sign test, not
depending on reports, leaves valid. Its calibration and promotion hold on
the distribution the audit sampled, so acquisition answers a shift
exactly as far as the audit's inputs represent it.

## 36.3 Proposing decompositions and interfaces

A proposer uses only `T` to return a finite family of experts with the
incumbent's external contract. Each expert may introduce new intermediate
constructor objects and an arbitrary internal composition. These declarations
are hypotheses about useful representations, not proofs of their meaning.
Freeze the whole family before evaluating any proposal on `E`.

**Theorem 36.2 (finite proposal selection).** Conditional on `T`, suppose
there are `k > 0` proposals and every no-better proposal's paired test has
false acceptance probability at most `α/k`. Then the probability of selecting
any no-better proposal is at most `α`. Independence between proposals is
unnecessary: selection implies that at least one proposal passed, so the union
bound applies. Averaging over independent `T` gives the unconditional bound
as in Theorem 36.1. With no proposals, nothing is selected.

The proposer must not select, retrain, or add proposals after seeing `E`.
Repeated adaptive searches need their own budget accounting. Shallow sequence
snapshots do not isolate mutable sample objects. This mechanism evaluates
proposed interfaces; it does not itself invent representations or prove transfer.
