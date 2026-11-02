import Mathlib.Algebra.BigOperators.Ring.Finset
import Mathlib.Algebra.Order.BigOperators.Group.Finset
import Mathlib.Data.Real.Basic

/-!
# Promoting a trained challenger

A challenger trained on a part `T` of the data and tested on an
independent part `E` is fixed before `E` is seen. If a test rejects with
probability at most `α` for every fixed challenger, it rejects with
probability at most `α` for the trained one (`split_test_le`).
-/

open Finset

namespace NCA

variable {T E C : Type*} [Fintype T] [Fintype E]

/-- **Split promotion** (Theorem 36.1). On the product of independent
weighted parts, a test whose rejection probability is at most `α` for
every fixed challenger keeps that bound for a challenger `train t`
computed from the training part alone. -/
theorem split_test_le (p : T → ℝ) (q : E → ℝ) (hp : ∀ t, 0 ≤ p t) (hsum : ∑ t, p t = 1)
    (train : T → C) (reject : C → E → Prop) [∀ c e, Decidable (reject c e)] {α : ℝ}
    (hα : ∀ c, ∑ e ∈ univ.filter (reject c), q e ≤ α) :
    ∑ t, p t * ∑ e ∈ univ.filter (reject (train t)), q e ≤ α := by
  calc ∑ t, p t * ∑ e ∈ univ.filter (reject (train t)), q e ≤ ∑ t, p t * α :=
        Finset.sum_le_sum fun t _ => mul_le_mul_of_nonneg_left (hα (train t)) (hp t)
    _ = α := by rw [← Finset.sum_mul, hsum, one_mul]

end NCA

namespace NCA

/-- Budget-sum step for a finite family of training-only proposals. -/
theorem proposal_budget_le {I : Type*} (family : Finset I) (mass budget : I → ℝ)
    (alpha : ℝ) (each : ∀ i ∈ family, mass i ≤ budget i)
    (total : ∑ i ∈ family, budget i ≤ alpha) :
    ∑ i ∈ family, mass i ≤ alpha := by
  exact (Finset.sum_le_sum each).trans total

/-- Reloading a candidate preserves its scored outcomes if it preserves its
function. This assumes executable equivalence; a digest alone does not prove it. -/
theorem reloaded_outcomes_eq {X Y L : Type*} (before after : X → Y)
    (score : Y → L → Bool) (samples : List (X × L))
    (same : ∀ x, before x = after x) :
    samples.map (fun row => score (before row.1) row.2) =
      samples.map (fun row => score (after row.1) row.2) := by
  simp_rw [same]

/-- Empirical optimality of a modal decoder on a fixed finite representation.
The hypothesis states that each chosen label has maximal training count. -/
theorem modal_decoder_optimal {K L : Type*} (keys : Finset K)
    (count : K → L → ℕ) (mode alternative : K → L)
    (maximal : ∀ k ∈ keys, ∀ label, count k label ≤ count k (mode k)) :
    ∑ k ∈ keys, count k (alternative k) ≤ ∑ k ∈ keys, count k (mode k) := by
  exact Finset.sum_le_sum fun k hk => maximal k hk (alternative k)

/-- A decoder on the first component is also a decoder on the joint
representation, with exactly the same predictions (Proposition 36.5). -/
theorem joint_decoder_simulates {X A B Y : Type*}
    (f : X → A) (g : X → B) (d : A → Y) :
    (fun x => (fun ab : A × B => d ab.1) (f x, g x)) = (fun x => d (f x)) := by
  rfl

end NCA
