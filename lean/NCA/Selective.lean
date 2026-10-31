import Mathlib.Algebra.Order.BigOperators.Group.Finset
import Mathlib.Algebra.BigOperators.Ring.Finset
import Mathlib.Data.Real.Basic
import Mathlib.Tactic.Linarith

/-!
# Selective answering and budgeted refinement

Each input `x` (from a finite population with weights `p x`) carries an error
bound `b x`, e.g. the sum of its symbols' calibrated error probabilities
(`composition_error_le_sum`), valid when the true error probability `q x` is
at most `b x`. Answering only when `b x ≤ δ` keeps the error rate among
answered inputs at most `δ`, whatever the input distribution.

Lowering bounds costs compute: refining symbol `i` costs `κ i` and lowers the
bound by `β i`. For a price `λ` per unit of compute, the refinement set
minimizing `bound + λ · cost` is the per-symbol threshold rule
`{i | λ κ i ≤ β i}`: refine exactly the symbols whose bound reduction is worth
their cost. Sweeping `λ` traces the optimal trade-off with local decisions.

A ladder of readings has a floor: the lowest risk each glyph can reach. A
target `δ` is reachable only if the floors sum to at most `δ`, so with a
per-glyph floor `ρ` an `L`-glyph input needs `L · ρ ≤ δ`: holding `δ` fixed as
inputs grow requires floors shrinking like `1 / L`.
-/

namespace NCA

open Finset

variable {X : Type} [Fintype X]

/-- **Selective risk.** If `q ≤ b` and only inputs with `b x ≤ δ` are
answered, the weighted error among answered inputs is at most `δ` times their
weight. -/
theorem selective_risk_le (p q b : X → ℝ) (δ : ℝ) (hp : ∀ x, 0 ≤ p x)
    (hq : ∀ x, q x ≤ b x) :
    ∑ x ∈ univ.filter (fun x => b x ≤ δ), p x * q x ≤
      δ * ∑ x ∈ univ.filter (fun x => b x ≤ δ), p x := by
  rw [mul_sum]
  refine sum_le_sum fun x hx => ?_
  have hb : b x ≤ δ := (mem_filter.mp hx).2
  calc p x * q x ≤ p x * δ := mul_le_mul_of_nonneg_left ((hq x).trans hb) (hp x)
    _ = δ * p x := mul_comm _ _

variable {I : Type} [DecidableEq I]

/-- Bound plus priced compute after refining the symbols in `T`. -/
def refinedObjective (r β κ : I → ℝ) (lam : ℝ) (S T : Finset I) : ℝ :=
  ∑ i ∈ S, r i - ∑ i ∈ T, β i + lam * ∑ i ∈ T, κ i

/-- **Threshold optimality.** Refining exactly the symbols whose bound
reduction is at least their priced cost minimizes bound plus priced compute
over all refinement sets. -/
theorem threshold_optimal (r β κ : I → ℝ) (lam : ℝ) (S T : Finset I) (hT : T ⊆ S) :
    refinedObjective r β κ lam S (S.filter fun i => lam * κ i ≤ β i) ≤
      refinedObjective r β κ lam S T := by
  set G := S.filter fun i => lam * κ i ≤ β i
  set f : I → ℝ := fun i => lam * κ i - β i
  have key : ∑ i ∈ G, f i ≤ ∑ i ∈ T, f i := by
    rw [← sum_inter_add_sum_sdiff G T f, ← sum_inter_add_sum_sdiff T G f, inter_comm]
    have h1 : ∑ i ∈ G \ T, f i ≤ 0 := sum_nonpos fun i hi => by
      have := (mem_filter.mp (mem_sdiff.mp hi).1).2
      simp only [f]; linarith
    have h2 : 0 ≤ ∑ i ∈ T \ G, f i := sum_nonneg fun i hi => by
      have hiS : i ∈ S := hT (mem_sdiff.mp hi).1
      have : ¬ lam * κ i ≤ β i := fun h => (mem_sdiff.mp hi).2 (mem_filter.mpr ⟨hiS, h⟩)
      simp only [f]; linarith
    linarith
  simp only [refinedObjective, f, sum_sub_distrib, ← mul_sum] at key ⊢
  linarith

omit [DecidableEq I] in
/-- **Floor.** If every glyph's risk is at least its floor `ρ i`, the bound
is at least the sum of floors; a target below it is unreachable. -/
theorem bound_ge_floor (S : Finset I) (r ρ : I → ℝ) (h : ∀ i ∈ S, ρ i ≤ r i) :
    ∑ i ∈ S, ρ i ≤ ∑ i ∈ S, r i :=
  sum_le_sum h

omit [DecidableEq I] in
/-- **Length limit.** With a uniform floor `ρ`, a bound at most `δ` forces
`|S| · ρ ≤ δ`. -/
theorem length_limit (S : Finset I) (r : I → ℝ) (ρ δ : ℝ) (h : ∀ i ∈ S, ρ ≤ r i)
    (hδ : ∑ i ∈ S, r i ≤ δ) : S.card * ρ ≤ δ := by
  have := bound_ge_floor S r (fun _ => ρ) h
  simp only [sum_const, nsmul_eq_mul] at this
  linarith

end NCA
