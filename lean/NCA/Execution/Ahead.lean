import Mathlib.Algebra.Order.BigOperators.Group.Finset
import Mathlib.Data.Real.Basic
import NCA.Execution.Levels

/-! Looking ahead through states foretold (chapter 72). -/
namespace NCA

variable {S T A V W : Type}

/-- 72.1: a foretelling whose state stands for the world's for `n` more presses has a way of `n` exactly
where the world has one. `stands k s t` says that `t` stands for `s` for `k` more presses; `reads` that
payment is told alike of a state and what stands for it; `keeps` that a press in the world and the same
press foretold lead to states of which one stands for the other, for one press fewer. -/
theorem foretold_way (step : S → A → S) (fore : T → A → T) (paid : S → Prop) (told : T → Prop)
    (stands : Nat → S → T → Prop)
    (reads : ∀ k s t, stands k s t → (paid s ↔ told t))
    (keeps : ∀ k s t a, stands (k + 1) s t → stands k (step s a) (fore t a)) :
    ∀ (n : Nat) (s : S) (t : T), stands n s t → (Way step paid n s ↔ Way fore told n t) := by
  intro n
  induction n with
  | zero =>
    intro s t st
    exact reads 0 s t st
  | succ k ih =>
    intro s t st
    constructor
    · intro way
      obtain ⟨a, after⟩ := (way_succ step paid k s).1 way
      exact (way_succ fore told k t).2 ⟨a, (ih (step s a) (fore t a) (keeps k s t a st)).1 after⟩
    · intro way
      obtain ⟨a, after⟩ := (way_succ fore told k t).1 way
      exact (way_succ step paid k s).2 ⟨a, (ih (step s a) (fore t a) (keeps k s t a st)).2 after⟩

/-- 72.1 for a foretelling that stands for the world however long: the same ways of every length. The
foretold state need not be the world's, only be read alike and stay so under every press. -/
theorem foretold_way_always (step : S → A → S) (fore : T → A → T) (paid : S → Prop) (told : T → Prop)
    (stands : S → T → Prop) (reads : ∀ s t, stands s t → (paid s ↔ told t))
    (keeps : ∀ s t a, stands s t → stands (step s a) (fore t a)) (n : Nat) (s : S) (t : T)
    (st : stands s t) : Way step paid n s ↔ Way fore told n t :=
  foretold_way step fore paid told (fun _ => stands) (fun _ => reads) (fun _ s t a => keeps s t a) n s t st

/-- Standing for a state for so many presses is standing for it for any fewer, where it is for one fewer. -/
theorem stands_fewer (stands : Nat → S → T → Prop) (shorter : ∀ k s t, stands (k + 1) s t → stands k s t)
    (n j : Nat) (s : S) (t : T) (le : j ≤ n) (st : stands n s t) : stands j s t := by
  induction n with
  | zero =>
    have none : j = 0 := by omega
    subst none
    exact st
  | succ k ih =>
    by_cases same : j = k + 1
    · subst same
      exact st
    · exact ih (by omega) (shorter k s t st)

/-- 72.2: such a foretelling is within so many presses of payment exactly where the world is. -/
theorem foretold_within (step : S → A → S) (fore : T → A → T) (paid : S → Prop) (told : T → Prop)
    (stands : Nat → S → T → Prop)
    (reads : ∀ k s t, stands k s t → (paid s ↔ told t))
    (keeps : ∀ k s t a, stands (k + 1) s t → stands k (step s a) (fore t a))
    (shorter : ∀ k s t, stands (k + 1) s t → stands k s t) (n : Nat) (s : S) (t : T)
    (st : stands n s t) : WithinPresses step paid n s ↔ WithinPresses fore told n t := by
  constructor
  · rintro ⟨j, le, way⟩
    exact ⟨j, le, (foretold_way step fore paid told stands reads keeps j s t
      (stands_fewer stands shorter n j s t le st)).1 way⟩
  · rintro ⟨j, le, way⟩
    exact ⟨j, le, (foretold_way step fore paid told stands reads keeps j s t
      (stands_fewer stands shorter n j s t le st)).2 way⟩

/-- 72.3: at a state `n + 1` presses from payment, a press after which the foretelling has a way of `n`
begins a shortest way in the world. -/
theorem foretold_begins_shortest (step : S → A → S) (fore : T → A → T) (paid : S → Prop) (told : T → Prop)
    (stands : Nat → S → T → Prop)
    (reads : ∀ k s t, stands k s t → (paid s ↔ told t))
    (keeps : ∀ k s t a, stands (k + 1) s t → stands k (step s a) (fore t a))
    (n : Nat) (s : S) (t : T) (a : A) (st : stands (n + 1) s t) (here : Least step paid (n + 1) s)
    (yes : Way fore told n (fore t a)) : Shortest step paid s a :=
  ⟨n, here, (foretold_way step fore paid told stands reads keeps n (step s a) (fore t a)
    (keeps n s t a st)).2 yes⟩

/-- 72.3: and a search that looks less deep finds no press there, so the first depth at which it finds one
is the least number of presses. -/
theorem foretold_silent_below (step : S → A → S) (fore : T → A → T) (paid : S → Prop) (told : T → Prop)
    (stands : Nat → S → T → Prop)
    (reads : ∀ k s t, stands k s t → (paid s ↔ told t))
    (keeps : ∀ k s t a, stands (k + 1) s t → stands k (step s a) (fore t a))
    (shorter : ∀ k s t, stands (k + 1) s t → stands k s t)
    (n j : Nat) (s : S) (t : T) (b : A) (st : stands (n + 1) s t) (here : Least step paid (n + 1) s)
    (lower : j < n) : ¬ Way fore told j (fore t b) := by
  intro way
  have after := stands_fewer stands shorter n j (step s b) (fore t b) (by omega) (keeps n s t b st)
  have real := (foretold_way step fore paid told stands reads keeps j (step s b) (fore t b) after).2 way
  have least := here.2 (j + 1) ((way_succ step paid j s).2 ⟨b, real⟩)
  omega

/-- 72.4: what is not seen cannot be foretold. A foretelling that gives a point of the state after from a
part of the state before (`near`) gives two states alike in that part the same; where the world gives them
differently, it is wrong of one. -/
theorem unseen_not_foretold (near : S → V) (after : S → W) (told : S → W)
    (sees : ∀ s s', near s = near s' → told s = told s') (s s' : S) (alike : near s = near s')
    (differ : after s ≠ after s') : told s ≠ after s ∨ told s' ≠ after s' := by
  by_cases first : told s = after s
  · right
    intro second
    exact differ (first.symm.trans ((sees s s' alike).trans second))
  · exact Or.inl first

/-- 72.5: a search that stops at the first depth at which some reading says "paid" stops short in a trial
where some reading below the distance is false. With each of the `readings` false in at most `e` trials, the
trials in which any is false are at most as many as the readings times `e`. -/
theorem false_stops_few {I Ω : Type} [DecidableEq Ω] (readings : Finset I) (falseAt : I → Finset Ω) (e : Nat)
    (few : ∀ i ∈ readings, (falseAt i).card ≤ e) : (readings.biUnion falseAt).card ≤ readings.card * e :=
  Finset.card_biUnion_le_card_mul readings falseAt e few

/-- 72.5, the bound met: where no two readings are false in the same trial and each is false in exactly `e`,
the trials in which some reading is false are the readings times `e`. -/
theorem false_stops_all {I Ω : Type} [DecidableEq Ω] (readings : Finset I) (falseAt : I → Finset Ω) (e : Nat)
    (apart : (readings : Set I).PairwiseDisjoint falseAt) (each : ∀ i ∈ readings, (falseAt i).card = e) :
    (readings.biUnion falseAt).card = readings.card * e := by
  rw [Finset.card_biUnion apart, Finset.sum_const_nat each]

/-- 72.6: the possible gain over immediate payment is bounded by the
chance of continuation, even if the second action is always paid. -/
theorem continuation_value_bounds {p c v : ℝ} (hc : 0 ≤ c) (hv : 0 ≤ v)
    (hv1 : v ≤ 1) (mass : p + c ≤ 1) :
    p ≤ p + c * v ∧ p + c * v ≤ p + c ∧ p + c ≤ 1 := by
  exact ⟨le_add_of_nonneg_right (mul_nonneg hc hv),
    add_le_add_right (mul_le_of_le_one_right hc hv1) p, mass⟩

/-- A branch whose entire remaining mass falls below a competing immediate
payment cannot win a two-step decision. Strictness preserves ties. -/
theorem continuation_pruned {p c v q d w : ℝ} (hc : 0 ≤ c) (hv : v ≤ 1)
    (hd : 0 ≤ d) (hw : 0 ≤ w) (below : p + c < q) :
    p + c * v < q + d * w := by
  exact lt_of_le_of_lt (add_le_add_right (mul_le_of_le_one_right hc hv) p)
    (lt_of_lt_of_le below (le_add_of_nonneg_right (mul_nonneg hd hw)))

end NCA
