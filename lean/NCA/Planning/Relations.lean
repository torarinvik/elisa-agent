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

/-- **Proposition 55.5 (a comparison stands for a value exactly when it is an equivalence).** A reading of whether
two things are the same is the equality of some value of each if and only if it is reflexive, symmetric and
transitive. -/
theorem sameness_stands_for_a_value {X : Type} (same : X → X → Prop) :
    (∃ (V : Type) (value : X → V), ∀ x y, same x y ↔ value x = value y) ↔ Equivalence same := by
  constructor
  · rintro ⟨V, value, reads⟩
    exact ⟨fun x => (reads x x).mpr rfl, fun given => (reads _ _).mpr ((reads _ _).mp given).symm,
      fun first second => (reads _ _).mpr (((reads _ _).mp first).trans ((reads _ _).mp second))⟩
  · intro equivalence
    exact ⟨Quotient ⟨same, equivalence⟩, Quotient.mk _, fun x y => (Quotient.eq (r := ⟨same, equivalence⟩)).symm⟩

/-- **Proposition 55.6 (a broken triple holds an error).** Where the true sameness is transitive, three things of
which the first and second are read the same, the second and third the same and the first and third different
have at least one of the three read wrongly. No label is needed to see it. -/
theorem broken_triple_holds_an_error {X : Type*} (truly said : X → X → Prop)
    (transitive : ∀ x y z, truly x y → truly y z → truly x z) (x y z : X)
    (first : said x y) (second : said y z) (third : ¬ said x z) :
    ¬ ((said x y ↔ truly x y) ∧ (said y z ↔ truly y z) ∧ (said x z ↔ truly x z)) := by
  rintro ⟨one, two, three⟩
  exact third (three.mpr (transitive x y z (one.mp first) (two.mp second)))

/-- A value's place among the values seen so far: how many of them lie below it. -/
def placeAmong (seen : List ℤ) (value : ℤ) : ℕ := (seen.filter (· < value)).length

/-- **Proposition 55.7 (places keep the order and lose steps while rungs are unseen).** Of a ladder whose rungs
0, 1 and 3 have been seen and 2 has not, the places among those seen are ordered as the rungs are, and read the
same step from 0 to 1 as from 1 to 3, where the rungs take different steps. -/
theorem places_keep_order_and_lose_steps :
    placeAmong [0, 1, 3] 0 < placeAmong [0, 1, 3] 1 ∧ placeAmong [0, 1, 3] 1 < placeAmong [0, 1, 3] 3 ∧
      placeAmong [0, 1, 3] 1 - placeAmong [0, 1, 3] 0 = placeAmong [0, 1, 3] 3 - placeAmong [0, 1, 3] 1 ∧
      (1 : ℤ) - 0 ≠ 3 - 1 := by
  decide

/-- How alike a row around a circle is to itself moved a gap along: the sum, over the places, of the value there
times the value a gap on. -/
def alikeMoved {G : Type*} [AddCommGroup G] [Fintype G] (row : G → ℤ) (gap : G) : ℤ :=
  ∑ place, row place * row (place + gap)

/-- **Proposition 55.8 (what a turn and a mirror leave alone).** How alike a row around a circle is to itself moved
along is unchanged, for every gap, when the row is turned by any amount and when it is mirrored. -/
theorem turning_and_mirroring_keep_alike_moved {G : Type*} [AddCommGroup G] [Fintype G] (row : G → ℤ)
    (turn gap : G) :
    alikeMoved (fun place => row (place + turn)) gap = alikeMoved row gap ∧
      alikeMoved (fun place => row (-place)) gap = alikeMoved row gap := by
  constructor
  · exact Fintype.sum_equiv (Equiv.addRight turn) _ _ fun place => by
      simp only [Equiv.coe_addRight, add_right_comm]
  · exact Fintype.sum_equiv ((Equiv.neg G).trans (Equiv.subRight gap)) _ _ fun place => by
      simp only [Equiv.trans_apply, Equiv.neg_apply, Equiv.subRight_apply, neg_add, sub_eq_add_neg,
        neg_add_cancel_right]
      exact mul_comm _ _

/-- **Proposition 55.9 (a chain reads sameness when no link crosses).** Where no two things read near are truly
different and any two things truly the same are joined by a chain of things read near, being joined by such a chain
is being truly the same. -/
theorem chain_reads_sameness {α : Type*} (same near : α → α → Prop) (eqv : Equivalence same)
    (none_crosses : ∀ x y, near x y → same x y) (chained : ∀ x y, same x y → Relation.EqvGen near x y) (x y : α) :
    Relation.EqvGen near x y ↔ same x y := by
  refine ⟨fun joined => ?_, chained x y⟩
  induction joined with
  | rel _ _ link => exact none_crosses _ _ link
  | refl _ => exact eqv.refl _
  | symm _ _ _ back => exact eqv.symm back
  | trans _ _ _ _ _ first second => exact eqv.trans first second

/-- **Proposition 55.10 (a greater divide only joins).** Things joined by a chain of links under one divide are
joined under every greater divide. -/
theorem greater_divide_only_joins {α : Type*} (far : α → α → ℚ) {low high : ℚ} (more : low ≤ high) (x y : α)
    (joined : Relation.EqvGen (fun a b => far a b < low) x y) :
    Relation.EqvGen (fun a b => far a b < high) x y := by
  induction joined with
  | rel _ _ link => exact Relation.EqvGen.rel _ _ (lt_of_lt_of_le link more)
  | refl _ => exact Relation.EqvGen.refl _
  | symm _ _ _ back => exact Relation.EqvGen.symm _ _ back
  | trans _ _ _ _ _ first second => exact Relation.EqvGen.trans _ _ _ first second

/-- **Proposition 55.11 (how much lies one way fixes the reach that way).** A part of a circle about a middle, of
reach `r` across an angle `w`, covers `r ^ 2 * w / 2`. Two reaches that cover the same across the same angle are
the same reach. -/
theorem covered_fixes_reach (r s w : ℚ) (wide : 0 < w) (reaches : 0 ≤ r) (also : 0 ≤ s)
    (covered : r ^ 2 * w / 2 = s ^ 2 * w / 2) : r = s := by
  have squares : r ^ 2 = s ^ 2 := by
    have := mul_right_cancel₀ (ne_of_gt wide) (by linarith : r ^ 2 * w = s ^ 2 * w)
    exact this
  nlinarith [sq_nonneg (r - s), sq_nonneg (r + s), mul_nonneg reaches also]

/-- **Proposition 55.12 (sameness, order and the sameness of steps do not tell a sum).** The rows 1, 3, 4 and
1, 3, 6 are ordered alike, hold no two values the same, and have no two of their three steps the same; in the first
the last value is the first plus the second and in the other it is not. -/
theorem same_and_order_and_steps_do_not_tell_a_sum :
    ((1 : ℤ) < 3 ∧ (3 : ℤ) < 4) ∧ ((1 : ℤ) < 3 ∧ (3 : ℤ) < 6) ∧
      ((3 : ℤ) - 1 ≠ 4 - 3 ∧ (3 : ℤ) - 1 ≠ 4 - 1 ∧ (4 : ℤ) - 3 ≠ 4 - 1) ∧
      ((3 : ℤ) - 1 ≠ 6 - 3 ∧ (3 : ℤ) - 1 ≠ 6 - 1 ∧ (6 : ℤ) - 3 ≠ 6 - 1) ∧
      (4 : ℤ) = 1 + 3 ∧ (6 : ℤ) ≠ 1 + 3 := by
  decide

/-- **Proposition 55.13 (a sum is a step that is a value).** The last of three values is the first plus the second
exactly when the step from the first to the last is the second, and the first less the second exactly when the
step from the last to the first is the second. -/
theorem sum_is_step_that_is_value (a b c : ℤ) : (c = a + b ↔ c - a = b) ∧ (c = a - b ↔ a - c = b) := by
  constructor <;> constructor <;> intro h <;> omega

/-- **Proposition 55.14 (a rule kept by every row is told by two rows agreeing).** Where the rows above either
all keep a rule or none does, and the last row is right exactly when it does as they do, whether the last row is
right is whether its reading agrees with a row's above; and it is not a function of the last row's reading alone,
which is right when true under one row above and when false under another. -/
theorem agreeing_rows_tell (above last : Bool) :
    ((last = above) ↔ (above = true ↔ last = true)) ∧
      ¬∃ judged : Bool → Bool, ∀ shown asked : Bool, judged asked = decide (asked = shown) := by
  refine ⟨by cases above <;> cases last <;> simp, ?_⟩
  rintro ⟨judged, told⟩
  have one := told true true
  have other := told false true
  rw [one] at other
  simp at other
/-- **Proposition 55.15 (the excess of two rows agrees wherever the nothing is put).** Adding one amount to every
value lowers each row's excess by that amount, so two rows have the same excess after exactly when they had
before; that a row is a sum, its excess nothing, is not kept. -/
theorem excess_agrees_wherever_nothing_is (a b c a' b' c' k : ℤ) :
    ((c + k) - (a + k) - (b + k) = c - a - b - k) ∧
      ((c + k) - (a + k) - (b + k) = (c' + k) - (a' + k) - (b' + k) ↔ c - a - b = c' - a' - b') ∧
      ¬∀ x y z shift : ℤ, z = x + y → z + shift = (x + shift) + (y + shift) := by
  refine ⟨by omega, by omega, ?_⟩
  intro kept
  have := kept 0 0 0 1 rfl
  omega

end NCA
