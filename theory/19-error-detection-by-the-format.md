# 19. Error detection by the format

## 19.1 The observation

The certificate bound of §18 charges its arity term `Σ ρ_shape` at every
word, so that term grows linearly with the formula and limits depth. It
overcharges: it is a union bound that treats
every arity error as silent. But the format is redundant. A prefix formula's
arity sequence is constrained, the reading is answered only if it parses,
and the truth parses too. Errors that break the constraint are *detected*
(the controller climbs or abstains). Only errors that preserve it can make
an answer wrong.

## 19.2 Single errors are detected

**Theorem 19.1.** Every formula's
preorder arity sequence sums to one less than its length:
`Σ_k (a_k − 1) = −1`.

**Theorem 19.2.** Two formulas with the same number of
words whose arity sequences agree everywhere except possibly at one
position have the same arity sequence.

*Proof.* Equal lengths and Theorem 19.1 give equal sums. Lists of equal length
and equal sum agreeing outside one position agree there too.

The premise is that word boundaries are known, so the reading and the truth
have the same number of words. The channel never corrupts spaces. Then, given
that the reading parses, the set of words whose arity is misread has size 0
or at least 2.

## 19.3 What a wrong answer requires

Let the reading `r` parse, let `t` be the truth, and let `E` be the words the
reading's certificate evaluates. Write `A_k` for "word `k`'s arity is
misread" and `W_k` for "word `k` is misread but its arity is right".

- If no arity is misread, the trees align node by node (Theorem 18.6). A
  wrong answer then needs a disagreement on an evaluated node (Theorem 18.3),
  that is, some `W_k` with `k ∈ E`.
- If some arity is misread, at least two are (§19.2).

Hence

> `wrong ⊆ (⋃_{k ∈ E} W_k) ∪ {at least two A_k}`

and (Theorem 19.3)

> `P(wrong | r) ≤ Σ_{k ∈ E} P(W_k | r) + P(at least two A_k | r)`.

**Evaluated words.** `P(W_k)` is the probability that the true word lies in
the read word's arity group `g` but differs from it, `p(g) − p(r_k)`. This is
at most the risk `1 − p(r_k) / p(g)` of the decision restricted to `g`
(Theorem 19.4), which §16 already calibrates. For `not`, alone in
its group, it is 0.

**Arity.** What remains is the probability of at least two arity failures
among all words.

## 19.4 Two bounds on two failures

Write `ρ_k` for word `k`'s arity risk and `S = Σ_k ρ_k`.

**Without further premises** (Theorem 19.5). The number of failures
`N = Σ_k 1[A_k]` has mean `S`. By Markov's inequality,
`P(N ≥ 2) ≤ S / 2`. Detection halves the arity term, using nothing but the
format.

**Without positive correlation** (Theorem 19.6). If failures at two
different words are never positively correlated given the readings,
`P(A_i ∩ A_j | r) ≤ ρ_i ρ_j`, then

> `P(N ≥ 2 | r) ≤ e₂(ρ) = Σ_{i<j} ρ_i ρ_j ≤ S² / 2`,

quadratically small when `S` is small. The premise is plausible because
each word is corrupted and read independently. It is not automatic: the
truth is a formula, and conditioning on that couples words (it is what
rules out single errors). So it is a premise to test, not a theorem. If it
fails in use, the audit of §17 still certifies a policy honestly. Both
bounds are valid under the premise, so the controller charges
`min(S/2, e₂)`.

A sharper bound would also use the sign of the errors: undetected errors
must cancel in `Σ (a − 1)`, and a dynamic program over the net arity change
computes that probability under independence. Since `e₂` is already
quadratic, this is not pursued.

## 19.5 Choosing the certificate

With detection, the arity charge covers all words whichever certificate is
chosen. The least-risk certificate therefore minimizes the evaluated words'
within-group risks alone: `bestCert` with `w_full` the restricted risk and
`w_shape = 0`.

## 19.6 Risk accounts

The bound is no longer a sum of per-item decision risks: `e₂` is a product
over pairs. The generic interface therefore moves one step:

- A consumer's certificate returns each item's **charge**, and the bound is
  the sum of charges.
- `refine` climbs the open item with the largest charge.
- Validity of the account is the consumer's theorem.

| account | charge of item `k` |
|---|---|
| static | risk of its fixed decision (as before) |
| certificate (§18) | risk of the decision it serves |
| detection, Markov | `ρ_k / 2`, plus its restricted risk if evaluated |
| detection, pairs | `ρ_k (S − ρ_k) / 2` (these sum to `e₂`), plus its restricted risk if evaluated |

For an ordered sequence, `S − ρ_k` is exactly the sum of the risks before
and after `k`. Prefix and suffix sums evaluate all such shares in linear
time without subtracting nearly equal floating-point values. If the two
partial sums bound their exact values from above and `ρ_k ≥ 0`, replacing
them by those bounds cannot lower the corresponding exact pair share.

## 19.7 Scaling

Over `m` words with arity risk `ρ` each, the arity term is

- `m ρ` without detection,
- `m ρ / 2` with Markov,
- about `(m ρ)² / 2` with pairs.

Under a target `δ` the length limit on that term moves from `m ≲ δ / ρ` to
`m ≲ √(2δ) / ρ`. For `δ = 0.2` and `ρ = 10⁻³` that is 632 words instead of
200.

[Theory index](../THEORY.md)
