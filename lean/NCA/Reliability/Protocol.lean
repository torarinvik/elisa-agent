import Mathlib.Data.Real.Basic
import Mathlib.Tactic.Linarith

/-! Arithmetic used by finite development-service thresholds. The identity of
cases, their certification and the integrity of recorded evidence are external
assumptions, not consequences of this calculation. -/

namespace NCA

/-- A natural-number count threshold implies the corresponding real fraction. -/
theorem finite_service_threshold {n successes : ℕ} (positive : 0 < n)
    (threshold : 3 * n ≤ 10 * successes) :
    (3 : ℝ) / 10 ≤ (successes : ℝ) / n := by
  have hn : (0 : ℝ) < n := by exact_mod_cast positive
  have h : (3 : ℝ) * n ≤ 10 * successes := by exact_mod_cast threshold
  apply (le_div_iff₀ hn).2
  linarith

end NCA
