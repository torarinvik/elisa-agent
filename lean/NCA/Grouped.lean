import Mathlib.Algebra.Order.BigOperators.Group.Finset
import Mathlib.Data.Real.Basic

/-!
# Calibration by groups

Calibration within each group transfers to any mixture of the groups
(`grouped_calibrated`): with nonnegative group proportions, expected
failures within each group at most the expected report within it give
expected failures at most the expected report overall.
-/

open Finset

namespace NCA

variable {G : Type*} [Fintype G]

/-- **Groups transfer across mixtures** (Theorem 37.1). -/
theorem grouped_calibrated (w failures report : G → ℝ) (hw : ∀ γ, 0 ≤ w γ)
    (hcal : ∀ γ, failures γ ≤ report γ) :
    ∑ γ, w γ * failures γ ≤ ∑ γ, w γ * report γ :=
  Finset.sum_le_sum fun γ _ => mul_le_mul_of_nonneg_left (hcal γ) (hw γ)

end NCA
