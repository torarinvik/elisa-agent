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
