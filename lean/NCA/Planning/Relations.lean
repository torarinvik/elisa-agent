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

/-- **Proposition 55.16 (wearing takes the runs and leaves the parts).** Across a run `t` pixels wide the deepest
pixel lasts `(t + 1) / 2` wearings, so after `w` wearings the run is gone exactly when `t ≤ 2 * w`; and where runs
are at most `t` wide and parts at least `T`, any `w` with `t ≤ 2 * w < T` takes every run and leaves every part. -/
theorem wearing_takes_runs_and_leaves_parts (t T w : ℕ) :
    ((t + 1) / 2 ≤ w ↔ t ≤ 2 * w) ∧
      (t ≤ 2 * w → 2 * w < T → ∀ run part : ℕ, run ≤ t → T ≤ part → (run + 1) / 2 ≤ w ∧ w < (part + 1) / 2) := by
  refine ⟨by omega, ?_⟩
  intro gone stands run part thin thick
  omega

/-- **Proposition 55.17 (a link that is long and joins many).** Where a link between classes is at least `D` long
and joins at least `m`, and a link within a class that joins more than `k` is at most `l` long, with `l < D` and
`k < m`, any divide of length in `(l, D]` and number in `(k, m]` takes the links between classes and no link
within; and a stray may weigh more than a link between classes by length times number. -/
theorem long_links_joining_many_part (l D k m divide number : ℕ) (hl : l < divide) (hD : divide ≤ D)
    (hk : k < number) (hm : number ≤ m) :
    (∀ length joins : ℕ, D ≤ length → m ≤ joins → divide ≤ length ∧ number ≤ joins) ∧
      (∀ length joins : ℕ, (k < joins → length ≤ l) → ¬(divide ≤ length ∧ number ≤ joins)) ∧
      (∃ stray far many : ℕ, many * far < stray * 1 ∧ 1 < many) := by
  refine ⟨fun length joins long much => ⟨by omega, by omega⟩, ?_, ⟨9, 2, 4, by norm_num, by norm_num⟩⟩
  intro length joins within both
  have := within (by omega)
  omega

/-- **Proposition 55.18 (rungs keep what reaches lose).** Where each shape draws its sizes at rising reaches, the
count of a shape's reaches below a figure's is the figure's size; and two shapes can draw a greater size at no
greater a reach than a lesser, so that reach alone does not order them. -/
theorem rungs_keep_what_reaches_lose :
    (∀ (reach : ℕ → ℕ), StrictMono reach → ∀ sizes size : ℕ, size < sizes →
      ((Finset.range sizes).filter fun other => reach other < reach size).card = size) ∧
      (∃ one other : ℕ → ℕ, StrictMono one ∧ StrictMono other ∧ one 2 ≤ other 1) := by
  refine ⟨?_, ⟨fun size => 2 * size, fun size => 5 * size, ?_, ?_, by norm_num⟩⟩
  · intro reach rising sizes size within
    have : ((Finset.range sizes).filter fun other => reach other < reach size) = Finset.range size := by
      ext other
      simp only [Finset.mem_filter, Finset.mem_range, rising.lt_iff_lt]
      omega
    rw [this, Finset.card_range]
  · intro a b h
    show 2 * a < 2 * b
    omega
  · intro a b h
    show 5 * a < 5 * b
    omega

/-- **Proposition 55.19 (made of two).** A line whose last set is the union of its first two and a line whose last
is the first less the second can both have every two of their sets differ, so sameness reads them alike; and each
is made its own way and not the other's. -/
theorem sameness_does_not_tell_how_a_set_is_made :
    let a : Finset ℕ := {1}
    let b : Finset ℕ := {2}
    let c : Finset ℕ := {1, 2}
    (a ≠ b ∧ a ≠ c ∧ b ≠ c) ∧ (c ≠ b ∧ c ≠ a ∧ b ≠ a) ∧
      c = a ∪ b ∧ a = c \ b ∧ c ≠ a \ b ∧ a ≠ c ∪ b := by
  decide

/-- **Proposition 55.20 (a rule that turns is read as turned alike).** On a ring of `n` places a turn by `k`
carries a set onto its image; if one turn carries the first of each of two pairs onto its second, that turn serves
both; and two turns one after the other are the turn by their sum. -/
theorem turned_by_one_turn_are_turned_alike (n : ℕ) [NeZero n] (k j : ZMod n) (a b c d : Finset (ZMod n))
    (first : b = a.image (· + k)) (second : d = c.image (· + k)) :
    (∃ turn : ZMod n, b = a.image (· + turn) ∧ d = c.image (· + turn)) ∧
      (a.image (· + k)).image (· + j) = a.image (· + (k + j)) := by
  refine ⟨⟨k, first, second⟩, ?_⟩
  rw [Finset.image_image]
  congr 1
  funext place
  simp [add_assoc]

/-- **Proposition 59.1 (what was written is among them).** A sum is a value that is a step; two lines of three have
the same excess, and the same total, exactly when two steps from a value to a step are the same; and a line that
holds another's values in another order has its total. -/
theorem written_relations_are_composed (a b c a' b' c' : ℤ) :
    (c = a + b ↔ b = c - a) ∧
      (c - a - b = c' - a' - b' ↔ (c - a) - b = (c' - a') - b') ∧
      (a + b + c = a' + b' + c' ↔ (c' - b) - a = (c - b') - a') ∧
      ((a' = b ∧ b' = c ∧ c' = a) ∨ (a' = c ∧ b' = a ∧ c' = b) ∨ (a' = b ∧ b' = a ∧ c' = c) →
        a + b + c = a' + b' + c') := by
  refine ⟨by omega, by omega, by omega, ?_⟩
  rintro (⟨rfl, rfl, rfl⟩ | ⟨rfl, rfl, rfl⟩ | ⟨rfl, rfl, rfl⟩) <;> omega

/-- **Proposition 59.2 (the bar bounds the chance).** With at most `2 ^ a` relations of a size and `n + 1 ≤ 2 ^ b`,
a bar of `a + b + c` bits leaves `N * (n + 1)` chances of `2⁻ᵗ` each no more than `2⁻ᶜ` in all: stated without
fractions. -/
theorem name_paid_bounds_chance (N n a b c : ℕ) (few : N ≤ 2 ^ a) (short : n + 1 ≤ 2 ^ b) :
    N * (n + 1) * 2 ^ c ≤ 2 ^ (a + b + c) := by
  calc N * (n + 1) * 2 ^ c ≤ 2 ^ a * 2 ^ b * 2 ^ c :=
        Nat.mul_le_mul_right _ (Nat.mul_le_mul few short)
    _ = 2 ^ (a + b + c) := by rw [← pow_add, ← pow_add]

/-- **Proposition 59.3 (a moved relation reads the moved situation).** Whether the steps between moved slots are
the same, in a situation, is whether the steps between the slots are the same in the situation with its values
moved back. -/
theorem moved_relation_reads_moved {S : Type*} (move : S → S) (held : S → ℤ) (p q r s : S) :
    (held (move q) - held (move p) = held (move s) - held (move r)) ↔
      ((held ∘ move) q - (held ∘ move) p = (held ∘ move) s - (held ∘ move) r) :=
  Iff.rfl

/-- **Proposition 60.1 (the right candidate keeps what the rule keeps).** A reading that is the same on every line
following a rule is the same on the whole lines of a situation that follows it and on its last line with the right
candidate in place. -/
theorem right_candidate_keeps_what_the_rule_keeps {Line Reading : Type} (rule : Line → Prop) (reading : Line → Reading)
    (kept : ∀ one other, rule one → rule other → reading one = reading other) (whole : List Line) (last : Line)
    (follows : ∀ line ∈ last :: whole, rule line) :
    (∀ one ∈ whole, ∀ other ∈ whole, reading one = reading other) ∧ ∀ line ∈ whole, reading last = reading line := by
  refine ⟨fun one hone other hother => kept one other (follows one (List.mem_cons_of_mem _ hone))
    (follows other (List.mem_cons_of_mem _ hother)), fun line hline => ?_⟩
  exact kept last line (follows last List.mem_cons_self) (follows line (List.mem_cons_of_mem _ hline))

/-- **Proposition 60.2 (a wrong candidate breaks what turns on the last slot).** If a reading is one to one in the
last slot and the right candidate reads as the whole lines agree, a candidate that fills the slot otherwise does
not. -/
theorem wrong_candidate_breaks_what_turns_on_the_last {Value Reading : Type} (reading : Value → Reading)
    (turns : Function.Injective reading) (agreed : Reading) (right wrong : Value) (keeps : reading right = agreed)
    (differs : wrong ≠ right) : reading wrong ≠ agreed := by
  intro same
  exact differs (turns (same.trans keeps.symm))

/-- **Proposition 60.3 (two lines can leave it open).** The lines `(5, 1, 3)` and `(4, 1, 2)` agree that the last is
the first less the second less one and that it is the first plus the second less three; the line `(4, 2, ·)` is
then completed by 1 and by 3. -/
theorem two_lines_can_leave_it_open :
    ((3 : ℤ) = 5 - 1 - 1 ∧ (2 : ℤ) = 4 - 1 - 1) ∧ ((3 : ℤ) = 5 + 1 - 3 ∧ (2 : ℤ) = 4 + 1 - 3) ∧
      (4 : ℤ) - 2 - 1 = 1 ∧ (4 : ℤ) + 2 - 3 = 3 ∧ (1 : ℤ) ≠ 3 := by
  norm_num

/-- **Proposition 60.4 (what turns on the last slot is kept by the right candidate alone).** Of readings that are
one to one in the last slot and that the right candidate keeps, the right candidate keeps every one and a candidate
that fills the slot otherwise keeps none. -/
theorem what_turns_on_the_last_is_kept_by_the_right_alone {Value Reading : Type} [DecidableEq Reading]
    (told : List ((Value → Reading) × Reading)) (turns : ∀ pair ∈ told, Function.Injective pair.1)
    (right wrong : Value) (keeps : ∀ pair ∈ told, pair.1 right = pair.2) (differs : wrong ≠ right) :
    (told.filter fun pair => pair.1 right = pair.2).length = told.length ∧
      (told.filter fun pair => pair.1 wrong = pair.2).length = 0 := by
  constructor
  · rw [List.filter_eq_self.mpr]
    intro pair held
    simpa using keeps pair held
  · rw [List.length_eq_zero_iff, List.filter_eq_nil_iff]
    intro pair held
    simp only [decide_eq_true_eq]
    intro same
    exact differs (turns pair held (same.trans (keeps pair held).symm))

end NCA
