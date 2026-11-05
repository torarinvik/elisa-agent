import Mathlib.Algebra.BigOperators.Group.Finset.Basic
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

/-- Theorem 50.6: `M` tests on the first case and at most `r` on each of `s` others. -/
theorem narrowing_cost {M r s : ℕ} (count : ℕ → ℕ) (first : count 0 ≤ M)
    (later : ∀ i, count (i + 1) ≤ r) :
    ∑ i ∈ Finset.range (s + 1), count i ≤ M + s * r := by
  induction s with
  | zero => simpa using first
  | succ n ih =>
    rw [Finset.sum_range_succ]
    have := later n
    nlinarith

/-- Theorem 50.7: equal longer prefixes have equal shorter ones. -/
theorem prefixes_refine {M V : Type} (vector : M → ℕ → V) {p q : ℕ} (le : p ≤ q) {a b : M}
    (same : ∀ i < q, vector a i = vector b i) : ∀ i < p, vector a i = vector b i :=
  fun i below => same i (lt_of_lt_of_le below le)

/-- Theorem 50.8: a pair of functions agrees with a pair-valued goal exactly when each part agrees. -/
theorem product_is_parts {X A B : Type} (g g' : X → A) (h h' : X → B) (x : X) :
    (g' x, h' x) = (g x, h x) ↔ g' x = g x ∧ h' x = h x := Prod.mk_inj

/-- Theorem 50.9: steps agreeing on all visited states and items give equal folds. -/
theorem equal_steps_fold_equally {S A : Type} (f g : S → A → S) (xs : List A) (s : S)
    (agree : ∀ t, ∀ a ∈ xs, f t a = g t a) : xs.foldl f s = xs.foldl g s := by
  induction xs generalizing s with
  | nil => rfl
  | cons a rest ih =>
    simp only [List.foldl_cons]
    rw [agree s a (by simp)]
    exact ih _ (fun t b member => agree t b (by simp [member]))

end NCA
