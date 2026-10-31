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

end NCA
