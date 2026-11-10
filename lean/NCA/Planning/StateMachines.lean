import Mathlib.Data.Fintype.Card
import Mathlib.Data.List.Basic

/-! Machines that read a sequence and answer from their final state: what a table of
answers to chosen sequences says about the states any such machine needs. -/

namespace NCA

/-- Theorem 51.1: prefixes whose answers differ after a common suffix end in different states. -/
theorem distinguished_prefixes_need_states {A Q O : Type} (step : Q → A → Q) (start : Q) (out : Q → O)
    (s t e : List A)
    (differ : out ((s ++ e).foldl step start) ≠ out ((t ++ e).foldl step start)) :
    s.foldl step start ≠ t.foldl step start := by
  intro same
  apply differ
  rw [List.foldl_append, List.foldl_append, same]

/-- Theorem 51.2: a machine giving `n` sequences pairwise distinct answers has at least `n` states. -/
theorem distinct_answers_need_states {A Q O : Type} [Fintype Q] (step : Q → A → Q) (start : Q)
    (out : Q → O) {n : ℕ} (word : Fin n → List A)
    (distinct : Function.Injective fun i => out ((word i).foldl step start)) :
    n ≤ Fintype.card Q := by
  have states : Function.Injective fun i => (word i).foldl step start :=
    fun i j same => distinct (congrArg out same)
  simpa using Fintype.card_le_of_injective _ states

end NCA
