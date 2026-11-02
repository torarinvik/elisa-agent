import Mathlib.Algebra.BigOperators.Ring.Finset
import Mathlib.Algebra.Order.BigOperators.Group.Finset
import Mathlib.Data.Real.Basic

/-!
# In-situ sampling

Keeping each invocation with probability `q`, independently of whether it
fails, scales both the expected failures and the expected report by `q`,
so calibrated reports stay calibrated on the kept invocations
(`sampled_calibrated`).
-/

open Finset

namespace NCA

variable {I : Type*} [Fintype I]

/-- **Sampling preserves the audit** (Theorem 38.1). -/
theorem sampled_calibrated (q : ℝ) (hq : 0 ≤ q) (failure report : I → ℝ)
    (hcal : ∑ i, failure i ≤ ∑ i, report i) :
    ∑ i, q * failure i ≤ ∑ i, q * report i := by
  rw [← Finset.mul_sum, ← Finset.mul_sum]
  exact mul_le_mul_of_nonneg_left hcal hq

end NCA
