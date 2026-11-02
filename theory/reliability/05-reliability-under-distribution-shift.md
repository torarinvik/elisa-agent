# 5. Reliability under distribution shift

A deterministic module with input space `X` fails on a set `B ⊆ X`. Its
failure rate depends on the input distribution: offline it is `ν₀(B)` for the
distribution it was evaluated on; inside a composition it is `(g_*μ)(B)`,
where `g : Ω → X` is the upstream computation feeding it.

**Definition (`ShiftBound ν ν₀ δ`).** `ν(s) ≤ ν₀(s) + δ` for every measurable
`s`. For probability measures this is equivalent to total variation distance
at most `δ`.

**Theorem 5.1 (shifted composition bound).** If
invocation `i` receives `gᵢ(ω)`, fails on `Bᵢ`, has offline failure rate at
most `εᵢ`, and `ShiftBound (gᵢ)_*μ ν₀ᵢ δᵢ`, then under the propagation
hypothesis `μ(correctᶜ) ≤ Σᵢ (εᵢ + δᵢ)`.

**Theorem 5.2.** There are probability measures and
a failure set with offline failure rate 0 and in-situ failure rate 1. Offline
rates alone bound nothing; the shift term cannot be dropped.

**Theorem 5.3.** Every valid shift bound satisfies
`δ ≥ ν(B) − ν₀(B)`. The measured excess of in-situ over offline failure rate is
therefore a lower bound on the distribution shift the composition induces,
and can be measured per module.

Design consequence: an upstream module's output convention is part of the
downstream module's contract. A segmenter that centers crops differently from
the recognizer's training data is type-correct but induces a shift `δ` that
the composition pays for in full.

[Theory index](../THEORY.md)
