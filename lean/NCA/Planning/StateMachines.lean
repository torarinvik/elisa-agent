import Mathlib.Algebra.Group.Basic
import Mathlib.Data.Fintype.Card
import Mathlib.Data.List.Basic
import Mathlib.Tactic.Abel

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

/-- Theorem 51.3: adding one-step differences along a sequence rebuilds the answer. -/
theorem differences_rebuild {A G : Type} [AddCommGroup G] (f : List A → G) (p w : List A) :
    w.foldl (fun (s : List A × G) a => (s.1 ++ [a], s.2 + (f (s.1 ++ [a]) - f s.1))) (p, f p)
      = (p ++ w, f (p ++ w)) := by
  induction w generalizing p with
  | nil => simp
  | cons a w ih =>
    have step : f p + (f (p ++ [a]) - f p) = f (p ++ [a]) := by abel
    simp only [List.foldl_cons, step]
    rw [ih (p ++ [a])]
    simp

/-- Theorem 51.4: where transitions add to a register, the change made by one more symbol is
fixed by the control state reached and that symbol. -/
theorem counter_differences_follow_control {A Q G : Type} [AddCommGroup G] (step : Q → A → Q)
    (gain : Q → A → G) (start : Q) (base : G) (w : List A) (a : A) :
    ((w ++ [a]).foldl (fun (s : Q × G) x => (step s.1 x, s.2 + gain s.1 x)) (start, base)).2
      - (w.foldl (fun (s : Q × G) x => (step s.1 x, s.2 + gain s.1 x)) (start, base)).2
      = gain (w.foldl (fun (s : Q × G) x => (step s.1 x, s.2 + gain s.1 x)) (start, base)).1 a := by
  simp [List.foldl_append]

end NCA
