# 16. Knowing when to be unsure

**Problem.** A long expression is answered correctly only if every glyph is
read correctly, so with per-glyph error `ε` the answer error grows like
`1 − (1 − ε)^L`: about 47% at `L = 63` for `ε = 0.01`.
Errors cannot be corrected without redundancy, but they can be *located*:
calibrated confidences say which glyphs are doubtful, compute can be spent
there, and the system can decline to answer when doubt remains.

**Theory.** Each input carries an error bound
`b`, the sum of its glyphs' calibrated error probabilities `1 − max p`
(union bound, §4). Refining glyph `i` costs `κ i` and lowers the bound by
`β i`.

| Theorem | Statement |
|---|---|
| 16.1 | if the true error probability is at most `b` and only inputs with `b ≤ δ` are answered, the error rate among answered inputs is at most `δ` |
| 16.2 | for a price `λ` per unit of compute, refining exactly `{i : λ κ i ≤ β i}` minimizes bound plus priced compute over all refinement sets |
| 16.3 | if every item's risk is at least `ρ`, a bound of at most `δ` needs `n · ρ ≤ δ`: holding `δ` as inputs grow needs floors shrinking like `1 / n` |

Theorem 16.1 also applies when a bound exists only for some inputs: answer
only where the certificate is available and its bound is at most `δ`, and
require the error-bound premise only on those available inputs. An unavailable
certificate is not an accepted bound, even if an implementation uses infinity
as a sentinel and the requested threshold is also infinite.

So the efficient policy is local: refine a glyph when its expected bound
reduction pays for its cost, and sweep `λ` (equivalently the target `δ`) to
trade compute for reliability.

**Decision demand.** What of an input can change the consumer's *decision*,
not only its value, is a demand too. Readings need to enter the bound only
where decision-demanded. Agreement on decisions is coarser than agreement on
values, so this is demand-soundness for a coarser reader
. The fuser's operator input only
rescales digit entries by `q_none`, and a positive rescaling leaves the digit
argmax unchanged, so while `q_none > 0` digit decisions need the digit reading
alone and operator decisions the operator reading alone.

**Decision-relative risk.** A decision may range over only some of a
reading's classes: at an operator position the parser chooses among
operators, never "not an operator". With `C` the classes it ranges over, the
item's risk becomes the error probability of that restricted decision,
`1 − max_C p / Σ_C p`. When the most probable class lies in `C` this never
exceeds `1 − max p` (Theorem 16.4), so the bound only tightens.
Renormalizing the full output's calibrated probabilities does not calibrate
the restricted decision, which can be over-confident. Each rung therefore
fits a separate temperature per restricted decision, on the held-out inputs
whose label is among its classes.

**Practice queue.** Abstentions
and doubtful glyphs show where the library is weakest. In use, glyphs with
calibrated risk `r ≥ θ` are queued for a teacher's label.

| Theorem | Statement |
|---|---|
| 16.5 | each queued label is expected to correct at least `θ` errors |
| 16.6 | at most `θ` expected errors per unqueued glyph escape the queue |
| 16.7 | the queue holds all but `θ · n` of the expected errors among `n` glyphs |
| 16.8 | drawing glyphs with probability `∝ r` finds `Σ r² / Σ r ≥ Σ r / n` expected errors per label, never fewer than random labels |

[Theory index](../THEORY.md)
