import Mathlib.Algebra.Order.BigOperators.Group.Finset
import Mathlib.Algebra.BigOperators.Ring.Finset
import Mathlib.Data.Real.Basic
import Mathlib.Tactic.Linarith

/-!
# The practice queue

A deployed system reads items `i` with calibrated error probabilities `r i`
and queues for a teacher's label those with `r i ≥ θ`. Every queued label is
expected to correct at least `θ` errors, and the expected errors left out of
the queue are at most `θ` per unqueued item. Labeling by risk therefore
captures all but `θ · n` of the expected errors among `n` items, while each
label is worth at least `θ`, against the average risk for a random label.

New expert versions trained on the queue enter the library only through the
upgrade rule (`NCA.Upgrade`): routes of other goals are unchanged and an
upgrade can be rolled back.
-/

namespace NCA

open Finset

variable {I : Type} [DecidableEq I] (S : Finset I) (r : I → ℝ) (θ : ℝ) [DecidablePred fun i => θ ≤ r i]

/-- Items queued for a label. -/
def queued : Finset I := S.filter fun i => θ ≤ r i

omit [DecidableEq I] in
/-- **Each label is worth at least `θ`.** -/
theorem queued_value : θ * (queued S r θ).card ≤ ∑ i ∈ queued S r θ, r i := by
  rw [mul_comm, ← nsmul_eq_mul, ← sum_const]
  exact sum_le_sum fun i hi => (mem_filter.mp hi).2

/-- **Few expected errors escape the queue.** -/
theorem unqueued_errors : ∑ i ∈ S \ queued S r θ, r i ≤ θ * (S \ queued S r θ).card := by
  rw [mul_comm, ← nsmul_eq_mul, ← sum_const]
  refine sum_le_sum fun i hi => ?_
  have hS := (mem_sdiff.mp hi).1
  have hq : ¬ θ ≤ r i := fun h => (mem_sdiff.mp hi).2 (mem_filter.mpr ⟨hS, h⟩)
  linarith

/-- **Captured errors.** The queue holds all but `θ · |S|` of the expected
errors (for `θ ≥ 0`). -/
theorem queued_captures (hθ : 0 ≤ θ) :
    ∑ i ∈ S, r i - θ * S.card ≤ ∑ i ∈ queued S r θ, r i := by
  have hsub : queued S r θ ⊆ S := filter_subset _ _
  have hsplit := sum_sdiff hsub (f := r)
  have hcard : ((S \ queued S r θ).card : ℝ) ≤ S.card := by
    exact_mod_cast card_le_card sdiff_subset
  have := unqueued_errors S r θ
  nlinarith

end NCA
