import Mathlib.MeasureTheory.Integral.Lebesgue.Add
import Mathlib.MeasureTheory.Measure.Typeclasses.Probability

/-!
# Confidence-triggered refinement

A cheap expert answers when it is confident (event `C`); otherwise it asks the
kernel for a refined answer, served by a fallback (which may itself refine
further). With `W₁` the cheap expert's errors and `W₂` the fallback's, the
composite answers wrongly exactly on `(C ∩ W₁) ∪ (Cᶜ ∩ W₂)`.

Because the fallback can be any module, including another such cascade, the
two-stage results compose into arbitrarily deep refinement chains.
-/

open MeasureTheory

namespace NCA

variable {Ω : Type*} [MeasurableSpace Ω] {μ : Measure Ω} {C W₁ W₂ : Set Ω}

/-- The composite's error event. -/
def cascadeWrong (C W₁ W₂ : Set Ω) : Set Ω := (C ∩ W₁) ∪ (Cᶜ ∩ W₂)

/-- **Error identity.** The composite's error probability is exactly the
probability of a confident error plus that of a deferred error. -/
theorem cascade_error_eq (hC : MeasurableSet C) (hW₂ : MeasurableSet W₂) :
    μ (cascadeWrong C W₁ W₂) = μ (C ∩ W₁) + μ (Cᶜ ∩ W₂) :=
  measure_union (Set.disjoint_of_subset_left Set.inter_subset_left
    (Set.disjoint_of_subset_right Set.inter_subset_left disjoint_compl_right))
    (hC.compl.inter hW₂)

/-- **Refinement never hurts when confidence is selective.** If the cheap
expert errs on its confident inputs no more often than the fallback would,
the composite is at least as accurate as always using the fallback. -/
theorem cascade_le_fallback (hC : MeasurableSet C) (hW₂ : MeasurableSet W₂)
    (hsel : μ (C ∩ W₁) ≤ μ (C ∩ W₂)) : μ (cascadeWrong C W₁ W₂) ≤ μ W₂ := by
  rw [cascade_error_eq hC hW₂]
  calc μ (C ∩ W₁) + μ (Cᶜ ∩ W₂) ≤ μ (C ∩ W₂) + μ (Cᶜ ∩ W₂) := by gcongr
    _ = μ W₂ := by
      rw [Set.inter_comm C W₂, Set.inter_comm Cᶜ W₂, ← Set.sdiff_eq]
      exact measure_inter_add_sdiff W₂ hC

/-- The composite's cost: `κ₁` always, plus `κ₂` when deferring. -/
noncomputable def cascadeCost (κ₁ κ₂ : ENNReal) (C : Set Ω) : Ω → ENNReal :=
  fun ω => κ₁ + Cᶜ.indicator (fun _ => κ₂) ω

/-- **Expected cost.** Refinement costs the cheap expert plus the fallback's
cost weighted by the probability of deferring. -/
theorem cascade_expected_cost [IsProbabilityMeasure μ] (κ₁ κ₂ : ENNReal)
    (hC : MeasurableSet C) :
    ∫⁻ ω, cascadeCost κ₁ κ₂ C ω ∂μ = κ₁ + κ₂ * μ Cᶜ := by
  unfold cascadeCost
  rw [lintegral_add_left (f := fun _ => κ₁) measurable_const, lintegral_const, measure_univ,
    mul_one,
    lintegral_indicator_const hC.compl]

/-! ## Relevance gating

A request is worth resolving only if its result can change the final answer.
Let `R` be the event that the requester's output influences the answer: off
`R`, the answer is wrong after refinement exactly when it is wrong without it
(`E_r ∩ Rᶜ = E_u ∩ Rᶜ`). A gate `G` predicts relevance; the gated composite
refines only on `Cᶜ ∩ G`. -/

/-- Error event when refining on `D` (`E_u`: wrong unrefined, `E_r`: wrong refined). -/
def refinedWrong (D E_u E_r : Set Ω) : Set Ω := (Dᶜ ∩ E_u) ∪ (D ∩ E_r)

/-- **Gating changes the error by at most the relevant requests it skips.**
Gated refinement errs at most as often as ungated refinement plus the
probability of skipping a request that was in fact relevant. -/
theorem gated_error_le {G R E_u E_r : Set Ω} (hR : E_r ∩ Rᶜ = E_u ∩ Rᶜ) :
    μ (refinedWrong (Cᶜ ∩ G) E_u E_r) ≤
      μ (refinedWrong Cᶜ E_u E_r) + μ (Cᶜ ∩ Gᶜ ∩ R) := by
  refine (measure_mono ?_).trans (measure_union_le _ _)
  intro ω hω
  by_cases hr : ω ∈ R
  · by_cases hc : ω ∈ C
    · left
      rcases hω with ⟨hd, hu⟩ | ⟨hd, _⟩
      · exact Or.inl ⟨fun h => h hc, hu⟩
      · exact absurd hc hd.1
    · by_cases hg : ω ∈ G
      · left
        rcases hω with ⟨hd, _⟩ | ⟨_, he⟩
        · exact absurd ⟨hc, hg⟩ hd
        · exact Or.inr ⟨hc, he⟩
      · exact Or.inr ⟨⟨hc, hg⟩, hr⟩
  · left
    have hsame : ω ∈ E_r ↔ ω ∈ E_u := by
      constructor
      · intro h
        have : ω ∈ E_r ∩ Rᶜ := ⟨h, hr⟩
        rw [hR] at this
        exact this.1
      · intro h
        have : ω ∈ E_u ∩ Rᶜ := ⟨h, hr⟩
        rw [← hR] at this
        exact this.1
    have hwrong : ω ∈ E_u := by
      rcases hω with ⟨_, hu⟩ | ⟨_, he⟩
      · exact hu
      · exact hsame.mp he
    by_cases hc : ω ∈ C
    · exact Or.inl ⟨fun h => h hc, hwrong⟩
    · exact Or.inr ⟨hc, hsame.mpr hwrong⟩

/-- **Sound gates are free.** If the gate covers every relevant input
(`R ⊆ G`), gated refinement errs exactly as often as ungated refinement. -/
theorem gated_error_eq_of_sound {G R E_u E_r : Set Ω} (hR : E_r ∩ Rᶜ = E_u ∩ Rᶜ)
    (hsound : R ⊆ G) :
    μ (refinedWrong (Cᶜ ∩ G) E_u E_r) = μ (refinedWrong Cᶜ E_u E_r) := by
  apply le_antisymm
  · have h := gated_error_le (μ := μ) (C := C) (G := G) hR
    have hzero : Cᶜ ∩ Gᶜ ∩ R = ∅ :=
      Set.subset_empty_iff.mp fun ω ⟨⟨_, hg⟩, hr⟩ => hg (hsound hr)
    simpa [hzero] using h
  · apply measure_mono
    intro ω hω
    rcases hω with ⟨hd, hu'⟩ | ⟨hd, he⟩
    · exact Or.inl ⟨fun h => hd h.1, hu'⟩
    · by_cases hg : ω ∈ G
      · exact Or.inr ⟨⟨hd, hg⟩, he⟩
      · have hnr : ω ∉ R := fun h => hg (hsound h)
        have : ω ∈ E_r ∩ Rᶜ := ⟨he, hnr⟩
        rw [hR] at this
        exact Or.inl ⟨fun h => hg h.2, this.1⟩

/-- **Gated cost.** Gated refinement costs `κ₁ + κ₂ · P(Cᶜ ∩ G)`. -/
theorem gated_expected_cost [IsProbabilityMeasure μ] (κ₁ κ₂ : ENNReal) {G : Set Ω}
    (hC : MeasurableSet C) (hG : MeasurableSet G) :
    ∫⁻ ω, κ₁ + (Cᶜ ∩ G).indicator (fun _ => κ₂) ω ∂μ = κ₁ + κ₂ * μ (Cᶜ ∩ G) := by
  rw [lintegral_add_left (f := fun _ => κ₁) measurable_const, lintegral_const, measure_univ,
    mul_one, lintegral_indicator_const (hC.compl.inter hG)]

end NCA
