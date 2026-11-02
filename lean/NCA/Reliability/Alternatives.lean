import Mathlib.Algebra.BigOperators.Ring.Finset
import Mathlib.Algebra.Order.BigOperators.Group.Finset
import Mathlib.Data.Real.Basic
import Mathlib.Tactic.Linarith

/-!
# Answering over alternatives

A fork offers candidates; `Q k` is the probability that candidate `k` is
correct, `R` that none is. If the answer is wrong with probability at most
`c k` when a candidate `k ∈ A` (one yielding that answer) is correct, it
is wrong with probability at most `1 − Σ_{k∈A} Q k (1 − c k)`
(`alternatives_le`), and lower bounds `q k ≤ Q k` keep the bound valid
(`alternatives_lower`).
-/

open Finset

namespace NCA

variable {K : Type*} [Fintype K] [DecidableEq K]

/-- **Answers over alternatives** (Theorem 39.1). `w k` is the conditional
probability of a wrong answer given that candidate `k` is correct, `wr`
given that none is. -/
theorem alternatives_le (Q c w : K → ℝ) (R wr : ℝ) (A : Finset K)
    (hQ : ∀ k, 0 ≤ Q k) (hR : 0 ≤ R) (hsum : ∑ k, Q k + R = 1)
    (hw : ∀ k, w k ≤ 1) (hwr : wr ≤ 1) (hA : ∀ k ∈ A, w k ≤ c k) :
    ∑ k, Q k * w k + R * wr ≤ 1 - ∑ k ∈ A, Q k * (1 - c k) := by
  have hsplit : ∀ f : K → ℝ, ∑ k, f k = ∑ k ∈ A, f k + ∑ k ∈ univ \ A, f k := fun f => by
    rw [← Finset.sum_sdiff (Finset.subset_univ A), add_comm]
  have h1 : ∑ k ∈ A, Q k * w k ≤ ∑ k ∈ A, Q k * c k :=
    Finset.sum_le_sum fun k hk => mul_le_mul_of_nonneg_left (hA k hk) (hQ k)
  have h2 : ∑ k ∈ univ \ A, Q k * w k ≤ ∑ k ∈ univ \ A, Q k :=
    Finset.sum_le_sum fun k _ => by nlinarith [hw k, hQ k]
  have h3 : R * wr ≤ R := by nlinarith
  have hQs := hsplit Q
  rw [hsplit (fun k => Q k * w k)]
  have : ∑ k ∈ A, Q k * (1 - c k) = ∑ k ∈ A, Q k - ∑ k ∈ A, Q k * c k := by
    rw [← Finset.sum_sub_distrib]; congr 1; ext k; rw [mul_sub, mul_one]
  linarith

omit [Fintype K] [DecidableEq K] in
/-- Lower bounds on the candidates' probabilities keep the bound valid. -/
theorem alternatives_lower (q Q c : K → ℝ) (A : Finset K) (hq : ∀ k, q k ≤ Q k)
    (hc : ∀ k, c k ≤ 1) :
    1 - ∑ k ∈ A, Q k * (1 - c k) ≤ 1 - ∑ k ∈ A, q k * (1 - c k) := by
  have : ∑ k ∈ A, q k * (1 - c k) ≤ ∑ k ∈ A, Q k * (1 - c k) :=
    Finset.sum_le_sum fun k _ => mul_le_mul_of_nonneg_right (hq k) (by linarith [hc k])
  linarith

end NCA
