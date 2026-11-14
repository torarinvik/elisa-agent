import Mathlib.Order.Monotone.Basic
import Mathlib.Data.Fin.VecNotation
import Mathlib.Data.Fintype.Basic
import Mathlib.Tactic

/-! Relations between what is read: what judgements on some values leave open about sameness, and what sameness and
order are unchanged by. -/

namespace NCA

/-- **Proposition 55.1 (judgements on some values do not settle sameness on others).** Sameness, and sameness of a
value in `U`, agree wherever the first value lies in `U` and differ at any value outside it. -/
theorem sameness_open_outside_shown {V : Type*} (U : Set V) (v : V) (new : v ∉ U) :
    (∀ a b, a ∈ U → (a = b ↔ a = b ∧ a ∈ U)) ∧ ¬(v = v ↔ v = v ∧ v ∈ U) :=
  ⟨fun _ _ shown => ⟨fun same => ⟨same, shown⟩, fun both => both.1⟩, fun agree => new (agree.mp rfl).2⟩

/-- **Proposition 55.2 (renaming).** Two values are the same exactly when their images under a one-to-one map are. -/
theorem sameness_renamed {V W : Type*} (rename : V → W) (one_to_one : Function.Injective rename) (a b : V) :
    rename a = rename b ↔ a = b :=
  one_to_one.eq_iff

/-- **Proposition 55.2 (rescaling).** Two values are ordered as their images under a strictly increasing map are. -/
theorem order_rescaled {V W : Type*} [LinearOrder V] [Preorder W] (rescale : V → W) (increasing : StrictMono rescale)
    (a b : V) : rescale a < rescale b ↔ a < b :=
  increasing.lt_iff_lt

/-- **Proposition 55.3 (each storey fixes the continuation), storey 0.** The last two steps of three values are the
same exactly when the last value is fixed by the two before it. -/
theorem same_step_fixes (a b c : ℤ) : c - b = b - a ↔ c = 2 * b - a := by
  constructor <;> intro h <;> omega

/-- **Proposition 55.3, storey 1.** The last two steps of steps of four values are the same exactly when the last
value is fixed by the three before it. -/
theorem same_step_of_steps_fixes (a b c d : ℤ) :
    (d - c) - (c - b) = (c - b) - (b - a) ↔ d = 3 * c - 3 * b + a := by
  constructor <;> intro h <;> omega

/-- **Proposition 55.3, storey 2.** The same one storey up, for five values. -/
theorem same_step_of_steps_of_steps_fixes (a b c d e : ℤ) :
    ((e - d) - (d - c)) - ((d - c) - (c - b)) = ((d - c) - (c - b)) - ((c - b) - (b - a)) ↔
      e = 4 * d - 6 * c + 4 * b - a := by
  constructor <;> intro h <;> omega

/-- The steps of a row of five values between places a given gap apart. -/
def stepsApart (row : Fin 5 → ℤ) : ℕ → List ℤ
  | 1 => [row 1 - row 0, row 2 - row 1, row 3 - row 2, row 4 - row 3]
  | 2 => [row 2 - row 0, row 3 - row 1, row 4 - row 2]
  | 3 => [row 3 - row 0, row 4 - row 1]
  | _ => []

/-- **Proposition 55.4 (the storey below does not tell).** Two rows of five values, increasing alike, in which no two
pairs of places that stand alike take the same step, and of which only the first has the same step of steps
throughout. -/
theorem storey_below_does_not_tell :
    ∃ steady broken : Fin 5 → ℤ,
      (List.ofFn steady).Pairwise (· < ·) ∧ (List.ofFn broken).Pairwise (· < ·) ∧
      (∀ gap, (stepsApart steady gap).Nodup ∧ (stepsApart broken gap).Nodup) ∧
      (steady 4 - steady 3) - (steady 3 - steady 2) = (steady 3 - steady 2) - (steady 2 - steady 1) ∧
      (broken 4 - broken 3) - (broken 3 - broken 2) ≠ (broken 3 - broken 2) - (broken 2 - broken 1) := by
  refine ⟨![0, 1, 3, 6, 10], ![0, 1, 3, 6, 11], by decide, by decide, ?_, by decide, by decide⟩
  intro gap
  match gap with
  | 0 => exact ⟨List.nodup_nil, List.nodup_nil⟩
  | 1 => exact ⟨by decide, by decide⟩
  | 2 => exact ⟨by decide, by decide⟩
  | 3 => exact ⟨by decide, by decide⟩
  | _ + 4 => exact ⟨List.nodup_nil, List.nodup_nil⟩

end NCA
