import Mathlib.Data.Nat.Basic
import Mathlib.Tactic.SplitIfs
import Lean.Elab.Tactic.Omega

/-! # Optimal-string-alignment recurrence for the symbolic word reader

The recurrence permits insertion, deletion, substitution and an adjacent
transposition, with the same prefix restrictions as the executable reader.
It is not the unrestricted Damerau–Levenshtein metric.
-/

namespace NCA

/-- One cell, using the current left cell and at most two preceding rows. -/
def editCell (above left diagonal previous : ℕ) (same swap : Bool) : ℕ :=
  let base := min (above + 1) (min (left + 1) (diagonal + if same then 0 else 1))
  if swap then min base (previous + 1) else base

/-- A diagonal alignment is always an available candidate. -/
theorem edit_cell_le_diagonal (above left diagonal previous : ℕ) (same swap : Bool) :
    editCell above left diagonal previous same swap ≤ diagonal + if same then 0 else 1 := by
  cases same <;> cases swap <;> simp [editCell] <;> omega

/-- A cyclic row write cannot alias either preceding row. -/
theorem edit_row_slots_distinct (i : ℕ) :
    (i + 2) % 3 ≠ (i + 1) % 3 ∧ (i + 2) % 3 ≠ i % 3 ∧ (i + 1) % 3 ≠ i % 3 := by
  omega

/-- Prefix-table specification; character indices are zero based. -/
def osaTable {C : Type} [DecidableEq C] (a b : ℕ → C) : ℕ → ℕ → ℕ
  | 0, j => j
  | i + 1, 0 => i + 1
  | i + 1, j + 1 =>
      editCell (osaTable a b i (j + 1)) (osaTable a b (i + 1) j)
        (osaTable a b i j) (osaTable a b (i - 1) (j - 1))
        (decide (a i = b j))
        (decide (0 < i ∧ 0 < j ∧ a i = b (j - 1) ∧ a (i - 1) = b j))
termination_by i j => i + j

theorem osa_empty_left {C : Type} [DecidableEq C] (a b : ℕ → C) (j : ℕ) :
    osaTable a b 0 j = j := by rw [osaTable]

theorem osa_empty_right {C : Type} [DecidableEq C] (a b : ℕ → C) (i : ℕ) :
    osaTable a b i 0 = i := by cases i <;> rw [osaTable]

/-- Identical prefixes have zero distance. -/
theorem osa_self {C : Type} [DecidableEq C] (a : ℕ → C) (n : ℕ) :
    osaTable a a n n = 0 := by
  induction n with
  | zero => rw [osaTable]
  | succ n ih => simp [osaTable, editCell, ih]

/-- Substitution with insertions/deletions bounds the distance by max length. -/
theorem osa_le_max {C : Type} [DecidableEq C] (a b : ℕ → C) :
    ∀ i j, osaTable a b i j ≤ max i j
  | 0, j => by simp [osaTable]
  | i + 1, 0 => by simp [osaTable]
  | i + 1, j + 1 => by
      rw [osaTable]
      have h := edit_cell_le_diagonal (osaTable a b i (j + 1))
        (osaTable a b (i + 1) j) (osaTable a b i j)
        (osaTable a b (i - 1) (j - 1))
        (decide (a i = b j))
        (decide (0 < i ∧ 0 < j ∧ a i = b (j - 1) ∧ a (i - 1) = b j))
      have ih := osa_le_max a b i j
      split_ifs at h <;> omega
termination_by i j => i + j

end NCA
