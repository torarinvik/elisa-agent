import NCA.Reliability.Reliability

/-!
# Reliability under distribution shift

A module's failure rate is a property of the module *and* the distribution of
inputs it receives. Inside a composition, that distribution is the pushforward
of the task distribution through the upstream modules, which generally differs
from the distribution the module was evaluated on in isolation.

A deterministic module with input space `X` fails on a set `B ⊆ X`. Its
*offline* failure rate is `ν₀ B` for a reference measure `ν₀`; its *in-situ*
failure rate is `(μ.map g) B`, where `g : Ω → X` is the upstream computation.
A `ShiftBound ν ν₀ δ` (one-sided total variation at most `δ`) bounds the gap.
-/

open MeasureTheory

namespace NCA

variable {X : Type*} [MeasurableSpace X]

/-- `ν` exceeds `ν₀` by at most `δ` on every measurable set. For probability
measures, `ShiftBound ν ν₀ δ` holds iff the total variation distance between
them is at most `δ`. -/
def ShiftBound (ν ν₀ : Measure X) (δ : ENNReal) : Prop :=
  ∀ s, MeasurableSet s → ν s ≤ ν₀ s + δ

theorem ShiftBound.refl (ν : Measure X) : ShiftBound ν ν 0 := fun _ _ => by simp

variable {Ω ι : Type*} [MeasurableSpace Ω] [Fintype ι] {μ : Measure Ω}

/-- **Shifted composition bound.** Each invocation `i` receives input
`g i ω` and fails on `B i`. If its offline failure rate is at most `ε i` and
its in-situ input distribution is within `δ i` of the offline one, the
composition fails with probability at most `∑ (ε i + δ i)`. -/
theorem composition_error_le_shifted
    {X : ι → Type*} [∀ i, MeasurableSpace (X i)]
    {g : ∀ i, Ω → X i} {B : ∀ i, Set (X i)} {ν₀ : ∀ i, Measure (X i)}
    {ε δ : ι → ENNReal} {correct : Set Ω}
    (hg : ∀ i, Measurable (g i)) (hB : ∀ i, MeasurableSet (B i))
    (hoffline : ∀ i, ν₀ i (B i) ≤ ε i)
    (hshift : ∀ i, ShiftBound (μ.map (g i)) (ν₀ i) (δ i))
    (hprop : (⋂ i, (g i ⁻¹' B i)ᶜ) ⊆ correct) :
    μ correctᶜ ≤ ∑ i, (ε i + δ i) := by
  refine composition_error_le_sum (fail := fun i => g i ⁻¹' B i) (fun i => ?_) hprop
  calc μ (g i ⁻¹' B i) = μ.map (g i) (B i) := (Measure.map_apply (hg i) (hB i)).symm
    _ ≤ ν₀ i (B i) + δ i := hshift i _ (hB i)
    _ ≤ ε i + δ i := by gcongr; exact hoffline i

/-- **The shift term is necessary.** A module that never fails offline can
fail always in situ: offline failure rates alone bound nothing. -/
theorem offline_rate_insufficient :
    ∃ (ν₀ ν : Measure Bool) (B : Set Bool), MeasurableSet B ∧
      IsProbabilityMeasure ν₀ ∧ IsProbabilityMeasure ν ∧ ν₀ B = 0 ∧ ν B = 1 := by
  refine ⟨Measure.dirac true, Measure.dirac false, {false}, measurableSet_singleton _,
    inferInstance, inferInstance, ?_, ?_⟩ <;> simp

/-- **Measured gaps lower-bound the shift.** Any valid shift bound is at least
the observed excess of in-situ over offline failure rate. -/
theorem shift_ge_gap {ν ν₀ : Measure X} {δ : ENNReal} {B : Set X}
    (h : ShiftBound ν ν₀ δ) (hB : MeasurableSet B) : ν B - ν₀ B ≤ δ :=
  tsub_le_iff_left.mpr (h B hB)

end NCA
