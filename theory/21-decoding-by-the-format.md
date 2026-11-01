# 21. Decoding by the format

## 21.1 From detection to correction

§19 used the prefix format to **detect** arity errors: a reading that does
not parse is refused, and the controller climbs or abstains. Once the summed
arity risk is near 1, most readings do not parse at any rung, and those
formulas cannot be answered at any cost.

A refused reading is still evidence. Its words' arity distributions say
which arities are likely, and the format says which arity sequences are
possible. The posterior over *possible* sequences picks out the most
probable formula. An error-detecting code used this way corrects errors.

## 21.2 The model

For each word `k`, let `qₖ(a)` be the calibrated probability that its arity
is `a ∈ {0, 1, 2}`: the arity decision's grouped reading (§18.3), under that
decision's temperature. Let `L_m` be the set of arity sequences of formulas
with `m` words.

**Premise (P).** Given the readings, the posterior probability of an arity
sequence `a` is

> `π(a) = Πₖ qₖ(aₖ) · 1[a ∈ L_m] / Z`,  `Z = Σ_{a ∈ L_m} Πₖ qₖ(aₖ)`.

(P) holds exactly when two things are true:

1. words are corrupted and read independently given the truth (the channel
   corrupts each word separately, and each reader sees one word);
2. the prior over arity sequences is the readers' own per-word prior,
   restricted to the sequences that parse.

The second part is a modeling choice. The evaluator knows the format, but
not the process that generated the formulas. Complete alternating trees are
far more constrained than (P) assumes; for one thing, the word count
determines the tree's shape. Using that would hardcode the task's generator
into the expert, against the requirement that experts be generic. (P) uses
only the format, the least informative prior consistent with it. Whether
the resulting risks are calibrated is an empirical question (§21.8), and
risk control (§17) remains the backstop.

## 21.3 The format is a regular language

**Definition** (`await`). The counter automaton
of prefix notation has states `some n`, meaning `n` subformulas are still
awaited, and a dead state `none`. A word of arity `a` read while `n + 1`
subformulas are awaited leaves `n + a` awaited. Reading anything when none
are awaited kills the run. A sequence is accepted when, started from one
awaited subformula, it ends with none awaited.

| Theorem | Statement |
|---|---|
| 21.1 | reading a formula's arity sequence consumes exactly one awaited subformula |
| 21.2 | every formula's arity sequence is accepted |
| 21.3 | a sequence of arities at most 2 is accepted from `n` awaited exactly when it is the concatenated arity sequence of `n` formulas |

So `L_m` is exactly the set of length-`m` words the automaton accepts. The
decoded sequence is therefore always a formula, and every formula is a
candidate.

## 21.4 Decoding by dynamic programming

For any deterministic automaton and position-wise weights `wₖ`, define the
score of a sequence as its weight product if accepted, else 0.

| Theorem | Statement |
|---|---|
| 21.4 | the sum-product recursion over states equals the total score of all sequences |
| 21.5 | with nonnegative weights, no sequence scores more than the max-product recursion |
| 21.6 | unless the maximum is 0, some sequence attains it; backtracking the maximizing choices finds it |

With `wₖ = qₖ`:

- `dpSum` from state `some 1` is `Z`;
- `dpMax` is `Πₖ qₖ(âₖ)` for the most probable parseable arity sequence
  `â`, the **decoded** sequence.

For equal-scoring candidates entering the same state, choose the smaller
alphabet index. This preserves the maximum and makes the selected predecessor
independent of the order in which those tied candidates are visited. It does
not remove differences caused by floating-point scores rounding differently.
For a nonnegative arity `a`, a transition from state `n ≥ 1` reaches
`n − 1 + a ≥ a`. Thus if `a` already exceeds the next row's largest viable
state, the transition can be discarded before calculating the sum.
If every arity is at most `A`, a reachable counter after `k` words is at most
`1 + k · max(A − 1, 0)`. Intersecting this reachability bound with the
completion bound `m − k` gives the state range needed by the exact decoder;
the smaller `k + 1` bound applies only when arities are at most two.

**Marginals.** Forward sums `F_k(n)` and backward sums `B_k(n)` over the
same states give each word's posterior arity distribution:

> `π(aₖ = a) = Σₙ F_k(n + 1) · qₖ(a) · B_{k+1}(n + a) / Z`.

Each is the sum-product theorem applied to a prefix and a suffix.

**Cost.** At position `k`, at most `min(k + 1, m − k)` subformulas can be
awaited and still be completed, because every awaited subformula needs at
least one more word. That leaves about `m² / 4` live states, with three
arities each. Forward, backward and max passes then take about `2.25 m²`
multiply-adds.

| depth | words | decoding ops | bottom-rung reading | top-rung reading |
|---:|---:|---:|---:|---:|
| 6 | 143 | 46k | 93k | 14.9M |
| 8 | 575 | 744k | 374k | 59.8M |

Decoding costs at most about 1% of a top-rung pass. It is computed once per
refinement step, in log space.

When the sequence of each word's most probable arity parses, it is `â`: it
maximizes the unconstrained product and is feasible. So decoding departs
from per-word decisions only where those decisions do not parse.

## 21.5 The risk of a decoded formula

Under (P), the decoded arity sequence is wrong with posterior probability
exactly

> `R = 1 − Πₖ qₖ(âₖ) / Z`.

**Theorem 21.7.** Since `Z ≤ 1`,
`R ≤ 1 − Πₖ qₖ(âₖ) ≤ Σₖ (1 − qₖ(âₖ))`. Correction is never worse than the
union bound over the decoded arities.

Detection's bounds charged the probability that two or more arity
decisions fail, whether or not the failures leave a parseable sequence.
`R` counts only failures that do, and it conditions on the truth being a
formula, which §19.4 had to set aside.

**Identities.** Given the arity sequence, (P) makes the words' identities
independent. Word `k`'s identity is distributed as its reading restricted
to the group `âₖ`. So each word is decoded as the most probable class within
its decoded arity group. That pairs every word's identity with its own
arity, which resolves the objection of §18.3 to choosing groups by mass.
With `E` the words the decoded formula's least-risk certificate evaluates
(§19.5), and `rₖ` the restricted risks, the argument of Theorem 19.3
gives

> `P(wrong | readings) ≤ R + Σ_{k ∈ E} rₖ`.

Numerically, calibrated group log-masses can be carried directly from logits,
so a finite group mass need not be rounded to zero before decoding. When only
probabilities are provided, representable positive masses are logged without
an arbitrary floor and exact zeros map to `−∞`. A row with no mass cannot
support a posterior account. These paths do not recover mass already rounded
to zero by an upstream expert and do not provide an outward-rounding guarantee.
A finite alternative whose probability is below binary64 range receives the
smallest positive value; if all allocated shares underflow, one retains that
value. Other rounding errors are not covered by this safeguard.
The selected and alternative path masses can be summed separately for any
finite nonnegative-arity alphabet. Multiplying every path weight by the same
positive factor leaves their normalized ratio unchanged; carrying the two
parts separately avoids losing a small alternative when a common log-weight
shift makes the rounded total equal the selected weight.
If adding two finite log weights overflows the representable log range, the
general-arity partition reports the calculation as unavailable instead of
interpreting the resulting infinity as a zero-weight path. This check does
not bound ordinary finite rounding errors.

## 21.6 Charges for refinement

Let `μₖ = 1 − π(aₖ = âₖ)` be word `k`'s posterior arity risk after decoding.
`μₖ` uses every other word's evidence through the format. A word whose
reading is uncertain can still have a small `μₖ` when only one arity fits
its neighbours.

**Errors come in pairs.** The truth and `â` are both formulas of `m` words,
so they differ in no position or in at least two (Theorem 19.2).
Applied to the posterior measure, Markov's inequality on the number of
differing positions (Theorem 19.5) gives

> `R ≤ ½ Σₖ μₖ`.

The account charges word `k`

> `R · μₖ / Σⱼ μⱼ`, plus `rₖ` if `k ∈ E`.

The charges sum to the bound of §21.5. Refinement climbs the word with the
largest charge, the word most likely misread *given the format*, not merely
the least confident reading.

## 21.7 Scaling

For words with arity risk `ρ` each and `S = mρ`:

- **detection:** abstains on every unparseable reading, whose probability
  approaches 1 as `S` grows past 1;
- **correction:** answers every reading, and charges `R`.

`R` is small when the competitors of `â` are improbable. The nearest
competitors differ in two positions, with opposite net arity change, so `R`
behaves like `e₂` restricted to cancelling pairs, divided by `Z`. Correction
therefore removes the hard limit `S < 1`, beyond which detection answers
nothing. What remains is the slower growth of the posterior weight of
cancelling pairs.

## 21.8 Testing the premises

Two premises are now in use. Each yields a prediction about counts over
independent formulas, which can be tested on held-out data.

**Calibration of `R` (premise P).** Over `N` formulas, let `O` be the number
whose decoded arity sequence is wrong. Under (P) with calibrated readings,
`O` is a sum of independent Bernoulli(`R_f`) variables, so
`E[O] = Σ_f R_f`. The test compares `O` with the Poisson-binomial
distribution of that sum (two-sided), overall and in bins of `R`. It runs at
the bottom rung, where errors are frequent enough to count, at depths 4 to
8 and under the noise shift.

The count distribution starts with mass 1 at zero. Adding an independent
Bernoulli event of probability `p` changes mass `q(k)` to
`(1-p)q(k) + p q(k-1)`, taking `q(-1) = 0`. Updating counts in descending
order retains the previous masses needed for this recurrence.
An event with probability zero leaves the distribution unchanged and does
not increase the maximum attainable count. An event with probability one
shifts the distribution by one; several such shifts can be combined.
The sum is always between zero and the number of events, so its lower tail
below zero and upper tail above that number are zero.
Before this recurrence, reduced-precision inputs are promoted so that forming
`1-p` does not round the complement in their original precision. The recurrence
still uses floating-point arithmetic and is not an outward-rounded certificate.
Finite tails are bounded above by one, and the two certain boundary tails
are returned as exactly one; undefined inputs continue to propagate NaNs.
For an excess p-value, an upper bound is computed separately. Either count
failures up to `N-observed`, or track counts below the observed threshold and
the upper tail itself. In the latter recurrence, a new event adds its success
probability times the previous mass immediately below the threshold. Use upper
bounds for each event's success and failure probabilities, and round each
nonzero product and sum upward. Monotonicity of the nonnegative recurrences
preserves the bound. This implementation assumes
IEEE 754 binary64 operations rounded to nearest, gradual underflow, and a
correctly rounded `nextafter`; the Lean recurrence proof is over exact reals.
Events whose success and failure bounds establish probability zero or one can
be removed first; each certain success reduces the threshold by one.
When displayed as a decimal inequality, the bound is rounded upward again at
the requested number of significant digits.

**The pairs premise of §19.** Let `O₂` be the number of formulas whose
per-word reading has at least two arity failures. If failures are not
positively correlated, `E[O₂] ≤ Σ_f e₂(f)`. A one-sided Poisson-binomial
test rejects the premise if `O₂` is significantly larger. A direct check:
over pairs of words, the observed rate of joint arity failures against the
product of the marginal rates, for adjacent and for distant pairs
separately.
The distant-pair diagnostic sums products at the requested separation
directly, avoiding subtraction of nearly equal pair totals. Its ratio is
undefined when the expected pair count is zero and is reported as unavailable.
The p-value uses an upper-rounded prefix accumulation of pair products,
capped at one for each formula. The all-pairs diagnostic also sums products
directly: the equivalent subtraction formula `(S² − Σρᵢ²)/2` can lose small
pair risks to cancellation.

Unlike the absence of observed errors, these tests can fail.

## 21.9 What correction cannot do: hard style

In the arithmetic task, the parser fixes the kind of every position:
digits at even positions, operators at odd ones (§14). A misread digit is
another digit, and a misread operator another operator. Either way, the
reading still parses. The format has no redundancy against such errors,
so neither detection nor correction has anything to work with.

Of the remaining hard-style errors:

- **Ambiguity between operators** (`+` against `×` under rotation) lies
  inside a decision the format leaves free. Its Bayes risk is
  a floor: no reader, however strong, certifies such a glyph below it.
- **Erased digits**, when the segmenter misses them, change the
  length's parity. Such readings do not parse and are already detected.
  When an erased digit is segmented but misread, it is an ordinary digit
  error.

For hard style, the efficient policy is to recognize early that a glyph's
risk cannot reach the target and abstain, rather than climb (§22).

[Theory index](../THEORY.md)
