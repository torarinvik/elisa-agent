import Mathlib.Algebra.Order.BigOperators.Ring.Finset
import Mathlib.Algebra.Order.Chebyshev
import Mathlib.Data.Fintype.BigOperators
import Mathlib.Data.Real.Basic
import Mathlib.Tactic.FieldSimp
import Mathlib.Tactic.Linarith
import Mathlib.Tactic.Positivity

/-! Search ordered by a prior over hypotheses or strategies: how many hypotheses can
precede one of given weight, which prior minimizes expected cost over a population of
goals, how mismatch degrades it, why learned subroutines make cost additive, and how many
experts of what size cost least to hold and to find. -/

namespace NCA

open Finset

/-- Fewer than `1 / c` hypotheses can have weight at least `c` under a subprobability. -/
theorem heavy_hypotheses_bound {H : Type} [DecidableEq H] (s : Finset H) (p : H → ℝ)
    (nonnegative : ∀ h ∈ s, 0 ≤ p h) (total : ∑ h ∈ s, p h ≤ 1) (c : ℝ) :
    ((s.filter fun h => c ≤ p h).card : ℝ) * c ≤ 1 := by
  have below : ((s.filter fun h => c ≤ p h).card : ℝ) * c ≤ ∑ h ∈ s.filter (fun h => c ≤ p h), p h := by
    have := Finset.card_nsmul_le_sum (s.filter fun h => c ≤ p h) p c
      (fun h member => (Finset.mem_filter.mp member).2)
    simpa [nsmul_eq_mul] using this
  have part : ∑ h ∈ s.filter (fun h => c ≤ p h), p h ≤ ∑ h ∈ s, p h :=
    Finset.sum_le_sum_of_subset_of_nonneg (Finset.filter_subset _ _)
      (fun h member _ => nonnegative h member)
  linarith

/-- Expected cost `∑ f / p` of any prior is at least the squared sum of `√f`. -/
theorem prior_cost_lower {ι : Type} (s : Finset ι) (a p : ι → ℝ)
    (positive : ∀ i ∈ s, 0 < p i) (total : ∑ i ∈ s, p i = 1) :
    (∑ i ∈ s, a i) ^ 2 ≤ ∑ i ∈ s, a i ^ 2 / p i := by
  have bound := Finset.sq_sum_div_le_sum_sq_div s a positive
  simpa [total] using bound

/-- The prior proportional to `√f` attains that lower bound. -/
theorem prior_cost_attained {ι : Type} (s : Finset ι) (a : ι → ℝ)
    (positive : ∀ i ∈ s, 0 < a i) (nonempty : s.Nonempty) :
    ∑ i ∈ s, a i ^ 2 / (a i / ∑ j ∈ s, a j) = (∑ i ∈ s, a i) ^ 2 := by
  have whole : 0 < ∑ j ∈ s, a j := Finset.sum_pos positive nonempty
  have each : ∀ i ∈ s, a i ^ 2 / (a i / ∑ j ∈ s, a j) = a i * ∑ j ∈ s, a j := by
    intro i member
    have := positive i member
    field_simp
  rw [Finset.sum_congr rfl each, ← Finset.sum_mul, sq]

/-- Mixing a prior with weight `λ` of a reference bounds every goal's cost by `1 / (λ u)`. -/
theorem mixture_bounds_any_goal {l p u : ℝ} (hl : 0 < l) (below : l ≤ 1) (hp : 0 ≤ p) (hu : 0 < u) :
    1 / ((1 - l) * p + l * u) ≤ 1 / (l * u) := by
  apply one_div_le_one_div_of_le (by positivity)
  have : 0 ≤ (1 - l) * p := mul_nonneg (by linarith) hp
  linarith

/-- The same mixture costs a goal at most `1 / (1 - λ)` times its cost under the prior. -/
theorem mixture_keeps_prior {l p u : ℝ} (hl : 0 ≤ l) (below : l < 1) (hp : 0 < p) (hu : 0 ≤ u) :
    1 / ((1 - l) * p + l * u) ≤ 1 / (1 - l) * (1 / p) := by
  have gap : 0 < 1 - l := by linarith
  rw [one_div_mul_one_div]
  apply one_div_le_one_div_of_le (by positivity)
  have : 0 ≤ l * u := mul_nonneg hl hu
  linarith

/-- A prior's expected cost degrades at most by the frequency ratio `ρ`. -/
theorem mismatch_cost {ι : Type} (s : Finset ι) (f g p : ι → ℝ) (ρ : ℝ)
    (positive : ∀ i ∈ s, 0 < p i) (ratio : ∀ i ∈ s, g i ≤ ρ * f i) :
    ∑ i ∈ s, g i / p i ≤ ρ * ∑ i ∈ s, f i / p i := by
  rw [Finset.mul_sum]
  refine Finset.sum_le_sum fun i member => ?_
  rw [← mul_div_assoc]
  exact div_le_div_of_nonneg_right (ratio i member) (positive i member).le

/-- `k ≥ 2` stages of cost `c ≥ 2` add where solving them jointly multiplies. -/
theorem curriculum_adds {c k : Nat} (hc : 2 ≤ c) (hk : 2 ≤ k) : k * c ≤ c ^ k := by
  induction k, hk using Nat.le_induction with
  | base => nlinarith
  | succ k hk ih =>
    have grown : k + 1 ≤ c ^ k := by nlinarith
    rw [pow_succ]
    exact Nat.mul_le_mul_right c grown

/-- One expert of `l` bits named by `m ≥ 2` users at `a` bits a use costs less than a copy
held by each, once it holds more than twice its address. -/
theorem shared_expert_pays {l a m : Nat} (hm : 2 ≤ m) (large : 2 * a < l) :
    l + m * a < m * l := by
  obtain ⟨j, rfl⟩ := Nat.exists_eq_add_of_le hm
  have grown : (j + 1) * (2 * a + 1) ≤ (j + 1) * l := Nat.mul_le_mul_left _ large
  nlinarith [grown, Nat.zero_le (j * a)]

/-- An expert with one user saves nothing over that user holding it. -/
theorem expert_used_once_saves_nothing (l a : Nat) : 1 * l ≤ l + 1 * a := by omega

/-- Experts of `l` bits on a route of `k` among `2 ^ a`, holding `c` bits between them: the
larger of the search for an expert and the search for the route has exponent at least the
root of `a * c`. -/
theorem larger_search_bounded_below {l k a c : Nat} (holds : c ≤ l * k) :
    a * c ≤ (max l (a * k)) ^ 2 := by
  have one : a * c ≤ l * (a * k) :=
    calc a * c ≤ a * (l * k) := Nat.mul_le_mul_left a holds
      _ = l * (a * k) := by ring
  rw [sq]
  exact one.trans (Nat.mul_le_mul (le_max_left _ _) (le_max_right _ _))

/-- The bound is met where an expert holds as many bits as its route's addresses. -/
theorem balanced_search_attains {l k a : Nat} (even : l = a * k) :
    (max l (a * k)) ^ 2 = a * (l * k) := by
  subst even
  rw [max_self]
  ring

/-- Tasks told apart by their routes of `k` experts among `n` number at most `n ^ k`. -/
theorem tasks_told_apart_by_routes {t n k : Nat} (route : Fin t → Fin k → Fin n)
    (apart : Function.Injective route) : t ≤ n ^ k := by
  simpa using Fintype.card_le_of_injective route apart

end NCA
