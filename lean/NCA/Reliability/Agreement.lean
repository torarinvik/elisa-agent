import Mathlib.Algebra.Order.BigOperators.Group.Finset
import Mathlib.Data.Real.Basic
import Mathlib.Tactic.Linarith

/-!
# Audits by agreement

If two experts agree whenever both are right, a disagreement implies that
one of them fails, so the probability of a disagreement is at most the sum
of their failure probabilities (`disagreement_le`).
-/

open Finset

namespace NCA

variable {Ω : Type*} [Fintype Ω]

/-- **Audit by agreement** (Theorem 40.1). -/
theorem disagreement_le (p : Ω → ℝ) (hp : ∀ ω, 0 ≤ p ω) (disagree failA failB : Ω → Prop)
    [DecidablePred disagree] [DecidablePred failA] [DecidablePred failB]
    (hboth : ∀ ω, disagree ω → failA ω ∨ failB ω) :
    ∑ ω ∈ univ.filter disagree, p ω ≤
      ∑ ω ∈ univ.filter failA, p ω + ∑ ω ∈ univ.filter failB, p ω := by
  simp only [Finset.sum_filter]
  rw [← Finset.sum_add_distrib]
  apply Finset.sum_le_sum
  intro ω _
  by_cases hd : disagree ω
  · rcases hboth ω hd with h | h
    · by_cases hb : failB ω <;> simp [hd, h, hb, hp ω]
    · by_cases ha : failA ω <;> simp [hd, h, ha, hp ω]
  · by_cases ha : failA ω <;> by_cases hb : failB ω <;> simp [hd, ha, hb, hp ω]

end NCA
