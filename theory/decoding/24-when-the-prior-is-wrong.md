# 24. When the prior is wrong

## 24.1 The question

The decoder of §21 is exact under premise (P): a prior over arity
sequences that is the readers' per-word prior restricted to sequences that
parse. The formulas of §18.1 come from a different generator, complete
alternating trees. This section asks how wrong the
decoded formula's risk `R` can then be, what can be guaranteed with no
prior at all, and what the premise tests of §21.8 should show.

Readings are the same under both priors; only the prior differs. Let `π*`
be the generator's prior over arity sequences of `m` words, and
`π_P(a) ∝ Πₖ πₖ(aₖ)` the prior of (P), with `πₖ` the per-word prior the
calibrated readings carry. Since the readings' likelihoods agree, the true
posterior weight of a sequence `a` is the model's weight `w(a) = Πₖ qₖ(aₖ)`
times the **prior ratio**

> `ρ(a) = π*(a) / π_P(a)` (up to a constant, which cancels).

The decoded sequence `â` is a single sequence, so only two numbers matter:

- `C = max_{a ≠ â} ρ(a)`, the largest ratio at a competitor;
- `c = ρ(â)`, the ratio at the decoded sequence.

Let `Λ = C / c`, and `R*` be the true posterior risk of `â`.

## 24.2 Bounded ratio

| Theorem | Statement |
|---|---|
| 24.1 | reweighting nonnegative weights by `ρ ≤ C` on an event and `ρ ≥ c` off it multiplies the event's odds by at most `C / c` |
| 24.2 | `R* ≤ Λ R / (1 − R + Λ R)` |
| 24.3 | for `Λ ≥ 1`, `R* ≤ Λ R` |
| 24.4 | if `ρ(â) ≥ ρ(a)` for every competitor (`Λ ≤ 1`), `R* ≤ R` |

The bound is in odds: the true odds of an error are at most `Λ` times the
model's. For small `R` it is close to `Λ R`. Exchanging the roles of the two
priors (Theorem 24.1 applied to the inverse ratio) gives a lower bound of
the same form, with the *smallest* ratio at a competitor in place of the
largest. Together they bracket how far the model's risk can be from the truth.

Only the ratio at competitors *relative to the decoded sequence* enters.
A prior that differs wildly from (P) does no harm where it treats `â` and
its competitors alike. A prior that removes mass from competitors, and not
from `â`, makes the model's risk conservative.

## 24.3 The generator of complete alternating trees

A complete alternating tree of depth `d` has `2^d − 1` connectives and `2^d`
leaves, each negated with probability 1/4. With `m` words, the number of
`not`s is fixed, `m − 2^{d+1} + 1`. So every arity sequence the generator
produces at that length has the same **histogram** of arities, and its
probability depends only on which leaves are negated:
`(1/4)^{nots} (3/4)^{2^d − nots}`, the same for all of them. Let `S_m` be
this support.

`π_P` is a product of one per-word prior, the same at every position,
because one reader reads every word. So it too depends only on the
histogram, and is constant on `S_m`. Hence

> `ρ = κ` on `S_m`, `ρ = 0` off it.

Two cases follow, and nothing in between:

1. **The decoded sequence is a complete tree** (`â ∈ S_m`). Then
   `ρ(â) = κ ≥ ρ(a)` for every competitor, so `R* ≤ R`
   (Theorem 24.4). The true risk is `R` restricted to the support:
   competitors the generator never produces drop out.
2. **The decoded sequence is not a complete tree** (`â ∉ S_m`). Then
   `ρ(â) = 0`, `Λ = ∞`, and the bound says nothing. Indeed the truth lies in
   `S_m` and differs from `â`, so `R* = 1`: the decoded formula is certainly
   wrong, whatever `R` says.

So for structured generators `Λ` is unbounded in general. Their support is
a thin subset of `L_m`, and the decoder, knowing only the format, can land
outside it. In that case the bound of §24.2 is vacuous. The model's risk is
then a claim that only data can check: the calibration test of §21.8 or the
audit of risk control (§24.5).

## 24.4 No prior, no guarantee

**Theorem 24.5.** Put weight 1 on a competitor of positive
weight `w'`, weight `t` on the decoded sequence (weight `ŵ`), and 0
elsewhere. The true risk is `w' / (w' + t ŵ) ≥ 1 − t ŵ / w'`, which tends to
1 as `t → 0`.

Every such prior is supported on `L_m`, so the format alone guarantees
nothing about a corrected answer. Correction answers formulas whose
readings do not parse because it assumes a prior. The coverage it gains is
paid for by that assumption.

The accounts differ in what they assume about the joint distribution of
word errors given the readings:

| account | assumes | checked by |
|---|---|---|
| certificate (§18) | each word's risk calibrated | per-word calibration on held-out words (§16) |
| detection, Markov (§19) | each word's arity risk calibrated given the readings | the same, approximately |
| detection, pairs (§19) | the above, and failures at different words not positively correlated | the pairs test (§21.8) |
| correction (§21) | the whole joint posterior, (P) | the calibration test of `R` (§21.8) |

Down the table, the premises are strictly stronger, and coverage rises with
them. Per-word calibration is fitted on held-out formulas from the
generator, so it is checked by data in distribution. (P) is not fitted to
anything.

## 24.5 Risk control certifies any account

Risk control (§17) never uses the account's premises. It treats each
candidate threshold `δ / λ` as a policy, answers audit formulas drawn from
the deployment generator, and tests each policy's error rate among answered
formulas in a fixed order (Theorem 17.5). With probability at least
`1 − α` over the audit, every certified policy's error rate among answered
formulas is at most `δ`, whether or not (P) holds. The account decides
*which* formulas a policy answers, and so how much it covers. Only the
audit decides whether the guarantee holds.

The price is audit labels. A policy with no errors on `n` answered audit
formulas is certified when the Clopper–Pearson bound `1 − α^{1/n}` is at
most `δ`, that is `n ≥ ln(1/α) / −ln(1 − δ)`. For `α = 0.1` that is 11
answered formulas at `δ = 0.2`, 45 at `δ = 0.05` and 230 at `δ = 0.01`.

The distribution-level guarantee does not need the prior, only labeled
formulas from where the system is used. The per-formula bound `R` is a
model's claim, and §24.3 shows when it fails.

**A better prior is an expert.** Theorems 21.4–21.6
hold for any deterministic automaton and any position-wise weights. A prior
given by a weighted finite automaton over arities, for example one fitted
to training formulas, enters the same dynamic program through a product
automaton. Its cost grows with the number of states. Such a prior would
then be declared by an expert rather than written into the evaluator, so
the evaluator stays generic over generators.

[Theory index](../THEORY.md)
