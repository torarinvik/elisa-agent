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

For exact real charges, an accumulator that begins at zero and replaces each
addition by any value at least as large as the exact sum of its operands is
an upper bound on the total, by induction over the charges. This statement
does not establish that a particular floating-point implementation satisfies
the per-addition premise or that the charges themselves bound real errors.

In exact arithmetic, positive probability mass outside the chosen group
gives strictly positive risk. When ordinary softmax arithmetic underflows to
zero despite finite alternative logits, the implementation recomputes the
alternative mass in log space and returns the smallest positive binary64
value if the result is still unrepresentable. This avoids reporting zero for
a finite alternative; it is not a proof that all computed risks are rounded
upward or are calibrated error bounds.

Expert probabilities are converted to binary64 before taking logarithms.
For finite nonnegative inputs, zero is replaced by the smallest positive
binary64 value so temperature fitting has finite log inputs; positive inputs
are not raised to an arbitrary larger floor, assuming gradual underflow. This
is numerical smoothing, not evidence that a zero-probability prediction has a
well-calibrated error rate. Negative outputs and all-zero vectors are invalid
probability inputs and are rejected, as are text, complex-valued, masked,
non-finite, empty, and non-vector outputs. An exact sum of one is not required: finite nonnegative weights with
positive total mass are normalized by the subsequent softmax. This validation
checks the representation, not whether the expert is statistically calibrated.
Distinct binary64 weights can round to the same binary64 logarithm, so the
log representation may lose their original ordering. CPU native and fallback
paths use the platform scalar logarithm; other devices can round differently.
Once two encoded values coincide, no deterministic decision using only those
encodings can distinguish their two possible original orders. Preserving
decisions for arbitrary restricted class groups therefore requires retaining
the original ordering information, or deciding from the original weights,
through the consumer interface. Changing logarithm implementations alone
cannot recover distinctions already lost to rounding.
`Rung.observe_ranked` now exposes a log tensor together with an immutable
binary64 snapshot of the original weights; its `top` operation uses those
weights for any supplied class subset. For positive temperature, the exact
power transform is strictly increasing, and division by a common positive
normalizer preserves its order. This is a building block for carrying
ordering information. Temperature scaling requires a finite positive
temperature: a negative value reverses logit order, zero is undefined, and
an infinite value does not retain the finite-temperature ordering guarantee.
In exact real arithmetic, dividing logits by a positive temperature preserves
their order and dividing by a negative temperature reverses it.
The scaled difference `(a - b) / T` equals `a / T - b / T` in real
arithmetic. With finite floating-point logits of opposite sign, the
subtraction can overflow even when the scaled difference is representable.
For a temperature greater than one, the implementation rescales the operands
separately when that overflow occurs; ordinary cases retain subtraction first
to avoid unnecessary cancellation. This does not make floating-point
arithmetic exact. A finite temperature may also be outside the range of the
logit tensor's dtype; the reference path uses binary64 intermediates in that
case so converting the temperature cannot silently produce zero or infinity.
`Rung.risk` accepts a ranked observation and charges
the group containing the original highest-weight class; its tensor-only form
selects from the numerical reading, including its tie behavior. In unequal groups, a tiny difference in the leading
weights can change the group risk substantially because other classes add
mass to one group. Numerical probabilities returned by `reading` can still
tie: a consumer using ranked risk must select with the same retained ordering.
The selective controller passes ranked observations to consumers or fusers
that opt in to preserving this choice; other consumers use numerical readings.

For independent known reductions, the priced objective has a local threshold
rule: refine when the reduction pays for its cost. Sweeping `λ` explores a
compute–risk tradeoff; it need not solve every hard-target problem, and the
implemented largest-charge heuristic does not know the reductions (§25.1).

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
The denominator must be positive: a restriction containing only zero-mass
classes has no conditional distribution. Individual classes may have zero
mass when the restriction as a whole has positive mass. The implementation
rejects an undefined restriction and invalid log weights rather than returning
NaNs; this is a representation check, not a calibration guarantee.
For finite nonnegative weights, multiplying every weight by the same positive
factor leaves the outside-mass ratio unchanged. If their sum overflows, the
implementation uses this identity to rescale; when the outside sum remains
finite it is accumulated before rescaling so individually tiny terms can
still contribute. Floating-point rounding remains possible.
Renormalizing the full output's calibrated probabilities does not calibrate
the restricted decision, which can be over-confident. Each rung therefore
fits a separate temperature per restricted decision, on the held-out inputs
whose label is among its classes. If a calibrated rung has no matching labels,
a decision with multiple entries has no fitted restricted temperature. Direct
queries report the missing calibration; refinement treats the account as
unavailable, can try higher rungs, and abstains if no usable account is found.
A later observation can also change a dynamic certificate so that the
unsupported decision is no longer needed, even if its own rung is fixed.
A decision with only one entry has zero conditional decision risk
regardless of temperature. An entirely uncalibrated rung's default temperature
is a numerical convention, not evidence of calibration. Calibration requires
one in-range integer label per held-out value. Labels and the sequence of
value references are snapshotted before expert invocation; individual values
are not deep-copied. The observations and label snapshot replace the previous
calibration only after fitting succeeds.

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
