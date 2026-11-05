import Mathlib.Data.Fintype.Card
import Mathlib.Data.Fintype.Pi
import Mathlib.Data.Fintype.BigOperators
import Mathlib.Tactic.Ring
import Mathlib.Tactic.Linarith

/-! A table of behaviour classes shared between goals: staged evaluation, how many
adaptive labels identify a class, and failure read from labels alone. -/

namespace NCA

/-- Theorem 50.1: evaluating only survivors on further inputs costs no more than all candidates. -/
theorem staged_evaluation {C S a e : ℕ} (survivors : S ≤ C) :
    C * (1 + a) + S * e ≤ C * (1 + a + e) := by
  have : S * e ≤ C * e := Nat.mul_le_mul_right e survivors
  nlinarith

/-- Theorem 50.2: `d` answers from `b` possibilities separate at most `b ^ d` classes. -/
theorem identification_lower_bound {M : Type} [Fintype M] {d b : ℕ}
    (answers : M → Fin d → Fin b) (separates : Function.Injective answers) :
    Fintype.card M ≤ b ^ d := by
  simpa using Fintype.card_le_of_injective answers separates

/-- Theorem 50.3: a label differing from every remaining class excludes them all. -/
theorem failure_certificate {M I V : Type} (remaining : M → Prop) (output : M → I → V)
    (goal : I → V) (j : I) (differs : ∀ m, remaining m → output m j ≠ goal j) :
    ¬ ∃ m, remaining m ∧ ∀ i, output m i = goal i := by
  rintro ⟨m, member, fits⟩
  exact differs m member (fits j)

end NCA
