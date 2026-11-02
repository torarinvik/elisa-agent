import Mathlib.Algebra.BigOperators.Ring.Finset
import Mathlib.Algebra.Order.BigOperators.Group.Finset
import Mathlib.MeasureTheory.Measure.MeasureSpace

/-!
# Composing cascades

A fallback expert answers with its first slot when confident and calls its
second slot otherwise; the second slot may itself be a fallback. The
quantities a planner needs are stated over a finite weighted sample space
(`p ω ≥ 0`), which covers both a probability distribution and an audit's
empirical distribution.

* The exact expected cost charges the second slot only where it is called
  (`fallback_cost_eq`). It differs from the formula that treats the second
  slot's cost as independent of the call by exactly the covariance of the
  deferral indicator with that cost (`fallback_cost_sub_independent`).
* A chain of recognizers, each answering where it is reached and confident,
  errs with probability `Σᵢ P(answered at i, wrong at i)` and costs
  `Σᵢ κᵢ P(level ≥ i)` (`chain_error_eq`, `chain_cost_eq`). Splitting one
  level into a two-stage cascade changes error and cost only on the newly
  deferred inputs (`split_error_eq`).
* Choosing the empirically best of several candidates is within `2ε` of the
  truly best when every candidate's estimate is within `ε`
  (`argmin_within`), and the chance that some estimate is not is at most the
  sum over candidates (`some_deviates_le`).
-/

open Finset

namespace NCA

section Weighted

variable {Ω : Type*} [Fintype Ω] [DecidableEq Ω] (p : Ω → ℝ)

/-- Weight of an event. -/
def wt (U : Finset Ω) : ℝ := ∑ ω ∈ U, p ω

/-- **Exact cost of a fallback.** With `U` the inputs on which the first
slot is unsure and `c ω` the second slot's cost on `ω`, the fallback's
expected cost is `κ₁` plus the second slot's cost summed over `U` only. -/
theorem fallback_cost_eq (hp : ∑ ω, p ω = 1) (κ₁ : ℝ) (U : Finset Ω) (c : Ω → ℝ) :
    ∑ ω, p ω * (κ₁ + if ω ∈ U then c ω else 0) = κ₁ + ∑ ω ∈ U, p ω * c ω := by
  simp only [mul_add, sum_add_distrib, ← sum_mul, hp, one_mul, mul_ite, mul_zero]
  rw [sum_ite_mem, univ_inter]

omit [Fintype Ω] [DecidableEq Ω] in
/-- The same as `P(U) · E[c | U]` when `U` has positive weight. -/
theorem fallback_cost_conditional (κ₁ : ℝ) (U : Finset Ω) (c : Ω → ℝ) (hU : 0 < wt p U) :
    κ₁ + ∑ ω ∈ U, p ω * c ω = κ₁ + wt p U * ((∑ ω ∈ U, p ω * c ω) / wt p U) := by
  rw [mul_div_cancel₀ _ hU.ne']

/-- **Correlated deferral.** The exact cost exceeds the independent formula
`κ₁ + P(U) · E[c]` by the covariance of the deferral indicator and the
second slot's cost. Nesting is dearer than the independent formula predicts
exactly when the second slot is costlier on the inputs it is called on. -/
theorem fallback_cost_sub_independent (U : Finset Ω) (c : Ω → ℝ) :
    ∑ ω ∈ U, p ω * c ω - wt p U * ∑ ω, p ω * c ω =
      ∑ ω, p ω * ((if ω ∈ U then 1 else 0) - wt p U) * c ω := by
  have h1 : ∑ ω ∈ U, p ω * c ω = ∑ ω, p ω * (if ω ∈ U then 1 else 0) * c ω := by
    simp only [mul_ite, mul_one, mul_zero, ite_mul, zero_mul]
    rw [sum_ite_mem, univ_inter]
  rw [h1, mul_sum, ← sum_sub_distrib]
  refine sum_congr rfl fun ω _ => ?_
  ring

/-- The sign of the covariance decides the direction of the error. -/
theorem fallback_cost_ge_independent (U : Finset Ω) (c : Ω → ℝ)
    (hcov : 0 ≤ ∑ ω, p ω * ((if ω ∈ U then 1 else 0) - wt p U) * c ω) :
    wt p U * ∑ ω, p ω * c ω ≤ ∑ ω ∈ U, p ω * c ω := by
  have := fallback_cost_sub_independent p U c
  linarith

end Weighted

section Chain

variable {Ω : Type*} [Fintype Ω] (p : Ω → ℝ) {k : ℕ}

/-- **Error of a chain.** If input `ω` is answered by level `lev ω` and
`W i` are level `i`'s errors, the chain errs with weight
`Σᵢ P(answered at i ∩ W i)`. -/
theorem chain_error_eq (lev : Ω → Fin k) (W : Fin k → Set Ω) [∀ i, DecidablePred (· ∈ W i)] :
    ∑ ω, (if ω ∈ W (lev ω) then p ω else 0) =
      ∑ i, ∑ ω ∈ univ.filter (fun ω => lev ω = i), (if ω ∈ W i then p ω else 0) := by
  rw [← sum_fiberwise univ lev]
  refine sum_congr rfl fun i _ => sum_congr rfl fun ω hω => ?_
  rw [(mem_filter.mp hω).2]

/-- **Cost of a chain.** Every level up to the answering one runs, so level
`i` is paid on the inputs that reach it: `Σᵢ κᵢ P(lev ≥ i)`. -/
theorem chain_cost_eq (lev : Ω → Fin k) (κ : Fin k → ℝ) :
    ∑ ω, p ω * ∑ i ∈ univ.filter (fun i => i ≤ lev ω), κ i =
      ∑ i, κ i * ∑ ω ∈ univ.filter (fun ω => i ≤ lev ω), p ω := by
  simp only [mul_sum, sum_filter]
  rw [sum_comm]
  refine sum_congr rfl fun i _ => sum_congr rfl fun ω _ => ?_
  split <;> ring

end Chain

section Split

variable {Ω : Type*} [Fintype Ω] [DecidableEq Ω] (p : Ω → ℝ)

omit [Fintype Ω] in
/-- **Adding a level.** Replacing the recognizer answering on `R` by a
cascade that keeps its answers on `C ⊆ R` and passes `R \ C` to a new
recognizer changes the error by the new recognizer's errors minus the old
one's, on `R \ C` only. Depth helps exactly when the new level errs less on
the inputs passed to it. -/
theorem split_error_eq (R C W W' : Finset Ω) :
    wt p (R ∩ C ∩ W) + wt p ((R \ C) ∩ W') - wt p (R ∩ W) =
      wt p ((R \ C) ∩ W') - wt p ((R \ C) ∩ W) := by
  have h : wt p (R ∩ W) = wt p (R ∩ C ∩ W) + wt p ((R \ C) ∩ W) := by
    unfold wt
    rw [← sum_union]
    · congr 1
      ext ω
      simp only [mem_inter, mem_union, mem_sdiff]
      constructor
      · rintro ⟨hR, hW⟩
        by_cases hc : ω ∈ C
        · exact Or.inl ⟨⟨hR, hc⟩, hW⟩
        · exact Or.inr ⟨⟨hR, hc⟩, hW⟩
      · rintro (⟨⟨hR, _⟩, hW⟩ | ⟨⟨hR, _⟩, hW⟩) <;> exact ⟨hR, hW⟩
    · rw [disjoint_left]
      intro ω h1 h2
      exact (mem_sdiff.mp (mem_inter.mp h2).1).2 (mem_inter.mp (mem_inter.mp h1).1).2
  rw [h]
  ring

end Split

section Selection

variable {K : Type*}

/-- **Selection within `2ε`.** If every candidate's estimate `est i` is
within `ε` of its true value `val i`, the candidate with the smallest
estimate has true value within `2ε` of every candidate's. -/
theorem argmin_within (est val : K → ℝ) (ε : ℝ) (h : ∀ i, |est i - val i| ≤ ε) {j : K}
    (hj : ∀ i, est j ≤ est i) (i : K) : val j ≤ val i + 2 * ε := by
  have hj' := abs_le.mp (h j)
  have hi' := abs_le.mp (h i)
  linarith [hj i]

open MeasureTheory

/-- **Some estimate deviates.** The probability that at least one of the
candidates' estimates deviates is at most the sum of the probabilities for
each: a union bound, so `K` candidates each failing with probability `β`
fail together with probability at most `K β`. -/
theorem some_deviates_le {Ω : Type*} [MeasurableSpace Ω] (μ : Measure Ω) (S : Finset K)
    (D : K → Set Ω) : μ (⋃ i ∈ S, D i) ≤ ∑ i ∈ S, μ (D i) :=
  measure_biUnion_finset_le S D

end Selection

end NCA
