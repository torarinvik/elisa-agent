import Mathlib.Algebra.BigOperators.Group.Finset.Basic
import Mathlib.Algebra.Order.BigOperators.Group.Finset
import Mathlib.Algebra.Order.Field.Basic
import Mathlib.Data.Real.Basic
import Mathlib.Tactic.FieldSimp
import Mathlib.Tactic.Linarith
import Mathlib.Tactic.Positivity
import Mathlib.Tactic.Ring

/-! Dividing a search budget among goals of unknown cost: what a cap costs, why a uniform
cap cannot be beaten without information, and what sharing enumeration saves. -/

namespace NCA

open Finset

/-- Theorem 49.1: total capped work grows with the cap. -/
theorem capped_work_monotone {ι : Type} (s : Finset ι) (t : ι → ℕ) {c d : ℕ} (le : c ≤ d) :
    ∑ i ∈ s, min (t i) c ≤ ∑ i ∈ s, min (t i) d :=
  Finset.sum_le_sum fun _ _ => min_le_min_left _ le

/-- Theorem 49.2: an allocation giving every goal at least `c` spends at least `N * c`. -/
theorem uniform_cap_minimax {ι : Type} (s : Finset ι) (a : ι → ℕ) (c : ℕ)
    (each : ∀ i ∈ s, c ≤ a i) : s.card * c ≤ ∑ i ∈ s, a i := by
  simpa [nsmul_eq_mul] using Finset.card_nsmul_le_sum s a c each

/-- If some goal gets less than `c`, the adversary can place a solvable goal of cost `c` there. -/
theorem underfunded_goal_unsolved {ι : Type} (a : ι → ℕ) (c : ℕ) (i : ι) (short : a i < c) :
    ¬ c ≤ a i := Nat.not_le.mpr short

/-- Theorem 49.3: doubling rounds up to `2 ^ k` total less than `2 ^ (k + 1)`. -/
theorem doubling_rounds (k : ℕ) : ∑ j ∈ range (k + 1), 2 ^ j < 2 ^ (k + 1) := by
  induction k with
  | zero => simp
  | succ n ih =>
    rw [Finset.sum_range_succ]
    have : 2 ^ (n + 1 + 1) = 2 ^ (n + 1) + 2 ^ (n + 1) := by ring
    omega

/-- Theorem 49.3: with `2 ^ k < 2 * c`, restarted doubling costs under `4 * c` per goal. -/
theorem doubling_competitive (k c : ℕ) (below : 2 ^ k < 2 * c) :
    ∑ j ∈ range (k + 1), 2 ^ j < 4 * c := by
  have := doubling_rounds k
  have double : 2 ^ (k + 1) = 2 * 2 ^ k := by ring
  omega

/-- Theorem 49.4: extending raises the overall rate exactly when the extension's rate is at least it. -/
theorem marginal_value {K k W w : ℝ} (hW : 0 < W) (hw : 0 < w) :
    K / W ≤ (K + k) / (W + w) ↔ K / W ≤ k / w := by
  rw [div_le_div_iff₀ hW (by positivity), div_le_div_iff₀ hW hw]
  constructor <;> intro h <;> nlinarith

/-- Theorem 49.5: parallel strategies cost at most the sum. -/
theorem parallel_within_sum (a b : ℕ) : 2 * min a b ≤ a + b := by omega

/-- Theorem 49.6: a predictor costing no more than the work it abandons lowers total work. -/
theorem predictor_saving {N e abandoned c total : ℝ} (pays : N * e ≤ abandoned * c) :
    total - abandoned * c + N * e ≤ total := by linarith

/-- Theorem 49.7: sharing is no costlier when contracts and lookups cost less than separate search. -/
theorem shared_enumeration {k N c l : ℕ} (pays : k * c + N * l ≤ N * c) :
    k * c + N * l ≤ ∑ _i ∈ range N, c := by simpa using pays

/-- Theorem 49.8: what a goal finds within `c` lies in the prefix shared search enumerates. -/
theorem shared_search_dominates {H : Type} (order : ℕ → H) (goal : H → Prop) {t c : ℕ}
    (found : goal (order t)) (within : t ≤ c) : ∃ j ≤ c, goal (order j) := ⟨t, within, found⟩

/-- Theorem 49.9: `s` checks with `h ≤ (1 / q) ^ s` leave at most one expected false pass. -/
theorem labels_log_reach {h q : ℝ} {s : ℕ} (positive : 0 < q) (few : h ≤ (1 / q) ^ s) :
    h * q ^ s ≤ 1 := by
  have power : 0 < q ^ s := pow_pos positive s
  calc h * q ^ s ≤ (1 / q) ^ s * q ^ s := mul_le_mul_of_nonneg_right few power.le
    _ = 1 := by rw [← mul_pow]; field_simp; simp

end NCA
