import Mathlib.Algebra.BigOperators.Ring.Finset
import Mathlib.Algebra.Order.BigOperators.Group.Finset
import Mathlib.Data.Real.Basic
import Mathlib.Tactic.Linarith

/-!
# Calibration audits

Over a finite weighted sample space, a count `F` of failed invocations is
at least `k` with probability at most its expectation divided by `k`
(`count_tail_le`). If the reports are calibrated, the expectation is at
most the total report, so the total report over `k` bounds the tail
(`audit_tail_le`): an audit observing many more failures than reported
refutes calibration. No independence is assumed.
-/

open Finset

namespace NCA

variable {Ω : Type*} [Fintype Ω] {p : Ω → ℝ}

/-- **Markov's inequality for counts.** -/
theorem count_tail_le (hp : ∀ ω, 0 ≤ p ω) (F : Ω → ℕ) {k : ℕ} (hk : 0 < k) :
    ∑ ω ∈ univ.filter (fun ω => k ≤ F ω), p ω ≤ (∑ ω, p ω * F ω) / k := by
  have hk' : (0 : ℝ) < k := by exact_mod_cast hk
  rw [le_div_iff₀ hk', Finset.sum_mul, Finset.sum_filter]
  apply Finset.sum_le_sum
  intro ω _
  split
  · next h =>
    have : (k : ℝ) ≤ F ω := by exact_mod_cast h
    nlinarith [hp ω]
  · exact mul_nonneg (hp ω) (Nat.cast_nonneg _)

/-- **Audit without independence** (Theorem 35.1). If the expected number
of failures is at most the total report `R`, the probability of at least
`k` failures is at most `R / k`. -/
theorem audit_tail_le (hp : ∀ ω, 0 ≤ p ω) (F : Ω → ℕ) {k : ℕ} (hk : 0 < k) {R : ℝ}
    (hcal : ∑ ω, p ω * F ω ≤ R) :
    ∑ ω ∈ univ.filter (fun ω => k ≤ F ω), p ω ≤ R / k := by
  have hk' : (0 : ℝ) < k := by exact_mod_cast hk
  exact (count_tail_le hp F hk).trans (div_le_div_of_nonneg_right hcal hk'.le)

end NCA
