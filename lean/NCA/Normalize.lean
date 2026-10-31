import NCA.Shift

/-!
# Normalization against distribution shift

A *normalizer* is a module `N : X → Y` placed before a recognizer, which is
then trained and evaluated on normalized inputs. A style shift is a map
`T : X → X` applied to reference inputs: the shifted distribution is
`ν₀.map T`. Normalization never increases a shift (data processing), removes
it completely when `N ∘ T = N`, and in general leaves at most the mass of the
inputs on which normalization fails to undo the style.
-/

open MeasureTheory

namespace NCA

variable {X Y : Type*} [MeasurableSpace X] [MeasurableSpace Y]

/-- **Contraction.** A measurable normalizer never increases a shift. -/
theorem ShiftBound.map {ν ν₀ : Measure X} {δ : ENNReal} {N : X → Y} (hN : Measurable N)
    (h : ShiftBound ν ν₀ δ) : ShiftBound (ν.map N) (ν₀.map N) δ := fun s hs => by
  rw [Measure.map_apply hN hs, Measure.map_apply hN hs]
  exact h _ (hN hs)

/-- **Partial invariance.** If normalization undoes the style on `G`
(`N (T x) = N x` for `x ∈ G`), the normalized shift is at most `ν₀ Gᶜ`. -/
theorem shift_le_of_invariant_on {ν₀ : Measure X} {N : X → Y} {T : X → X} {G : Set X}
    (hN : Measurable N) (hT : Measurable T) (hinv : ∀ x ∈ G, N (T x) = N x) :
    ShiftBound ((ν₀.map T).map N) (ν₀.map N) (ν₀ Gᶜ) := fun s hs => by
  rw [Measure.map_map hN hT, Measure.map_apply (hN.comp hT) hs, Measure.map_apply hN hs]
  calc ν₀ ((N ∘ T) ⁻¹' s) ≤ ν₀ (N ⁻¹' s ∪ Gᶜ) := by
        refine measure_mono fun x hx => ?_
        by_cases hx' : x ∈ G
        · exact Or.inl (by simpa [Set.mem_preimage, hinv x hx'] using hx)
        · exact Or.inr hx'
    _ ≤ ν₀ (N ⁻¹' s) + ν₀ Gᶜ := measure_union_le _ _

/-- **Invariance.** A normalizer that undoes the style everywhere removes the
shift. -/
theorem shift_zero_of_invariant {ν₀ : Measure X} {N : X → Y} {T : X → X}
    (hN : Measurable N) (hT : Measurable T) (hinv : ∀ x, N (T x) = N x) :
    ShiftBound ((ν₀.map T).map N) (ν₀.map N) 0 := by
  simpa using shift_le_of_invariant_on (G := Set.univ) (ν₀ := ν₀) hN hT fun x _ => hinv x

end NCA
